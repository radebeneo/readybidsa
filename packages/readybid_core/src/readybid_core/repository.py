"""Data access for the API and worker.

`SupabaseRepository` uses the service role key, which BYPASSES row level security. It
therefore never decides who may see what: every caller must authorise through
`readybid_core.authz` first. RLS remains in place as a second line of defence for any
direct client access.
"""

import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any, Protocol

from postgrest.exceptions import APIError

from readybid_core.analysis import FinalRequirement
from readybid_core.matching import RequirementAssessment
from readybid_core.models import (
    ActionItem,
    AnalysisRun,
    Document,
    EvidenceMatch,
    EvidenceMatchSource,
    EvidenceSelection,
    Organisation,
    OrganisationMembership,
    ProcessingJob,
    Requirement,
    RequirementSource,
    ReviewDecision,
    SegmentStatus,
    SourceSegment,
    Tender,
)

# Namespace for deterministic requirement and source ids (idempotent persistence).
ID_NAMESPACE = uuid.UUID("6f1d9c2e-4b8a-4e21-9d7c-3a5b0e8f1c42")


class DuplicateError(Exception):
    """A unique constraint was violated (for example a concurrent document version)."""


def requirement_row_id(run_id: str, dedupe_key: str) -> str:
    return str(uuid.uuid5(ID_NAMESPACE, f"requirement:{run_id}:{dedupe_key}"))


def source_row_id(requirement_id: str, segment_id: str, quote_sha256: str) -> str:
    return str(uuid.uuid5(ID_NAMESPACE, f"source:{requirement_id}:{segment_id}:{quote_sha256}"))


def evidence_match_row_id(requirement_id: str) -> str:
    return str(uuid.uuid5(ID_NAMESPACE, f"evidence_match:{requirement_id}"))


def evidence_source_row_id(match_id: str, segment_id: str, quote_sha256: str) -> str:
    return str(uuid.uuid5(ID_NAMESPACE, f"evidence_source:{match_id}:{segment_id}:{quote_sha256}"))


def action_item_row_id(requirement_id: str, origin: str) -> str:
    return str(uuid.uuid5(ID_NAMESPACE, f"action_item:{requirement_id}:{origin}"))


