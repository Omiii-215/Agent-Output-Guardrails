"""Action preflight rules (module M5). Pure over the frozen preflight snapshot."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.domain.outcomes import RuleResult, Severity
from backend.policies.engine import NoParams, RuleOutput, rule

MODULE = "payment_gateway"


@rule(
    "action.payload_integrity",
    version=1,
    module=MODULE,
    title="Frozen payload matches its server digest",
    severity=Severity.CRITICAL,
)
def payload_integrity(inputs: dict[str, Any], params: NoParams) -> RuleOutput:
    p = inputs["proposal"]
    if p["digest"] == p["recomputed_digest"]:
        return RuleOutput(RuleResult.PASS, "DIGEST_MATCHES", "Payload unchanged since proposal.")
    return RuleOutput(
        RuleResult.FAIL,
        "DIGEST_MISMATCH",
        "The stored payload no longer matches its digest.",
        observed={"digest": p["digest"], "recomputed": p["recomputed_digest"]},
    )


class ModeParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowed_modes: list[Literal["SIMULATED", "LIVE"]] = Field(default_factory=lambda: ["SIMULATED"])


@rule(
    "action.mode_allowed",
    version=1,
    module=MODULE,
    title="Execution mode is enabled",
    params=ModeParams,
    severity=Severity.CRITICAL,
)
def mode_allowed(inputs: dict[str, Any], params: ModeParams) -> RuleOutput:
    mode = inputs["proposal"]["mode"]
    if mode in params.allowed_modes:
        return RuleOutput(RuleResult.PASS, "MODE_ALLOWED", f"{mode} execution is enabled.")
    return RuleOutput(
        RuleResult.FAIL,
        "MODE_NOT_ALLOWED",
        f"{mode} execution is not enabled for this organization.",
        expected={"allowed_modes": params.allowed_modes},
    )


@rule(
    "action.not_halted",
    version=1,
    module=MODULE,
    title="Emergency stop is not active",
    severity=Severity.CRITICAL,
)
def not_halted(inputs: dict[str, Any], params: NoParams) -> RuleOutput:
    controls = inputs.get("controls", {})
    if controls.get("halted"):
        return RuleOutput(
            RuleResult.FAIL,
            "EMERGENCY_STOP",
            "Financial actions are halted for this organization.",
            observed={"reason": controls.get("reason")},
        )
    return RuleOutput(RuleResult.PASS, "NOT_HALTED", "Actions are not halted.")


@rule(
    "action.source_current",
    version=1,
    module=MODULE,
    title="Underlying review is complete and current",
    severity=Severity.CRITICAL,
)
def source_current(inputs: dict[str, Any], params: NoParams) -> RuleOutput:
    source = inputs.get("source", {})
    evaluation = inputs.get("document_evaluation")
    if source.get("stale"):
        return RuleOutput(
            RuleResult.FAIL,
            "SOURCE_CHANGED",
            "The records this proposal was built from have changed.",
            observed={"changed": source.get("changed", [])},
        )
    if not evaluation:
        return RuleOutput(
            RuleResult.UNKNOWN, "NO_DOCUMENT_EVALUATION", "The source was never evaluated."
        )
    if not evaluation.get("current"):
        return RuleOutput(
            RuleResult.FAIL, "EVALUATION_STALE", "A newer evaluation or input exists."
        )
    outcome, unresolved = evaluation.get("outcome"), int(evaluation.get("unresolved", 0))
    if outcome == "PASS" or (outcome == "REVIEW" and unresolved == 0):
        return RuleOutput(RuleResult.PASS, "SOURCE_ELIGIBLE", "Review complete.")
    return RuleOutput(
        RuleResult.FAIL,
        "SOURCE_NOT_ELIGIBLE",
        "The underlying evaluation has unresolved findings.",
        observed={"outcome": outcome, "unresolved": unresolved},
    )


@rule(
    "action.beneficiary_verified",
    version=1,
    module=MODULE,
    title="Payee is the current, verified bank account",
    severity=Severity.CRITICAL,
)
def beneficiary_verified(inputs: dict[str, Any], params: NoParams) -> RuleOutput:
    ben = inputs.get("beneficiary") or {}
    if not ben:
        return RuleOutput(RuleResult.UNKNOWN, "BENEFICIARY_MISSING", "No payee on record.")
    if not ben.get("matches_current"):
        return RuleOutput(
            RuleResult.FAIL,
            "BENEFICIARY_CHANGED",
            "The vendor's bank details changed after this proposal was created.",
        )
    if ben.get("verification_status") != "VERIFIED":
        return RuleOutput(
            RuleResult.FAIL, "BENEFICIARY_UNVERIFIED", "Payee bank details are not verified."
        )
    return RuleOutput(RuleResult.PASS, "BENEFICIARY_OK", "Payee verified and current.")


@rule(
    "action.no_duplicate_execution",
    version=1,
    module=MODULE,
    title="No other payment exists for the same obligation",
    severity=Severity.CRITICAL,
)
def no_duplicate(inputs: dict[str, Any], params: NoParams) -> RuleOutput:
    dup = inputs.get("duplicates", {})
    others, executed = dup.get("other_active_proposals", []), dup.get("executed", [])
    if executed or others:
        return RuleOutput(
            RuleResult.FAIL,
            "DUPLICATE_ACTION",
            "Another proposal or payment already exists for this obligation.",
            observed={"other_active_proposals": others, "executed": executed},
        )
    return RuleOutput(RuleResult.PASS, "NO_DUPLICATE_ACTION", "No other payment found.")


@rule(
    "action.within_spend_limit",
    version=1,
    module=MODULE,
    title="Amount fits the remaining spend limit",
    severity=Severity.CRITICAL,
)
def within_spend_limit(inputs: dict[str, Any], params: NoParams) -> RuleOutput:
    amount = int(inputs["proposal"]["amount_minor"])
    currency = inputs["proposal"]["currency"]
    buckets = [b for b in inputs.get("spend", []) if b["currency"] == currency]
    if not buckets:
        return RuleOutput(
            RuleResult.UNKNOWN,
            "NO_SPEND_LIMIT",
            f"No spend limit is configured for {currency}.",
        )
    for b in buckets:
        available = int(b["limit_minor"]) - int(b["committed_minor"]) - int(b["reserved_minor"])
        if amount > available:
            return RuleOutput(
                RuleResult.FAIL,
                "SPEND_LIMIT_EXCEEDED",
                f"The {b['window'].lower()} limit has insufficient remaining capacity.",
                observed={"amount_minor": amount, "available_minor": available},
                expected={"limit_minor": b["limit_minor"]},
            )
    return RuleOutput(RuleResult.PASS, "WITHIN_LIMIT", "Amount fits the remaining limit.")
