"""Reports which external integrations are configured.

Never includes secret values. Supabase and Groq are only checked for
configuration (no network call on every dashboard load). Redis is pinged with
a short timeout because the job queue is local infrastructure.
"""

from collections.abc import Callable

from pydantic import BaseModel
from redis import Redis
from redis.exceptions import RedisError

from readybid_core.config import Settings


class IntegrationState(BaseModel):
    configured: bool
    # None means reachability was not checked.
    reachable: bool | None = None
    detail: str | None = None


class GroqState(IntegrationState):
    model: str


class IntegrationsStatus(BaseModel):
    supabase: IntegrationState
    groq: GroqState
    redis: IntegrationState


RedisCheck = Callable[[str], str | None]


def check_redis(url: str, timeout_seconds: float = 0.5) -> str | None:
    """Ping Redis. Returns None on success, otherwise a short error message."""
    client = Redis.from_url(
        url, socket_connect_timeout=timeout_seconds, socket_timeout=timeout_seconds
    )
    try:
        client.ping()
        return None
    except (RedisError, OSError) as error:
        return f"{type(error).__name__}: {error}"
    finally:
        client.close()


def _missing(names: list[str]) -> str:
    return "Integration not configured: set " + ", ".join(names) + "."


def get_integration_status(
    settings: Settings, redis_check: RedisCheck = check_redis
) -> IntegrationsStatus:
    supabase_missing = [
        name
        for name, value in (
            ("SUPABASE_URL", settings.supabase_url),
            ("SUPABASE_SERVICE_ROLE_KEY", settings.supabase_service_role_key),
        )
        if value is None
    ]
    supabase = IntegrationState(
        configured=not supabase_missing,
        detail=_missing(supabase_missing) if supabase_missing else None,
    )

    groq = GroqState(
        configured=settings.groq_api_key is not None,
        model=settings.groq_model,
        detail=None if settings.groq_api_key is not None else _missing(["GROQ_API_KEY"]),
    )

    if settings.redis_url is None:
        redis = IntegrationState(configured=False, detail=_missing(["REDIS_URL"]))
    else:
        error = redis_check(settings.redis_url)
        redis = IntegrationState(
            configured=True,
            reachable=error is None,
            detail=None if error is None else f"Configured but not reachable ({error}).",
        )

    return IntegrationsStatus(supabase=supabase, groq=groq, redis=redis)
