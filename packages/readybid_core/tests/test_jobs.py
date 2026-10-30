"""Analysis job tests with a MOCKED model provider (ScriptedProvider) and in-memory fakes.

These prove the pipeline logic: segmenting, citation validation, coverage flags, retries
and idempotent persistence. They do not prove a real model's behaviour; see
test_live_groq.py for that.
"""

import json
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from rq.timeouts import JobTimeoutException

from readybid_core import jobs
from readybid_core.analysis import FinalRequirement
from readybid_core.citations import ValidatedCitation
from readybid_core.clients import NotConfigured
from readybid_core.jobs import (
    JobContext,
    enqueue_analysis,
    mark_job_failed,
    retry_pending,
    rq_job_id,
    run_analysis,
    segments_to_rows,
)
from readybid_core.llm import LLMError
from readybid_core.models import AnalysisRun, Document, EvidenceSelection, ProcessingJob
from readybid_core.pdf import extract_segments, validate_pdf
from readybid_core.repository import requirement_rows
from readybid_core.storage import StorageError, evidence_storage_path
from readybid_testing.fakes import (
    FakeQueue,
    FakeRepository,
    FakeStorage,
    Response,
    ScriptedProvider,
    primary_passages,
    quote_each_primary_passage,
    requirement,
)
from readybid_testing.pdfs import IMAGE_ONLY, PageSpec, build_pdf
from readybid_testing.scenario import make_settings, queue_run, seed_document

USER = "11111111-1111-4111-8111-111111111111"
PAGE_1 = "Bidders must submit a valid tax compliance status pin with the bid"
PAGE_3 = "The bidder must attend the compulsory briefing session on site"


@dataclass
class Harness:
    ctx: JobContext
    repo: FakeRepository
    storage: FakeStorage
    document: Document
    run: AnalysisRun
    job: ProcessingJob
    provider: ScriptedProvider

    def analyse(self) -> dict[str, object]:
        return run_analysis(self.ctx, self.run.id, self.job.id)

    @property
    def stored_run(self) -> AnalysisRun:
        return self.repo.runs[self.run.id]

    @property
    def stored_job(self) -> ProcessingJob:
        return self.repo.jobs[self.job.id]


def harness(
    pages: list[PageSpec], respond: Callable[[str], Response], **settings: object
) -> Harness:
    repo, storage = FakeRepository(), FakeStorage()
    _, document = seed_document(repo, storage, build_pdf(pages), user_id=USER)
    run, job = queue_run(repo, document)
    provider = ScriptedProvider(respond)
    ctx = JobContext(
        settings=make_settings(**settings),
        repo=repo,
        storage=storage,
        provider_factory=lambda: provider,
    )
    return Harness(ctx, repo, storage, document, run, job, provider)


def segment_for(h: Harness, page: int) -> str:
    return next(s.id for s in h.repo.list_segments(h.document.id) if s.page_number == page)


# Successful runs ----------------------------------------------------------------------
def test_completed_run_saves_requirements_with_pages_from_segment_metadata() -> None:
    h = harness([PAGE_1, PAGE_3], quote_each_primary_passage)

    result = h.analyse()

    assert result["status"] == "completed"
    saved = h.repo.list_requirements(h.run.id)
    assert [r.requirement_text for r in saved] == [PAGE_1, PAGE_3]
    # The scripted model claims page 999 for every citation; that value must be ignored.
    assert [s.page_number for r in saved for s in r.sources] == [1, 2]
    assert [s.segment_id for r in saved for s in r.sources] == [
        segment_for(h, 1),
        segment_for(h, 2),
    ]
    assert h.stored_run.coverage_complete is True
    assert h.stored_run.flagged_pages == []
    assert (h.stored_job.status, h.stored_job.progress) == ("completed", 100)


def test_image_only_page_is_kept_and_flagged_as_incomplete_coverage() -> None:
    h = harness([PAGE_1, IMAGE_ONLY, PAGE_3], quote_each_primary_passage)

    assert h.analyse()["status"] == "completed"

    segments = h.repo.list_segments(h.document.id)
    assert [(s.page_number, s.extraction_status) for s in segments] == [
        (1, "ok"),
        (2, "empty"),
        (3, "ok"),
    ]
    assert segments[1].extraction_note and "scanned" in segments[1].extraction_note
    assert h.stored_run.pages_total == 3
    assert h.stored_run.flagged_pages == [2]
    assert h.stored_run.coverage_complete is False
    # The model is told the page has no text rather than being shown nothing at all.
    assert "[no extractable text]" in h.provider.calls[0][1]["content"]


