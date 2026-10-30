"""FastAPI application.

Run from the repository root:
    uv run uvicorn readybid_api.main:app --reload --port 8000

Security model
* Every endpoint except /health and /integrations/status needs a Supabase access token
  (``Authorization: Bearer ...``), verified in ``readybid_api.auth``.
* Organisation membership is resolved from the database for the verified user id. Ids in
  paths and bodies are only lookup keys: each resource is loaded and its organisation is
  checked (``readybid_core.authz``) before anything is returned or changed.
* The repository uses the Supabase service role key, which bypasses row level security,
  so these checks are the enforcement point. RLS stays on as a second line of defence.
  Resources in other organisations return 404, the same as missing ones.
* Storage paths are generated here and never returned. Files are only reachable through
  short-lived signed URLs issued after a permission check.

Evidence and review
* Evidence documents belong to an organisation, not a tender. An analysis only uses the
  evidence documents explicitly selected for it, each pinned to its SHA-256.
* Review decisions are append-only and belong to one analysis run. They never change the
  stored AI assessment.
"""

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from redis.exceptions import RedisError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from readybid_api import __version__, review
from readybid_api.auth import AuthError, AuthUnavailable
from readybid_api.schemas import (
    AnalysisOut,
    AnalysisRunOut,
    ChecklistExportOut,
    ChecklistOut,
    CreateOrganisationIn,
    CreateTenderIn,
    DecisionIn,
    DecisionOut,
    DocumentOut,
    EvidenceDocumentOut,
    EvidenceListOut,
    EvidenceSourceViewOut,
    FileUrlOut,
    JobOut,
    OrganisationOut,
    RequirementOut,
    RequirementsOut,
    SourceViewOut,
    StartAnalysisIn,
    TenderDetailOut,
    TenderOut,
)
from readybid_api.services import Services
from readybid_core.authz import (
    NotFound,
    Principal,
    authorise_document,
    authorise_evidence_document,
    authorise_evidence_source,
    authorise_job,
    authorise_run,
    authorise_source,
    authorise_tender,
    require_organisation,
    resolve_principal,
)
from readybid_core.clients import NotConfigured
from readybid_core.config import Settings, get_settings
from readybid_core.integrations import IntegrationsStatus, get_integration_status
from readybid_core.jobs import enqueue_analysis, rq_job_id, segments_to_rows
from readybid_core.models import (
    ACTIVE_STATUSES,
    EVIDENCE_LABELS,
    AnalysisRun,
    Document,
    EvidenceSelection,
    ProcessingJob,
    ReviewDecision,
    Tender,
)
from readybid_core.pdf import (
    PdfValidationError,
    Segment,
    ValidatedPdf,
    extract_segments,
    validate_pdf,
)
from readybid_core.repository import DuplicateError, Repository
from readybid_core.storage import (
    DocumentStorage,
    StorageError,
    document_storage_path,
    evidence_storage_path,
)

logger = logging.getLogger(__name__)

# Allowance for multipart boundaries and part headers on top of the file itself.
MULTIPART_OVERHEAD_BYTES = 64 * 1024
# Attempts to claim the next document version when concurrent uploads collide.
VERSION_ATTEMPTS = 3
# Extra time beyond job timeouts and retry delays before an active job counts as stuck.
STUCK_JOB_GRACE_SECONDS = 300


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str


router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)


def services_of(request: Request) -> Services:
    return request.app.state.services


def current_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> Principal:
    if credentials is None:
        raise AuthError("Sign in to continue.")
    services = services_of(request)
    user_id = services.verifier().verify(credentials.credentials)
    return resolve_principal(services.repo(), user_id)


CurrentPrincipal = Annotated[Principal, Depends(current_principal)]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _upload_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def clean_filename(name: str | None) -> str:
    """Keep a display name only. Filenames are metadata and never reach storage paths."""
    base = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    base = "".join(ch for ch in base if ch.isprintable()).strip()
    return (base or "document.pdf")[:255]


