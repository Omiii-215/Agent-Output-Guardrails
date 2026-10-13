"""Declarative policy documents (LLD §5).

Policies are typed configuration validated with strict Pydantic models. They
select reviewed rule functions and set bounded parameters; customers never
submit code, SQL or free-form expressions.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.domain.money import CURRENCY_EXPONENTS
from backend.domain.outcomes import Outcome

Effect = Literal["BLOCK", "REVIEW", "INDETERMINATE"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RuleConfig(StrictModel):
    code: str = Field(pattern=r"^[a-z_]+\.[a-z_]+$")
    version: int = Field(ge=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    on_fail: Literal["BLOCK", "REVIEW"]
    on_unknown: Effect = "INDETERMINATE"


class ApprovalTier(StrictModel):
    above_minor: int = Field(ge=0)
    count: int = Field(ge=1, le=5)


class ApprovalConfig(StrictModel):
    required_role: Literal["finance_approver"] = "finance_approver"
    count: int = Field(default=1, ge=1, le=5)
    tiers: list[ApprovalTier] = Field(default_factory=list)
    maker_can_approve: bool = False
    expiry_minutes: int = Field(default=120, ge=5, le=7 * 24 * 60)

    def approvals_required(self, amount_minor: int) -> int:
        required = self.count
        for tier in self.tiers:
            if amount_minor > tier.above_minor:
                required = max(required, tier.count)
        return required


class SpendLimit(StrictModel):
    currency: str
    window: Literal["DAY", "MONTH"] = "DAY"
    limit_minor: int = Field(gt=0)

    @field_validator("currency")
    @classmethod
    def _currency(cls, value: str) -> str:
        if value not in CURRENCY_EXPONENTS:
            raise ValueError(f"Unsupported currency '{value}'")
        return value


class Scenario(StrictModel):
    """A regression example run before publishing."""

    name: str = Field(min_length=1, max_length=200)
    inputs: dict[str, Any]
    expected_outcome: Outcome


class PolicyDocument(StrictModel):
    schema_version: Literal[1] = 1
    policy_code: str = Field(pattern=r"^[a-z0-9-]{3,60}$")
    module: str
    description: str = ""
    rounding: Literal["HALF_UP", "HALF_EVEN"] = "HALF_UP"
    rules: list[RuleConfig] = Field(min_length=1, max_length=50)
    approval: ApprovalConfig | None = None
    spend_limits: list[SpendLimit] = Field(default_factory=list)
    scenarios: list[Scenario] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def _unique_rules(self) -> PolicyDocument:
        codes = [r.code for r in self.rules]
        if len(codes) != len(set(codes)):
            raise ValueError("Each rule may appear once per policy")
        return self
