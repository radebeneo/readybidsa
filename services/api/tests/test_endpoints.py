"""API tests against in-memory fakes (no Supabase, Redis or Groq) and a MOCKED model.

They prove the API's authorisation, validation and wiring. Postgres RLS and storage policies
are not exercised here; they need a live Supabase project.
"""

import csv
import io
import json
import re
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from readybid_api.auth import AuthError
from readybid_api.main import create_app
from readybid_api.review import CSV_COLUMNS, spreadsheet_safe
from readybid_api.services import Services
from readybid_core.config import Settings
from readybid_core.jobs import JobContext, rq_job_id, run_analysis
from readybid_core.matching import WITHHELD_TEXT
from readybid_testing.fakes import (
    NO_TEXT_MARKER,
    FakeQueue,
    FakeRepository,
    FakeStorage,
    ScriptedProvider,
    primary_passages,
    quote_each_primary_passage,
)
from readybid_testing.fakes import requirement as extracted_requirement
from readybid_testing.pdfs import (
    IMAGE_ONLY,
    build_encrypted_pdf,
    build_malformed_pdf,
    build_pdf,
)
from readybid_testing.scenario import make_settings

USER_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
USER_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
TOKENS = {"token-a": USER_A, "token-b": USER_B}
A = {"Authorization": "Bearer token-a"}
B = {"Authorization": "Bearer token-b"}
NOT_FOUND = {"detail": "Not found."}

PAGE_1 = "Bidders must submit a valid tax compliance status pin with the bid"
PAGE_3 = "The bidder must attend the compulsory briefing session on site"


class FakeVerifier:
    def verify(self, token: str) -> str:
        try:
            return TOKENS[token]
        except KeyError:
            raise AuthError("Invalid or expired access token.") from None


@dataclass
class Api:
    client: TestClient
    settings: Settings
    repo: FakeRepository
    storage: FakeStorage
    queue: FakeQueue | None

    def onboard(self, headers: dict[str, str], name: str = "dev-fixture org") -> str:
        response = self.client.post("/organisations", json={"name": name}, headers=headers)
        assert response.status_code == 201, response.text
        return response.json()["id"]

    def new_tender(self, headers: dict[str, str], org_id: str) -> str:
        response = self.client.post(
            f"/organisations/{org_id}/tenders",
            json={"title": "dev-fixture tender", "reference": " "},
            headers=headers,
        )
        assert response.status_code == 201, response.text
        return response.json()["id"]

    def upload(
        self, headers: dict[str, str], tender_id: str, data: bytes, name: str = "tender.pdf"
    ) -> Any:
        return self.client.post(
            f"/tenders/{tender_id}/documents",
            files={"file": (name, data, "application/pdf")},
            headers=headers,
        )

    def start(self, headers: dict[str, str], tender_id: str, document_id: str) -> Any:
        return self.client.post(
            f"/tenders/{tender_id}/analyses", json={"document_id": document_id}, headers=headers
        )

    def work(
        self,
        run_id: str,
        job_id: str,
        respond: Callable[[str], str | Exception] = quote_each_primary_passage,
    ) -> None:
        """Run the queued job in-process, as the worker would, with the mocked model."""
        ctx = JobContext(
            settings=self.settings,
            repo=self.repo,
            storage=self.storage,
            provider_factory=lambda: ScriptedProvider(respond),
        )
        run_analysis(ctx, run_id, job_id)


def make_api(*, queue: FakeQueue | None = None, with_queue: bool = True, **settings: Any) -> Api:
    config = make_settings(**settings)
    repo, storage = FakeRepository(), FakeStorage()
    if with_queue and queue is None:
        queue = FakeQueue()
    services = Services(config, repo=repo, storage=storage, queue=queue, verifier=FakeVerifier())
    return Api(TestClient(create_app(services=services)), config, repo, storage, queue)


@dataclass
class Workspace:
    org_id: str
    tender_id: str
    document_id: str
    run_id: str
    job_id: str
    source_id: str


def analysed_workspace(api: Api, headers: dict[str, str] = A) -> Workspace:
    org_id = api.onboard(headers)
    tender_id = api.new_tender(headers, org_id)
    upload = api.upload(headers, tender_id, build_pdf([PAGE_1, IMAGE_ONLY, PAGE_3]))
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]
    started = api.start(headers, tender_id, document_id)
    assert started.status_code == 202, started.text
    run_id, job_id = started.json()["analysis"]["id"], started.json()["job"]["id"]
    api.work(run_id, job_id)
    requirements = api.client.get(f"/analyses/{run_id}/requirements", headers=headers).json()
    source_id = requirements["requirements"][0]["sources"][0]["id"]
    return Workspace(org_id, tender_id, document_id, run_id, job_id, source_id)


# Authentication -----------------------------------------------------------------------
def test_requests_without_a_valid_token_are_rejected() -> None:
    api = make_api()

    missing = api.client.get("/organisations")
    invalid = api.client.get("/organisations", headers={"Authorization": "Bearer nope"})

    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert invalid.status_code == 401


def test_missing_supabase_configuration_returns_503_not_placeholder_data() -> None:
    client = TestClient(create_app(make_settings()))

    response = client.get("/organisations", headers=A)

    assert response.status_code == 503
    assert "Integration not configured" in response.json()["detail"]


# Organisations and tenders ------------------------------------------------------------
def test_first_login_creates_one_organisation_owned_by_the_caller() -> None:
    api = make_api()

    org_id = api.onboard(A, "  Acme Builders  ")
    again = api.client.post("/organisations", json={"name": "Second"}, headers=A)
    listed = api.client.get("/organisations", headers=A).json()

    assert again.status_code == 409
    assert listed == [{"id": org_id, "name": "Acme Builders", "role": "owner"}]
    assert api.client.get("/organisations", headers=B).json() == []