# Organisations ------------------------------------------------------------------------
@router.get("/organisations", response_model=list[OrganisationOut])
def list_organisations(request: Request, principal: CurrentPrincipal) -> list[OrganisationOut]:
    memberships = services_of(request).repo().list_memberships(principal.user_id)
    return [OrganisationOut(id=m.organisation_id, name=m.name, role=m.role) for m in memberships]


@router.post("/organisations", status_code=201, response_model=OrganisationOut)
def create_organisation(
    body: CreateOrganisationIn, request: Request, principal: CurrentPrincipal
) -> OrganisationOut:
    # First sign-in only. Joining or creating further organisations is out of scope here.
    if principal.organisation_ids:
        raise HTTPException(status_code=409, detail="You already belong to an organisation.")
    org = services_of(request).repo().create_organisation(body.name, principal.user_id)
    return OrganisationOut(id=org.id, name=org.name, role="owner")


# Tenders ------------------------------------------------------------------------------
@router.get("/organisations/{organisation_id}/tenders", response_model=list[TenderOut])
def list_tenders(
    organisation_id: UUID, request: Request, principal: CurrentPrincipal
) -> list[TenderOut]:
    org_id = require_organisation(principal, str(organisation_id))
    tenders = services_of(request).repo().list_tenders(org_id)
    return [TenderOut.model_validate(t) for t in tenders]


@router.post("/organisations/{organisation_id}/tenders", status_code=201, response_model=TenderOut)
def create_tender(
    organisation_id: UUID, body: CreateTenderIn, request: Request, principal: CurrentPrincipal
) -> TenderOut:
    org_id = require_organisation(principal, str(organisation_id))
    tender = (
        services_of(request)
        .repo()
        .create_tender(org_id, body.title, body.reference, principal.user_id)
    )
    return TenderOut.model_validate(tender)


@router.get("/tenders/{tender_id}", response_model=TenderDetailOut)
def get_tender(tender_id: UUID, request: Request, principal: CurrentPrincipal) -> TenderDetailOut:
    repo = services_of(request).repo()
    tender = authorise_tender(repo, principal, str(tender_id))
    documents = [
        d for d in repo.list_documents(tender.id) if d.organisation_id == tender.organisation_id
    ]
    run = repo.latest_analysis_run(tender.id)
    if run is not None and run.organisation_id != tender.organisation_id:
        run = None
    job = repo.get_job_for_run(run.id) if run is not None else None
    return TenderDetailOut(
        tender=TenderOut.model_validate(tender),
        documents=[DocumentOut.model_validate(d) for d in documents],
        latest_analysis=AnalysisRunOut.model_validate(run) if run else None,
        latest_job=JobOut.model_validate(job) if job else None,
    )


# Uploads ------------------------------------------------------------------------------
@dataclass(frozen=True)
class PdfUpload:
    data: bytes
    filename: str
    validated: ValidatedPdf
    fields: dict[str, str]


async def read_pdf_upload(
    request: Request, settings: Settings, text_fields: Sequence[str] = ()
) -> PdfUpload:
    """Read one bounded PDF upload plus named text fields, and validate the PDF content."""
    limit = settings.max_upload_bytes
    limit_mb = limit / (1024 * 1024)
    too_large = _upload_error(413, "too_large", f"The file is larger than {limit_mb:g} MB.")
    # Check the declared size before reading the body. The server enforces Content-Length,
    # so this bounds how much is read.
    declared = request.headers.get("content-length")
    if declared is None:
        raise HTTPException(status_code=411, detail="Content-Length is required.")
    try:
        declared_bytes = int(declared)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Content-Length.") from None
    if declared_bytes > limit + MULTIPART_OVERHEAD_BYTES:
        raise too_large

    form = await request.form(max_files=1, max_fields=2 + len(text_fields))
    try:
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise _upload_error(422, "missing_file", "Attach the PDF in the 'file' field.")
        data = await upload.read(limit + 1)
        filename = clean_filename(upload.filename)
        fields: dict[str, str] = {}
        for name in text_fields:
            value = form.get(name)
            fields[name] = value.strip() if isinstance(value, str) else ""
    finally:
        await form.close()
    if len(data) > limit:
        raise too_large

    # Validate the content itself. The filename and declared content type are not trusted.
    try:
        validated = await run_in_threadpool(
            validate_pdf, data, max_bytes=limit, max_pages=settings.max_pdf_pages
        )
    except PdfValidationError as error:
        raise _upload_error(422, error.code, error.message) from None
    return PdfUpload(data=data, filename=filename, validated=validated, fields=fields)


