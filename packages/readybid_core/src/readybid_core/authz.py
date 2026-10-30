"""Server-side authorisation.

The repository uses the service role key and bypasses RLS, so every read and write is
checked here first. Organisation membership is always resolved from the database for the
verified user id, never taken from the client. Resources outside the caller's
organisations raise `NotFound`, the same as resources that do not exist, so the API does
not reveal which ids exist in other organisations.
"""

from dataclasses import dataclass

from readybid_core.models import (
    AnalysisRun,
    Document,
    EvidenceMatch,
    EvidenceMatchSource,
    ProcessingJob,
    RequirementSource,
    SourceSegment,
    Tender,
)
from readybid_core.repository import Repository


class NotFound(Exception):
    pass


@dataclass(frozen=True)
class Principal:
    user_id: str
    organisation_ids: frozenset[str]

    def can_access(self, organisation_id: str) -> bool:
        return organisation_id in self.organisation_ids


def resolve_principal(repo: Repository, user_id: str) -> Principal:
    memberships = repo.list_memberships(user_id)
    return Principal(
        user_id=user_id, organisation_ids=frozenset(m.organisation_id for m in memberships)
    )


def require_organisation(principal: Principal, organisation_id: str) -> str:
    if not principal.can_access(organisation_id):
        raise NotFound("organisation")
    return organisation_id


def authorise_tender(repo: Repository, principal: Principal, tender_id: str) -> Tender:
    tender = repo.get_tender(tender_id)
    if tender is None or not principal.can_access(tender.organisation_id):
        raise NotFound("tender")
    return tender


def authorise_document(repo: Repository, principal: Principal, document_id: str) -> Document:
    document = repo.get_document(document_id)
    if document is None or not principal.can_access(document.organisation_id):
        raise NotFound("document")
    return document


def authorise_evidence_document(
    repo: Repository, principal: Principal, document_id: str
) -> Document:
    document = authorise_document(repo, principal, document_id)
    if document.document_type != "evidence" or document.tender_id is not None:
        raise NotFound("document")
    return document


def authorise_run(repo: Repository, principal: Principal, run_id: str) -> AnalysisRun:
    run = repo.get_analysis_run(run_id)
    if run is None or not principal.can_access(run.organisation_id):
        raise NotFound("analysis")
    return run


def authorise_job(repo: Repository, principal: Principal, job_id: str) -> ProcessingJob:
    job = repo.get_processing_job(job_id)
    if job is None or not principal.can_access(job.organisation_id):
        raise NotFound("job")
    return job


@dataclass(frozen=True)
class AuthorisedSource:
    source: RequirementSource
    document: Document
    segment: SourceSegment


def authorise_source(repo: Repository, principal: Principal, source_id: str) -> AuthorisedSource:
    source = repo.get_requirement_source(source_id)
    if source is None or not principal.can_access(source.organisation_id):
        raise NotFound("source")
    document = repo.get_document(source.document_id)
    segment = repo.get_segment(source.segment_id)
    # Every linked record must agree on organisation and document, or nothing is returned.
    if (
        document is None
        or segment is None
        or document.organisation_id != source.organisation_id
        or segment.organisation_id != source.organisation_id
        or segment.document_id != document.id
        or segment.document_sha256 != document.sha256
        or segment.page_number != source.page_number
    ):
        raise NotFound("source")
    return AuthorisedSource(source=source, document=document, segment=segment)


@dataclass(frozen=True)
class AuthorisedEvidenceSource:
    source: EvidenceMatchSource
    match: EvidenceMatch
    document: Document
    segment: SourceSegment


def authorise_evidence_source(
    repo: Repository, principal: Principal, source_id: str
) -> AuthorisedEvidenceSource:
    source = repo.get_evidence_match_source(source_id)
    if source is None or not principal.can_access(source.organisation_id):
        raise NotFound("source")
    match = repo.get_evidence_match(source.evidence_match_id)
    document = repo.get_document(source.document_id)
    segment = repo.get_segment(source.segment_id)
    selection = next(
        (
            s
            for s in repo.list_evidence_selections(source.analysis_run_id)
            if s.document_id == source.document_id
        ),
        None,
    )
    # The passage must come from an evidence document selected for this run, at the
    # selected version, on the stated page, all in the same organisation.
    if (
        match is None
        or document is None
        or segment is None
        or selection is None
        or match.organisation_id != source.organisation_id
        or match.analysis_run_id != source.analysis_run_id
        or document.organisation_id != source.organisation_id
        or document.document_type != "evidence"
        or selection.organisation_id != source.organisation_id
        or selection.document_sha256 != document.sha256
        or segment.organisation_id != source.organisation_id
        or segment.document_id != document.id
        or segment.document_sha256 != document.sha256
        or segment.page_number != source.page_number
    ):
        raise NotFound("source")
    return AuthorisedEvidenceSource(source=source, match=match, document=document, segment=segment)
