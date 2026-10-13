"""Deterministic invoice checks. Each rule is pure over the frozen snapshot."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.domain.money import Money, MoneyError, line_amount, parse_minor
from backend.domain.outcomes import RuleResult, Severity
from backend.policies.engine import NoParams, RuleOutput, rule

MODULE = "invoices"


class Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TotalParams(Params):
    tolerance_minor: int = Field(default=0, ge=0, le=10_000)


@rule(
    "invoice.total_matches_lines",
    version=1,
    module=MODULE,
    title="Invoice total equals its line items",
    params=TotalParams,
    severity=Severity.CRITICAL,
)
def total_matches_lines(inputs: dict[str, Any], params: TotalParams) -> RuleOutput:
    inv = inputs.get("invoice", {})
    lines = inv.get("lines") or []
    currency = inv.get("currency")
    if not lines or inv.get("total_minor") is None or not currency:
        return RuleOutput(
            RuleResult.UNKNOWN,
            "LINES_OR_TOTAL_MISSING",
            "Line items, currency and the stated total are needed to check arithmetic.",
        )
    rounding = inputs.get("rounding", "HALF_UP")
    try:
        computed = Money.zero(currency)
        for line in lines:
            computed = computed + line_amount(
                line["quantity"],
                line["unit_price"],
                currency,
                tax_rate=line.get("tax_rate"),
                rounding=rounding,
            )
        stated = Money(parse_minor(inv["total_minor"]), currency)
    except (MoneyError, KeyError) as exc:
        return RuleOutput(RuleResult.UNKNOWN, "LINES_UNPARSEABLE", f"Line items invalid: {exc}")
    diff = computed.abs_diff(stated)
    observed = {"computed_total_minor": computed.minor, "stated_total_minor": stated.minor}
    if diff <= params.tolerance_minor:
        return RuleOutput(RuleResult.PASS, "TOTAL_MATCHES", "Total equals line items.", observed)
    return RuleOutput(
        RuleResult.FAIL,
        "TOTAL_MISMATCH",
        f"Line items add up to {computed.format()} but the invoice states {stated.format()}.",
        observed={**observed, "difference_minor": diff},
        expected={"tolerance_minor": params.tolerance_minor},
        evidence_refs=tuple(inputs.get("fields", {}).get("total", {}).get("evidence_refs", [])),
    )


@rule(
    "invoice.paid_duplicate",
    version=1,
    module=MODULE,
    title="Invoice has not already been paid",
    severity=Severity.CRITICAL,
)
def paid_duplicate(inputs: dict[str, Any], params: NoParams) -> RuleOutput:
    inv = inputs.get("invoice", {})
    if not inv.get("number_normalized"):
        return RuleOutput(RuleResult.UNKNOWN, "INVOICE_NUMBER_MISSING", "No invoice number.")
    paid = inputs.get("duplicates", {}).get("paid", [])
    if paid:
        refs = ", ".join(p["external_reference"] for p in paid)
        return RuleOutput(
            RuleResult.FAIL,
            "PAID_DUPLICATE",
            f"This vendor invoice number was already paid ({refs}).",
            observed={"payments": paid},
        )
    return RuleOutput(RuleResult.PASS, "NOT_PREVIOUSLY_PAID", "No payment found for this invoice.")


@rule(
    "invoice.duplicate_candidate",
    version=1,
    module=MODULE,
    title="No other open invoice matches",
)
def duplicate_candidate(inputs: dict[str, Any], params: NoParams) -> RuleOutput:
    dup = inputs.get("duplicates", {})
    exact, similar = dup.get("open", []), dup.get("similar", [])
    if exact:
        return RuleOutput(
            RuleResult.FAIL,
            "DUPLICATE_CANDIDATE",
            "Another invoice from this vendor has the same number and currency.",
            observed={"matches": exact},
        )
    if similar:
        return RuleOutput(
            RuleResult.FAIL,
            "SIMILAR_INVOICE",
            "Another invoice from this vendor has the same amount within a few days. "
            "Similarity alone does not prove a duplicate.",
            observed={"matches": similar},
        )
    return RuleOutput(RuleResult.PASS, "NO_DUPLICATE", "No matching open invoice.")


@rule(
    "beneficiary.is_verified",
    version=1,
    module=MODULE,
    title="Payee bank details are independently verified",
    severity=Severity.CRITICAL,
)
def beneficiary_verified(inputs: dict[str, Any], params: NoParams) -> RuleOutput:
    ben = inputs.get("beneficiary")
    if not ben:
        return RuleOutput(
            RuleResult.UNKNOWN,
            "BENEFICIARY_MISSING",
            "The vendor has no bank details on record.",
        )
    ref = (f"beneficiary-version-{ben['revision']}",)
    status = ben.get("verification_status")
    if status == "VERIFIED":
        return RuleOutput(RuleResult.PASS, "BENEFICIARY_VERIFIED", "Bank details verified.")
    if status == "REJECTED":
        return RuleOutput(
            RuleResult.FAIL,
            "BENEFICIARY_REJECTED",
            "Verification of these bank details was rejected.",
            observed={"revision": ben["revision"]},
            evidence_refs=ref,
        )
    return RuleOutput(
        RuleResult.UNKNOWN,
        "BENEFICIARY_VERIFICATION_MISSING",
        "The selected bank details do not have a current verification record.",
        observed={"revision": ben["revision"], "changed": ben.get("changed_recently", False)},
        evidence_refs=ref,
    )


class CurrencyParams(Params):
    allowed: list[str] = Field(default_factory=lambda: ["INR"], min_length=1)


@rule(
    "invoice.currency_supported",
    version=1,
    module=MODULE,
    title="Invoice currency is supported",
    params=CurrencyParams,
)
def currency_supported(inputs: dict[str, Any], params: CurrencyParams) -> RuleOutput:
    currency = inputs.get("invoice", {}).get("currency")
    if not currency:
        return RuleOutput(RuleResult.UNKNOWN, "CURRENCY_MISSING", "No currency.")
    if currency in params.allowed:
        return RuleOutput(RuleResult.PASS, "CURRENCY_OK", f"{currency} is supported.")
    return RuleOutput(
        RuleResult.FAIL,
        "CURRENCY_UNSUPPORTED",
        f"{currency} invoices are outside the agreed scope and need manual handling.",
        observed={"currency": currency},
        expected={"allowed": params.allowed},
    )


class PoParams(Params):
    required_above_minor: int = Field(default=0, ge=0)


@rule(
    "invoice.po_reference",
    version=1,
    module=MODULE,
    title="Purchase order reference present",
    params=PoParams,
)
def po_reference(inputs: dict[str, Any], params: PoParams) -> RuleOutput:
    inv = inputs.get("invoice", {})
    total = inv.get("total_minor")
    if total is None:
        return RuleOutput(RuleResult.UNKNOWN, "TOTAL_MISSING", "No total.")
    if Decimal(str(total)) <= params.required_above_minor:
        return RuleOutput(RuleResult.NOT_APPLICABLE, "PO_NOT_REQUIRED", "No PO needed.")
    if inv.get("po_number"):
        return RuleOutput(RuleResult.PASS, "PO_PRESENT", "Purchase order referenced.")
    return RuleOutput(
        RuleResult.FAIL,
        "PO_MISSING",
        "Invoices above the threshold need a purchase order reference.",
        expected={"required_above_minor": params.required_above_minor},
    )
