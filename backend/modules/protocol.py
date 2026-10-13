"""Contract every workflow module implements (LLD §1).

Modules return structured facts and findings; presentation, notifications,
approvals and execution belong to the shared platform. ``evaluate`` has no
external side effects: external data is fetched and recorded before the
snapshot is built.
"""

from __future__ import annotations

from typing import Any, Protocol

from backend.cases.models import Case
from backend.persistence.database import TenantSession
from backend.policies.engine import EvaluationResult
from backend.policies.schema import PolicyDocument


class ModuleEvaluator(Protocol):
    module: str

    def validate_inputs(self, inputs: dict[str, Any]) -> list[str]:
        """Return problems with the normalised inputs (empty when valid)."""

    def build_snapshot(self, tx: TenantSession, case: Case) -> tuple[dict, dict]:
        """Frozen inputs plus the source revisions they were read from."""

    def evaluate(self, snapshot: dict[str, Any], policy: PolicyDocument) -> EvaluationResult:
        """Pure, deterministic evaluation of a frozen snapshot."""
