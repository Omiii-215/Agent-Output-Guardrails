"""Product template for payment preflight and approval requirements.

Limits, tiers and expiry are example settings for the simulator, not
recommendations; each customer configures and republishes its own version.
"""

from __future__ import annotations

import copy
from typing import Any

_RULES = [
    "action.payload_integrity",
    "action.not_halted",
    "action.source_current",
    "action.beneficiary_verified",
    "action.no_duplicate_execution",
    "action.within_spend_limit",
]

_OK: dict[str, Any] = {
    "proposal": {
        "digest": "sha256:a",
        "recomputed_digest": "sha256:a",
        "mode": "SIMULATED",
        "amount_minor": "590000",
        "currency": "INR",
    },
    "controls": {"halted": False},
    "source": {"stale": False},
    "document_evaluation": {"outcome": "PASS", "unresolved": 0, "current": True},
    "beneficiary": {"matches_current": True, "verification_status": "VERIFIED"},
    "duplicates": {"other_active_proposals": [], "executed": []},
    "spend": [
        {
            "currency": "INR",
            "window": "DAY",
            "limit_minor": "250000000",
            "committed_minor": "0",
            "reserved_minor": "0",
        }
    ],
}


def _with(path: str, value: Any) -> dict[str, Any]:
    data = copy.deepcopy(_OK)
    *parents, leaf = path.split(".")
    target = data
    for key in parents:
        target = target[key]
    target[leaf] = value
    return data


PAYMENT_PREFLIGHT: dict[str, Any] = {
    "policy_code": "payment-preflight",
    "module": "payment_gateway",
    "description": "Controls every proposed payment before approval and again before execution.",
    "rules": [
        {
            "code": "action.mode_allowed",
            "version": 1,
            "parameters": {"allowed_modes": ["SIMULATED"]},
            "on_fail": "BLOCK",
        },
        *[
            {"code": code, "version": 1, "on_fail": "BLOCK", "on_unknown": "BLOCK"}
            for code in _RULES
        ],
    ],
    "approval": {
        "required_role": "finance_approver",
        "count": 1,
        "tiers": [{"above_minor": 10_000_000, "count": 2}],
        "maker_can_approve": False,
        "expiry_minutes": 120,
    },
    "spend_limits": [{"currency": "INR", "window": "DAY", "limit_minor": 250_000_000}],
    "scenarios": [
        {"name": "eligible payment", "inputs": _OK, "expected_outcome": "PASS"},
        {
            "name": "live mode blocked",
            "inputs": _with("proposal.mode", "LIVE"),
            "expected_outcome": "BLOCK",
        },
        {
            "name": "emergency stop blocks",
            "inputs": _with("controls.halted", True),
            "expected_outcome": "BLOCK",
        },
        {
            "name": "changed payee blocks",
            "inputs": _with("beneficiary.matches_current", False),
            "expected_outcome": "BLOCK",
        },
        {
            "name": "over limit blocks",
            "inputs": _with("proposal.amount_minor", "250000001"),
            "expected_outcome": "BLOCK",
        },
    ],
}
