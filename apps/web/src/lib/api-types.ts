// Response shapes of the ReadyBid API.
// Mirrors services/api/src/readybid_api/schemas.py. Keep the two in sync.

export type RunStatus = "queued" | "running" | "completed" | "partial" | "failed";

export const RUN_STATUS_LABELS: Record<RunStatus, string> = {
  queued: "Queued",
  running: "Running",
  completed: "Completed",
  partial: "Partial results",
  failed: "Failed",
};

export function isActiveStatus(status: RunStatus): boolean {
  return status === "queued" || status === "running";
}

export type MatchingStatus = "not_requested" | "pending" | "completed" | "partial" | "failed";

export const MATCHING_STATUS_LABELS: Record<MatchingStatus, string> = {
  not_requested: "No evidence selected",
  pending: "Matching evidence",
  completed: "Evidence matched",
  partial: "Evidence partly matched",
  failed: "Evidence matching failed",
};

/** The uploader's own description of an evidence file. A label, never a verified fact. */
export const EVIDENCE_LABELS = [
  "reference_letter",
  "company_profile",
  "staff_certificate",
  "declaration",
  "tax_status",
  "other",
] as const;

export type EvidenceLabel = (typeof EVIDENCE_LABELS)[number];

export const EVIDENCE_LABEL_NAMES: Record<EvidenceLabel, string> = {
  reference_letter: "Reference letter",
  company_profile: "Company profile",
  staff_certificate: "Staff certificate",
  declaration: "Declaration",
  tax_status: "Tax status document",
  other: "Other",
};

export function evidenceLabelName(label: string | null): string {
  if (label === null) return "Unlabelled";
  return (EVIDENCE_LABEL_NAMES as Record<string, string>)[label] ?? label;
}

export type TextStatus = "readable" | "partly_readable" | "unreadable" | "not_extracted";

export const TEXT_STATUS_LABELS: Record<TextStatus, string> = {
  readable: "Text readable",
  partly_readable: "Some pages unreadable",
  unreadable: "No readable text",
  not_extracted: "Text not extracted yet",
};

/** AI statuses, the derived "human_reviewed", and "not_assessed" when no assessment exists. */
export type ChecklistStatus =
  | "evidence_found_review_required"
  | "missing_evidence"
  | "ambiguous_requirement"
  | "potential_blocker_review_required"
  | "extraction_incomplete"
  | "human_reviewed"
  | "not_assessed";

export const CHECKLIST_STATUS_LABELS: Record<ChecklistStatus, string> = {
  evidence_found_review_required: "Candidate evidence found, review required",
  missing_evidence: "No evidence found in the selected documents",
  ambiguous_requirement: "Requirement is ambiguous",
  potential_blocker_review_required: "Potential blocker, review required",
  extraction_incomplete: "Evidence text incomplete",
  human_reviewed: "Reviewed by a person",
  not_assessed: "Not assessed",
};

export function checklistStatusLabel(status: string): string {
  return (CHECKLIST_STATUS_LABELS as Record<string, string>)[status] ?? status;
}

export const DECISIONS = [
  "unresolved",
  "satisfied_for_submission_review",
  "not_satisfied",
  "not_applicable",
] as const;

export type Decision = (typeof DECISIONS)[number];

export const DECISION_LABELS: Record<Decision, string> = {
  unresolved: "Unresolved",
  satisfied_for_submission_review: "Satisfied, for submission review",
  not_satisfied: "Not satisfied",
  not_applicable: "Not applicable",
};

export function decisionLabel(decision: string): string {
  return (DECISION_LABELS as Record<string, string>)[decision] ?? decision;
}

export type OrganisationOut = {
  id: string;
  name: string;
  role: string;
};

export type TenderOut = {
  id: string;
  organisation_id: string;
  title: string;
  reference: string | null;
  created_at: string | null;
};

export type DocumentOut = {
  id: string;
  /** null for organisation-level evidence documents. */
  tender_id: string | null;
  document_type: string;
  evidence_label: string | null;
  original_filename: string;
  sha256: string;
  size_bytes: number;
  page_count: number;
  version: number;
  created_at: string | null;
};

export type FileUrlOut = {
  document_id: string;
  original_filename: string;
  version: number;
  signed_url: string;
  expires_in_seconds: number;
};

export type JobOut = {
  id: string;
  analysis_run_id: string;
  status: RunStatus;
  stage: string;
  progress: number;
  attempts: number;
  error: string | null;
  updated_at: string | null;
};

export type AnalysisRunOut = {
  id: string;
  tender_id: string;
  document_id: string;
  document_sha256: string;
  status: RunStatus;
  model: string;
  pages_total: number | null;
  flagged_pages: number[];
  truncated_pages: number[];
  rejected_citations: number;
  dropped_requirements: number;
  groups_total: number;
  groups_completed: number;
  groups_failed: number;
  coverage_complete: boolean | null;
  error: string | null;
  matching_status: MatchingStatus;
  matching_requirements_total: number;
  matching_requirements_failed: number;
  matching_rejected_citations: number;
  matching_truncated_segments: string[];
  matching_error: string | null;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
};

