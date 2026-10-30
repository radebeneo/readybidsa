from fastapi.testclient import TestClient

from readybid_api.main import create_app
from readybid_core.config import Settings


def make_client(**overrides: str) -> TestClient:
    settings = Settings(_env_file=None, cors_origins="http://localhost:3000", **overrides)
    return TestClient(create_app(settings))


def test_health() -> None:
    response = make_client().get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "readybid-api", "version": "0.1.0"}


def test_integration_status_when_nothing_configured() -> None:
    response = make_client().get("/integrations/status")

    assert response.status_code == 200
    body = response.json()
    assert body["supabase"]["configured"] is False
    assert body["groq"]["configured"] is False
    assert body["groq"]["model"] == "openai/gpt-oss-120b"
    assert body["redis"]["configured"] is False
    assert "Integration not configured" in body["redis"]["detail"]


def test_cors_allows_configured_origin() -> None:
    response = make_client().options(
        "/health",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_rejects_unknown_origin() -> None:
    response = make_client().get("/health", headers={"Origin": "https://evil.example"})

    assert "access-control-allow-origin" not in response.headers
