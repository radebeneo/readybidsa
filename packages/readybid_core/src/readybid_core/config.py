"""Runtime settings shared by the API and worker.

Values come from environment variables or a `.env` file in the current
working directory (run commands from the repository root). Empty values are
treated as unset, so placeholder-only `.env` files report
"Integration not configured" instead of failing.
"""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# llama-3.3-70b-versatile was retired on Groq's Free and Developer tiers on 2026-08-16.
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"

# RQ's scheduler polls Redis every second by default. Each poll sends several commands,
# which would use up a hosted Redis command quota (e.g. Upstash free tier) within days.
DEFAULT_RQ_SCHEDULER_INTERVAL_SECONDS = 10


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_env: str = "development"

    # Comma-separated list of browser origins allowed to call the API.
    cors_origins: str = "http://localhost:3000"

    supabase_url: str | None = None
    supabase_service_role_key: SecretStr | None = None
    # Optional legacy HS256 JWT secret. When unset, access tokens are verified against the
    # project's JWKS endpoint (asymmetric signing keys).
    supabase_jwt_secret: SecretStr | None = None
    supabase_storage_bucket: str = "documents"

    groq_api_key: SecretStr | None = None
    groq_model: str = DEFAULT_GROQ_MODEL

    redis_url: str | None = None

    # Upload limits. Keep max_upload_bytes <= the storage bucket's file_size_limit.
    max_upload_bytes: int = Field(default=15 * 1024 * 1024, gt=0)
    max_pdf_pages: int = Field(default=100, gt=0)

    # Signed URLs for downloads and source views are issued only after a permission check.
    signed_url_ttl_seconds: int = Field(default=120, ge=10, le=3600)

    # Model call bounds.
    llm_timeout_seconds: float = Field(default=60.0, gt=0)
    llm_max_completion_tokens: int = Field(default=4096, gt=0)
    llm_max_repair_attempts: int = Field(default=2, ge=0, le=2)
    llm_max_requirements_per_group: int = Field(default=40, gt=0)

    # Analysis strategy: bounded page groups across the whole document.
    analysis_pages_per_group: int = Field(default=4, gt=0)
    analysis_max_group_chars: int = Field(default=24_000, gt=0)
    analysis_boundary_context_chars: int = Field(default=600, ge=0)

    # Evidence matching bounds. Every batch sees the same bounded evidence text; segments
    # cut to fit are recorded on the run and reported as incomplete coverage.
    matching_requirements_per_batch: int = Field(default=6, gt=0, le=20)
    matching_max_evidence_chars: int = Field(default=24_000, gt=0)
    matching_max_segment_chars: int = Field(default=4_000, gt=0)
    max_evidence_documents_per_analysis: int = Field(default=10, gt=0, le=20)

    # Background job bounds.
    job_timeout_seconds: int = Field(default=900, gt=0)
    job_max_retries: int = Field(default=2, ge=0)
    # How often the worker's scheduler moves due retries back onto the queue. Capped at 60 s
    # so retry delays (see readybid_core.jobs) stay close to their configured intervals.
    rq_scheduler_interval_seconds: int = Field(
        default=DEFAULT_RQ_SCHEDULER_INTERVAL_SECONDS, ge=1, le=60
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
