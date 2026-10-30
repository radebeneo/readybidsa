"""Review checklist, decisions and export for one analysis run.

* Built from stored rows only. Nothing here calls a model.
* AI assessments and human decisions stay separate. A decision never changes the stored AI
  status. The checklist shows "human_reviewed" only while the latest decision for a
  requirement is something other than "unresolved".
* Decisions belong to one run. A newer run starts unresolved and shows a decision from an
  earlier run of the same tender only as a hint, matched on the requirement's dedupe key.
* Every row is filtered to the run's organisation again, after authorisation.
"""

import csv
import io
from collections.abc import Iterable
from datetime import datetime

from readybid_api.schemas import (
    AnalysisRunOut,
    AssessmentOut,
    ChecklistItemOut,
    ChecklistOut,
    CoverageOut,
    DecisionOut,
    DocumentOut,
    EvidenceDocumentOut,
    EvidenceSourceOut,
    PageWarningOut,
    RequirementOut,
    ReviewIndicatorsOut,
    SelectedEvidenceOut,
    TenderOut,
    TextStatus,
)
from readybid_core.authz import NotFound
from readybid_core.models import (
    AnalysisRun,
    Document,
    EvidenceMatch,
    Requirement,
    ReviewDecision,
    SegmentStatus,
)
from readybid_core.repository import Repository

# Earlier runs of the same tender checked for decision hints, and the history window.
EARLIER_RUNS_CHECKED = 5
RUN_HISTORY_LIMIT = 25

AI_STATUS_LABELS = {
    "evidence_found_review_required": "Candidate evidence found (review required)",
    "missing_evidence": "No candidate evidence found",
    "ambiguous_requirement": "Requirement is ambiguous",
    "potential_blocker_review_required": "Potential blocker (review required)",
    "extraction_incomplete": "Evidence text incomplete",
    "human_reviewed": "Human reviewed",
    "not_assessed": "Not assessed",
}
DECISION_LABELS = {
    "unresolved": "Unresolved",
    "satisfied_for_submission_review": "Satisfied for submission review",
    "not_satisfied": "Not satisfied",
    "not_applicable": "Not applicable",
}


# Requirements and coverage --------------------------------------------------------------
def visible_requirements(repo: Repository, run: AnalysisRun) -> list[Requirement]:
    """Requirements of the run that keep at least one source in the analysed document."""
    result: list[Requirement] = []
    for requirement in repo.list_requirements(run.id):
        if requirement.organisation_id != run.organisation_id:
            continue
        sources = [
            s
            for s in requirement.sources
            if s.organisation_id == run.organisation_id and s.document_id == run.document_id
        ]
        if sources:  # never show a requirement without a source
            result.append(requirement.model_copy(update={"sources": sources}))
    return result


def find_requirement(repo: Repository, run: AnalysisRun, requirement_id: str) -> Requirement:
    for requirement in visible_requirements(repo, run):
        if requirement.id == requirement_id:
            return requirement
    raise NotFound("requirement")


def tender_page_warnings(
    repo: Repository, run: AnalysisRun, document: Document
) -> list[PageWarningOut]:
    return [
        PageWarningOut(
            page_number=s.page_number, status=s.extraction_status, note=s.extraction_note
        )
        for s in repo.list_segments(document.id)
        if s.organisation_id == run.organisation_id
        and s.document_sha256 == run.document_sha256
        and s.extraction_status != "ok"
    ]


def coverage_out(run: AnalysisRun, warnings: list[PageWarningOut]) -> CoverageOut:
    return CoverageOut(
        complete=run.coverage_complete,
        pages_total=run.pages_total,
        flagged_pages=warnings,
        truncated_pages=run.truncated_pages,
        groups_total=run.groups_total,
        groups_completed=run.groups_completed,
        groups_failed=run.groups_failed,
        rejected_citations=run.rejected_citations,
        dropped_requirements=run.dropped_requirements,
    )


# Evidence documents ---------------------------------------------------------------------
def summarise_text(
    page_count: int, statuses: Iterable[SegmentStatus]
) -> tuple[int, list[PageWarningOut], TextStatus]:
    """(pages with clean text, flagged pages, overall text status) for one document version."""
    by_page = {s.page_number: s for s in statuses}
    readable = sum(1 for s in by_page.values() if s.extraction_status == "ok")
    flagged = [
        PageWarningOut(
            page_number=s.page_number, status=s.extraction_status, note=s.extraction_note
        )
        for s in sorted(by_page.values(), key=lambda s: s.page_number)
        if s.extraction_status != "ok"
    ]
    status: TextStatus
    if not by_page:
        status = "not_extracted"
    elif readable >= page_count:
        status = "readable"
    elif readable == 0:
        status = "unreadable"
    else:
        status = "partly_readable"
    return readable, flagged, status