def _insert_next_version(repo: Repository, draft: Document) -> Document:
    if draft.tender_id is None:
        raise ValueError("Only tender documents are versioned.")
    for attempt in range(1, VERSION_ATTEMPTS + 1):
        version = repo.latest_document_version(draft.tender_id) + 1
        try:
            return repo.insert_document(draft.model_copy(update={"version": version}))
        except DuplicateError:
            if attempt == VERSION_ATTEMPTS:
                raise
    raise AssertionError("unreachable")


def _remove_quietly(storage: DocumentStorage, path: str) -> None:
    try:
        storage.remove(path)
    except StorageError:
        logger.warning("Could not remove orphaned upload %s", path)


def store_document(
    repo: Repository,
    storage: DocumentStorage,
    principal: Principal,
    tender: Tender,
    filename: str,
    data: bytes,
    validated: ValidatedPdf,
) -> Document:
    """Upload first, then record the row, so a row never points at a missing file."""
    document_id = str(uuid.uuid4())
    path = document_storage_path(tender.organisation_id, tender.id, document_id)
    storage.upload_pdf(path, data)
    draft = Document(
        id=document_id,
        organisation_id=tender.organisation_id,
        tender_id=tender.id,
        original_filename=filename,
        storage_path=path,
        sha256=validated.sha256,
        size_bytes=validated.size_bytes,
        page_count=validated.page_count,
        version=1,
        created_by=principal.user_id,
    )
    try:
        return _insert_next_version(repo, draft)
    except Exception:
        _remove_quietly(storage, path)
        raise


@router.post("/tenders/{tender_id}/documents", status_code=201, response_model=DocumentOut)
async def upload_document(
    tender_id: UUID, request: Request, principal: CurrentPrincipal
) -> DocumentOut:
    services = services_of(request)
    repo = services.repo()
    tender = await run_in_threadpool(authorise_tender, repo, principal, str(tender_id))
    upload = await read_pdf_upload(request, services.settings)
    document = await run_in_threadpool(
        store_document,
        repo,
        services.storage(),
        principal,
        tender,
        upload.filename,
        upload.data,
        upload.validated,
    )
    return DocumentOut.model_validate(document)


@router.get("/documents/{document_id}/file", response_model=FileUrlOut)
def get_document_file(
    document_id: UUID, request: Request, principal: CurrentPrincipal
) -> FileUrlOut:
    services = services_of(request)
    document = authorise_document(services.repo(), principal, str(document_id))
    ttl = services.settings.signed_url_ttl_seconds
    return FileUrlOut(
        document_id=document.id,
        original_filename=document.original_filename,
        version=document.version,
        signed_url=services.storage().signed_url(document.storage_path, ttl),
        expires_in_seconds=ttl,
    )


