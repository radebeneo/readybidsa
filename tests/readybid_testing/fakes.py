"""In-memory fakes for automated tests only. The app never uses these.

`FakeRepository` mirrors the database constraints the code relies on: unique document
versions per tender, idempotent segment and requirement upserts, and the
requirement_sources foreign key that ties a source to its segment's organisation,
document and page.
"""

import json
import re
import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from redis.exceptions import ConnectionError as RedisConnectionError

from readybid_core.analysis import FinalRequirement
from readybid_core.llm import Message
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
from readybid_core.repository import DuplicateError, evidence_match_rows, requirement_rows
from readybid_core.storage import StorageError


def _now() -> datetime:
    return datetime.now(UTC)


class FakeRepository:
    def __init__(self) -> None:
        self.organisations: dict[str, Organisation] = {}
        self.members: list[tuple[str, str, str]] = []  # (organisation_id, user_id, role)
        self.tenders: dict[str, Tender] = {}
        self.documents: dict[str, Document] = {}
        self.segments: dict[str, SourceSegment] = {}
        self.runs: dict[str, AnalysisRun] = {}
        self.jobs: dict[str, ProcessingJob] = {}
        self.requirement_rows: dict[str, dict[str, Any]] = {}
        self.source_rows: dict[str, dict[str, Any]] = {}
        self.selections: list[EvidenceSelection] = []
        self.match_rows: dict[str, dict[str, Any]] = {}
        self.match_source_rows: dict[str, dict[str, Any]] = {}
        self.action_rows: dict[str, dict[str, Any]] = {}
        self.decisions: list[ReviewDecision] = []
        # Simulate concurrent uploads claiming the same version this many times.
        self.conflicting_document_inserts = 0

    # Organisations ----------------------------------------------------------------------
    def list_memberships(self, user_id: str) -> list[OrganisationMembership]:
        return [
            OrganisationMembership(
                organisation_id=org_id, name=self.organisations[org_id].name, role=role
            )
            for org_id, member, role in self.members
            if member == user_id
        ]

    def create_organisation(self, name: str, owner_user_id: str) -> Organisation:
        org = Organisation(id=str(uuid.uuid4()), name=name)
        self.organisations[org.id] = org
        self.members.append((org.id, owner_user_id, "owner"))
        return org

    # Tenders ------------------------------------------------------------------------------
    def list_tenders(self, organisation_id: str) -> list[Tender]:
        rows = [t for t in self.tenders.values() if t.organisation_id == organisation_id]
        return list(reversed(rows))

    def create_tender(
        self, organisation_id: str, title: str, reference: str | None, created_by: str
    ) -> Tender:
        tender = Tender(
            id=str(uuid.uuid4()),
            organisation_id=organisation_id,
            title=title,
            reference=reference,
            created_by=created_by,
            created_at=_now(),
        )
        self.tenders[tender.id] = tender
        return tender

    def get_tender(self, tender_id: str) -> Tender | None:
        return self.tenders.get(tender_id)

    # Documents ----------------------------------------------------------------------------
    def list_documents(self, tender_id: str) -> list[Document]:
        rows = [d for d in self.documents.values() if d.tender_id == tender_id]
        return sorted(rows, key=lambda d: d.version, reverse=True)

    def list_evidence_documents(self, organisation_id: str) -> list[Document]:
        rows = [
            d
            for d in self.documents.values()
            if d.organisation_id == organisation_id and d.document_type == "evidence"
        ]
        return list(reversed(rows))

    def latest_document_version(self, tender_id: str) -> int:
        versions = [d.version for d in self.documents.values() if d.tender_id == tender_id]
        return max(versions, default=0)

    def insert_document(self, document: Document) -> Document:
        if self.conflicting_document_inserts > 0:
            self.conflicting_document_inserts -= 1
            raise DuplicateError(
                "duplicate key value violates unique constraint (tender_id, version)"
            )
        if document.document_type == "evidence":
            # Mirrors the documents_shape check constraint.
            if document.tender_id is not None or not document.evidence_label:
                raise ValueError("evidence documents need a label and no tender")
        elif document.tender_id is None:
            raise ValueError("tender documents need a tender")
        for existing in self.documents.values():
            # Postgres treats NULL tender ids as distinct, so evidence never collides here.
            if document.tender_id is not None and (existing.tender_id, existing.version) == (
                document.tender_id,
                document.version,
            ):
                raise DuplicateError("duplicate (tender_id, version)")
            if existing.storage_path == document.storage_path or existing.id == document.id:
                raise DuplicateError("duplicate document")
        stored = document.model_copy(update={"created_at": _now()})
        self.documents[stored.id] = stored
        return stored

    def get_document(self, document_id: str) -> Document | None:
        return self.documents.get(document_id)

    # Segments -----------------------------------------------------------------------------
    def upsert_segments(self, segments: Sequence[SourceSegment]) -> None:
        for segment in segments:
            self.segments.setdefault(segment.id, segment)  # ignore_duplicates=True

    def list_segments(self, document_id: str) -> list[SourceSegment]:
        rows = [s for s in self.segments.values() if s.document_id == document_id]
        return sorted(rows, key=lambda s: s.page_number)

    def list_segment_statuses(self, document_ids: Sequence[str]) -> list[SegmentStatus]:
        wanted = set(document_ids)
        rows = sorted(
            (s for s in self.segments.values() if s.document_id in wanted),
            key=lambda s: (s.document_id, s.page_number),
        )
        return [
            SegmentStatus(
                document_id=s.document_id,
                document_sha256=s.document_sha256,
                page_number=s.page_number,
                extraction_status=s.extraction_status,
                extraction_note=s.extraction_note,
            )
            for s in rows
        ]

    def get_segment(self, segment_id: str) -> SourceSegment | None:
        return self.segments.get(segment_id)

    # Analysis runs ------------------------------------------------------------------------
    def create_analysis_run(self, run: AnalysisRun) -> AnalysisRun:
        stored = run.model_copy(update={"created_at": _now()})
        self.runs[stored.id] = stored
        return stored

    def get_analysis_run(self, run_id: str) -> AnalysisRun | None:
        return self.runs.get(run_id)

    def latest_analysis_run(self, tender_id: str) -> AnalysisRun | None:
        rows = [r for r in self.runs.values() if r.tender_id == tender_id]
        return rows[-1] if rows else None

    def list_analysis_runs(self, tender_id: str, limit: int) -> list[AnalysisRun]:
        rows = [r for r in self.runs.values() if r.tender_id == tender_id]
        return list(reversed(rows))[:limit]

    def update_analysis_run(self, run_id: str, fields: dict[str, Any]) -> None:
        current = self.runs[run_id]
        self.runs[run_id] = AnalysisRun.model_validate({**current.model_dump(), **fields})

    # Processing jobs ----------------------------------------------------------------------
    def create_processing_job(self, job: ProcessingJob) -> ProcessingJob:
        stored = job.model_copy(update={"created_at": _now(), "updated_at": _now()})
        self.jobs[stored.id] = stored
        return stored

    def get_processing_job(self, job_id: str) -> ProcessingJob | None:
        return self.jobs.get(job_id)

    def get_job_for_run(self, run_id: str) -> ProcessingJob | None:
        return next((j for j in self.jobs.values() if j.analysis_run_id == run_id), None)

    def update_processing_job(self, job_id: str, fields: dict[str, Any]) -> None:
        current = self.jobs[job_id]
        self.jobs[job_id] = ProcessingJob.model_validate(
            {**current.model_dump(), **fields, "updated_at": _now()}
        )

    # Requirements -------------------------------------------------------------------------
    def save_requirements(self, run: AnalysisRun, requirements: Sequence[FinalRequirement]) -> None:
        req_rows, src_rows = requirement_rows(run, requirements)
        for row in src_rows:
            segment = self.segments.get(row["segment_id"])
            key = (row["organisation_id"], row["document_id"], row["page_number"])
            if (
                segment is None
                or (
                    segment.organisation_id,
                    segment.document_id,
                    segment.page_number,
                )
                != key
            ):
                raise ValueError("requirement_sources foreign key violation")
        for row in req_rows:
            self.requirement_rows[row["id"]] = row
        for row in src_rows:
            self.source_rows.setdefault(row["id"], row)
        keep = {row["id"] for row in req_rows}
        stale = [
            rid
            for rid, row in self.requirement_rows.items()
            if row["analysis_run_id"] == run.id and rid not in keep
        ]
        for rid in stale:
            del self.requirement_rows[rid]
            for sid in [s for s, src in self.source_rows.items() if src["requirement_id"] == rid]:
                del self.source_rows[sid]

    def list_requirements(self, run_id: str) -> list[Requirement]:
        rows = sorted(
            (r for r in self.requirement_rows.values() if r["analysis_run_id"] == run_id),
            key=lambda r: r["position"],
        )
        result = []
        for row in rows:
            sources = sorted(
                (s for s in self.source_rows.values() if s["requirement_id"] == row["id"]),
                key=lambda s: s["page_number"],
            )
            result.append(Requirement.model_validate({**row, "sources": sources}))
        return result

    def get_requirement_source(self, source_id: str) -> RequirementSource | None:
        row = self.source_rows.get(source_id)
        return RequirementSource.model_validate(row) if row else None

    # Evidence selection and matching ------------------------------------------------------
    def add_evidence_selections(self, selections: Sequence[EvidenceSelection]) -> None:
        for selection in selections:
            run = self.runs.get(selection.analysis_run_id)
            document = self.documents.get(selection.document_id)
            # Mirrors the composite foreign keys on analysis_evidence_documents.
            if (
                run is None
                or document is None
                or run.organisation_id != selection.organisation_id
                or document.organisation_id != selection.organisation_id
                or document.sha256 != selection.document_sha256
                or document.document_type != "evidence"
            ):
                raise ValueError("analysis_evidence_documents foreign key violation")
            if any(
                (s.analysis_run_id, s.document_id)
                == (selection.analysis_run_id, selection.document_id)
                for s in self.selections
            ):
                raise DuplicateError("duplicate (analysis_run_id, document_id)")
        for selection in selections:
            self.selections.append(selection.model_copy(update={"created_at": _now()}))

    def list_evidence_selections(self, run_id: str) -> list[EvidenceSelection]:
        return [s for s in self.selections if s.analysis_run_id == run_id]

    def save_evidence_matches(
        self, run: AnalysisRun, assessments: Sequence[RequirementAssessment], model: str
    ) -> None:
        match_rows, src_rows, action_rows = evidence_match_rows(run, assessments, model)
        selected = {
            (s.organisation_id, s.document_id, s.document_sha256)
            for s in self.selections
            if s.analysis_run_id == run.id
        }
        for row in match_rows:
            requirement = self.requirement_rows.get(row["requirement_id"])
            if (
                requirement is None
                or requirement["analysis_run_id"] != run.id
                or requirement["organisation_id"] != row["organisation_id"]
            ):
                raise ValueError("evidence_matches foreign key violation")
        for row in src_rows:
            segment = self.segments.get(row["segment_id"])
            if (
                segment is None
                or (segment.organisation_id, segment.document_id, segment.page_number)
                != (row["organisation_id"], row["document_id"], row["page_number"])
                or (row["organisation_id"], row["document_id"], segment.document_sha256)
                not in selected
            ):
                raise ValueError("evidence_match_sources foreign key violation")
        for row in match_rows:
            self.match_rows[row["id"]] = row
        for row in src_rows:
            self.match_source_rows[row["id"]] = row
        for row in action_rows:
            self.action_rows[row["id"]] = row
        keep_matches = {row["id"] for row in match_rows}
        keep_sources = {row["id"] for row in src_rows}
        keep_actions = {row["id"] for row in action_rows}
        for table, keep in (
            (self.match_rows, keep_matches),
            (self.match_source_rows, keep_sources),
            (self.action_rows, keep_actions),
        ):
            for key in [k for k, r in table.items() if r["analysis_run_id"] == run.id]:
                if key not in keep:
                    del table[key]

    def list_evidence_matches(self, run_id: str) -> list[EvidenceMatch]:
        result = []
        for row in self.match_rows.values():
            if row["analysis_run_id"] != run_id:
                continue
            sources = sorted(
                (s for s in self.match_source_rows.values() if s["evidence_match_id"] == row["id"]),
                key=lambda s: (s["document_id"], s["page_number"]),
            )
            result.append(EvidenceMatch.model_validate({**row, "sources": sources}))
        return result

    def get_evidence_match(self, match_id: str) -> EvidenceMatch | None:
        row = self.match_rows.get(match_id)
        return EvidenceMatch.model_validate(row) if row else None

    def get_evidence_match_source(self, source_id: str) -> EvidenceMatchSource | None:
        row = self.match_source_rows.get(source_id)
        return EvidenceMatchSource.model_validate(row) if row else None

    def list_action_items(self, run_id: str) -> list[ActionItem]:
        return [
            ActionItem.model_validate(row)
            for row in self.action_rows.values()
            if row["analysis_run_id"] == run_id
        ]

    # Review decisions (append-only, like the database trigger) ----------------------------
    def insert_review_decision(self, decision: ReviewDecision) -> ReviewDecision:
        requirement = self.requirement_rows.get(decision.requirement_id)
        if (
            requirement is None
            or requirement["analysis_run_id"] != decision.analysis_run_id
            or requirement["organisation_id"] != decision.organisation_id
        ):
            raise ValueError("review_decisions foreign key violation")
        if decision.decision == "not_applicable" and not (decision.notes or "").strip():
            raise ValueError("review_decisions_notes_required check violation")
        stored = decision.model_copy(update={"created_at": _now()})
        self.decisions.append(stored)
        return stored

    def list_review_decisions(self, run_id: str) -> list[ReviewDecision]:
        return [d for d in self.decisions if d.analysis_run_id == run_id]


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.signed: list[str] = []
        self.fail_downloads = 0

    def upload_pdf(self, path: str, data: bytes) -> None:
        if path in self.objects:
            raise StorageError("Upload failed: object exists")
        self.objects[path] = data

    def download(self, path: str) -> bytes:
        if self.fail_downloads > 0:
            self.fail_downloads -= 1
            raise StorageError("Download failed: simulated outage")
        if path not in self.objects:
            raise StorageError("Download failed: not found")
        return self.objects[path]

    def signed_url(self, path: str, ttl_seconds: int) -> str:
        if path not in self.objects:
            raise StorageError("Signing failed: not found")
        self.signed.append(path)
        return (
            f"https://storage.test/object/sign/documents/{path}?token=dev-fixture&ttl={ttl_seconds}"
        )

    def remove(self, path: str) -> None:
        self.objects.pop(path, None)


