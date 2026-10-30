"""Background job functions run by the RQ worker.

Jobs live in the shared core so the API (which enqueues) and the worker (which executes)
import the same code.

Analysis job
* States: queued -> running -> completed | partial | failed.
* Safe to retry: segment, requirement and evidence match ids are deterministic and writes
  are upserts, so a retried job converges on the same rows instead of duplicating them.
* A job for a run that is already terminal does nothing.
* Bounded: the RQ timeout kills the job, and the analysis also stops starting new page
  groups or matching batches after a soft deadline so it can record a partial result first.
* Transient errors (storage, network) are re-raised so RQ retries them. Permanent errors
  (hash mismatch, unreadable PDF, missing configuration) fail the run immediately.

Evidence matching
* Runs in the same job, after requirement extraction, only when evidence documents were
  explicitly selected for the run. With no selection, no matching calls are made.
* Its outcome is tracked in the run's matching_* fields, separately from extraction, so a
  matching failure never hides or changes the extracted requirements.
"""

import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from readybid_core.analysis import AnalysisSegment, analyse_document
from readybid_core.config import Settings, get_settings
from readybid_core.llm import LLMProvider
from readybid_core.matching import EvidenceDocumentInput, RequirementInput, match_evidence
from readybid_core.models import TERMINAL_STATUSES, AnalysisRun, Document, SourceSegment
from readybid_core.pdf import PdfValidationError, Segment, extract_segments, sha256_hex
from readybid_core.repository import Repository
from readybid_core.storage import DocumentStorage, StorageError

logger = logging.getLogger(__name__)

QUEUE_NAME = "readybid"
# Fraction of the RQ job timeout after which no new page groups are started.
SOFT_DEADLINE_FRACTION = 0.8


def ping_job() -> dict[str, str]:
    """Trivial job used to confirm the queue and worker are connected."""
    return {"status": "ok", "service": "readybid-worker"}


def rq_job_id(processing_job_id: str) -> str:
    return f"analysis-{processing_job_id}"


class PermanentJobError(Exception):
    """An error that a retry cannot fix."""