def test_fully_scanned_document_makes_no_model_calls_and_reports_no_coverage() -> None:
    h = harness([IMAGE_ONLY, IMAGE_ONLY], quote_each_primary_passage)

    h.analyse()

    assert h.provider.calls == []
    assert h.repo.list_requirements(h.run.id) == []
    assert h.stored_run.flagged_pages == [1, 2]
    assert h.stored_run.coverage_complete is False


def test_escaped_document_text_is_unescaped_before_citation_check_and_storage() -> None:
    page = "Bidders must submit B-BBEE & tax <original> certificates with the bid"
    h = harness([page], quote_each_primary_passage)

    h.analyse()

    prompt = h.provider.calls[0][1]["content"]
    # Document text is untrusted, so the model sees it escaped...
    assert "B-BBEE &amp; tax &lt;original&gt; certificates" in prompt
    assert "<original>" not in prompt
    # ...but citation checks and stored rows use the original text.
    saved = h.repo.list_requirements(h.run.id)
    assert len(saved) == 1
    assert saved[0].sources[0].quote == page
    assert saved[0].requirement_text == page
    assert h.stored_run.rejected_citations == 0


# Citations ----------------------------------------------------------------------------
def test_invalid_citations_are_rejected_and_uncited_requirements_dropped() -> None:
    def respond(prompt: str) -> str:
        seg_id, text = primary_passages(prompt)[0]
        items = [
            requirement(seg_id, "Bidders must submit an original BEE certificate", text="a"),
            requirement("seg_" + "0" * 32, text, text="b"),  # segment not in this analysis
            requirement(seg_id, "tax", text="c"),  # too short to be a real citation
            requirement(
                seg_id,
                text,
                text="d",
                extra_sources=[{"segment_id": seg_id, "quote": "an invented quotation here"}],
            ),
        ]
        return json.dumps({"requirements": items})

    h = harness([PAGE_1], respond)

    h.analyse()

    saved = h.repo.list_requirements(h.run.id)
    assert [r.requirement_text for r in saved] == ["d"]
    assert [s.quote for s in saved[0].sources] == [PAGE_1]
    assert h.stored_run.rejected_citations == 4
    assert h.stored_run.dropped_requirements == 3


def test_citation_to_another_document_cannot_be_persisted() -> None:
    run = AnalysisRun(
        id="r",
        organisation_id="o",
        tender_id="t",
        document_id="doc-a",
        document_sha256="0" * 64,
        model="m",
    )
    citation = ValidatedCitation("seg_x", "doc-b", 1, "some quote text", "1" * 64)
    item = FinalRequirement(
        "k" * 64, 0, "t", "x", "returnable", None, "submission", None, None, [citation]
    )

    with pytest.raises(ValueError, match="does not belong"):
        requirement_rows(run, [item])


# Model failures -----------------------------------------------------------------------
def test_invalid_json_is_repaired_once_then_used() -> None:
    answers = iter(["this is not json", None])

    def respond(prompt: str) -> str:
        answer = next(answers)
        return answer if answer is not None else quote_each_primary_passage(prompt)

    h = harness([PAGE_1], respond)

    assert h.analyse()["status"] == "completed"
    assert len(h.provider.calls) == 2
    assert "could not be used" in h.provider.calls[1][-1]["content"]
    assert len(h.repo.list_requirements(h.run.id)) == 1


def test_persistently_invalid_output_fails_without_fabricating_results() -> None:
    h = harness([PAGE_1], lambda prompt: json.dumps({"requirements": [{"title": 1}]}))

    result = h.analyse()

    assert result["status"] == "failed"
    assert len(h.provider.calls) == 3  # first attempt plus at most 2 repairs
    assert h.repo.list_requirements(h.run.id) == []
    assert "after 3 attempts" in (h.stored_run.error or "")
    assert h.stored_job.status == "failed"


def test_failed_page_group_gives_partial_result_and_incomplete_coverage() -> None:
    def respond(prompt: str) -> Response:
        if any(text == PAGE_3 for _, text in primary_passages(prompt)):
            return LLMError("rate_limited", "The model provider rate limit was reached.")
        return quote_each_primary_passage(prompt)

    h = harness([PAGE_1, PAGE_3], respond, analysis_pages_per_group=1)

    assert h.analyse()["status"] == "partial"
    run = h.stored_run
    assert (run.groups_total, run.groups_completed, run.groups_failed) == (2, 1, 1)
    assert run.coverage_complete is False
    assert run.error and run.error.startswith("1 of 2 page groups failed")
    assert [r.requirement_text for r in h.repo.list_requirements(h.run.id)] == [PAGE_1]