def test_blank_names_are_rejected() -> None:
    api = make_api()

    assert api.client.post("/organisations", json={"name": "  "}, headers=A).status_code == 422


def test_tenders_are_created_and_listed_per_organisation() -> None:
    api = make_api()
    org_id = api.onboard(A)

    tender_id = api.new_tender(A, org_id)
    listed = api.client.get(f"/organisations/{org_id}/tenders", headers=A).json()

    assert [t["id"] for t in listed] == [tender_id]
    assert listed[0]["reference"] is None  # blank reference stored as null
    assert listed[0]["organisation_id"] == org_id


def test_ids_must_be_uuids() -> None:
    api = make_api()

    assert api.client.get("/tenders/not-a-uuid", headers=A).status_code == 422


# Uploads ------------------------------------------------------------------------------
def test_upload_stores_the_file_privately_and_versions_each_upload() -> None:
    api = make_api()
    tender_id = api.new_tender(A, api.onboard(A))
    pdf = build_pdf([PAGE_1, PAGE_3])

    first = api.upload(A, tender_id, pdf, name="..\\..\\secret/Tender Pack.pdf")
    second = api.upload(A, tender_id, pdf)

    assert first.status_code == 201, first.text
    body = first.json()
    assert body["version"] == 1 and second.json()["version"] == 2
    assert body["page_count"] == 2
    assert body["original_filename"] == "Tender Pack.pdf"
    assert len(body["sha256"]) == 64
    assert "storage_path" not in first.text
    # The object path is built from server ids only, never from the filename.
    stored = api.repo.documents[body["id"]]
    assert stored.storage_path.endswith(f"/{tender_id}/{body['id']}.pdf")
    assert api.storage.objects[stored.storage_path] == pdf


@pytest.mark.parametrize(
    ("data", "code"),
    [
        (b"", "empty_file"),
        (b"PK\x03\x04 this is a zip file, not a pdf", "not_pdf"),
        (build_malformed_pdf(), "malformed_pdf"),
        (build_encrypted_pdf(), "encrypted_pdf"),
    ],
)
def test_invalid_uploads_are_rejected_by_content(data: bytes, code: str) -> None:
    api = make_api()
    tender_id = api.new_tender(A, api.onboard(A))

    response = api.upload(A, tender_id, data, name="looks-fine.pdf")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == code
    assert api.storage.objects == {}
    assert api.repo.documents == {}


def test_upload_page_limit_is_configurable() -> None:
    api = make_api(max_pdf_pages=2)
    tender_id = api.new_tender(A, api.onboard(A))

    response = api.upload(A, tender_id, build_pdf([PAGE_1, PAGE_1, PAGE_1]))

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "too_many_pages"


@pytest.mark.parametrize("size", [5_000, 200_000])
def test_upload_size_limit_is_configurable(size: int) -> None:
    # 5 KB is read and then rejected; 200 KB is rejected from Content-Length before reading.
    api = make_api(max_upload_bytes=2_000)
    tender_id = api.new_tender(A, api.onboard(A))
    data = build_pdf([PAGE_1]) + b"%" * size

    response = api.upload(A, tender_id, data)

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "too_large"
    assert api.storage.objects == {}