class FakeQueue:
    """Records enqueue_call arguments instead of talking to Redis."""

    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[dict[str, Any]] = []
        self.fail = fail

    def enqueue_call(self, func: Callable[..., Any], **kwargs: Any) -> Any:
        if self.fail:
            raise RedisConnectionError("simulated Redis outage")
        self.calls.append({"func": func, **kwargs})
        return SimpleNamespace(id=kwargs.get("job_id"))


# Scripted model ---------------------------------------------------------------------------
_PASSAGE = re.compile(
    r'<segment id="(?P<id>[^"]+)" role="(?P<role>primary|context)">\n(?P<text>.*?)\n</segment>',
    re.DOTALL,
)
NO_TEXT_MARKER = "[no extractable text]"

Response = str | Exception


class ScriptedProvider:
    """Fake LLM: answers each group prompt with `respond(user_prompt)`.

    `respond` returns raw model text, or an exception to raise (for example LLMError).
    """

    model = "dev-fixture-model"

    def __init__(self, respond: Callable[[str], Response]) -> None:
        self._respond = respond
        self.calls: list[list[Message]] = []

    def complete_json(
        self, messages: Sequence[Message], *, schema_name: str, json_schema: dict[str, Any]
    ) -> str:
        self.calls.append(list(messages))
        result = self._respond(messages[1]["content"])
        if isinstance(result, Exception):
            raise result
        return result


