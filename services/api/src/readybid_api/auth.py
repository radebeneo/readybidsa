"""Verifies Supabase access tokens.

Two modes, chosen by configuration:

* JWKS (default): the project's asymmetric signing keys, fetched from
  ``<SUPABASE_URL>/auth/v1/.well-known/jwks.json`` and cached. Only RS256 and ES256 are
  accepted.
* HS256: used only when ``SUPABASE_JWT_SECRET`` is set (legacy shared-secret projects).

The accepted algorithms are fixed per mode, so a token cannot choose how it is verified.
A token must be signed by this project, have audience "authenticated", come from this
project's auth server, carry ``exp`` and ``sub``, and have role "authenticated". The user
id is the only thing taken from it: organisation membership is always looked up in the
database (see ``readybid_core.authz``).
"""

import uuid
from typing import Any, Protocol

import jwt

from readybid_core.clients import NotConfigured
from readybid_core.config import Settings
from readybid_core.integrations import _missing

AUDIENCE = "authenticated"
ASYMMETRIC_ALGORITHMS = ["RS256", "ES256"]
# Small allowance for clock differences between Supabase and this server.
LEEWAY_SECONDS = 30


class AuthError(Exception):
    """The token is missing, malformed, expired or not issued for this project."""


class AuthUnavailable(Exception):
    """The signing keys could not be fetched. This is not the caller's fault."""


class TokenVerifier(Protocol):
    def verify(self, token: str) -> str:
        """Return the verified user id or raise AuthError."""
        ...


class SigningKeySource(Protocol):
    def get_signing_key_from_jwt(self, token: str) -> Any: ...


class SupabaseTokenVerifier:
    def __init__(self, settings: Settings, *, jwks_client: SigningKeySource | None = None) -> None:
        if settings.supabase_url is None:
            raise NotConfigured(_missing(["SUPABASE_URL"]))
        self._issuer = settings.supabase_url.rstrip("/") + "/auth/v1"
        secret = settings.supabase_jwt_secret
        self._secret = secret.get_secret_value() if secret is not None else None
        self._jwks: SigningKeySource | None = None
        if self._secret is None:
            self._jwks = jwks_client or jwt.PyJWKClient(
                f"{self._issuer}/.well-known/jwks.json", cache_keys=True, lifespan=300, timeout=5
            )

    def _key(self, token: str) -> tuple[Any, list[str]]:
        if self._secret is not None:
            return self._secret, ["HS256"]
        assert self._jwks is not None
        try:
            return self._jwks.get_signing_key_from_jwt(token).key, ASYMMETRIC_ALGORITHMS
        except jwt.PyJWKClientConnectionError:
            raise AuthUnavailable("Could not fetch the token signing keys.") from None

    def verify(self, token: str) -> str:
        try:
            key, algorithms = self._key(token)
            claims = jwt.decode(
                token,
                key,
                algorithms=algorithms,
                audience=AUDIENCE,
                issuer=self._issuer,
                leeway=LEEWAY_SECONDS,
                options={"require": ["exp", "sub", "aud", "iss"]},
            )
        except jwt.PyJWTError:
            raise AuthError("Invalid or expired access token.") from None
        return user_id_from_claims(claims)


def user_id_from_claims(claims: dict[str, Any]) -> str:
    if claims.get("role") != "authenticated":
        raise AuthError("Invalid or expired access token.")
    try:
        return str(uuid.UUID(str(claims.get("sub"))))
    except ValueError:
        raise AuthError("Invalid or expired access token.") from None
