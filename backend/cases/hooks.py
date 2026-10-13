"""Synchronous hooks for material input changes.

When a module changes the facts a case was evaluated on (a corrected invoice,
a new payee version), dependent records such as action proposals must be
invalidated in the same transaction. Modules register handlers here instead of
importing each other.
"""

from __future__ import annotations

from collections.abc import Callable

from backend.cases.models import Case
from backend.persistence.database import TenantSession

Hook = Callable[[TenantSession, Case, str], None]

_HOOKS: list[Hook] = []


def on_inputs_changed(hook: Hook) -> Hook:
    _HOOKS.append(hook)
    return hook


def notify_inputs_changed(tx: TenantSession, case: Case, reason: str) -> None:
    for hook in _HOOKS:
        hook(tx, case, reason)
