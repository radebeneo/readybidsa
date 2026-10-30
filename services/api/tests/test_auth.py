"""Access token verification. Tokens are signed locally with test keys (no network)."""

import time
from types import SimpleNamespace
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from readybid_api.auth import AuthError, AuthUnavailable, SupabaseTokenVerifier
from readybid_core.clients import NotConfigured
from readybid_core.config import Settings

SUPABASE_URL = "https://dev-fixture.supabase.co"
ISSUER = SUPABASE_URL + "/auth/v1"
SECRET = "dev-fixture-jwt-secret-that-is-long-enough-for-hs256"
USER = "22222222-2222-4222-8222-222222222222"


def claims(**overrides: Any) -> dict[str, Any]:
    now = int(time.time())
    base: dict[str, Any] = {
        "sub": USER,
        "aud": "authenticated",
        "iss": ISSUER,
        "role": "authenticated",
        "iat": now,
        "exp": now + 300,
        **overrides,
    }
    return {key: value for key, value in base.items() if value is not None}


def hs_verifier() -> SupabaseTokenVerifier:
    settings = Settings(_env_file=None, supabase_url=SUPABASE_URL, supabase_jwt_secret=SECRET)
    return SupabaseTokenVerifier(settings)


def test_valid_hs256_token_returns_user_id() -> None:
    token = jwt.encode(claims(), SECRET, algorithm="HS256")

    assert hs_verifier().verify(token) == USER


@pytest.mark.parametrize(
    "bad_claims",
    [
        {"exp": int(time.time()) - 120},  # expired beyond the leeway
        {"aud": "anon"},
        {"iss": "https://other-project.supabase.co/auth/v1"},
        {"role": "anon"},
        {"sub": None},
        {"sub": "not-a-uuid"},
        {"exp": None},
    ],
)
def test_hs256_token_with_bad_claims_is_rejected(bad_claims: dict[str, Any]) -> None:
    token = jwt.encode(claims(**bad_claims), SECRET, algorithm="HS256")

    with pytest.raises(AuthError):
        hs_verifier().verify(token)


def test_token_signed_with_another_secret_is_rejected() -> None:
    token = jwt.encode(claims(), SECRET + "-other", algorithm="HS256")

    with pytest.raises(AuthError):
        hs_verifier().verify(token)


def test_unsigned_and_garbage_tokens_are_rejected() -> None:
    unsigned = jwt.encode(claims(), None, algorithm="none")

    for token in (unsigned, "garbage", ""):
        with pytest.raises(AuthError):
            hs_verifier().verify(token)


class FakeJwks:
    def __init__(self, public_key: Any = None, error: Exception | None = None) -> None:
        self.public_key = public_key
        self.error = error

    def get_signing_key_from_jwt(self, token: str) -> Any:
        if self.error is not None:
            raise self.error
        return SimpleNamespace(key=self.public_key)


@pytest.fixture(scope="module")
def rsa_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def jwks_verifier(jwks: FakeJwks) -> SupabaseTokenVerifier:
    return SupabaseTokenVerifier(
        Settings(_env_file=None, supabase_url=SUPABASE_URL), jwks_client=jwks
    )


def test_valid_rs256_token_is_accepted_in_jwks_mode(rsa_key: rsa.RSAPrivateKey) -> None:
    token = jwt.encode(claims(), rsa_key, algorithm="RS256")

    assert jwks_verifier(FakeJwks(rsa_key.public_key())).verify(token) == USER


def test_jwks_mode_rejects_hs256_tokens(rsa_key: rsa.RSAPrivateKey) -> None:
    # Algorithm confusion: an HS256 token "signed" with the public key must not pass.
    public_pem = rsa_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    token = jwt.encode(claims(), SECRET, algorithm="HS256")

    with pytest.raises(AuthError):
        jwks_verifier(FakeJwks(public_pem)).verify(token)


def test_unknown_signing_key_is_rejected() -> None:
    jwks = FakeJwks(error=jwt.PyJWKClientError("Unable to find a signing key"))

    with pytest.raises(AuthError):
        jwks_verifier(jwks).verify("header.payload.signature")


def test_unreachable_jwks_is_a_service_error_not_an_auth_failure() -> None:
    jwks = FakeJwks(error=jwt.PyJWKClientConnectionError("timed out"))

    with pytest.raises(AuthUnavailable):
        jwks_verifier(jwks).verify("header.payload.signature")


def test_verifier_requires_supabase_url() -> None:
    with pytest.raises(NotConfigured, match="Integration not configured"):
        SupabaseTokenVerifier(Settings(_env_file=None))
