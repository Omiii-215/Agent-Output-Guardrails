"""Domain errors with stable, machine-readable reason codes.

Route handlers translate these into structured HTTP responses. The status
codes follow the LLD: 401 unauthenticated, 403 forbidden, 404 not found (also
used for cross-tenant objects), 409 revision/state conflicts, 422 invalid
input, 429 rate/cost limits.
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    status_code: int = 400
    default_code: str = "BAD_REQUEST"

    def __init__(self, message: str, *, code: str | None = None, details: Any = None):
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.details = details


class Unauthenticated(DomainError):
    status_code = 401
    default_code = "UNAUTHENTICATED"


class Forbidden(DomainError):
    status_code = 403
    default_code = "FORBIDDEN"


class NotFound(DomainError):
    status_code = 404
    default_code = "NOT_FOUND"


class Conflict(DomainError):
    status_code = 409
    default_code = "CONFLICT"


class InvalidInput(DomainError):
    status_code = 422
    default_code = "INVALID_INPUT"


class RateLimited(DomainError):
    status_code = 429
    default_code = "RATE_LIMITED"