def evidence_documents_out(
    repo: Repository, documents: list[Document]
) -> list[EvidenceDocumentOut]:
    statuses = repo.list_segment_statuses([d.id for d in documents]) if documents else []
    result: list[EvidenceDocumentOut] = []
    for document in documents:
        readable, flagged, status = summarise_text(
            document.page_count,
            (
                s
                for s in statuses
                if s.document_id == document.id and s.document_sha256 == document.sha256
            ),
        )
        result.append(
            EvidenceDocumentOut(
                **DocumentOut.model_validate(document).model_dump(),
                pages_with_text=readable,
                flagged_pages=flagged,
                text_status=status,
            )
        )
    return result


def selected_evidence(
    repo: Repository, run: AnalysisRun
) -> tuple[list[SelectedEvidenceOut], dict[str, Document]]:
    """Evidence documents explicitly selected for the run, at their selected versions."""
    selections = [
        s for s in repo.list_evidence_selections(run.id) if s.organisation_id == run.organisation_id
    ]
    documents: dict[str, Document] = {}
    for selection in selections:
        document = repo.get_document(selection.document_id)
        if (
            document is not None
            and document.organisation_id == run.organisation_id
            and document.document_type == "evidence"
        ):
            documents[document.id] = document
    statuses = repo.list_segment_statuses(list(documents)) if documents else []
    result: list[SelectedEvidenceOut] = []
    for selection in selections:
        document = documents.get(selection.document_id)
        if document is None:
            continue
        readable, flagged, status = summarise_text(
            document.page_count,
            (
                s
                for s in statuses
                if s.document_id == document.id and s.document_sha256 == selection.document_sha256
            ),
        )
        result.append(
            SelectedEvidenceOut(
                document_id=document.id,
                original_filename=document.original_filename,
                evidence_label=document.evidence_label,
                version=document.version,
                page_count=document.page_count,
                selected_sha256=selection.document_sha256,
                matches_selected_version=document.sha256 == selection.document_sha256,
                pages_with_text=readable,
                flagged_pages=flagged,
                text_status=status,
            )
        )
    result.sort(key=lambda e: (e.original_filename.casefold(), e.document_id))
    return result, documents


def assessment_out(match: EvidenceMatch, documents: dict[str, Document]) -> AssessmentOut:
    sources: list[EvidenceSourceOut] = []
    for source in match.sources:
        document = documents.get(source.document_id)
        # Only passages from documents selected for this run, in the same organisation.
        if document is None or source.organisation_id != match.organisation_id:
            continue
        sources.append(
            EvidenceSourceOut(
                id=source.id,
                document_id=document.id,
                document_filename=document.original_filename,
                evidence_label=document.evidence_label,
                page_number=source.page_number,
                quote=source.quote,
                relationship=source.relationship,
                extraction_status=source.extraction_status,
                counts_as_candidate=source.extraction_status == "ok",
            )
        )
    return AssessmentOut(
        ai_status=match.ai_status,
        explanation=match.explanation,
        uncertainty_notes=match.uncertainty_notes,
        count_summary=match.count_summary,
        required_count=match.required_count,
        candidate_document_count=match.candidate_document_count,
        model=match.model,
        sources=sources,
    )


# Decisions ------------------------------------------------------------------------------
def earlier_decisions(repo: Repository, run: AnalysisRun) -> dict[str, ReviewDecision]:
    """Latest decided (not "unresolved") decision per dedupe key from earlier runs."""
    history = [
        r
        for r in repo.list_analysis_runs(run.tender_id, RUN_HISTORY_LIMIT)
        if r.organisation_id == run.organisation_id
    ]
    ids = [r.id for r in history]
    if run.id not in ids:
        return {}
    hints: dict[str, ReviewDecision] = {}
    for previous in history[ids.index(run.id) + 1 :][:EARLIER_RUNS_CHECKED]:
        keys = {
            r.id: r.dedupe_key
            for r in repo.list_requirements(previous.id)
            if r.organisation_id == run.organisation_id
        }
        latest: dict[str, ReviewDecision] = {}
        for decision in repo.list_review_decisions(previous.id):
            if decision.organisation_id == run.organisation_id and decision.requirement_id in keys:
                latest[decision.requirement_id] = decision
        for requirement_id, decision in latest.items():
            if decision.decision != "unresolved":
                hints.setdefault(keys[requirement_id], decision)
    return hints