def test_upload_without_a_file_field_is_rejected() -> None:
    api = make_api()
    tender_id = api.new_tender(A, api.onboard(A))

    response = api.client.post(
        f"/tenders/{tender_id}/documents", data={"other": "value"}, headers=A
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "missing_file"


def test_concurrent_version_conflict_is_retried() -> None:
    api = make_api()
    tender_id = api.new_tender(A, api.onboard(A))
    api.repo.conflicting_document_inserts = 1

    response = api.upload(A, tender_id, build_pdf([PAGE_1]))

    assert response.status_code == 201
    assert response.json()["version"] == 1


def test_persistent_version_conflict_returns_409_and_removes_the_orphaned_file() -> None:
    api = make_api()
    tender_id = api.new_tender(A, api.onboard(A))
    api.repo.conflicting_document_inserts = 10

    response = api.upload(A, tender_id, build_pdf([PAGE_1]))

    assert response.status_code == 409
    assert api.storage.objects == {}


# Analysis -----------------------------------------------------------------------------
def test_full_flow_returns_source_linked_requirements_and_coverage_warnings() -> None:
    api = make_api()
    ws = analysed_workspace(api)

    job = api.client.get(f"/jobs/{ws.job_id}", headers=A).json()
    assert (job["status"], job["progress"]) == ("completed", 100)
    assert api.queue is not None and api.queue.calls[0]["job_id"] == rq_job_id(ws.job_id)

    response = api.client.get(f"/analyses/{ws.run_id}/requirements", headers=A)
    body = response.json()
    assert [r["requirement_text"] for r in body["requirements"]] == [PAGE_1, PAGE_3]
    assert [r["sources"][0]["page_number"] for r in body["requirements"]] == [1, 3]
    assert body["coverage"]["complete"] is False
    assert body["coverage"]["flagged_pages"] == [
        {
            "page_number": 2,
            "status": "empty",
            "note": "No extractable text. The page may be scanned or image-only.",
        }
    ]
    assert "not legal advice" in body["notice"]
    assert body["document"]["version"] == 1
    assert "storage_path" not in response.text

    source = api.client.get(f"/sources/{ws.source_id}", headers=A).json()
    assert source["page_number"] == 1
    assert source["quote"] == PAGE_1
    assert source["signed_url"].startswith("https://storage.test/")
    assert source["expires_in_seconds"] == api.settings.signed_url_ttl_seconds

    file = api.client.get(f"/documents/{ws.document_id}/file", headers=A).json()
    assert file["signed_url"].startswith("https://storage.test/")

    detail = api.client.get(f"/tenders/{ws.tender_id}", headers=A).json()
    assert detail["latest_analysis"]["id"] == ws.run_id
    assert detail["latest_job"]["status"] == "completed"
    assert [d["id"] for d in detail["documents"]] == [ws.document_id]


def test_starting_twice_while_running_returns_the_same_analysis() -> None:
    api = make_api()
    tender_id = api.new_tender(A, api.onboard(A))
    document_id = api.upload(A, tender_id, build_pdf([PAGE_1])).json()["id"]

    first = api.start(A, tender_id, document_id).json()
    second = api.start(A, tender_id, document_id).json()

    assert first["analysis"]["id"] == second["analysis"]["id"]
    assert api.queue is not None and len(api.queue.calls) == 1
    assert len(api.repo.runs) == 1


def test_stuck_analysis_is_failed_and_replaced() -> None:
    api = make_api()
    tender_id = api.new_tender(A, api.onboard(A))
    document_id = api.upload(A, tender_id, build_pdf([PAGE_1])).json()["id"]
    first = api.start(A, tender_id, document_id).json()
    job_id = first["job"]["id"]
    api.repo.jobs[job_id] = api.repo.jobs[job_id].model_copy(
        update={"updated_at": datetime(2020, 1, 1, tzinfo=UTC)}
    )

    second = api.start(A, tender_id, document_id).json()

    assert second["analysis"]["id"] != first["analysis"]["id"]
    old = api.repo.runs[first["analysis"]["id"]]
    assert old.status == "failed" and "stopped responding" in (old.error or "")


def test_queue_outage_fails_the_run_visibly() -> None:
    api = make_api(queue=FakeQueue(fail=True))
    tender_id = api.new_tender(A, api.onboard(A))
    document_id = api.upload(A, tender_id, build_pdf([PAGE_1])).json()["id"]

    response = api.start(A, tender_id, document_id)

    assert response.status_code == 503
    [run] = api.repo.runs.values()
    assert run.status == "failed"


@pytest.mark.parametrize(
    ("overrides", "missing"),
    [({"groq_api_key": None}, "GROQ_API_KEY"), ({"with_queue": False}, "REDIS_URL")],
)
def test_analysis_needs_model_and_queue_configuration(
    overrides: dict[str, Any], missing: str
) -> None:
    api = make_api(**overrides)
    tender_id = api.new_tender(A, api.onboard(A))
    document_id = api.upload(A, tender_id, build_pdf([PAGE_1])).json()["id"]

    response = api.start(A, tender_id, document_id)

    assert response.status_code == 503
    assert "Integration not configured" in response.json()["detail"]
    assert missing in response.json()["detail"]
    assert api.repo.runs == {}


# Tenant isolation ---------------------------------------------------------------------
def test_user_b_cannot_reach_anything_in_user_a_organisation() -> None:
    api = make_api()
    ws = analysed_workspace(api, A)
    b_tender = api.new_tender(B, api.onboard(B, "B org"))
    objects_before = dict(api.storage.objects)
    signed_before = len(api.storage.signed)
    runs_before = len(api.repo.runs)
    client = api.client

    attempts = {
        "list A tenders": client.get(f"/organisations/{ws.org_id}/tenders", headers=B),
        "create tender in A": client.post(
            f"/organisations/{ws.org_id}/tenders", json={"title": "x"}, headers=B
        ),
        "read A tender": client.get(f"/tenders/{ws.tender_id}", headers=B),
        "upload to A tender": api.upload(B, ws.tender_id, build_pdf([PAGE_1])),
        "A file url": client.get(f"/documents/{ws.document_id}/file", headers=B),
        "analyse A tender": api.start(B, ws.tender_id, ws.document_id),
        "analyse A document in B tender": api.start(B, b_tender, ws.document_id),
        "A job": client.get(f"/jobs/{ws.job_id}", headers=B),
        "A analysis": client.get(f"/analyses/{ws.run_id}", headers=B),
        "A requirements": client.get(f"/analyses/{ws.run_id}/requirements", headers=B),
        "A source": client.get(f"/sources/{ws.source_id}", headers=B),
    }

    for name, response in attempts.items():
        assert (response.status_code, response.json()) == (404, NOT_FOUND), name
    # Other organisations' resources look exactly like ids that do not exist.
    missing = client.get(f"/tenders/{uuid.uuid4()}", headers=A)
    assert (missing.status_code, missing.json()) == (404, NOT_FOUND)
    assert api.storage.objects == objects_before
    assert len(api.storage.signed) == signed_before
    assert len(api.repo.runs) == runs_before
    assert client.get(f"/organisations/{ws.org_id}/tenders", headers=A).status_code == 200


def test_a_document_from_another_tender_in_the_same_org_cannot_be_analysed_there() -> None:
    api = make_api()
    org_id = api.onboard(A)
    tender_1, tender_2 = api.new_tender(A, org_id), api.new_tender(A, org_id)
    document_id = api.upload(A, tender_1, build_pdf([PAGE_1])).json()["id"]

    assert api.start(A, tender_2, document_id).status_code == 404


# Evidence matching fixtures -----------------------------------------------------------
# One MOCKED model answers both prompt types. On purpose it over-claims: it reports evidence
# when fewer letters than required exist, calls the scoring item a potential blocker, cites
# pages with no extractable text and claims documents are genuine. The tests show the
# deterministic rules correcting each of these.
PAGE_REFERENCES = "Bidders must submit three reference letters for similar completed projects"
PAGE_SCORING = "Preference points are awarded for a valid B-BBEE certificate"
SCORING_CONSEQUENCE = "Bidders without a certificate score zero preference points"
LETTER_QUOTE = "confirms satisfactory completion of the road works"
LETTER_TEXT = f"dev-fixture Client One {LETTER_QUOTE} in 2025"
SECOND_LETTER_TEXT = f"dev-fixture Client Two {LETTER_QUOTE} in 2024"
PROFILE_TEXT = "dev-fixture Builders company profile: civil works delivered since 2015"
OVERCLAIM = "The reference letters are genuine and legally sufficient."

_EVIDENCE_SEGMENT = re.compile(
    r'<segment id="(?P<id>[^"]+)" document="(?P<document>D\d+)" page="(?P<page>\d+)" '
    r'extraction="(?P<status>[^"]+)">\n(?P<text>.*?)\n</segment>',
    re.DOTALL,
)
_MATCHING_REQUIREMENT = re.compile(
    r'<requirement ref="(?P<ref>R\d+)" category="(?P<category>[^"]*)">\n'
    r"Title: [^\n]*\nRequirement: (?P<text>[^\n]*)\n"
)


def _assessment(
    ref: str,
    assessment: str,
    explanation: str,
    *,
    required_count: int | None = None,
    candidates: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    return {
        "requirement_ref": ref,
        "assessment": assessment,
        "explanation": explanation,
        "uncertainty_notes": None,
        "required_count": required_count,
        "candidates": list(candidates),
    }


def matching_answer(prompt: str) -> str:
    segments = list(_EVIDENCE_SEGMENT.finditer(prompt))
    assessments: list[dict[str, Any]] = []
    for item in _MATCHING_REQUIREMENT.finditer(prompt):
        ref, text = item["ref"], item["text"]
        if "reference letters" in text:
            candidates = [
                {
                    "segment_id": s["id"],
                    "quote": LETTER_QUOTE if LETTER_QUOTE in s["text"] else NO_TEXT_MARKER,
                    "relationship": "This letter is verified.",
                }
                for s in segments
                if LETTER_QUOTE in s["text"] or s["text"] == NO_TEXT_MARKER
            ]
            assessments.append(
                _assessment(
                    ref, "evidence_found", OVERCLAIM, required_count=3, candidates=candidates
                )
            )
        elif item["category"] == "scoring":
            assessments.append(
                _assessment(ref, "potential_blocker", "No certificate appears in the evidence.")
            )
        else:
            assessments.append(_assessment(ref, "missing_evidence", "No passage appears relevant."))
    return json.dumps({"assessments": assessments})


def tender_and_matching_model(prompt: str) -> str:
    """Mocked model for both prompt types: requirement extraction and evidence matching."""
    if "<evidence>" in prompt and "<requirements>" in prompt:
        return matching_answer(prompt)
    items: list[dict[str, Any]] = []
    for segment_id, text in primary_passages(prompt):
        if text == NO_TEXT_MARKER:
            continue
        if "Preference points" in text:
            item = extracted_requirement(segment_id, text, category="scoring", stage="evaluation")
            item["consequence"] = SCORING_CONSEQUENCE
        else:
            item = extracted_requirement(segment_id, text)
        items.append(item)
    return json.dumps({"requirements": items})


def recording(prompts: list[str]) -> Callable[[str], str]:
    def respond(prompt: str) -> str:
        prompts.append(prompt)
        return tender_and_matching_model(prompt)

    return respond


# Evidence workspace helpers -----------------------------------------------------------
def upload_evidence(
    api: Api,
    headers: dict[str, str],
    org_id: str,
    data: bytes,
    label: str,
    name: str = "evidence.pdf",
) -> Any:
    return api.client.post(
        f"/organisations/{org_id}/evidence",
        data={"label": label},
        files={"file": (name, data, "application/pdf")},
        headers=headers,
    )


def add_evidence(
    api: Api, headers: dict[str, str], org_id: str, pages: Sequence[Any], label: str, name: str
) -> str:
    response = upload_evidence(api, headers, org_id, build_pdf(list(pages)), label, name)
    assert response.status_code == 201, response.text
    document_id: str = response.json()["id"]
    return document_id


def start_with_evidence(
    api: Api,
    headers: dict[str, str],
    tender_id: str,
    document_id: str,
    evidence_ids: Sequence[str],
) -> Any:
    return api.client.post(
        f"/tenders/{tender_id}/analyses",
        json={"document_id": document_id, "evidence_document_ids": list(evidence_ids)},
        headers=headers,
    )


def analyse(
    api: Api,
    headers: dict[str, str],
    tender_id: str,
    document_id: str,
    evidence_ids: Sequence[str],
    respond: Callable[[str], str] = tender_and_matching_model,
) -> str:
    started = start_with_evidence(api, headers, tender_id, document_id, evidence_ids)
    assert started.status_code == 202, started.text
    body = started.json()
    api.work(body["analysis"]["id"], body["job"]["id"], respond)
    run_id: str = body["analysis"]["id"]
    return run_id


EvidenceSpec = tuple[Sequence[Any], str, str]  # pages, label, filename
DEFAULT_EVIDENCE: tuple[EvidenceSpec, ...] = (
    ((LETTER_TEXT,), "reference_letter", "letter-one.pdf"),
    ((PROFILE_TEXT,), "company_profile", "profile.pdf"),
)


@dataclass
class EvidenceWorkspace:
    org_id: str
    tender_id: str
    document_id: str
    evidence_ids: list[str]
    run_id: str


def matched_workspace(
    api: Api, headers: dict[str, str] = A, evidence: Sequence[EvidenceSpec] = DEFAULT_EVIDENCE
) -> EvidenceWorkspace:
    org_id = api.onboard(headers)
    tender_id = api.new_tender(headers, org_id)
    upload = api.upload(headers, tender_id, build_pdf([PAGE_REFERENCES, PAGE_SCORING]))
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]
    evidence_ids = [
        add_evidence(api, headers, org_id, pages, label, name) for pages, label, name in evidence
    ]
    run_id = analyse(api, headers, tender_id, document_id, evidence_ids)
    return EvidenceWorkspace(org_id, tender_id, document_id, evidence_ids, run_id)


def get_checklist(api: Api, headers: dict[str, str], run_id: str) -> dict[str, Any]:
    response = api.client.get(f"/analyses/{run_id}/checklist", headers=headers)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def item_for(checklist: dict[str, Any], fragment: str) -> dict[str, Any]:
    [item] = [i for i in checklist["items"] if fragment in i["requirement"]["requirement_text"]]
    found: dict[str, Any] = item
    return found


def decide(
    api: Api,
    headers: dict[str, str],
    run_id: str,
    requirement_id: str,
    decision: str,
    notes: str | None = None,
) -> Any:
    return api.client.post(
        f"/analyses/{run_id}/decisions",
        json={"requirement_id": requirement_id, "decision": decision, "notes": notes},
        headers=headers,
    )


# Evidence library ---------------------------------------------------------------------
def test_evidence_upload_keeps_flagged_pages_and_hides_storage_paths() -> None:
    api = make_api()
    org_id = api.onboard(A)

    response = upload_evidence(
        api, A, org_id, build_pdf([LETTER_TEXT, IMAGE_ONLY]), "reference_letter", "letter.pdf"
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["document_type"] == "evidence"
    assert body["tender_id"] is None
    assert body["evidence_label"] == "reference_letter"
    assert (body["page_count"], body["pages_with_text"]) == (2, 1)
    assert body["text_status"] == "partly_readable"
    # The unreadable page is flagged and kept, never dropped.
    assert [(p["page_number"], p["status"]) for p in body["flagged_pages"]] == [(2, "empty")]
    assert "storage_path" not in response.text
    stored = api.repo.documents[body["id"]]
    assert stored.storage_path.endswith(f"{org_id}/evidence/{body['id']}.pdf")
    assert stored.storage_path in api.storage.objects

    listed = api.client.get(f"/organisations/{org_id}/evidence", headers=A)
    assert listed.status_code == 200, listed.text
    assert [d["id"] for d in listed.json()["documents"]] == [body["id"]]
    assert listed.json()["max_per_analysis"] == api.settings.max_evidence_documents_per_analysis
    assert "not check that a document is genuine" in listed.json()["notice"]
    assert "storage_path" not in listed.text


@pytest.mark.parametrize("label", ["", "certified_copy", "REFERENCE_LETTER"])
def test_evidence_upload_needs_a_known_label(label: str) -> None:
    api = make_api()
    org_id = api.onboard(A)

    response = upload_evidence(api, A, org_id, build_pdf([LETTER_TEXT]), label)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_label"
    assert api.storage.objects == {}
    assert api.repo.documents == {}


# Evidence selection -------------------------------------------------------------------
def test_only_explicitly_selected_evidence_is_used() -> None:
    api = make_api(max_evidence_documents_per_analysis=2)
    org_id = api.onboard(A)
    tender_id = api.new_tender(A, org_id)
    document_id = api.upload(A, tender_id, build_pdf([PAGE_REFERENCES])).json()["id"]
    letters = [
        add_evidence(api, A, org_id, [f"{LETTER_TEXT} copy {n}"], "reference_letter", f"l{n}.pdf")
        for n in range(3)
    ]

    too_many = start_with_evidence(api, A, tender_id, document_id, letters)
    tender_file = start_with_evidence(api, A, tender_id, document_id, [document_id])
    unknown = start_with_evidence(api, A, tender_id, document_id, [str(uuid.uuid4())])

    assert too_many.status_code == 422
    assert (tender_file.status_code, tender_file.json()) == (404, NOT_FOUND)
    assert (unknown.status_code, unknown.json()) == (404, NOT_FOUND)
    assert api.repo.runs == {}

    # Duplicates collapse, so two unique documents fit the limit of two.
    prompts: list[str] = []
    run_id = analyse(
        api, A, tender_id, document_id, [letters[0], letters[0], letters[1]], recording(prompts)
    )

    checklist = get_checklist(api, A, run_id)
    assert [e["document_id"] for e in checklist["evidence"]] == letters[:2]
    matching_prompts = [p for p in prompts if "<evidence>" in p]
    assert matching_prompts
    assert all('document="D2"' in p and 'document="D3"' not in p for p in matching_prompts)
    assert all("copy 2" not in p for p in matching_prompts)


def test_analysis_without_selected_evidence_makes_no_matching_calls() -> None:
    api = make_api()
    org_id = api.onboard(A)
    # In the library, but not selected: it must not be used.
    add_evidence(api, A, org_id, [LETTER_TEXT], "reference_letter", "letter.pdf")
    tender_id = api.new_tender(A, org_id)
    upload = api.upload(A, tender_id, build_pdf([PAGE_REFERENCES, PAGE_SCORING]))
    prompts: list[str] = []

    run_id = analyse(api, A, tender_id, upload.json()["id"], [], recording(prompts))

    assert prompts and not any("<evidence>" in p for p in prompts)
    checklist = get_checklist(api, A, run_id)
    assert checklist["analysis"]["matching_status"] == "not_requested"
    assert checklist["evidence"] == []
    assert len(checklist["items"]) == 2
    assert {i["current_status"] for i in checklist["items"]} == {"not_assessed"}
    assert all(i["assessment"] is None for i in checklist["items"])
    assert "No evidence was selected" in checklist["items"][0]["next_action"]
    assert checklist["indicators"]["not_assessed"] == 2


def test_a_different_evidence_selection_starts_a_new_analysis() -> None:
    api = make_api()
    org_id = api.onboard(A)
    tender_id = api.new_tender(A, org_id)
    document_id = api.upload(A, tender_id, build_pdf([PAGE_REFERENCES])).json()["id"]
    letter = add_evidence(api, A, org_id, [LETTER_TEXT], "reference_letter", "letter.pdf")
    profile = add_evidence(api, A, org_id, [PROFILE_TEXT], "company_profile", "profile.pdf")

    first = start_with_evidence(api, A, tender_id, document_id, [letter]).json()
    second = start_with_evidence(api, A, tender_id, document_id, [letter, profile]).json()
    again = start_with_evidence(api, A, tender_id, document_id, [profile, letter]).json()

    assert first["analysis"]["matching_status"] == "pending"
    assert second["analysis"]["id"] != first["analysis"]["id"]
    # Same document and same selection (in any order) reuses the active run.
    assert again["analysis"]["id"] == second["analysis"]["id"]
    assert api.queue is not None and len(api.queue.calls) == 2


# Acceptance: matching rules -----------------------------------------------------------
def test_missing_reference_letters_produce_an_evidence_gap_finding() -> None:
    api = make_api()
    ws = matched_workspace(api)

    checklist = get_checklist(api, A, ws.run_id)
    item = item_for(checklist, "three reference letters")
    assessment = item["assessment"]

    # The model claimed "evidence found" for one letter when the tender asks for three.
    assert assessment["ai_status"] == "missing_evidence"
    assert item["current_status"] == "missing_evidence"
    assert assessment["required_count"] == 3
    assert assessment["candidate_document_count"] == 1
    assert "asks for 3" in assessment["count_summary"]
    assert "At least 2 more may be needed" in assessment["count_summary"]
    # Wording that claims documents are genuine or verified is withheld.
    assert assessment["explanation"] == WITHHELD_TEXT
    [source] = assessment["sources"]
    assert (source["document_filename"], source["page_number"]) == ("letter-one.pdf", 1)
    assert source["quote"] == LETTER_QUOTE
    assert source["counts_as_candidate"] is True
    assert source["relationship"] == WITHHELD_TEXT
    assert "does not mean the requirement was not met" in (item["next_action"] or "")
    assert checklist["indicators"]["unresolved"] == 2
    assert "not proof" in checklist["notice"]
    assert "ready to submit" not in json.dumps(checklist).casefold()

    view = api.client.get(f"/evidence-sources/{source['id']}", headers=A)
    assert view.status_code == 200, view.text
    assert (view.json()["page_number"], view.json()["quote"]) == (1, LETTER_QUOTE)
    assert view.json()["evidence_label"] == "reference_letter"
    assert view.json()["signed_url"].startswith("https://storage.test/")
    assert "storage_path" not in view.text


def test_a_scoring_gap_is_never_classified_as_a_potential_blocker() -> None:
    api = make_api()
    ws = matched_workspace(api)

    checklist = get_checklist(api, A, ws.run_id)
    item = item_for(checklist, "Preference points")

    assert item["requirement"]["category"] == "scoring"
    assert item["requirement"]["consequence"] == SCORING_CONSEQUENCE
    # The model proposed "potential_blocker"; missing scoring evidence affects points only.
    assert item["assessment"]["ai_status"] == "missing_evidence"
    assert checklist["indicators"]["potential_blockers"] == 0
    assert checklist["indicators"]["missing_evidence"] == 2


def test_unreadable_evidence_never_counts_as_candidate_support() -> None:
    api = make_api()
    ws = matched_workspace(
        api,
        evidence=(
            ((IMAGE_ONLY,), "reference_letter", "scanned-letter.pdf"),
            ((PROFILE_TEXT,), "company_profile", "profile.pdf"),
        ),
    )

    checklist = get_checklist(api, A, ws.run_id)
    item = item_for(checklist, "three reference letters")
    assessment = item["assessment"]
    [scanned] = [e for e in checklist["evidence"] if e["original_filename"] == "scanned-letter.pdf"]

    assert scanned["text_status"] == "unreadable"
    assert [p["status"] for p in scanned["flagged_pages"]] == ["empty"]
    # The model cited the unreadable page; that citation is rejected and nothing counts.
    # The readable profile still drives the result, so the gap stays visible with a warning.
    assert assessment["ai_status"] == "missing_evidence"
    assert assessment["candidate_document_count"] == 0
    assert not any(s["counts_as_candidate"] for s in assessment["sources"])
    assert checklist["analysis"]["matching_rejected_citations"] >= 1
    assert checklist["indicators"]["extraction_warnings"] >= 1
    next_action = item["next_action"] or ""
    assert "Extraction warning" in next_action
    assert "scanned-letter.pdf (page 1 unreadable)" in next_action
    assert "profile.pdf" not in next_action
    assert "scanned-letter.pdf" in (assessment["count_summary"] or "")


# Acceptance: human review -------------------------------------------------------------
def test_review_decisions_are_recorded_and_survive_a_refresh() -> None:
    api = make_api()
    ws = matched_workspace(api)
    item = item_for(get_checklist(api, A, ws.run_id), "three reference letters")
    requirement_id = item["requirement"]["id"]

    no_note = decide(api, A, ws.run_id, requirement_id, "not_applicable", "   ")
    unknown = decide(api, A, ws.run_id, str(uuid.uuid4()), "not_satisfied")
    first = decide(api, A, ws.run_id, requirement_id, "not_satisfied", "Need two more letters")
    second = decide(
        api, A, ws.run_id, requirement_id, "satisfied_for_submission_review", "  Added letters "
    )

    assert no_note.status_code == 422
    assert (unknown.status_code, unknown.json()) == (404, NOT_FOUND)
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert second.json()["reviewer_id"] == USER_A
    assert second.json()["notes"] == "Added letters"

    # A fresh request, as after a page refresh, returns the stored decisions.
    checklist = get_checklist(api, A, ws.run_id)
    refreshed = item_for(checklist, "three reference letters")
    assert refreshed["current_status"] == "human_reviewed"
    assert refreshed["assessment"]["ai_status"] == "missing_evidence"  # AI status unchanged
    assert refreshed["decision"]["id"] == second.json()["id"]
    assert [d["decision"] for d in refreshed["decision_history"]] == [
        "not_satisfied",
        "satisfied_for_submission_review",
    ]
    assert all(d["reviewer_id"] == USER_A for d in refreshed["decision_history"])
    assert all(d["created_at"] for d in refreshed["decision_history"])
    assert checklist["indicators"]["unresolved"] == 1

    # Moving it back to unresolved shows the AI status again.
    assert decide(api, A, ws.run_id, requirement_id, "unresolved").status_code == 201
    reopened = item_for(get_checklist(api, A, ws.run_id), "three reference letters")
    assert reopened["current_status"] == "missing_evidence"


def test_a_new_analysis_does_not_overwrite_earlier_decisions() -> None:
    api = make_api()
    ws = matched_workspace(api)
    first_item = item_for(get_checklist(api, A, ws.run_id), "three reference letters")
    decided = decide(
        api,
        A,
        ws.run_id,
        first_item["requirement"]["id"],
        "satisfied_for_submission_review",
        "Checked by hand",
    )
    assert decided.status_code == 201, decided.text

    run_2 = analyse(api, A, ws.tender_id, ws.document_id, ws.evidence_ids)

    assert run_2 != ws.run_id
    new_item = item_for(get_checklist(api, A, run_2), "three reference letters")
    assert new_item["requirement"]["id"] != first_item["requirement"]["id"]
    # The new run starts unresolved; the earlier decision is shown only as a hint.
    assert new_item["decision"] is None
    assert new_item["decision_history"] == []
    assert new_item["current_status"] == "missing_evidence"
    assert new_item["earlier_decision"]["id"] == decided.json()["id"]
    assert new_item["earlier_decision"]["analysis_run_id"] == ws.run_id
    # The earlier run keeps its own decision.
    old_item = item_for(get_checklist(api, A, ws.run_id), "three reference letters")
    assert old_item["current_status"] == "human_reviewed"
    assert old_item["decision"]["id"] == decided.json()["id"]


# Acceptance: tenant isolation ---------------------------------------------------------
def test_user_b_cannot_reach_user_a_evidence_checklist_or_decisions() -> None:
    api = make_api()
    ws = matched_workspace(api, A)
    item = item_for(get_checklist(api, A, ws.run_id), "three reference letters")
    requirement_id = item["requirement"]["id"]
    evidence_source_id = item["assessment"]["sources"][0]["id"]
    b = matched_workspace(api, B)
    decisions_before = len(api.repo.decisions)
    documents_before = len(api.repo.documents)
    runs_before = len(api.repo.runs)
    signed_before = len(api.storage.signed)
    client = api.client

    attempts = {
        "list A evidence": client.get(f"/organisations/{ws.org_id}/evidence", headers=B),
        "upload into A library": upload_evidence(
            api, B, ws.org_id, build_pdf([LETTER_TEXT]), "reference_letter"
        ),
        "select A evidence": start_with_evidence(
            api, B, b.tender_id, b.document_id, [ws.evidence_ids[0]]
        ),
        "A checklist": client.get(f"/analyses/{ws.run_id}/checklist", headers=B),
        "decide on A run": decide(api, B, ws.run_id, requirement_id, "not_satisfied"),
        "A requirement in B run": decide(api, B, b.run_id, requirement_id, "not_satisfied"),
        "A csv export": client.get(f"/analyses/{ws.run_id}/export?format=csv", headers=B),
        "A json export": client.get(f"/analyses/{ws.run_id}/export?format=json", headers=B),
        "A evidence source": client.get(f"/evidence-sources/{evidence_source_id}", headers=B),
    }

    for name, response in attempts.items():
        assert (response.status_code, response.json()) == (404, NOT_FOUND), name
    assert len(api.repo.decisions) == decisions_before
    assert len(api.repo.documents) == documents_before
    assert len(api.repo.runs) == runs_before
    assert len(api.storage.signed) == signed_before
    b_library = client.get(f"/organisations/{b.org_id}/evidence", headers=B).json()
    assert sorted(d["id"] for d in b_library["documents"]) == sorted(b.evidence_ids)
    assert client.get(f"/analyses/{ws.run_id}/checklist", headers=A).status_code == 200


# Export -------------------------------------------------------------------------------
FORMULA_TRIGGERS = "=+-@\t\r\n|\uff1d\uff0b\uff0d\uff20"
FORMULA_NOTE = '=HYPERLINK("https://attacker.test","Open")'


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("=1+1", "'=1+1"),
        ("+27 82 000 0000", "'+27 82 000 0000"),
        ("-5", "'-5"),
        ("@SUM(A1)", "'@SUM(A1)"),
        ("\tcmd", "'\tcmd"),
        ("\r=cmd", "'\r=cmd"),
        ("|pipe", "'|pipe"),
        ("  =cmd", "'  =cmd"),
        ("\u00a0=cmd", "'\u00a0=cmd"),
        ("\uff1dcmd", "'\uff1dcmd"),
        ("\uff20cmd", "'\uff20cmd"),
        ("plain text", "plain text"),
        ("a=b", "a=b"),
        ("", ""),
        (None, ""),
        (3, "3"),
    ],
)
def test_spreadsheet_safe_neutralises_formula_triggers(value: object, expected: str) -> None:
    assert spreadsheet_safe(value) == expected


