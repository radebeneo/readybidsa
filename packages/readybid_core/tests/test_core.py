from readybid_core.clients import (
    REPOSITORY_TIMEOUT_SECONDS,
    STORAGE_TIMEOUT_SECONDS,
    build_repository_and_storage,
)
from readybid_core.config import Settings
from readybid_core.integrations import get_integration_status
from readybid_core.jobs import ping_job
from readybid_core.pdf import extract_pages, unreadable_pages
from readybid_testing.pdfs import build_pdf


def test_extract_pages_keeps_and_flags_unreadable_pages() -> None:
    pdf = build_pdf(["Bidders must submit a valid tax clearance certificate", None])

    pages = extract_pages(pdf)

    assert len(pages) == 2  # the empty page is not dropped
    assert pages[0].readable is True
    assert "tax clearance certificate" in pages[0].text
    assert pages[1].readable is False
    assert unreadable_pages(pages) == [2]


def test_settings_treat_empty_values_as_unset(monkeypatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000, https://example.test")

    settings = Settings(_env_file=None)

    assert settings.groq_api_key is None
    assert settings.cors_origin_list == ["http://localhost:3000", "https://example.test"]


def test_integration_status_reports_missing_config_without_network() -> None:
    def fail_if_called(url: str) -> str | None:
        raise AssertionError("Redis must not be checked when REDIS_URL is unset")

    status = get_integration_status(Settings(_env_file=None), redis_check=fail_if_called)

    assert status.supabase.configured is False
    assert "SUPABASE_URL" in (status.supabase.detail or "")
    assert status.groq.configured is False
    assert status.groq.model == "openai/gpt-oss-120b"
    assert status.redis.configured is False


def test_integration_status_never_contains_secret_values() -> None:
    settings = Settings(
        _env_file=None,
        supabase_url="https://project.supabase.co",
        supabase_service_role_key="secret-service-key",
        groq_api_key="secret-groq-key",
        redis_url="redis://localhost:6379/0",
    )

    status = get_integration_status(settings, redis_check=lambda url: "ConnectionError: refused")
    dumped = status.model_dump_json()

    assert status.supabase.configured and status.groq.configured
    assert status.redis.configured is True and status.redis.reachable is False
    assert "secret-service-key" not in dumped
    assert "secret-groq-key" not in dumped


def test_ping_job() -> None:
    assert ping_job() == {"status": "ok", "service": "readybid-worker"}


def _uses_http2(client) -> bool:
    return bool(client._transport._pool._http2)


def test_supabase_clients_use_http1_with_separate_timeouts() -> None:
    """Regression: a shared HTTP/2 connection failed under concurrent API requests on
    Windows (httpx.ReadError WinError 10035), which made the checklist endpoint return 500.
    Building the clients makes no network calls."""
    settings = Settings(
        _env_file=None,
        supabase_url="https://project.supabase.co",
        supabase_service_role_key="test-service-role-key",
    )

    repo, storage = build_repository_and_storage(settings)

    repo_http = repo._client.postgrest.session
    storage_http = storage._bucket._client
    assert repo_http is not storage_http
    assert not _uses_http2(repo_http)
    assert not _uses_http2(storage_http)
    assert repo_http.timeout.read == REPOSITORY_TIMEOUT_SECONDS
    assert storage_http.timeout.read == STORAGE_TIMEOUT_SECONDS