class EvidenceUnavailable(Exception):
    """A selected evidence document cannot be used. A retry cannot fix it."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass
class JobContext:
    settings: Settings
    repo: Repository
    storage: DocumentStorage
    provider_factory: Callable[[], LLMProvider]
    clock: Callable[[], float] = time.monotonic


def _now() -> str:
    return datetime.now(UTC).isoformat()


def failed_run_fields(run: AnalysisRun | None, message: str) -> dict[str, Any]:
    """Fields that mark a run failed, including pending evidence matching."""
    fields: dict[str, Any] = {"status": "failed", "error": message, "finished_at": _now()}
    if run is not None and run.matching_status == "pending":
        fields["matching_status"] = "failed"
        fields["matching_error"] = "The analysis failed before evidence could be matched."
    return fields


def segments_to_rows(document: Document, segments: Sequence[Segment]) -> list[SourceSegment]:
    return [
        SourceSegment(
            id=s.id,
            organisation_id=document.organisation_id,
            document_id=document.id,
            document_sha256=document.sha256,
            page_number=s.page_number,
            text=s.text,
            char_count=s.char_count,
            extraction_status=s.status,
            extraction_note=s.note,
        )
        for s in segments
    ]


def load_evidence(ctx: JobContext, run: AnalysisRun) -> list[EvidenceDocumentInput]:
    """Load the evidence documents selected for a run, with their page segments.

    Segments are normally extracted at upload. If they are missing (for example the upload
    could not save them), the stored file is checked against its hash and extracted again.
    Raises EvidenceUnavailable when a selection no longer matches its document, and
    StorageError when the file cannot be downloaded (transient).
    """
    repo = ctx.repo
    result: list[EvidenceDocumentInput] = []
    for selection in repo.list_evidence_selections(run.id):
        if selection.organisation_id != run.organisation_id:
            raise EvidenceUnavailable("A selected evidence document could not be found.")
        document = repo.get_document(selection.document_id)
        if (
            document is None
            or document.organisation_id != run.organisation_id
            or document.document_type != "evidence"
        ):
            raise EvidenceUnavailable("A selected evidence document no longer exists.")
        if document.sha256 != selection.document_sha256:
            raise EvidenceUnavailable(
                f"{document.original_filename} does not match the version that was selected."
            )
        segments = [
            s
            for s in repo.list_segments(document.id)
            if s.organisation_id == run.organisation_id and s.document_sha256 == document.sha256
        ]
        if len({s.page_number for s in segments}) < document.page_count:
            data = ctx.storage.download(document.storage_path)
            if sha256_hex(data) != document.sha256:
                raise EvidenceUnavailable(
                    f"The stored file for {document.original_filename} does not match its "
                    "recorded SHA-256. Upload it again."
                )
            try:
                extracted = extract_segments(
                    data, document_id=document.id, document_sha256=document.sha256
                )
            except PdfValidationError as error:
                raise EvidenceUnavailable(
                    f"{document.original_filename}: {error.message}"
                ) from None
            segments = segments_to_rows(document, extracted)
            repo.upsert_segments(segments)
        result.append(
            EvidenceDocumentInput(
                id=document.id,
                sha256=document.sha256,
                filename=document.original_filename,
                label=document.evidence_label or "other",
                page_count=document.page_count,
                segments=tuple(
                    AnalysisSegment(
                        id=s.id,
                        page_number=s.page_number,
                        text=s.text,
                        status=s.extraction_status,
                    )
                    for s in sorted(segments, key=lambda s: s.page_number)
                ),
            )
        )
    return sorted(result, key=lambda d: (d.filename.casefold(), d.id))


def _match_evidence_step(
    ctx: JobContext,
    run: AnalysisRun,
    provider: LLMProvider,
    deadline: float,
    set_job: Callable[..., None],
) -> dict[str, Any]:
    """Match the run's saved requirements against its selected evidence. Returns run fields."""
    repo = ctx.repo
    settings = ctx.settings
    requirements = [
        r
        for r in repo.list_requirements(run.id)
        if r.organisation_id == run.organisation_id and r.sources
    ]
    total = len(requirements)
    set_job("matching evidence", 91)
    try:
        documents = load_evidence(ctx, run)
    except EvidenceUnavailable as error:
        repo.save_evidence_matches(run, [], provider.model)
        return {
            "matching_status": "failed",
            "matching_requirements_total": total,
            "matching_requirements_failed": total,
            "matching_error": error.message,
        }
    except StorageError:
        set_job("waiting to retry (storage unavailable)", 91, status="queued")
        raise  # transient: let RQ retry

    def on_progress(done: int, count: int) -> None:
        progress = 91 + int(7 * done / count) if count else 98
        set_job(f"matching evidence ({done}/{count})", min(progress, 98))

    result = match_evidence(
        provider=provider,
        requirements=[
            RequirementInput(
                id=r.id,
                title=r.title,
                requirement_text=r.requirement_text,
                category=r.category,
                evidence_needed=r.evidence_needed,
                consequence=r.consequence,
                ambiguity_notes=r.ambiguity_notes,
            )
            for r in requirements
        ],
        documents=documents,
        batch_size=settings.matching_requirements_per_batch,
        max_evidence_chars=settings.matching_max_evidence_chars,
        max_segment_chars=settings.matching_max_segment_chars,
        max_repair_attempts=settings.llm_max_repair_attempts,
        deadline=deadline,
        on_progress=on_progress,
        clock=ctx.clock,
    )
    repo.save_evidence_matches(run, result.assessments, provider.model)
    return {
        "matching_status": result.status,
        "matching_requirements_total": result.requirements_total,
        "matching_requirements_failed": result.requirements_failed,
        "matching_rejected_citations": result.rejected_citations,
        "matching_truncated_segments": result.truncated_segments,
        "matching_error": result.error,
    }