def test_fatal_provider_error_stops_further_model_calls() -> None:
    def respond(prompt: str) -> Response:
        return LLMError("auth_failed", "The model provider rejected the API key.", fatal=True)

    h = harness([PAGE_1, PAGE_3, PAGE_1], respond, analysis_pages_per_group=1)

    assert h.analyse()["status"] == "failed"
    assert len(h.provider.calls) == 1
    assert h.stored_run.error == "The model provider rejected the API key."


def test_missing_model_configuration_fails_the_run_but_keeps_page_coverage() -> None:
    h = harness([PAGE_1, IMAGE_ONLY], quote_each_primary_passage)

    def not_configured() -> ScriptedProvider:
        raise NotConfigured("Integration not configured: set GROQ_API_KEY.")

    h.ctx.provider_factory = not_configured

    assert h.analyse()["status"] == "failed"
    assert "Integration not configured" in (h.stored_run.error or "")
    assert h.stored_run.flagged_pages == [2]


# Storage, integrity, retries and idempotency ------------------------------------------
def test_transient_storage_error_is_raised_for_retry_and_the_retry_converges() -> None:
    h = harness([PAGE_1], quote_each_primary_passage)
    h.storage.fail_downloads = 1

    with pytest.raises(StorageError):
        h.analyse()
    assert h.stored_job.status == "queued"
    assert h.stored_job.stage.startswith("waiting to retry")
    assert h.stored_run.status == "running"

    assert h.analyse()["status"] == "completed"
    assert h.stored_job.attempts == 2


def test_stored_file_that_does_not_match_its_hash_fails_the_run() -> None:
    h = harness([PAGE_1], quote_each_primary_passage)
    h.storage.objects[h.document.storage_path] = build_pdf(["dev-fixture tampered content page"])

    assert h.analyse()["status"] == "failed"
    assert "SHA-256" in (h.stored_run.error or "")
    assert h.provider.calls == []


def test_rerunning_an_interrupted_job_does_not_duplicate_rows() -> None:
    h = harness([PAGE_1, PAGE_3], quote_each_primary_passage)
    h.analyse()
    first_requirements = set(h.repo.requirement_rows)
    first_sources = set(h.repo.source_rows)

    # Simulate a crash after the rows were saved but before the run was finalised.
    h.repo.update_analysis_run(h.run.id, {"status": "running"})
    h.analyse()

    assert set(h.repo.requirement_rows) == first_requirements
    assert set(h.repo.source_rows) == first_sources
    assert len(h.repo.segments) == 2


def test_job_for_a_finished_run_does_nothing() -> None:
    h = harness([PAGE_1], quote_each_primary_passage)
    h.analyse()
    calls = len(h.provider.calls)

    assert h.analyse() == {"status": "completed", "skipped": True}
    assert len(h.provider.calls) == calls


def test_job_and_run_from_different_organisations_are_refused() -> None:
    h = harness([PAGE_1], quote_each_primary_passage)
    h.repo.jobs[h.job.id] = h.job.model_copy(update={"organisation_id": "other-org"})

    with pytest.raises(jobs.PermanentJobError):
        h.analyse()
    assert h.provider.calls == []


# RQ failure callback and enqueueing ---------------------------------------------------
def rq_job(h: Harness, retries_left: int | None) -> SimpleNamespace:
    return SimpleNamespace(args=(h.run.id, h.job.id), retries_left=retries_left)


def test_retry_pending_reads_retries_left() -> None:
    assert retry_pending(SimpleNamespace(retries_left=1)) is True
    assert retry_pending(SimpleNamespace(retries_left=0)) is False
    assert retry_pending(SimpleNamespace(retries_left=None)) is False
    assert retry_pending(SimpleNamespace()) is False


def test_failure_with_retry_pending_shows_waiting_not_failed(monkeypatch) -> None:
    h = harness([PAGE_1], quote_each_primary_passage)
    monkeypatch.setattr(jobs, "_default_context", lambda: h.ctx)

    mark_job_failed(rq_job(h, 1), None, RuntimeError, RuntimeError("boom"), None)

    assert h.stored_job.status == "queued"
    assert h.stored_job.stage == "waiting to retry"
    assert h.stored_run.status == "queued"