def _csv_rows(content: bytes) -> list[list[str]]:
    return list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))


def test_csv_export_is_complete_and_formula_safe() -> None:
    api = make_api()
    ws = matched_workspace(
        api,
        evidence=(
            ((LETTER_TEXT, IMAGE_ONLY), "reference_letter", "letter-one.pdf"),
            ((PROFILE_TEXT,), "company_profile", "profile.pdf"),
        ),
    )
    item = item_for(get_checklist(api, A, ws.run_id), "three reference letters")
    decided = decide(api, A, ws.run_id, item["requirement"]["id"], "not_satisfied", FORMULA_NOTE)
    assert decided.status_code == 201, decided.text

    response = api.client.get(f"/analyses/{ws.run_id}/export?format=csv", headers=A)

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-disposition"] == (
        f'attachment; filename="readybid-checklist-{ws.run_id}.csv"'
    )
    assert response.content.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in response.content
    assert b"storage_path" not in response.content

    rows = _csv_rows(response.content)
    header_index = rows.index(list(CSV_COLUMNS))
    meta = [r for r in rows[:header_index] if r]
    labels = [r[0] for r in meta]
    values = {r[0]: r[1] for r in meta if len(r) == 2}

    # Tender identity, analysis timestamp and document versions.
    assert values["Tender id"] == ws.tender_id
    assert values["Analysis id"] == ws.run_id
    assert values["Analysis created"]
    assert values["Exported at"]
    assert "not proof" in values["Notice"]
    tender_sha = api.repo.documents[ws.document_id].sha256
    assert f"sha256 {tender_sha}" in values["Tender document"]
    assert "version 1" in values["Tender document"]
    evidence_rows = [r[1] for r in meta if r[0] == "Evidence document"]
    assert len(evidence_rows) == 2
    for evidence_id in ws.evidence_ids:
        sha = api.repo.documents[evidence_id].sha256
        assert any(f"sha256 {sha}" in r for r in evidence_rows)
    # Review indicators and unresolved warnings.
    assert "Review indicators" in labels
    assert "1 unresolved of 2" in values["Review indicators"]
    warnings = [r[1] for r in meta if r[0] == "Extraction warning"]
    assert any(w.startswith("letter-one.pdf page 2") for w in warnings)

    # Requirements, findings, source refs and human decisions.
    items = [dict(zip(CSV_COLUMNS, r, strict=True)) for r in rows[header_index + 1 :] if r]
    assert len(items) == 2
    [letters] = [i for i in items if "three reference letters" in i["Requirement text"]]
    assert letters["Tender source refs"].startswith("p.1 [")
    assert "asks for 3" in letters["Count summary"]
    assert ws.evidence_ids[0] in letters["Evidence source refs"]
    assert LETTER_QUOTE in letters["Candidate evidence"]
    assert letters["Decision notes"] == "'" + FORMULA_NOTE
    assert letters["Reviewer id"] == USER_A
    assert letters["Decided at"]
    [scoring] = [i for i in items if "Preference points" in i["Requirement text"]]
    assert scoring["Reviewer id"] == ""

    # No cell may start (after leading whitespace) with a formula trigger.
    for row in rows:
        for cell in row:
            # An empty slice is "in" every string, so only test a real first character.
            first = cell[:1]
            assert not first or first not in FORMULA_TRIGGERS, cell
            visible = cell.lstrip(" \t\r\n\u00a0")[:1]
            assert not visible or visible not in FORMULA_TRIGGERS or first == "'", cell
    assert "ready to submit" not in response.content.decode("utf-8-sig").casefold()