def unassessed_action(run: AnalysisRun) -> str:
    if run.matching_status == "not_requested":
        return (
            "No evidence was selected for this analysis. Check this requirement yourself, or "
            "select evidence documents and run a new analysis."
        )
    if run.matching_status == "pending":
        return "Evidence matching has not finished yet."
    return (
        "This requirement could not be assessed against the selected evidence. Check it "
        "yourself or run a new analysis."
    )


def current_status(match: EvidenceMatch | None, latest: ReviewDecision | None) -> str:
    if latest is not None and latest.decision != "unresolved":
        return "human_reviewed"
    return match.ai_status if match is not None else "not_assessed"


# Checklist --------------------------------------------------------------------------------
def build_checklist(repo: Repository, run: AnalysisRun) -> ChecklistOut:
    tender = repo.get_tender(run.tender_id)
    document = repo.get_document(run.document_id)
    if (
        tender is None
        or document is None
        or tender.organisation_id != run.organisation_id
        or document.organisation_id != run.organisation_id
    ):
        raise NotFound("analysis")

    warnings = tender_page_warnings(repo, run, document)
    evidence, evidence_documents = selected_evidence(repo, run)
    matches = {
        m.requirement_id: m
        for m in repo.list_evidence_matches(run.id)
        if m.organisation_id == run.organisation_id
    }
    actions = {
        a.requirement_id: a.description
        for a in repo.list_action_items(run.id)
        if a.organisation_id == run.organisation_id and a.status == "open"
    }
    history: dict[str, list[ReviewDecision]] = {}
    for decision in repo.list_review_decisions(run.id):
        if decision.organisation_id == run.organisation_id:
            history.setdefault(decision.requirement_id, []).append(decision)
    hints = earlier_decisions(repo, run)

    items: list[ChecklistItemOut] = []
    for requirement in visible_requirements(repo, run):
        match = matches.get(requirement.id)
        decisions = history.get(requirement.id, [])
        latest = decisions[-1] if decisions else None
        hint = hints.get(requirement.dedupe_key)
        items.append(
            ChecklistItemOut(
                requirement=RequirementOut.model_validate(requirement),
                assessment=assessment_out(match, evidence_documents) if match else None,
                current_status=current_status(match, latest),
                next_action=actions.get(requirement.id)
                if match is not None
                else unassessed_action(run),
                decision=DecisionOut.model_validate(latest) if latest else None,
                decision_history=[DecisionOut.model_validate(d) for d in decisions],
                earlier_decision=DecisionOut.model_validate(hint) if hint else None,
            )
        )

    def ai_count(status: str) -> int:
        return sum(1 for i in items if i.assessment and i.assessment.ai_status == status)

    extraction_warnings = (
        len(warnings)
        + len(run.truncated_pages)
        + sum(e.page_count - e.pages_with_text for e in evidence)
        + len(run.matching_truncated_segments)
    )
    indicators = ReviewIndicatorsOut(
        requirements_total=len(items),
        unresolved=sum(
            1 for i in items if i.decision is None or i.decision.decision == "unresolved"
        ),
        potential_blockers=ai_count("potential_blocker_review_required"),
        missing_evidence=ai_count("missing_evidence"),
        not_assessed=sum(1 for i in items if i.assessment is None),
        extraction_warnings=extraction_warnings,
    )
    return ChecklistOut(
        tender=TenderOut.model_validate(tender),
        analysis=AnalysisRunOut.model_validate(run),
        document=DocumentOut.model_validate(document),
        coverage=coverage_out(run, warnings),
        evidence=evidence,
        items=items,
        indicators=indicators,
    )


# CSV export -------------------------------------------------------------------------------
# Leading characters that spreadsheet apps may treat as the start of a formula, including
# full-width forms that some apps normalise.
_FORMULA_TRIGGERS = frozenset("=+-@\t\r\n|\uff1d\uff0b\uff0d\uff20")


def spreadsheet_safe(value: object) -> str:
    """Neutralise text a spreadsheet would run as a formula (CSV injection)."""
    text = "" if value is None else str(value)
    if not text:
        return text
    stripped = text.lstrip(" \t\r\n\u00a0")
    if text[0] in _FORMULA_TRIGGERS or (stripped and stripped[0] in _FORMULA_TRIGGERS):
        return "'" + text
    return text


