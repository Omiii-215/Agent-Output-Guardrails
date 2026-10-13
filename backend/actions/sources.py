"""Workflow modules describe the facts behind a proposed payment.

The gateway is shared; each module registers a source that resolves its own
tenant-owned records into ``PaymentFacts`` and reports whether those records
have changed since a proposal was frozen.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from backend.cases.models import Case
from backend.domain.money import Money
from backend.errors import InvalidInput
from backend.persistence.database import TenantSession


@dataclass(frozen=True)
class PaymentFacts:
    expected_amount: Money
    vendor_id: uuid.UUID
    beneficiary: dict[str, Any] | None  # version id, revision, fingerprint, ifsc, status
    subject: dict[str, Any]  # e.g. invoice id/version/number
    document_evaluation: dict[str, Any] | None  # id, outcome, unresolved, current
    source_revisions: dict[str, Any]
    executed_references: list[dict[str, Any]] = field(default_factory=list)


Source = Callable[[TenantSession, Case], PaymentFacts]

_SOURCES: dict[str, Source] = {}


def register(module: str, source: Source) -> None:
    _SOURCES[module] = source


def facts_for(tx: TenantSession, case: Case) -> PaymentFacts:
    source = _SOURCES.get(case.module)
    if source is None:
        raise InvalidInput(
            f"Module '{case.module}' cannot propose payments", code="ACTIONS_UNSUPPORTED"
        )
    return source(tx, case)