# Evidence library ---------------------------------------------------------------------
def store_evidence_document(
    repo: Repository,
    storage: DocumentStorage,
    principal: Principal,
    organisation_id: str,
    document_id: str,
    label: str,
    upload: PdfUpload,
    segments: Sequence[Segment],
) -> Document:
    """Upload, record the row, then save page segments (flagged pages included)."""
    path = evidence_storage_path(organisation_id, document_id)
    storage.upload_pdf(path, upload.data)
    draft = Document(
        id=document_id,
        organisation_id=organisation_id,
        tender_id=None,
        document_type="evidence",
        evidence_label=label,
        original_filename=upload.filename,
        storage_path=path,
        sha256=upload.validated.sha256,
        size_bytes=upload.validated.size_bytes,
        page_count=upload.validated.page_count,
        version=1,
        created_by=principal.user_id,
    )
    try:
        document = repo.insert_document(draft)
    except Exception:
        _remove_quietly(storage, path)
        raise
    try:
        repo.upsert_segments(segments_to_rows(document, segments))
    except Exception:
        # Not fatal: before matching, the worker checks the file hash and extracts again.
        logger.warning("Could not save segments for evidence %s", document.id, exc_info=True)
    return document


@router.get("/organisations/{organisation_id}/evidence", response_model=EvidenceListOut)
def list_evidence(
    organisation_id: UUID, request: Request, principal: CurrentPrincipal
) -> EvidenceListOut:
    services = services_of(request)
    repo = services.repo()
    org_id = require_organisation(principal, str(organisation_id))
    documents = [
        d
        for d in repo.list_evidence_documents(org_id)
        if d.organisation_id == org_id and d.document_type == "evidence"
    ]
    return EvidenceListOut(
        documents=review.evidence_documents_out(repo, documents),
        max_per_analysis=services.settings.max_evidence_documents_per_analysis,
    )


@router.post(
    "/organisations/{organisation_id}/evidence",
    status_code=201,
    response_model=EvidenceDocumentOut,
)
async def upload_evidence(
    organisation_id: UUID, request: Request, principal: CurrentPrincipal
) -> EvidenceDocumentOut:
    services = services_of(request)
    repo = services.repo()
    org_id = require_organisation(principal, str(organisation_id))
    upload = await read_pdf_upload(request, services.settings, ("label",))
    label = upload.fields.get("label", "")
    if label not in EVIDENCE_LABELS:
        raise _upload_error(
            422, "invalid_label", f"Choose a document type: {', '.join(EVIDENCE_LABELS)}."
        )

    document_id = str(uuid.uuid4())
    try:
        segments = await run_in_threadpool(
            extract_segments,
            upload.data,
            document_id=document_id,
            document_sha256=upload.validated.sha256,
        )
    except PdfValidationError as error:
        raise _upload_error(422, error.code, error.message) from None

    document = await run_in_threadpool(
        store_evidence_document,
        repo,
        services.storage(),
        principal,
        org_id,
        document_id,
        label,
        upload,
        segments,
    )
    described = await run_in_threadpool(review.evidence_documents_out, repo, [document])
    return described[0]


# Analysis -----------------------------------------------------------------------------
def _job_is_live(job: ProcessingJob, settings: Settings) -> bool:
    """False when an active job has not reported progress for longer than any run could take."""
    if job.updated_at is None:
        return True
    updated = job.updated_at if job.updated_at.tzinfo else job.updated_at.replace(tzinfo=UTC)
    limit = settings.job_timeout_seconds * (settings.job_max_retries + 1) + STUCK_JOB_GRACE_SECONDS
    return (datetime.now(UTC) - updated).total_seconds() < limit


def resolve_evidence_selection(
    repo: Repository,
    principal: Principal,
    tender: Tender,
    document_ids: Sequence[UUID],
    limit: int,
) -> list[Document]:
    """Authorise each explicitly selected evidence document. Nothing is added implicitly."""
    unique = list(dict.fromkeys(str(document_id) for document_id in document_ids))
    if len(unique) > limit:
        raise HTTPException(
            status_code=422,
            detail=f"Select at most {limit} evidence documents for one analysis.",
        )
    documents: list[Document] = []
    for document_id in unique:
        document = authorise_evidence_document(repo, principal, document_id)
        if document.organisation_id != tender.organisation_id:
            raise NotFound("document")
        documents.append(document)
    return documents