def requirement_rows(
    run: AnalysisRun, requirements: Sequence[FinalRequirement]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build requirement and source rows with deterministic ids for one run."""
    req_rows: list[dict[str, Any]] = []
    src_rows: list[dict[str, Any]] = []
    for item in requirements:
        req_id = requirement_row_id(run.id, item.dedupe_key)
        req_rows.append(
            {
                "id": req_id,
                "organisation_id": run.organisation_id,
                "analysis_run_id": run.id,
                "document_id": run.document_id,
                "dedupe_key": item.dedupe_key,
                "position": item.position,
                "title": item.title,
                "requirement_text": item.requirement_text,
                "category": item.category,
                "evidence_needed": item.evidence_needed,
                "stage": item.stage,
                "consequence": item.consequence,
                "ambiguity_notes": item.ambiguity_notes,
            }
        )
        for citation in item.sources:
            if citation.document_id != run.document_id:
                raise ValueError("Citation does not belong to the analysed document.")
            src_rows.append(
                {
                    "id": source_row_id(req_id, citation.segment_id, citation.quote_sha256),
                    "organisation_id": run.organisation_id,
                    "requirement_id": req_id,
                    "document_id": run.document_id,
                    "segment_id": citation.segment_id,
                    "page_number": citation.page_number,
                    "quote": citation.quote,
                    "quote_sha256": citation.quote_sha256,
                }
            )
    return req_rows, src_rows


def evidence_match_rows(
    run: AnalysisRun, assessments: Sequence[RequirementAssessment], model: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Build match, candidate source and action item rows with deterministic ids."""
    match_rows: list[dict[str, Any]] = []
    src_rows: list[dict[str, Any]] = []
    action_rows: list[dict[str, Any]] = []
    for item in assessments:
        match_id = evidence_match_row_id(item.requirement_id)
        match_rows.append(
            {
                "id": match_id,
                "organisation_id": run.organisation_id,
                "analysis_run_id": run.id,
                "requirement_id": item.requirement_id,
                "ai_status": item.ai_status,
                "explanation": item.explanation,
                "uncertainty_notes": item.uncertainty_notes,
                "count_summary": item.count_summary,
                "required_count": item.required_count,
                "candidate_document_count": item.candidate_document_count,
                "model": model,
            }
        )
        for candidate in item.candidates:
            src_rows.append(
                {
                    "id": evidence_source_row_id(
                        match_id, candidate.segment_id, candidate.quote_sha256
                    ),
                    "organisation_id": run.organisation_id,
                    "evidence_match_id": match_id,
                    "analysis_run_id": run.id,
                    "document_id": candidate.document_id,
                    "segment_id": candidate.segment_id,
                    "page_number": candidate.page_number,
                    "quote": candidate.quote,
                    "quote_sha256": candidate.quote_sha256,
                    "relationship": candidate.relationship,
                    "extraction_status": candidate.extraction_status,
                }
            )
        action_rows.append(
            {
                "id": action_item_row_id(item.requirement_id, "matching"),
                "organisation_id": run.organisation_id,
                "analysis_run_id": run.id,
                "requirement_id": item.requirement_id,
                "evidence_match_id": match_id,
                "origin": "matching",
                "description": item.next_action,
                "status": "open",
            }
        )
    return match_rows, src_rows, action_rows


class Repository(Protocol):
    def list_memberships(self, user_id: str) -> list[OrganisationMembership]: ...
    def create_organisation(self, name: str, owner_user_id: str) -> Organisation: ...

    def list_tenders(self, organisation_id: str) -> list[Tender]: ...
    def create_tender(
        self, organisation_id: str, title: str, reference: str | None, created_by: str
    ) -> Tender: ...
    def get_tender(self, tender_id: str) -> Tender | None: ...

    def list_documents(self, tender_id: str) -> list[Document]: ...
    def list_evidence_documents(self, organisation_id: str) -> list[Document]: ...
    def latest_document_version(self, tender_id: str) -> int: ...
    def insert_document(self, document: Document) -> Document: ...
    def get_document(self, document_id: str) -> Document | None: ...

    def upsert_segments(self, segments: Sequence[SourceSegment]) -> None: ...
    def list_segments(self, document_id: str) -> list[SourceSegment]: ...
    def list_segment_statuses(self, document_ids: Sequence[str]) -> list[SegmentStatus]: ...
    def get_segment(self, segment_id: str) -> SourceSegment | None: ...

    def create_analysis_run(self, run: AnalysisRun) -> AnalysisRun: ...
    def get_analysis_run(self, run_id: str) -> AnalysisRun | None: ...
    def latest_analysis_run(self, tender_id: str) -> AnalysisRun | None: ...
    def list_analysis_runs(self, tender_id: str, limit: int) -> list[AnalysisRun]: ...
    def update_analysis_run(self, run_id: str, fields: dict[str, Any]) -> None: ...

    def create_processing_job(self, job: ProcessingJob) -> ProcessingJob: ...
    def get_processing_job(self, job_id: str) -> ProcessingJob | None: ...
    def get_job_for_run(self, run_id: str) -> ProcessingJob | None: ...
    def update_processing_job(self, job_id: str, fields: dict[str, Any]) -> None: ...

    def save_requirements(
        self, run: AnalysisRun, requirements: Sequence[FinalRequirement]
    ) -> None: ...
    def list_requirements(self, run_id: str) -> list[Requirement]: ...
    def get_requirement_source(self, source_id: str) -> RequirementSource | None: ...

    def add_evidence_selections(self, selections: Sequence[EvidenceSelection]) -> None: ...
    def list_evidence_selections(self, run_id: str) -> list[EvidenceSelection]: ...
    def save_evidence_matches(
        self, run: AnalysisRun, assessments: Sequence[RequirementAssessment], model: str
    ) -> None: ...
    def list_evidence_matches(self, run_id: str) -> list[EvidenceMatch]: ...
    def get_evidence_match(self, match_id: str) -> EvidenceMatch | None: ...
    def get_evidence_match_source(self, source_id: str) -> EvidenceMatchSource | None: ...
    def list_action_items(self, run_id: str) -> list[ActionItem]: ...

    def insert_review_decision(self, decision: ReviewDecision) -> ReviewDecision: ...
    def list_review_decisions(self, run_id: str) -> list[ReviewDecision]: ...


def _is_unique_violation(error: APIError) -> bool:
    return getattr(error, "code", None) == "23505"


PAGE_SIZE = 1000
SEGMENT_STATUS_COLUMNS = (
    "document_id, document_sha256, page_number, extraction_status, extraction_note"
)


class SupabaseRepository:
    """Postgres access through PostgREST with the service role key (server only)."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def _table(self, name: str) -> Any:
        return self._client.table(name)

    @staticmethod
    def _first(response: Any) -> dict[str, Any] | None:
        data = response.data or []
        return data[0] if data else None

    def _select_all(self, build: Callable[[], Any]) -> list[dict[str, Any]]:
        """Page through a query, since PostgREST caps the rows returned per request."""
        rows: list[dict[str, Any]] = []
        start = 0
        while True:
            batch = build().range(start, start + PAGE_SIZE - 1).execute().data or []
            rows.extend(batch)
            if len(batch) < PAGE_SIZE:
                return rows
            start += PAGE_SIZE

    def _delete_stale(self, table: str, run_id: str, keep: set[str]) -> None:
        existing = self._select_all(
            lambda: self._table(table).select("id").eq("analysis_run_id", run_id).order("id")
        )
        stale = [row["id"] for row in existing if row["id"] not in keep]
        for start in range(0, len(stale), 100):
            self._table(table).delete().in_("id", stale[start : start + 100]).execute()

    # Organisations ----------------------------------------------------------------------
    def list_memberships(self, user_id: str) -> list[OrganisationMembership]:
        response = (
            self._table("organisation_members")
            .select("organisation_id, role, organisations(name)")
            .eq("user_id", user_id)
            .execute()
        )
        result = []
        for row in response.data or []:
            org = row.get("organisations") or {}
            result.append(
                OrganisationMembership(
                    organisation_id=row["organisation_id"],
                    name=org.get("name", ""),
                    role=row["role"],
                )
            )
        return result

    def create_organisation(self, name: str, owner_user_id: str) -> Organisation:
        org_id = str(uuid.uuid4())
        self._table("organisations").insert({"id": org_id, "name": name}).execute()
        self._table("organisation_members").insert(
            {"organisation_id": org_id, "user_id": owner_user_id, "role": "owner"}
        ).execute()
        return Organisation(id=org_id, name=name)

    # Tenders ------------------------------------------------------------------------------
    def list_tenders(self, organisation_id: str) -> list[Tender]:
        response = (
            self._table("tenders")
            .select("*")
            .eq("organisation_id", organisation_id)
            .order("created_at", desc=True)
            .limit(200)
            .execute()
        )
        return [Tender.model_validate(row) for row in response.data or []]

    def create_tender(
        self, organisation_id: str, title: str, reference: str | None, created_by: str
    ) -> Tender:
        response = (
            self._table("tenders")
            .insert(
                {
                    "organisation_id": organisation_id,
                    "title": title,
                    "reference": reference,
                    "created_by": created_by,
                }
            )
            .execute()
        )
        row = self._first(response)
        if row is None:
            raise RuntimeError("Tender insert returned no row.")
        return Tender.model_validate(row)

    def get_tender(self, tender_id: str) -> Tender | None:
        row = self._first(self._table("tenders").select("*").eq("id", tender_id).execute())
        return Tender.model_validate(row) if row else None

    # Documents ----------------------------------------------------------------------------
    def list_documents(self, tender_id: str) -> list[Document]:
        response = (
            self._table("documents")
            .select("*")
            .eq("tender_id", tender_id)
            .order("version", desc=True)
            .execute()
        )
        return [Document.model_validate(row) for row in response.data or []]

    def list_evidence_documents(self, organisation_id: str) -> list[Document]:
        response = (
            self._table("documents")
            .select("*")
            .eq("organisation_id", organisation_id)
            .eq("document_type", "evidence")
            .order("created_at", desc=True)
            .limit(200)
            .execute()
        )
        return [Document.model_validate(row) for row in response.data or []]

    def latest_document_version(self, tender_id: str) -> int:
        row = self._first(
            self._table("documents")
            .select("version")
            .eq("tender_id", tender_id)
            .order("version", desc=True)
            .limit(1)
            .execute()
        )
        return int(row["version"]) if row else 0

    def insert_document(self, document: Document) -> Document:
        payload = document.model_dump(exclude={"created_at"}, mode="json")
        try:
            row = self._first(self._table("documents").insert(payload).execute())
        except APIError as error:
            if _is_unique_violation(error):
                raise DuplicateError(str(error)) from None
            raise
        return Document.model_validate(row) if row else document

    def get_document(self, document_id: str) -> Document | None:
        row = self._first(self._table("documents").select("*").eq("id", document_id).execute())
        return Document.model_validate(row) if row else None

    # Segments -----------------------------------------------------------------------------
    def upsert_segments(self, segments: Sequence[SourceSegment]) -> None:
        rows = [segment.model_dump(mode="json") for segment in segments]
        for start in range(0, len(rows), 50):
            self._table("source_segments").upsert(
                rows[start : start + 50], on_conflict="id", ignore_duplicates=True
            ).execute()

    def list_segments(self, document_id: str) -> list[SourceSegment]:
        response = (
            self._table("source_segments")
            .select("*")
            .eq("document_id", document_id)
            .order("page_number")
            .execute()
        )
        return [SourceSegment.model_validate(row) for row in response.data or []]

    def list_segment_statuses(self, document_ids: Sequence[str]) -> list[SegmentStatus]:
        result: list[SegmentStatus] = []
        ids = list(dict.fromkeys(document_ids))
        for start in range(0, len(ids), 50):
            chunk = ids[start : start + 50]
            rows = self._select_all(
                lambda chunk=chunk: (
                    self._table("source_segments")
                    .select(SEGMENT_STATUS_COLUMNS)
                    .in_("document_id", chunk)
                    .order("document_id")
                    .order("page_number")
                )
            )
            result.extend(SegmentStatus.model_validate(row) for row in rows)
        return result

    def get_segment(self, segment_id: str) -> SourceSegment | None:
        row = self._first(self._table("source_segments").select("*").eq("id", segment_id).execute())
        return SourceSegment.model_validate(row) if row else None

    # Analysis runs ------------------------------------------------------------------------
    def create_analysis_run(self, run: AnalysisRun) -> AnalysisRun:
        payload = run.model_dump(mode="json", exclude={"created_at", "started_at", "finished_at"})
        row = self._first(self._table("analysis_runs").insert(payload).execute())
        return AnalysisRun.model_validate(row) if row else run

    def get_analysis_run(self, run_id: str) -> AnalysisRun | None:
        row = self._first(self._table("analysis_runs").select("*").eq("id", run_id).execute())
        return AnalysisRun.model_validate(row) if row else None

    def latest_analysis_run(self, tender_id: str) -> AnalysisRun | None:
        row = self._first(
            self._table("analysis_runs")
            .select("*")
            .eq("tender_id", tender_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return AnalysisRun.model_validate(row) if row else None

    def list_analysis_runs(self, tender_id: str, limit: int) -> list[AnalysisRun]:
        response = (
            self._table("analysis_runs")
            .select("*")
            .eq("tender_id", tender_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [AnalysisRun.model_validate(row) for row in response.data or []]

    def update_analysis_run(self, run_id: str, fields: dict[str, Any]) -> None:
        self._table("analysis_runs").update(fields).eq("id", run_id).execute()

    # Processing jobs ----------------------------------------------------------------------
    def create_processing_job(self, job: ProcessingJob) -> ProcessingJob:
        payload = job.model_dump(mode="json", exclude={"created_at", "updated_at"})
        row = self._first(self._table("processing_jobs").insert(payload).execute())
        return ProcessingJob.model_validate(row) if row else job

    def get_processing_job(self, job_id: str) -> ProcessingJob | None:
        row = self._first(self._table("processing_jobs").select("*").eq("id", job_id).execute())
        return ProcessingJob.model_validate(row) if row else None

    def get_job_for_run(self, run_id: str) -> ProcessingJob | None:
        row = self._first(
            self._table("processing_jobs").select("*").eq("analysis_run_id", run_id).execute()
        )
        return ProcessingJob.model_validate(row) if row else None

    def update_processing_job(self, job_id: str, fields: dict[str, Any]) -> None:
        payload = {**fields, "updated_at": datetime.now(UTC).isoformat()}
        self._table("processing_jobs").update(payload).eq("id", job_id).execute()

    # Requirements -------------------------------------------------------------------------
    def save_requirements(self, run: AnalysisRun, requirements: Sequence[FinalRequirement]) -> None:
        """Idempotent: deterministic ids, upserts, then removal of rows no longer produced."""
        req_rows, src_rows = requirement_rows(run, requirements)
        for start in range(0, len(req_rows), 100):
            self._table("requirements").upsert(
                req_rows[start : start + 100], on_conflict="id"
            ).execute()
        for start in range(0, len(src_rows), 200):
            self._table("requirement_sources").upsert(
                src_rows[start : start + 200], on_conflict="id", ignore_duplicates=True
            ).execute()
        keep = [row["id"] for row in req_rows]
        stale = self._table("requirements").delete().eq("analysis_run_id", run.id)
        if keep:
            stale = stale.not_.in_("id", keep)
        stale.execute()

    def list_requirements(self, run_id: str) -> list[Requirement]:
        response = (
            self._table("requirements")
            .select("*, requirement_sources(*)")
            .eq("analysis_run_id", run_id)
            .order("position")
            .execute()
        )
        result = []
        for row in response.data or []:
            sources = sorted(
                row.pop("requirement_sources", None) or [], key=lambda s: s["page_number"]
            )
            result.append(Requirement.model_validate({**row, "sources": sources}))
        return result

    def get_requirement_source(self, source_id: str) -> RequirementSource | None:
        row = self._first(
            self._table("requirement_sources").select("*").eq("id", source_id).execute()
        )
        return RequirementSource.model_validate(row) if row else None

    # Evidence selection and matching ------------------------------------------------------
    def add_evidence_selections(self, selections: Sequence[EvidenceSelection]) -> None:
        if not selections:
            return
        rows = [s.model_dump(mode="json", exclude={"created_at"}) for s in selections]
        try:
            self._table("analysis_evidence_documents").insert(rows).execute()
        except APIError as error:
            if _is_unique_violation(error):
                raise DuplicateError(str(error)) from None
            raise

    def list_evidence_selections(self, run_id: str) -> list[EvidenceSelection]:
        response = (
            self._table("analysis_evidence_documents")
            .select("*")
            .eq("analysis_run_id", run_id)
            .execute()
        )
        return [EvidenceSelection.model_validate(row) for row in response.data or []]

    def save_evidence_matches(
        self, run: AnalysisRun, assessments: Sequence[RequirementAssessment], model: str
    ) -> None:
        """Idempotent: deterministic ids, upserts, then removal of rows no longer produced."""
        match_rows, src_rows, action_rows = evidence_match_rows(run, assessments, model)
        for start in range(0, len(match_rows), 100):
            self._table("evidence_matches").upsert(
                match_rows[start : start + 100], on_conflict="id"
            ).execute()
        for start in range(0, len(src_rows), 200):
            self._table("evidence_match_sources").upsert(
                src_rows[start : start + 200], on_conflict="id"
            ).execute()
        for start in range(0, len(action_rows), 100):
            self._table("action_items").upsert(
                action_rows[start : start + 100], on_conflict="id"
            ).execute()
        # Matches cascade to their sources and action items, so remove stale matches first.
        self._delete_stale("evidence_matches", run.id, {row["id"] for row in match_rows})
        self._delete_stale("evidence_match_sources", run.id, {row["id"] for row in src_rows})
        self._delete_stale("action_items", run.id, {row["id"] for row in action_rows})

    def list_evidence_matches(self, run_id: str) -> list[EvidenceMatch]:
        rows = self._select_all(
            lambda: (
                self._table("evidence_matches")
                .select("*, evidence_match_sources(*)")
                .eq("analysis_run_id", run_id)
                .order("id")
            )
        )
        result = []
        for row in rows:
            sources = sorted(
                row.pop("evidence_match_sources", None) or [],
                key=lambda s: (s["document_id"], s["page_number"]),
            )
            result.append(EvidenceMatch.model_validate({**row, "sources": sources}))
        return result

    def get_evidence_match(self, match_id: str) -> EvidenceMatch | None:
        row = self._first(self._table("evidence_matches").select("*").eq("id", match_id).execute())
        return EvidenceMatch.model_validate(row) if row else None

    def get_evidence_match_source(self, source_id: str) -> EvidenceMatchSource | None:
        row = self._first(
            self._table("evidence_match_sources").select("*").eq("id", source_id).execute()
        )
        return EvidenceMatchSource.model_validate(row) if row else None

    def list_action_items(self, run_id: str) -> list[ActionItem]:
        rows = self._select_all(
            lambda: (
                self._table("action_items").select("*").eq("analysis_run_id", run_id).order("id")
            )
        )
        return [ActionItem.model_validate(row) for row in rows]

    # Review decisions ---------------------------------------------------------------------
    def insert_review_decision(self, decision: ReviewDecision) -> ReviewDecision:
        payload = decision.model_dump(mode="json", exclude={"created_at"})
        row = self._first(self._table("review_decisions").insert(payload).execute())
        return ReviewDecision.model_validate(row) if row else decision

    def list_review_decisions(self, run_id: str) -> list[ReviewDecision]:
        rows = self._select_all(
            lambda: (
                self._table("review_decisions")
                .select("*")
                .eq("analysis_run_id", run_id)
                .order("created_at")
                .order("id")
            )
        )
        return [ReviewDecision.model_validate(row) for row in rows]
