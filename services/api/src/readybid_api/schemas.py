"""Request and response bodies for the HTTP API.

Response models list their fields explicitly, so internal values such as storage paths
never reach the browser even though the underlying rows contain them.
"""

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from readybid_core.models import Decision

PREPARATION_NOTICE = (
    "ReadyBid helps you prepare a tender response. These requirements were extracted from "
    "the tender document for your review. They are not legal advice, an eligibility "
    "guarantee or an award prediction. Check each one against the source page."
)

EVIDENCE_NOTICE = (
    "Labels are your own description of each file. ReadyBid only reads the text. It does "
    "not check that a document is genuine, current, signed, authorised or sufficient."
)

CHECKLIST_NOTICE = (
    "This checklist helps you prepare a tender response. Candidate evidence was proposed by "
    "an AI model for your review and is not proof that a requirement is met. It is not "
    "legal advice, an eligibility guarantee or an award prediction. Check every item "
    "against the tender and your own documents before you submit."
)

# readable: every page has clean text. unreadable: no page does. not_extracted: no text yet.
TextStatus = Literal["readable", "partly_readable", "unreadable", "not_extracted"]


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# Organisations and tenders ------------------------------------------------------------
class OrganisationOut(Out):
    id: str
    name: str
    role: str


class CreateOrganisationIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)

    @field_validator("name", mode="before")
    @classmethod
    def _clean_name(cls, value: object) -> object:
        return _strip(value)


class TenderOut(Out):
    id: str
    organisation_id: str
    title: str
    reference: str | None
    created_at: datetime | None


class CreateTenderIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    reference: str | None = Field(default=None, max_length=200)

    @field_validator("title", mode="before")
    @classmethod
    def _clean_title(cls, value: object) -> object:
        return _strip(value)

    @field_validator("reference", mode="before")
    @classmethod
    def _clean_reference(cls, value: object) -> object:
        return _strip(value) or None


# Documents ----------------------------------------------------------------------------
class DocumentOut(Out):
    id: str
    # None for organisation-level evidence documents.
    tender_id: str | None
    document_type: str
    evidence_label: str | None = None
    original_filename: str
    sha256: str
    size_bytes: int
    page_count: int
    version: int
    created_at: datetime | None


class FileUrlOut(BaseModel):
    document_id: str
    original_filename: str
    version: int
    signed_url: str
    expires_in_seconds: int


# Analysis -----------------------------------------------------------------------------
class JobOut(Out):
    id: str
    analysis_run_id: str
    status: str
    stage: str
    progress: int
    attempts: int
    error: str | None
    updated_at: datetime | None


class AnalysisRunOut(Out):
    id: str
    tender_id: str
    document_id: str
    document_sha256: str
    status: str
    model: str
    pages_total: int | None
    flagged_pages: list[int]
    truncated_pages: list[int]
    rejected_citations: int
    dropped_requirements: int
    groups_total: int
    groups_completed: int
    groups_failed: int
    coverage_complete: bool | None
    error: str | None
    matching_status: str
    matching_requirements_total: int
    matching_requirements_failed: int
    matching_rejected_citations: int
    matching_truncated_segments: list[str]
    matching_error: str | None
    created_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None


class StartAnalysisIn(BaseModel):
    document_id: UUID
    # Explicit choice only: evidence is never taken from the library automatically.
    evidence_document_ids: list[UUID] = Field(default_factory=list, max_length=50)


class AnalysisOut(BaseModel):
    analysis: AnalysisRunOut
    job: JobOut | None


class TenderDetailOut(BaseModel):
    tender: TenderOut
    documents: list[DocumentOut]
    latest_analysis: AnalysisRunOut | None
    latest_job: JobOut | None


# Requirements and sources -------------------------------------------------------------
class PageWarningOut(BaseModel):
    page_number: int
    status: str
    note: str | None


class CoverageOut(BaseModel):
    # None while the analysis is still running.
    complete: bool | None
    pages_total: int | None
    flagged_pages: list[PageWarningOut]
    truncated_pages: list[int]
    groups_total: int
    groups_completed: int
    groups_failed: int
    rejected_citations: int
    dropped_requirements: int


