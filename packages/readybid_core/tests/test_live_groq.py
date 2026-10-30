"""LIVE model test: makes a real Groq call on a synthetic fixture.

Skipped (and reported as not run) unless GROQ_API_KEY is configured. Uses GROQ_MODEL, which
defaults to openai/gpt-oss-120b.
"""

import pytest

from readybid_core.analysis import AnalysisSegment, analyse_document
from readybid_core.citations import normalise_whitespace
from readybid_core.clients import build_llm_provider
from readybid_core.config import Settings
from readybid_core.pdf import extract_segments, sha256_hex
from readybid_testing.pdfs import build_pdf

SETTINGS = Settings()

pytestmark = pytest.mark.skipif(
    SETTINGS.groq_api_key is None,
    reason="LIVE test not run: GROQ_API_KEY is not configured.",
)

FIXTURE_PAGE = (
    "dev-fixture tender. Bidders must submit a valid tax compliance status pin. "
    "Bidders must attend the compulsory briefing session on 3 March."
)


def test_live_model_returns_requirements_with_valid_citations() -> None:
    pdf = build_pdf([FIXTURE_PAGE])
    sha = sha256_hex(pdf)
    segments = extract_segments(pdf, document_id="dev-fixture-doc", document_sha256=sha)

    result = analyse_document(
        provider=build_llm_provider(SETTINGS),
        document_id="dev-fixture-doc",
        document_sha256=sha,
        segments=[
            AnalysisSegment(id=s.id, page_number=s.page_number, text=s.text, status=s.status)
            for s in segments
        ],
        pages_per_group=SETTINGS.analysis_pages_per_group,
        max_group_chars=SETTINGS.analysis_max_group_chars,
        boundary_context_chars=SETTINGS.analysis_boundary_context_chars,
        max_requirements_per_group=SETTINGS.llm_max_requirements_per_group,
        max_repair_attempts=SETTINGS.llm_max_repair_attempts,
    )

    assert result.status == "completed", result.error
    assert result.requirements, "the model returned no cited requirements"
    page_text = normalise_whitespace(segments[0].text)
    for item in result.requirements:
        for source in item.sources:
            assert source.page_number == 1
            assert source.quote in page_text
