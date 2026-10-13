"""Short-lived, HMAC-signed object grants.

A grant authorises one operation (upload or download) on one object of one
organization until it expires. The API issues a grant only after checking the
caller's membership and permission, mirroring S3 presigned URLs. Tokens carry
identifiers only, never personal data.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass
from typing import Literal

from backend.errors import Forbidden

Operation = Literal["upload", "download"]


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


@dataclass(frozen=True)
class Grant:
    organization_id: uuid.UUID
    object_key: str
    document_version_id: uuid.UUID
    operation: Operation
    expires_at: int
    max_bytes: int | None = None


class GrantSigner:
    def __init__(self, secret: str, ttl_seconds: int):
        self._secret = secret.encode()
        self.ttl = ttl_seconds

    def _sign(self, body: str) -> str:
        return _b64(hmac.new(self._secret, body.encode(), hashlib.sha256).digest())

    def issue(
        self,
        organization_id: uuid.UUID,
        object_key: str,
        document_version_id: uuid.UUID,
        operation: Operation,
        *,
        max_bytes: int | None = None,
        now: float | None = None,
    ) -> tuple[str, int]:
        expires = int((now if now is not None else time.time()) + self.ttl)
        body = _b64(
            json.dumps(
                {
                    "o": str(organization_id),
                    "k": object_key,
                    "d": str(document_version_id),
                    "op": operation,
                    "exp": expires,
                    "max": max_bytes,
                },
                separators=(",", ":"),
            ).encode()
        )
        return f"{body}.{self._sign(body)}", expires

    def verify(self, token: str, operation: Operation, *, now: float | None = None) -> Grant:
        try:
            body, signature = token.split(".", 1)
        except ValueError:
            raise Forbidden("Invalid grant", code="INVALID_GRANT") from None
        if not hmac.compare_digest(signature, self._sign(body)):
            raise Forbidden("Invalid grant", code="INVALID_GRANT")
        data = json.loads(_unb64(body))
        if data["op"] != operation:
            raise Forbidden("Grant does not permit this operation", code="INVALID_GRANT")
        if data["exp"] < (now if now is not None else time.time()):
            raise Forbidden("Grant expired", code="GRANT_EXPIRED")
        return Grant(
            organization_id=uuid.UUID(data["o"]),
            object_key=data["k"],
            document_version_id=uuid.UUID(data["d"]),
            operation=operation,
            expires_at=data["exp"],
            max_bytes=data.get("max"),
        )