export type AnalysisOut = {
  analysis: AnalysisRunOut;
  job: JobOut | null;
};

export type TenderDetailOut = {
  tender: TenderOut;
  documents: DocumentOut[];
  latest_analysis: AnalysisRunOut | null;
  latest_job: JobOut | null;
};

export type PageWarningOut = {
  page_number: number;
  status: string;
  note: string | null;
};

export type CoverageOut = {
  /** null while the analysis is still running. */
  complete: boolean | null;
  pages_total: number | null;
  flagged_pages: PageWarningOut[];
  truncated_pages: number[];
  groups_total: number;
  groups_completed: number;
  groups_failed: number;
  rejected_citations: number;
  dropped_requirements: number;
};

export type SourceOut = {
  id: string;
  segment_id: string;
  page_number: number;
  quote: string;
};

export type RequirementOut = {
  id: string;
  position: number;
  title: string;
  requirement_text: string;
  category: string;
  evidence_needed: string | null;
  stage: string;
  consequence: string | null;
  ambiguity_notes: string | null;
  sources: SourceOut[];
};

export type RequirementsOut = {
  analysis: AnalysisRunOut;
  document: DocumentOut;
  coverage: CoverageOut;
  requirements: RequirementOut[];
  notice: string;
};

export type SourceViewOut = {
  id: string;
  requirement_id: string;
  document_id: string;
  document_filename: string;
  document_version: number;
  page_number: number;
  quote: string;
  extraction_status: string;
  extraction_note: string | null;
  signed_url: string;
  expires_in_seconds: number;
};

// Evidence library -----------------------------------------------------------------------

export type EvidenceDocumentOut = DocumentOut & {
  pages_with_text: number;
  flagged_pages: PageWarningOut[];
  text_status: TextStatus;
};

export type EvidenceListOut = {
  documents: EvidenceDocumentOut[];
  max_per_analysis: number;
  notice: string;
};

// Checklist and review -------------------------------------------------------------------

export type EvidenceSourceOut = {
  id: string;
  document_id: string;
  document_filename: string;
  evidence_label: string | null;
  page_number: number;
  quote: string;
  relationship: string | null;
  extraction_status: string;
  /** Only passages from cleanly extracted pages count as candidate support. */
  counts_as_candidate: boolean;
};

export type AssessmentOut = {
  ai_status: string;
  explanation: string;
  uncertainty_notes: string | null;
  count_summary: string;
  required_count: number | null;
  candidate_document_count: number;
  model: string;
  sources: EvidenceSourceOut[];
};

export type DecisionOut = {
  id: string;
  analysis_run_id: string;
  requirement_id: string;
  decision: string;
  notes: string | null;
  reviewer_id: string;
  created_at: string | null;
};

export type DecisionIn = {
  requirement_id: string;
  decision: Decision;
  notes: string | null;
};

export type ChecklistItemOut = {
  requirement: RequirementOut;
  assessment: AssessmentOut | null;
  /** The AI status, "human_reviewed" when a reviewer decided, or "not_assessed". */
  current_status: string;
  next_action: string | null;
  decision: DecisionOut | null;
  decision_history: DecisionOut[];
  /** A decision recorded on an earlier analysis of this tender. A hint only. */
  earlier_decision: DecisionOut | null;
};

export type SelectedEvidenceOut = {
  document_id: string;
  original_filename: string;
  evidence_label: string | null;
  version: number;
  page_count: number;
  selected_sha256: string;
  matches_selected_version: boolean;
  pages_with_text: number;
  flagged_pages: PageWarningOut[];
  text_status: TextStatus;
};

/** Counts that point reviewers at work still to do. Never a readiness score. */
export type ReviewIndicatorsOut = {
  requirements_total: number;
  unresolved: number;
  potential_blockers: number;
  missing_evidence: number;
  not_assessed: number;
  extraction_warnings: number;
};

export type ChecklistOut = {
  tender: TenderOut;
  analysis: AnalysisRunOut;
  document: DocumentOut;
  coverage: CoverageOut;
  evidence: SelectedEvidenceOut[];
  items: ChecklistItemOut[];
  indicators: ReviewIndicatorsOut;
  notice: string;
};

export type EvidenceSourceViewOut = {
  id: string;
  evidence_match_id: string;
  requirement_id: string;
  document_id: string;
  document_filename: string;
  document_version: number;
  evidence_label: string | null;
  page_number: number;
  quote: string;
  relationship: string | null;
  extraction_status: string;
  extraction_note: string | null;
  signed_url: string;
  expires_in_seconds: number;
};