def _when(value: datetime | None) -> str:
    return value.isoformat() if value else ""


CSV_COLUMNS = (
    "Position",
    "Requirement",
    "Requirement text",
    "Category",
    "Stage",
    "Tender source refs",
    "Tender quote",
    "Current assessment",
    "AI assessment",
    "Count summary",
    "Explanation",
    "Uncertainty",
    "Candidate evidence",
    "Evidence source refs",
    "Proposed next action",
    "Human decision",
    "Decision notes",
    "Reviewer id",
    "Decided at",
    "Earlier decision (hint only)",
)


def checklist_csv(checklist: ChecklistOut, exported_at: datetime) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="\r\n")

    def row(*values: object) -> None:
        writer.writerow([spreadsheet_safe(v) for v in values])

    run = checklist.analysis
    tender = checklist.tender
    document = checklist.document
    indicators = checklist.indicators
    row("ReadyBid SA review checklist")
    row("Notice", checklist.notice)
    row("Tender", tender.title)
    row("Tender reference", tender.reference or "")
    row("Tender id", tender.id)
    row("Analysis id", run.id)
    row("Analysis status", run.status)
    row("Analysis created", _when(run.created_at))
    row("Analysis finished", _when(run.finished_at))
    row("Evidence matching", run.matching_status)
    row("Exported at", exported_at.isoformat())
    row(
        "Tender document",
        f"{document.original_filename} (version {document.version}, "
        f"{document.page_count} pages, sha256 {document.sha256})",
    )
    for evidence in checklist.evidence:
        row(
            "Evidence document",
            f"{evidence.original_filename} (label {evidence.evidence_label or 'other'}, "
            f"version {evidence.version}, {evidence.pages_with_text} of "
            f"{evidence.page_count} pages with readable text, "
            f"sha256 {evidence.selected_sha256})",
        )
    row(
        "Review indicators",
        f"{indicators.unresolved} unresolved of {indicators.requirements_total}; "
        f"{indicators.potential_blockers} potential blockers; "
        f"{indicators.missing_evidence} with no candidate evidence; "
        f"{indicators.not_assessed} not assessed; "
        f"{indicators.extraction_warnings} extraction warnings",
    )
    for page in checklist.coverage.flagged_pages:
        row("Extraction warning", f"Tender page {page.page_number}: {page.note or page.status}")
    for evidence in checklist.evidence:
        for page in evidence.flagged_pages:
            row(
                "Extraction warning",
                f"{evidence.original_filename} page {page.page_number}: {page.note or page.status}",
            )
        if not evidence.matches_selected_version:
            row(
                "Extraction warning",
                f"{evidence.original_filename} no longer matches the selected version.",
            )
    if run.error:
        row("Analysis warning", run.error)
    if run.matching_error:
        row("Matching warning", run.matching_error)
    row()
    row(*CSV_COLUMNS)
    for item in checklist.items:
        requirement = item.requirement
        assessment = item.assessment
        decision = item.decision
        hint = item.earlier_decision
        row(
            requirement.position,
            requirement.title,
            requirement.requirement_text,
            requirement.category,
            requirement.stage,
            "\n".join(f"p.{s.page_number} [{s.id}]" for s in requirement.sources),
            "\n".join(s.quote for s in requirement.sources),
            AI_STATUS_LABELS.get(item.current_status, item.current_status),
            AI_STATUS_LABELS.get(assessment.ai_status, assessment.ai_status)
            if assessment
            else AI_STATUS_LABELS["not_assessed"],
            assessment.count_summary if assessment else "",
            assessment.explanation if assessment else "",
            assessment.uncertainty_notes or "" if assessment else "",
            "\n".join(
                f"{s.document_filename} p.{s.page_number}"
                f"{'' if s.counts_as_candidate else ' (page text incomplete, not counted)'}"
                f": {s.quote}"
                for s in assessment.sources
            )
            if assessment
            else "",
            "\n".join(f"{s.document_id} p.{s.page_number} [{s.id}]" for s in assessment.sources)
            if assessment
            else "",
            item.next_action or "",
            DECISION_LABELS.get(decision.decision, decision.decision)
            if decision
            else DECISION_LABELS["unresolved"],
            decision.notes or "" if decision else "",
            decision.reviewer_id if decision else "",
            _when(decision.created_at) if decision else "",
            f"{DECISION_LABELS.get(hint.decision, hint.decision)} on analysis "
            f"{hint.analysis_run_id}"
            if hint
            else "",
        )
    return buffer.getvalue()