def run_analysis(ctx: JobContext, run_id: str, job_id: str) -> dict[str, Any]:
    """Run one analysis. Returns a small summary (stored as the RQ result)."""
    repo = ctx.repo
    run = repo.get_analysis_run(run_id)
    job = repo.get_processing_job(job_id)
    if run is None or job is None or job.analysis_run_id != run.id:
        raise PermanentJobError("Analysis run or job not found.")
    if job.organisation_id != run.organisation_id:
        raise PermanentJobError("Job and analysis run belong to different organisations.")
    if run.status in TERMINAL_STATUSES:
        return {"status": run.status, "skipped": True}

    def set_job(stage: str, progress: int, **extra: Any) -> None:
        repo.update_processing_job(job_id, {"stage": stage, "progress": progress, **extra})

    def fail(message: str) -> dict[str, Any]:
        repo.update_analysis_run(run_id, failed_run_fields(run, message))
        set_job("failed", 100, status="failed", error=message)
        return {"status": "failed", "error": message}

    repo.update_analysis_run(run_id, {"status": "running", "started_at": _now(), "error": None})
    set_job("downloading", 5, status="running", attempts=job.attempts + 1, error=None)

    document = repo.get_document(run.document_id)
    if (
        document is None
        or document.organisation_id != run.organisation_id
        or document.tender_id != run.tender_id
    ):
        return fail("The analysed document no longer exists.")
    if document.sha256 != run.document_sha256:
        return fail("The document version does not match the analysis run.")

    try:
        data = ctx.storage.download(document.storage_path)
    except StorageError:
        set_job("waiting to retry (storage unavailable)", 5, status="queued")
        raise  # transient: let RQ retry
    if sha256_hex(data) != document.sha256:
        return fail("The stored file does not match its recorded SHA-256. Upload it again.")

    set_job("extracting text", 15)
    try:
        segments = extract_segments(data, document_id=document.id, document_sha256=document.sha256)
    except PdfValidationError as error:
        return fail(error.message)

    repo.upsert_segments(segments_to_rows(document, segments))
    flagged = [s.page_number for s in segments if s.status != "ok"]
    repo.update_analysis_run(run_id, {"pages_total": len(segments), "flagged_pages": flagged})

    try:
        provider = ctx.provider_factory()
    except RuntimeError as error:  # NotConfigured
        return fail(str(error))

    settings = ctx.settings
    deadline = ctx.clock() + settings.job_timeout_seconds * SOFT_DEADLINE_FRACTION

    def on_progress(completed: int, failed: int, total: int) -> None:
        done = completed + failed
        progress = 20 + int(70 * done / total) if total else 90
        repo.update_analysis_run(
            run_id,
            {"groups_total": total, "groups_completed": completed, "groups_failed": failed},
        )
        set_job(f"analysing page groups ({done}/{total})", min(progress, 90))

    set_job("analysing page groups", 20)
    result = analyse_document(
        provider=provider,
        document_id=document.id,
        document_sha256=document.sha256,
        segments=[
            AnalysisSegment(id=s.id, page_number=s.page_number, text=s.text, status=s.status)
            for s in segments
        ],
        pages_per_group=settings.analysis_pages_per_group,
        max_group_chars=settings.analysis_max_group_chars,
        boundary_context_chars=settings.analysis_boundary_context_chars,
        max_requirements_per_group=settings.llm_max_requirements_per_group,
        max_repair_attempts=settings.llm_max_repair_attempts,
        deadline=deadline,
        on_progress=on_progress,
        clock=ctx.clock,
    )

    set_job("saving requirements", 90)
    if result.status != "failed":
        repo.save_requirements(run, result.requirements)

    matching: dict[str, Any] = {}
    if run.matching_status != "not_requested":
        if result.status == "failed":
            matching = {
                "matching_status": "failed",
                "matching_error": "Requirements could not be extracted, so no evidence was "
                "matched.",
            }
        else:
            matching = _match_evidence_step(ctx, run, provider, deadline, set_job)

    error = result.error
    if result.status == "partial":
        error = f"{result.groups_failed} of {result.groups_total} page groups failed: " + (
            result.failures[0].reason if result.failures else "unknown error"
        )
    repo.update_analysis_run(
        run_id,
        {
            "status": result.status,
            "groups_total": result.groups_total,
            "groups_completed": result.groups_completed,
            "groups_failed": result.groups_failed,
            "flagged_pages": result.flagged_pages,
            "truncated_pages": result.truncated_pages,
            "rejected_citations": result.rejected_citations,
            "dropped_requirements": result.dropped_requirements,
            "coverage_complete": result.coverage_complete,
            "error": error,
            "finished_at": _now(),
            **matching,
        },
    )
    set_job(result.status, 100, status=result.status, error=error)
    return {
        "status": result.status,
        "requirements": len(result.requirements),
        "groups_failed": result.groups_failed,
        "matching": matching.get("matching_status", run.matching_status),
    }