def test_final_failure_and_timeout_mark_the_run_failed(monkeypatch) -> None:
    h = harness([PAGE_1], quote_each_primary_passage)
    monkeypatch.setattr(jobs, "_default_context", lambda: h.ctx)

    mark_job_failed(rq_job(h, 0), None, JobTimeoutException, JobTimeoutException(), None)

    assert h.stored_run.status == "failed"
    assert h.stored_run.error == "Processing took too long and was stopped."
    assert (h.stored_job.status, h.stored_job.progress) == ("failed", 100)


def test_failure_callback_never_overwrites_a_finished_run(monkeypatch) -> None:
    h = harness([PAGE_1], quote_each_primary_passage)
    h.analyse()
    monkeypatch.setattr(jobs, "_default_context", lambda: h.ctx)

    mark_job_failed(rq_job(h, 0), None, RuntimeError, RuntimeError("late"), None)

    assert h.stored_run.status == "completed"


def test_enqueue_uses_bounded_timeout_retries_and_failure_callback() -> None:
    queue = FakeQueue()
    settings = make_settings(job_timeout_seconds=600, job_max_retries=2)

    rq_id = enqueue_analysis(queue, settings, "run-1", "job-1")

    assert rq_id == rq_job_id("job-1")
    [call] = queue.calls
    assert call["args"] == ("run-1", "job-1")
    assert call["job_id"] == rq_id
    assert call["timeout"] == 600
    assert call["retry"].max == 2
    assert call["on_failure"].func is mark_job_failed


# Evidence matching inside the analysis job ----------------------------------------------
PROFILE_PAGE = "Bidders must submit a company profile with the bid"
EVIDENCE_TEXT = "dev-fixture company profile for Acme Civils describing road maintenance work"

_REQUIREMENT_REF = re.compile(r'<requirement ref="(?P<ref>[^"]+)"')
_EVIDENCE_SEGMENT = re.compile(
    r'<segment id="(?P<id>[^"]+)" document="[^"]+" page="\d+" extraction="(?P<status>[^"]+)">'
    r"\n(?P<text>.*?)\n</segment>",
    re.DOTALL,
)


def is_matching_prompt(prompt: str) -> bool:
    return "<evidence>" in prompt and "<requirements>" in prompt


def cite_first_readable_evidence(prompt: str) -> str:
    """One assessment per requirement ref, quoting the first cleanly extracted evidence page."""
    readable = [
        (m["id"], m["text"]) for m in _EVIDENCE_SEGMENT.finditer(prompt) if m["status"] == "ok"
    ]
    assessments = [
        {
            "requirement_ref": ref,
            "assessment": "evidence_found" if readable else "missing_evidence",
            "explanation": "The passage may relate to the requirement.",
            "uncertainty_notes": None,
            "required_count": None,
            "candidates": [
                {
                    "segment_id": readable[0][0],
                    "quote": readable[0][1],
                    "relationship": "May describe the company.",
                }
            ]
            if readable
            else [],
        }
        for ref in _REQUIREMENT_REF.findall(prompt)
    ]
    return json.dumps({"assessments": assessments})


def analyse_then_match(prompt: str) -> str:
    if is_matching_prompt(prompt):
        return cite_first_readable_evidence(prompt)
    return quote_each_primary_passage(prompt)


def matching_calls(h: Harness) -> list[str]:
    return [c[1]["content"] for c in h.provider.calls if is_matching_prompt(c[1]["content"])]


def seed_evidence(
    h: Harness, pages: list[PageSpec], *, label: str = "company_profile", extract: bool = True
) -> Document:
    """An organisation-level evidence document, stored and (by default) extracted as at upload."""
    organisation_id = h.document.organisation_id
    document_id = str(uuid.uuid4())
    path = evidence_storage_path(organisation_id, document_id)
    pdf = build_pdf(pages)
    h.storage.upload_pdf(path, pdf)
    validated = validate_pdf(pdf, max_bytes=15 * 1024 * 1024, max_pages=100)
    document = h.repo.insert_document(
        Document(
            id=document_id,
            organisation_id=organisation_id,
            tender_id=None,
            document_type="evidence",
            evidence_label=label,
            original_filename=f"dev-fixture-{label}.pdf",
            storage_path=path,
            sha256=validated.sha256,
            size_bytes=validated.size_bytes,
            page_count=validated.page_count,
            version=1,
            created_by=USER,
        )
    )
    if extract:
        segments = extract_segments(pdf, document_id=document.id, document_sha256=document.sha256)
        h.repo.upsert_segments(segments_to_rows(document, segments))
    return document


