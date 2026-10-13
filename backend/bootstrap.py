"""Import modules that register rules, job handlers, event consumers and case
detail providers. The API and the worker both call ``load()`` at start-up."""

from __future__ import annotations

import importlib

_MODULES = (
    "backend.policies.rules_common",
    "backend.modules.invoices.rules",
    "backend.modules.invoices.handlers",
    "backend.modules.invoices.extraction",
    "backend.ai.explanations",
    "backend.actions.rules",
    "backend.actions.proposals",
    "backend.actions.handlers",
    "backend.approvals.service",
    "backend.actions.execution",
    "backend.actions.execution_handlers",
    "backend.modules.invoices.action_source",
    "backend.modules.reconciliation.handlers",
    "backend.audit.handlers",
)


def load() -> None:
    for name in _MODULES:
        importlib.import_module(name)