def _default_context() -> JobContext:
    from readybid_core.clients import build_llm_provider, build_repository_and_storage

    settings = get_settings()
    repo, storage = build_repository_and_storage(settings)
    return JobContext(
        settings=settings,
        repo=repo,
        storage=storage,
        provider_factory=lambda: build_llm_provider(settings),
    )


def analyse_document_job(run_id: str, job_id: str) -> dict[str, Any]:
    """RQ entry point. Builds real clients from settings in the worker process."""
    try:
        ctx = _default_context()
    except RuntimeError as error:
        logger.error("Analysis job cannot start: %s", error)
        raise PermanentJobError(str(error)) from None
    try:
        return run_analysis(ctx, run_id, job_id)
    except PermanentJobError as error:
        run = ctx.repo.get_analysis_run(run_id)
        ctx.repo.update_analysis_run(run_id, failed_run_fields(run, str(error)))
        ctx.repo.update_processing_job(
            job_id, {"status": "failed", "stage": "failed", "progress": 100, "error": str(error)}
        )
        raise


def retry_pending(job: Any) -> bool:
    """True when RQ will run this job again after the current failed attempt.

    RQ (2.12) calls the failure callback on *every* failed attempt, before it decrements
    ``retries_left`` (see ``rq/worker/base.py`` perform_job -> handle_job_failure ->
    ``job.retry``). So a positive ``retries_left`` inside the callback means another
    attempt is coming.
    """
    retries_left = getattr(job, "retries_left", None)
    return isinstance(retries_left, int) and retries_left > 0


def mark_job_failed(job: Any, connection: Any, exc_type: Any, exc_value: Any, tb: Any) -> None:
    """RQ failure callback. Runs after every failed attempt, including timeouts.

    The run is only marked failed once no retry is pending, so a transient error on the
    first attempt does not show a failure the user would then see silently recover.
    """
    args = getattr(job, "args", None) or ()
    if len(args) != 2:
        return
    run_id, job_id = args
    timed_out = exc_type is not None and exc_type.__name__ == "JobTimeoutException"
    message = (
        "Processing took too long and was stopped."
        if timed_out
        else "Processing failed after retries."
    )
    try:
        ctx = _default_context()
        run = ctx.repo.get_analysis_run(run_id)
        if run is not None and run.status in TERMINAL_STATUSES:
            return
        if retry_pending(job):
            ctx.repo.update_processing_job(
                job_id, {"status": "queued", "stage": "waiting to retry", "error": None}
            )
            return
        ctx.repo.update_analysis_run(run_id, failed_run_fields(run, message))
        ctx.repo.update_processing_job(
            job_id, {"status": "failed", "stage": "failed", "progress": 100, "error": message}
        )
    except Exception:  # noqa: BLE001 - never raise from a failure callback
        logger.exception("Could not record job failure for run %s", run_id)


def enqueue_analysis(queue: Any, settings: Settings, run_id: str, job_id: str) -> str:
    """Enqueue the analysis job with bounded retries and timeout. Returns the RQ job id."""
    from rq import Callback, Retry

    rq_id = rq_job_id(job_id)
    queue.enqueue_call(
        analyse_document_job,
        args=(run_id, job_id),
        timeout=settings.job_timeout_seconds,
        result_ttl=86_400,
        failure_ttl=7 * 86_400,
        job_id=rq_id,
        retry=Retry(max=settings.job_max_retries, interval=[10, 60])
        if settings.job_max_retries
        else None,
        on_failure=Callback(mark_job_failed),
    )
    return rq_id