def primary_passages(prompt: str) -> list[tuple[str, str]]:
    """(segment id, text as shown to the model) for each primary passage in a group prompt."""
    return [(m["id"], m["text"]) for m in _PASSAGE.finditer(prompt) if m["role"] == "primary"]


def requirement(
    segment_id: str,
    quote: str,
    *,
    text: str | None = None,
    category: str = "returnable",
    stage: str = "submission",
    extra_sources: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    return {
        "title": "dev-fixture requirement",
        "requirement_text": text or quote,
        "category": category,
        "evidence_needed": None,
        "stage": stage,
        "consequence": None,
        "ambiguity_notes": None,
        # "page" is a model-invented field: it must be ignored in favour of segment metadata.
        "sources": [{"segment_id": segment_id, "quote": quote, "page": 999}, *extra_sources],
    }


def _clip(text: str, limit: int = 300) -> str:
    if len(text) <= limit:
        return text
    # Cut at a space so an escaped entity such as & is never split.
    return text[:limit].rsplit(" ", 1)[0]


def quote_each_primary_passage(prompt: str) -> str:
    """One requirement per readable primary page, quoting the text exactly as shown."""
    items = [
        requirement(segment_id, _clip(text))
        for segment_id, text in primary_passages(prompt)
        if text != NO_TEXT_MARKER
    ]
    return json.dumps({"requirements": items})