def _same_selection(repo: Repository, run: AnalysisRun, evidence: Sequence[Document]) -> bool:
    selected = {
        (s.document_id, s.document_sha256)
        for s in repo.list_evidence_selections(run.id)
        if s.organisation_id == run.organisation_id
    }
    return selected == {(d.id, d.sha256) for d in evidence}


@router.post("/tenders/{tender_id}/analyses", status_code=202, response_model=AnalysisOut)
def start_analysis(
    tender_id: UUID, body: StartAnalysisIn, request: Request, principal: CurrentPrincipal
) -> AnalysisOut:
    services = services_of(request)
    settings = services.settings
    repo = services.repo()
    tender = authorise_tender(repo, principal, str(tender_id))
    document = authorise_document(repo, principal, str(body.document_id))
    if document.tender_id != tender.id:
        raise NotFound("document")
    evidence = resolve_evidence_selection(
        repo,
        principal,
        tender,
        body.evidence_document_ids,
        settings.max_evidence_documents_per_analysis,
    )
    services.ensure_llm_configured()
    queue = services.queue()

    # Starting twice while a run is active returns the existing run instead of a duplicate,
    # but only when it analyses the same document with the same evidence selection.
    latest = repo.latest_analysis_run(tender.id)
    if latest is not None and latest.status in ACTIVE_STATUSES:
        latest_job = repo.get_job_for_run(latest.id)
        if latest_job is not None and _job_is_live(latest_job, settings):
            if latest.document_id == document.id and _same_selection(repo, latest, evidence):
                return AnalysisOut(
                    analysis=AnalysisRunOut.model_validate(latest),
                    job=JobOut.model_validate(latest_job),
                )
        elif latest_job is not None:
            message = "Processing stopped responding and was replaced by a new analysis."
            repo.update_analysis_run(
                latest.id, {"status": "failed", "error": message, "finished_at": _now()}
            )
            repo.update_processing_job(
                latest_job.id,
                {"status": "failed", "stage": "failed", "progress": 100, "error": message},
            )

    run = repo.create_analysis_run(
        AnalysisRun(
            id=str(uuid.uuid4()),
            organisation_id=tender.organisation_id,
            tender_id=tender.id,
            document_id=document.id,
            document_sha256=document.sha256,
            model=settings.groq_model,
            matching_status="pending" if evidence else "not_requested",
            created_by=principal.user_id,
        )
    )
    if evidence:
        try:
            repo.add_evidence_selections(
                [
                    EvidenceSelection(
                        analysis_run_id=run.id,
                        organisation_id=run.organisation_id,
                        document_id=d.id,
                        document_sha256=d.sha256,
                    )
                    for d in evidence
                ]
            )
        except Exception:
            message = "The evidence selection could not be saved. Start the analysis again."
            repo.update_analysis_run(
                run.id,
                {
                    "status": "failed",
                    "error": message,
                    "matching_status": "failed",
                    "matching_error": message,
                    "finished_at": _now(),
                },
            )
            raise

    job_id = str(uuid.uuid4())
    job = repo.create_processing_job(
        ProcessingJob(
            id=job_id,
            organisation_id=run.organisation_id,
            analysis_run_id=run.id,
            rq_job_id=rq_job_id(job_id),
        )
    )
    try:
        enqueue_analysis(queue, settings, run.id, job.id)
    except RedisError:
        logger.warning("Could not enqueue analysis %s", run.id, exc_info=True)
        message = "The job queue is unavailable. Start the analysis again later."
        failed: dict[str, object] = {"status": "failed", "error": message, "finished_at": _now()}
        if evidence:
            failed["matching_status"] = "failed"
            failed["matching_error"] = message
        repo.update_analysis_run(run.id, failed)
        repo.update_processing_job(
            job.id, {"status": "failed", "stage": "failed", "progress": 100, "error": message}
        )
        raise HTTPException(status_code=503, detail=message) from None
    return AnalysisOut(analysis=AnalysisRunOut.model_validate(run), job=JobOut.model_validate(job))


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: UUID, request: Request, principal: CurrentPrincipal) -> JobOut:
    job = authorise_job(services_of(request).repo(), principal, str(job_id))
    return JobOut.model_validate(job)