def test_json_export_carries_the_checklist_and_decisions() -> None:
    api = make_api()
    ws = matched_workspace(api)
    item = item_for(get_checklist(api, A, ws.run_id), "three reference letters")
    decided = decide(api, A, ws.run_id, item["requirement"]["id"], "not_satisfied", "Need 2")
    assert decided.status_code == 201, decided.text

    response = api.client.get(f"/analyses/{ws.run_id}/export?format=json", headers=A)

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-disposition"] == (
        f'attachment; filename="readybid-checklist-{ws.run_id}.json"'
    )
    assert "storage_path" not in response.text
    body = response.json()
    assert body["exported_at"]
    checklist = body["checklist"]
    assert checklist["tender"]["id"] == ws.tender_id
    assert checklist["analysis"]["id"] == ws.run_id
    assert checklist["document"]["sha256"] == api.repo.documents[ws.document_id].sha256
    assert sorted(e["selected_sha256"] for e in checklist["evidence"]) == sorted(
        api.repo.documents[e].sha256 for e in ws.evidence_ids
    )
    exported = item_for(checklist, "three reference letters")
    assert exported["decision"]["id"] == decided.json()["id"]
    assert exported["decision"]["reviewer_id"] == USER_A
    assert exported["assessment"]["sources"][0]["page_number"] == 1
    assert "not proof" in checklist["notice"]


def test_export_rejects_unknown_formats() -> None:
    api = make_api()
    ws = matched_workspace(api)

    response = api.client.get(f"/analyses/{ws.run_id}/export?format=xlsx", headers=A)

    assert response.status_code == 422
