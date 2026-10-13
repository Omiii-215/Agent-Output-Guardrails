"""Canonical serialisation and digests (algorithm ``canon-v1``).

Rules: object keys sorted; no insignificant whitespace; UTF-8; integers and
decimals rendered as strings (decimals normalised so ``1.50`` == ``1.5``);
timestamps must be timezone-aware and are rendered in UTC; floats are rejected.
The server computes every digest. Clients never supply one (ADR 0002).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

CANON_ALGORITHM = "canon-v1"


class CanonicalizationError(TypeError):
    pass


def _normalise(value: Any) -> Any:
    if value is None or isinstance(value, bool | str):
        return value
    if isinstance(value, Enum):
        return _normalise(value.value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        raise CanonicalizationError("Floats are not permitted in canonical payloads")
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise CanonicalizationError("Non-finite decimal")
        normalised = value.normalize()
        text = format(normalised, "f")
        return "0" if text in ("-0", "0") else text
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise CanonicalizationError("Timestamps must be timezone-aware")
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalizationError("Object keys must be strings")
            out[key] = _normalise(item)
        return out
    if isinstance(value, list | tuple):
        return [_normalise(item) for item in value]
    if hasattr(value, "model_dump"):
        return _normalise(value.model_dump(mode="python"))
    raise CanonicalizationError(f"Unsupported type {type(value).__name__}")


def to_jsonable(value: Any) -> Any:
    """JSON-safe form used for stored payloads (same rules as the canonical form)."""
    return _normalise(value)


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        _normalise(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    """Return ``sha256:<hex>`` of the canonical form of ``value``."""
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()