@router.get("/analyses/{run_id}", response_model=AnalysisOut)
def get_analysis(run_id: UUID, request: Request, principal: CurrentPrincipal) -> AnalysisOut:
    repo = services_of(request).repo()
    run = authorise_run(repo, principal, str(run_id))
    job = repo.get_job_for_run(run.id)
    if job is not None and job.organisation_id != run.organisation_id:
        job = None
    return AnalysisOut(
        analysis=AnalysisRunOut.model_validate(run),
        job=JobOut.model_validate(job) if job else None,
    )


@router.get("/analyses/{run_id}/requirements", response_model=RequirementsOut)
def list_requirements(
    run_id: UUID, request: Request, principal: CurrentPrincipal
) -> RequirementsOut:
    repo = services_of(request).repo()
    run = authorise_run(repo, principal, str(run_id))
    document = repo.get_document(run.document_id)
    if document is None or document.organisation_id != run.organisation_id:
        raise NotFound("analysis")
    warnings = review.tender_page_warnings(repo, run, document)
    return RequirementsOut(
        analysis=AnalysisRunOut.model_validate(run),
        document=DocumentOut.model_validate(document),
        coverage=review.coverage_out(run, warnings),
        requirements=[
            RequirementOut.model_validate(r) for r in review.visible_requirements(repo, run)
        ],
    )


@router.get("/sources/{source_id}", response_model=SourceViewOut)
def get_source(source_id: UUID, request: Request, principal: CurrentPrincipal) -> SourceViewOut:
    services = services_of(request)
    authorised = authorise_source(services.repo(), principal, str(source_id))
    ttl = services.settings.signed_url_ttl_seconds
    signed_url = services.storage().signed_url(authorised.document.storage_path, ttl)
    return SourceViewOut(
        id=authorised.source.id,
        requirement_id=authorised.source.requirement_id,
        document_id=authorised.document.id,
        document_filename=authorised.document.original_filename,
        document_version=authorised.document.version,
        # The page always comes from the stored segment, never from model output.
        page_number=authorised.segment.page_number,
        quote=authorised.source.quote,
        extraction_status=authorised.segment.extraction_status,
        extraction_note=authorised.segment.extraction_note,
        signed_url=signed_url,
        expires_in_seconds=ttl,
    )


# Checklist and review -----------------------------------------------------------------
@router.get("/analyses/{run_id}/checklist", response_model=ChecklistOut)
def get_checklist(run_id: UUID, request: Request, principal: CurrentPrincipal) -> ChecklistOut:
    repo = services_of(request).repo()
    run = authorise_run(repo, principal, str(run_id))
    return review.build_checklist(repo, run)


@router.post("/analyses/{run_id}/decisions", status_code=201, response_model=DecisionOut)
def record_decision(
    run_id: UUID, body: DecisionIn, request: Request, principal: CurrentPrincipal
) -> DecisionOut:
    repo = services_of(request).repo()
    run = authorise_run(repo, principal, str(run_id))
    # The requirement must belong to this run and organisation.
    requirement = review.find_requirement(repo, run, str(body.requirement_id))
    decision = repo.insert_review_decision(
        ReviewDecision(
            id=str(uuid.uuid4()),
            organisation_id=run.organisation_id,
            analysis_run_id=run.id,
            requirement_id=requirement.id,
            decision=body.decision,
            notes=body.notes,
            reviewer_id=principal.user_id,
        )
    )
    return DecisionOut.model_validate(decision)


