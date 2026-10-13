"""Trace identifiers and redacted logging.

Every request gets a trace ID (accepted from ``X-Trace-Id`` when it is a
well-formed token, generated otherwise). Generic log records pass through a
redaction filter so account numbers and similar values do not reach logs.
"""

from __future__ import annotations

import contextvars
import logging
import re
import uuid

_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_id", default=None)

_TRACE_ID_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")

# Long digit runs (account numbers, card-like numbers) and IFSC codes.
_REDACT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b\d{9,18}\b"),
    re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"),
)


def new_trace_id(candidate: str | None = None) -> str:
    if candidate and _TRACE_ID_RE.match(candidate):
        return candidate
    return uuid.uuid4().hex


def set_trace_id(value: str) -> contextvars.Token[str | None]:
    return _trace_id.set(value)


def reset_trace_id(token: contextvars.Token[str | None]) -> None:
    _trace_id.reset(token)


def current_trace_id() -> str | None:
    return _trace_id.get()


def redact(text: str) -> str:
    for pattern in _REDACT_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(str(record.msg))
        if record.args:
            record.args = tuple(redact(str(a)) for a in record.args)
        record.trace_id = current_trace_id() or "-"
        return True


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter())
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s trace=%(trace_id)s %(message)s")
    )
    root = logging.getLogger("finguard")
    root.handlers[:] = [handler]
    root.setLevel(level)
    root.propagate = False
