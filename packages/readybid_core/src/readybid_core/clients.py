"""Builds real integration clients from settings. Server-only: uses secret keys.

Missing configuration raises `NotConfigured` with the "Integration not configured"
message. Callers surface that message instead of falling back to placeholder data.
"""

from typing import Any

from readybid_core.config import Settings
from readybid_core.integrations import _missing
from readybid_core.llm import GroqProvider, LLMProvider
from readybid_core.repository import SupabaseRepository
from readybid_core.storage import SupabaseStorage


class NotConfigured(RuntimeError):
    pass


REPOSITORY_TIMEOUT_SECONDS = 30
STORAGE_TIMEOUT_SECONDS = 60


def http_client(timeout_seconds: float) -> Any:
    """An HTTP/1.1 client with its own connection pool.

    supabase-py otherwise creates one HTTP/2 connection per client. The API shares that
    client across FastAPI's worker threads, and concurrent reads on the shared HTTP/2
    connection failed on Windows with `httpx.ReadError: [WinError 10035]`. HTTP/1.1 gives
    each concurrent request its own pooled connection.
    """
    import httpx

    return httpx.Client(http2=False, timeout=timeout_seconds, follow_redirects=True)


def supabase_client(
    settings: Settings, *, timeout_seconds: float = REPOSITORY_TIMEOUT_SECONDS
) -> Any:
    missing = [
        name
        for name, value in (
            ("SUPABASE_URL", settings.supabase_url),
            ("SUPABASE_SERVICE_ROLE_KEY", settings.supabase_service_role_key),
        )
        if value is None
    ]
    if missing:
        raise NotConfigured(_missing(missing))
    from supabase import create_client
    from supabase.lib.client_options import SyncClientOptions

    assert settings.supabase_url is not None
    assert settings.supabase_service_role_key is not None
    # With an injected httpx client, supabase-py ignores postgrest_client_timeout and
    # storage_client_timeout, so the timeout is set on the client itself.
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key.get_secret_value(),
        options=SyncClientOptions(
            auto_refresh_token=False,
            persist_session=False,
            httpx_client=http_client(timeout_seconds),
        ),
    )


def build_repository_and_storage(settings: Settings) -> tuple[SupabaseRepository, SupabaseStorage]:
    # Separate clients keep the existing timeouts: 30 s for queries, 60 s for file transfers.
    repo_client = supabase_client(settings, timeout_seconds=REPOSITORY_TIMEOUT_SECONDS)
    storage_client = supabase_client(settings, timeout_seconds=STORAGE_TIMEOUT_SECONDS)
    return (
        SupabaseRepository(repo_client),
        SupabaseStorage(storage_client, settings.supabase_storage_bucket),
    )


def build_llm_provider(settings: Settings) -> LLMProvider:
    if settings.groq_api_key is None:
        raise NotConfigured(_missing(["GROQ_API_KEY"]))
    return GroqProvider(
        api_key=settings.groq_api_key.get_secret_value(),
        model=settings.groq_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_completion_tokens=settings.llm_max_completion_tokens,
    )