@router.get("/analyses/{run_id}/export", response_model=None)
def export_checklist(
    run_id: UUID,
    request: Request,
    principal: CurrentPrincipal,
    file_format: Annotated[Literal["csv", "json"], Query(alias="format")] = "csv",
) -> Response:
    repo = services_of(request).repo()
    run = authorise_run(repo, principal, str(run_id))
    checklist = review.build_checklist(repo, run)
    exported_at = datetime.now(UTC)
    # run.id is a validated UUID, so the filename cannot carry user-controlled text.
    name = f"readybid-checklist-{run.id}.{file_format}"
    headers = {"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"}
    if file_format == "json":
        body = ChecklistExportOut(exported_at=exported_at, checklist=checklist)
        return JSONResponse(content=body.model_dump(mode="json"), headers=headers)
    # The byte order mark lets spreadsheet apps detect UTF-8.
    content = "\ufeff" + review.checklist_csv(checklist, exported_at)
    return Response(content=content, media_type="text/csv; charset=utf-8", headers=headers)


@router.get("/evidence-sources/{source_id}", response_model=EvidenceSourceViewOut)
def get_evidence_source(
    source_id: UUID, request: Request, principal: CurrentPrincipal
) -> EvidenceSourceViewOut:
    services = services_of(request)
    authorised = authorise_evidence_source(services.repo(), principal, str(source_id))
    ttl = services.settings.signed_url_ttl_seconds
    signed_url = services.storage().signed_url(authorised.document.storage_path, ttl)
    return EvidenceSourceViewOut(
        id=authorised.source.id,
        evidence_match_id=authorised.match.id,
        requirement_id=authorised.match.requirement_id,
        document_id=authorised.document.id,
        document_filename=authorised.document.original_filename,
        document_version=authorised.document.version,
        evidence_label=authorised.document.evidence_label,
        # The page always comes from the stored segment, never from model output.
        page_number=authorised.segment.page_number,
        quote=authorised.source.quote,
        relationship=authorised.source.relationship,
        extraction_status=authorised.segment.extraction_status,
        extraction_note=authorised.segment.extraction_note,
        signed_url=signed_url,
        expires_in_seconds=ttl,
    )


# App ----------------------------------------------------------------------------------
def _error(status_code: int, detail: str, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail}, headers=headers)


def _register_error_handlers(app: FastAPI) -> None:
    async def not_found(request: Request, error: Exception) -> JSONResponse:
        return _error(404, "Not found.")

    async def not_configured(request: Request, error: Exception) -> JSONResponse:
        return _error(503, str(error))

    async def unauthorised(request: Request, error: Exception) -> JSONResponse:
        return _error(401, str(error), {"WWW-Authenticate": "Bearer"})

    async def auth_unavailable(request: Request, error: Exception) -> JSONResponse:
        return _error(503, "Sign-in could not be checked right now. Try again shortly.")

    async def storage_failed(request: Request, error: Exception) -> JSONResponse:
        logger.warning("Storage error: %s", error)
        return _error(502, "File storage is unavailable. Try again shortly.")

    async def duplicate(request: Request, error: Exception) -> JSONResponse:
        return _error(409, "Another upload for this tender finished at the same time. Try again.")

    app.add_exception_handler(NotFound, not_found)
    app.add_exception_handler(NotConfigured, not_configured)
    app.add_exception_handler(AuthError, unauthorised)
    app.add_exception_handler(AuthUnavailable, auth_unavailable)
    app.add_exception_handler(StorageError, storage_failed)
    app.add_exception_handler(DuplicateError, duplicate)


def create_app(settings: Settings | None = None, *, services: Services | None = None) -> FastAPI:
    if services is None:
        services = Services(settings or get_settings())
    settings = services.settings

    app = FastAPI(title="ReadyBid SA API", version=__version__)
    app.state.settings = settings
    app.state.services = services

    # Explicit allow-list only. Auth uses bearer tokens, not cookies, so no credentials.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )
    _register_error_handlers(app)

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", service="readybid-api", version=__version__)

    @app.get("/integrations/status", response_model=IntegrationsStatus)
    def integrations_status(request: Request) -> IntegrationsStatus:
        return get_integration_status(request.app.state.settings)

    app.include_router(router)
    return app


app = create_app()
