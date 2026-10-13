"""Case detail composition.

The shared platform renders a case; workflow modules contribute sections
(invoice fields, findings, proposals …) and the IDs of related objects whose
audit events belong in the case history.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from backend.cases.models import Case
from backend.persistence.database import TenantSession


@dataclass
class DetailSection:
    data: dict[str, Any] = field(default_factory=dict)
    related_ids: list[uuid.UUID] = field(default_factory=list)


Provider = Callable[[TenantSession, Case], DetailSection]

_PROVIDERS: dict[str | None, list[Provider]] = {}


def register(module: str | None, provider: Provider) -> None:
    """Register a provider for one module, or ``None`` for every case."""
    _PROVIDERS.setdefault(module, []).append(provider)


def compose(tx: TenantSession, case: Case) -> DetailSection:
    result = DetailSection()
    for provider in (*_PROVIDERS.get(None, []), *_PROVIDERS.get(case.module, [])):
        section = provider(tx, case)
        result.data.update(section.data)
        result.related_ids.extend(section.related_ids)
    return result