def select_evidence(h: Harness, *documents: Document) -> None:
    """Pin the documents to the run, as POST /tenders/{id}/analyses does."""
    h.repo.update_analysis_run(h.run.id, {"matching_status": "pending"})
    h.repo.add_evidence_selections(
        [
            EvidenceSelection(
                analysis_run_id=h.run.id,
                organisation_id=h.run.organisation_id,
                document_id=d.id,
                document_sha256=d.sha256,
            )
            for d in documents
        ]
    )


def test_selected_evidence_is_matched_after_requirements_and_saved_with_its_source() -> None:
    h = harness([PROFILE_PAGE], analyse_then_match)
    evidence = seed_evidence(h, [EVIDENCE_TEXT])
    select_evidence(h, evidence)

    result = h.analyse()

    assert result["status"] == "completed"
    assert result["matching"] == "completed"
    run = h.stored_run
    assert (run.matching_status, run.matching_requirements_total) == ("completed", 1)
    assert (run.matching_requirements_failed, run.matching_rejected_citations) == (0, 0)
    assert run.matching_error is None
    assert len(matching_calls(h)) == 1
    [requirement_row] = h.repo.list_requirements(h.run.id)
    [match] = h.repo.list_evidence_matches(h.run.id)
    assert match.requirement_id == requirement_row.id
    # The model proposes; the stored status always leaves the row for human review.
    assert match.ai_status == "evidence_found_review_required"
    [source] = match.sources
    assert (source.document_id, source.page_number) == (evidence.id, 1)
    assert source.extraction_status == "ok"
    assert source.quote == EVIDENCE_TEXT
    assert (h.stored_job.status, h.stored_job.progress) == ("completed", 100)


def test_run_without_selected_evidence_never_matches_library_documents() -> None:
    h = harness([PROFILE_PAGE], analyse_then_match)
    seed_evidence(h, [EVIDENCE_TEXT])  # in the library, but not selected

    result = h.analyse()

    assert result["status"] == "completed"
    assert result["matching"] == "not_requested"
    assert h.stored_run.matching_status == "not_requested"
    assert matching_calls(h) == []
    assert h.repo.list_evidence_matches(h.run.id) == []
    assert len(h.repo.list_requirements(h.run.id)) == 1


def test_evidence_changed_after_selection_fails_matching_but_keeps_requirements() -> None:
    h = harness([PROFILE_PAGE], analyse_then_match)
    evidence = seed_evidence(h, [EVIDENCE_TEXT])
    select_evidence(h, evidence)
    h.repo.documents[evidence.id] = evidence.model_copy(update={"sha256": "0" * 64})

    result = h.analyse()

    # EvidenceUnavailable cannot be fixed by a retry: matching fails, extraction stands.
    assert result["status"] == "completed"
    assert result["matching"] == "failed"
    run = h.stored_run
    assert run.matching_status == "failed"
    assert "does not match the version that was selected" in (run.matching_error or "")
    assert (run.matching_requirements_total, run.matching_requirements_failed) == (1, 1)
    assert matching_calls(h) == []
    assert h.repo.list_evidence_matches(h.run.id) == []
    assert len(h.repo.list_requirements(h.run.id)) == 1
    assert h.stored_job.status == "completed"


def test_storage_outage_while_loading_evidence_is_raised_for_retry_and_the_retry_converges() -> (
    None
):
    h = harness([PROFILE_PAGE], analyse_then_match)
    # No segments saved at upload, so the job must download and extract the evidence file.
    evidence = seed_evidence(h, [EVIDENCE_TEXT], extract=False)
    select_evidence(h, evidence)
    stored_file = h.storage.objects.pop(evidence.storage_path)

    with pytest.raises(StorageError):
        h.analyse()
    assert h.stored_job.status == "queued"
    assert h.stored_job.stage.startswith("waiting to retry")
    assert h.stored_run.status == "running"
    assert h.stored_run.matching_status == "pending"

    h.storage.objects[evidence.storage_path] = stored_file
    result = h.analyse()

    assert result["status"] == "completed"
    assert h.stored_run.matching_status == "completed"
    assert [s.page_number for s in h.repo.list_segments(evidence.id)] == [1]
    [match] = h.repo.list_evidence_matches(h.run.id)
    assert [s.document_id for s in match.sources] == [evidence.id]
    assert h.stored_job.attempts == 2
