"""Builders for test data in the in-memory fakes."""

import uuid
from typing import Any

from readybid_core.config import Settings
from readybid_core.models import AnalysisRun, Document, ProcessingJob, Tender
from readybid_core.pdf import validate_pdf
from readybid_core.storage import document_storage_path
from readybid_testing.fakes import FakeRepository, FakeStorage


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "cors_origins": "http://localhost:3000",
        "groq_api_key": "dev-fixture-key",
        **overrides,
    }
    return Settings(_env_file=None, **values)


def seed_document(
    repo: FakeRepository, storage: FakeStorage, pdf: bytes, *, user_id: str
) -> tuple[Tender, Document]:
    org = repo.create_organisation("dev-fixture organisation", user_id)
    tender = repo.create_tender(org.id, "dev-fixture tender", None, user_id)
    document_id = str(uuid.uuid4())
    path = document_storage_path(org.id, tender.id, document_id)
    storage.upload_pdf(path, pdf)
    validated = validate_pdf(pdf, max_bytes=15 * 1024 * 1024, max_pages=100)
    document = repo.insert_document(
        Document(
            id=document_id,
            organisation_id=org.id,
            tender_id=tender.id,
            original_filename="dev-fixture-tender.pdf",
            storage_path=path,
            sha256=validated.sha256,
            size_bytes=validated.size_bytes,
            page_count=validated.page_count,
            version=1,
            created_by=user_id,
        )
    )
    return tender, document


def queue_run(repo: FakeRepository, document: Document) -> tuple[AnalysisRun, ProcessingJob]:
    run = repo.create_analysis_run(
        AnalysisRun(
            id=str(uuid.uuid4()),
            organisation_id=document.organisation_id,
            tender_id=document.tender_id,
            document_id=document.id,
            document_sha256=document.sha256,
            model="dev-fixture-model",
        )
    )
    job = repo.create_processing_job(
        ProcessingJob(
            id=str(uuid.uuid4()), organisation_id=run.organisation_id, analysis_run_id=run.id
        )
    )
    return run, job
