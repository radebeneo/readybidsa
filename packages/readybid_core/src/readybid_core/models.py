"""Typed rows for the tables in supabase/migrations. Shared by the API and the worker."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RunStatus = Literal["queued", "running", "completed", "partial", "failed"]
TERMINAL_STATUSES: frozenset[str] = frozenset({"completed", "partial", "failed"})
ACTIVE_STATUSES: frozenset[str] = frozenset({"queued", "running"})

MatchingStatus = Literal["not_requested", "pending", "completed", "partial", "failed"]

# The uploader's own label for an evidence document. A label, never a verified fact.
EvidenceLabel = Literal[
    "reference_letter",
    "company_profile",
    "staff_certificate",
    "declaration",
    "tax_status",
    "other",
]
EVIDENCE_LABELS: tuple[str, ...] = (
    "reference_letter",
    "company_profile",
    "staff_certificate",
    "declaration",
    "tax_status",
    "other",
)

# AI assessment of one requirement against the selected evidence. "human_reviewed" is not
# stored here: the API shows it when a human decision exists, keeping the AI status intact.
AiStatus = Literal[
    "evidence_found_review_required",
    "missing_evidence",
    "ambiguous_requirement",
    "potential_blocker_review_required",
    "extraction_incomplete",
]

# Human review decisions, stored separately from AI assessments.
Decision = Literal[
    "unresolved",
    "satisfied_for_submission_review",
    "not_satisfied",
    "not_applicable",
]


class Row(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Organisation(Row):
    id: str
    name: str


class OrganisationMembership(Row):
    organisation_id: str
    name: str
    role: str


class Tender(Row):
    id: str
    organisation_id: str
    title: str
    reference: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None


class Document(Row):
    id: str
    organisation_id: str
    # Set for tender documents; None for organisation-level evidence documents.
    tender_id: str | None = None
    document_type: Literal["tender", "evidence"] = "tender"
    evidence_label: str | None = None
    original_filename: str
    storage_path: str
    sha256: str
    size_bytes: int
    page_count: int
    version: int
    created_by: str | None = None
    created_at: datetime | None = None


class SourceSegment(Row):
    id: str
    organisation_id: str
    document_id: str
    document_sha256: str
    page_number: int
    text: str
    char_count: int
    extraction_status: str
    extraction_note: str | None = None


class SegmentStatus(Row):
    """A segment's extraction status without its text, for listings."""

    document_id: str
    document_sha256: str
    page_number: int
    extraction_status: str
    extraction_note: str | None = None


class AnalysisRun(Row):
    id: str
    organisation_id: str
    tender_id: str
    document_id: str
    document_sha256: str
    status: RunStatus = "queued"
    model: str
    pages_total: int | None = None
    flagged_pages: list[int] = Field(default_factory=list)
    truncated_pages: list[int] = Field(default_factory=list)
    rejected_citations: int = 0
    dropped_requirements: int = 0
    groups_total: int = 0
    groups_completed: int = 0
    groups_failed: int = 0
    coverage_complete: bool | None = None
    error: str | None = None
    # Evidence matching, tracked separately from requirement extraction.
    matching_status: MatchingStatus = "not_requested"
    matching_requirements_total: int = 0
    matching_requirements_failed: int = 0
    matching_rejected_citations: int = 0
    matching_truncated_segments: list[str] = Field(default_factory=list)
    matching_error: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ProcessingJob(Row):
    id: str
    organisation_id: str
    analysis_run_id: str
    kind: str = "analyse_document"
    status: RunStatus = "queued"
    stage: str = "queued"
    progress: int = 0
    attempts: int = 0
    rq_job_id: str | None = None
    error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RequirementSource(Row):
    id: str
    organisation_id: str
    requirement_id: str
    document_id: str
    segment_id: str
    page_number: int
    quote: str
    quote_sha256: str


class Requirement(Row):
    id: str
    organisation_id: str
    analysis_run_id: str
    document_id: str
    dedupe_key: str
    position: int
    title: str
    requirement_text: str
    category: str
    evidence_needed: str | None = None
    stage: str
    consequence: str | None = None
    ambiguity_notes: str | None = None
    sources: list[RequirementSource] = Field(default_factory=list)


# Evidence and review ----------------------------------------------------------------------
class EvidenceSelection(Row):
    """One evidence document explicitly selected for one analysis run, pinned to its hash."""

    analysis_run_id: str
    organisation_id: str
    document_id: str
    document_sha256: str
    created_at: datetime | None = None


class EvidenceMatchSource(Row):
    id: str
    organisation_id: str
    evidence_match_id: str
    analysis_run_id: str
    document_id: str
    segment_id: str
    page_number: int
    quote: str
    quote_sha256: str
    relationship: str | None = None
    # Copied from the segment. Only "ok" passages count as candidate support.
    extraction_status: str


class EvidenceMatch(Row):
    id: str
    organisation_id: str
    analysis_run_id: str
    requirement_id: str
    ai_status: AiStatus
    explanation: str
    uncertainty_notes: str | None = None
    count_summary: str
    required_count: int | None = None
    candidate_document_count: int = 0
    model: str
    created_at: datetime | None = None
    sources: list[EvidenceMatchSource] = Field(default_factory=list)


class ActionItem(Row):
    id: str
    organisation_id: str
    analysis_run_id: str
    requirement_id: str
    evidence_match_id: str
    origin: str = "matching"
    description: str
    status: str = "open"
    created_at: datetime | None = None


class ReviewDecision(Row):
    id: str
    organisation_id: str
    analysis_run_id: str
    requirement_id: str
    decision: Decision
    notes: str | None = None
    reviewer_id: str
    created_at: datetime | None = None
