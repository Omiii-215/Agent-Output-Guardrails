"""Time and identifier helpers. System timestamps are timezone-aware UTC."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def ensure_aware(value: datetime) -> datetime:
    """Treat naive datetimes (e.g. read back from SQLite) as UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def new_id() -> uuid.UUID:
    return uuid.uuid4()
