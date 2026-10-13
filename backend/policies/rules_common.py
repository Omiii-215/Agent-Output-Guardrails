"""Rules shared by every module."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.domain.outcomes import RuleResult, Severity
from backend.policies.engine import RuleOutput, rule


class RequiredFieldsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: list[str] = Field(min_length=1, max_length=40)
    # ENTERED = typed by a person; EXTRACTED = machine-read, needs confirmation.
    accepted_statuses: list[Literal["VERIFIED", "ENTERED", "EXTRACTED"]] = ["VERIFIED"]


@rule(
    "evidence.required_fields",
    version=1,
    module="*",
    title="Required fields are present and verified",
    params=RequiredFieldsParams,
    severity=Severity.CRITICAL,
)
def required_fields(inputs: dict[str, Any], params: RequiredFieldsParams) -> RuleOutput:
    fields = inputs.get("fields", {})
    missing, unverified, refs = [], [], []
    for name in params.fields:
        entry = fields.get(name)
        if not entry or entry.get("value") in (None, ""):
            missing.append(name)
            continue
        if entry.get("status") not in params.accepted_statuses:
            unverified.append(name)
        refs.extend(entry.get("evidence_refs", []))
    if missing or unverified:
        return RuleOutput(
            RuleResult.UNKNOWN,
            "REQUIRED_FIELDS_MISSING" if missing else "REQUIRED_FIELDS_UNVERIFIED",
            "Required fields must be present and confirmed by a reviewer before evaluation.",
            observed={"missing": missing, "unverified": unverified},
            expected={"fields": params.fields},
            evidence_refs=tuple(refs),
        )
    return RuleOutput(
        RuleResult.PASS,
        "REQUIRED_FIELDS_PRESENT",
        "All required fields are present.",
        evidence_refs=tuple(refs),
    )
