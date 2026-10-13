"""OIDC bearer-token verification.

The identity provider (Cognito in the pilot) proves who the caller is. It does
not establish organization membership or financial authority; the backend
checks membership separately on every request.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import jwt

from backend.errors import Unauthenticated

KeyResolver = Callable[[str], Any]


class OidcVerifier:
    def __init__(
        self,
        issuer: str,
        audience: str,
        *,
        key_resolver: KeyResolver | None = None,
        algorithms: tuple[str, ...] = ("RS256",),
        leeway_seconds: int = 30,
    ):
        self.issuer = issuer
        self.audience = audience
        self.algorithms = list(algorithms)
        self.leeway = leeway_seconds
        if key_resolver is None:
            jwks = jwt.PyJWKClient(f"{issuer.rstrip('/')}/.well-known/jwks.json")
            key_resolver = lambda token: jwks.get_signing_key_from_jwt(token).key  # noqa: E731
        self._resolve_key = key_resolver

    def verify(self, token: str) -> str:
        """Return the verified ``sub`` claim or raise ``Unauthenticated``."""
        try:
            key = self._resolve_key(token)
            claims = jwt.decode(
                token,
                key,
                algorithms=self.algorithms,
                audience=self.audience,
                issuer=self.issuer,
                leeway=self.leeway,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
        except jwt.PyJWTError as exc:
            raise Unauthenticated("Invalid or expired token", code="INVALID_TOKEN") from exc
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise Unauthenticated("Token has no subject", code="INVALID_TOKEN")
        return subject