class SourceOut(Out):
    id: str
    segment_id: str
    page_number: int
    quote: str


class RequirementOut(Out):
    id: str
    position: int
    title: str
    requirement_text: str
    category: str
    evidence_needed: str | None
    stage: str
    consequence: str | None
    ambiguity_notes: str | None
    sources: list[SourceOut]


class RequirementsOut(BaseModel):
    analysis: AnalysisRunOut
    document: DocumentOut
    coverage: CoverageOut
    requirements: list[RequirementOut]
    notice: str = PREPARATION_NOTICE


class SourceViewOut(BaseModel):
    id: str
    requirement_id: str
    document_id: str
    document_filename: str
    document_version: int
    page_number: int
    quote: str
    extraction_status: str
    extraction_note: str | None
    signed_url: str
    expires_in_seconds: int


# Evidence library ---------------------------------------------------------------------
class EvidenceDocumentOut(DocumentOut):
    pages_with_text: int
    flagged_pages: list[PageWarningOut]
    text_status: TextStatus


class EvidenceListOut(BaseModel):
    documents: list[EvidenceDocumentOut]
    max_per_analysis: int
    notice: str = EVIDENCE_NOTICE


# Checklist and review -----------------------------------------------------------------
class EvidenceSourceOut(BaseModel):
    id: str
    document_id: str
    document_filename: str
    evidence_label: str | None
    page_number: int
    quote: str
    relationship: str | None
    extraction_status: str
    # Only passages from cleanly extracted pages count as candidate support.
    counts_as_candidate: bool


class AssessmentOut(BaseModel):
    ai_status: str
    explanation: str
    uncertainty_notes: str | None
    count_summary: str
    required_count: int | None
    candidate_document_count: int
    model: str
    sources: list[EvidenceSourceOut]


class DecisionOut(Out):
    id: str
    analysis_run_id: str
    requirement_id: str
    decision: str
    notes: str | None
    reviewer_id: str
    created_at: datetime | None


class DecisionIn(BaseModel):
    requirement_id: UUID
    decision: Decision
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("notes", mode="before")
    @classmethod
    def _clean_notes(cls, value: object) -> object:
        return _strip(value) or None

    @model_validator(mode="after")
    def _notes_for_not_applicable(self) -> Self:
        if self.decision == "not_applicable" and not self.notes:
            raise ValueError("Add a note explaining why this requirement does not apply.")
        return self


class ChecklistItemOut(BaseModel):
    requirement: RequirementOut
    assessment: AssessmentOut | None
    # The AI status, "human_reviewed" when a reviewer decided, or "not_assessed".
    current_status: str
    next_action: str | None
    decision: DecisionOut | None
    decision_history: list[DecisionOut]
    # A decision recorded on an earlier analysis of this tender. Shown as a hint only.
    earlier_decision: DecisionOut | None


class SelectedEvidenceOut(BaseModel):
    document_id: str
    original_filename: str
    evidence_label: str | None
    version: int
    page_count: int
    selected_sha256: str
    matches_selected_version: bool
    pages_with_text: int
    flagged_pages: list[PageWarningOut]
    text_status: TextStatus


class ReviewIndicatorsOut(BaseModel):
    """Counts that point reviewers at work still to do. Never a readiness score."""

    requirements_total: int
    unresolved: int
    potential_blockers: int
    missing_evidence: int
    not_assessed: int
    extraction_warnings: int


class ChecklistOut(BaseModel):
    tender: TenderOut
    analysis: AnalysisRunOut
    document: DocumentOut
    coverage: CoverageOut
    evidence: list[SelectedEvidenceOut]
    items: list[ChecklistItemOut]
    indicators: ReviewIndicatorsOut
    notice: str = CHECKLIST_NOTICE


class ChecklistExportOut(BaseModel):
    exported_at: datetime
    checklist: ChecklistOut


class EvidenceSourceViewOut(BaseModel):
    id: str
    evidence_match_id: str
    requirement_id: str
    document_id: str
    document_filename: str
    document_version: int
    evidence_label: str | None
    page_number: int
    quote: str
    relationship: str | None
    extraction_status: str
    extraction_note: str | None
    signed_url: str
    expires_in_seconds: int
