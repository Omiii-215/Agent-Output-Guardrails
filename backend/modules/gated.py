"""Input contracts for the five modules that are designed but not enabled.

Each contract states the evidence a future release must receive, what its
output may claim, and the validation gate before activation. No evaluator is
registered for these modules, so the API cannot produce scores, pass/fail
results or working-looking submissions for them (flows §1).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AmlAlertInput(_Contract):
    alert_id: str
    alert_source: str = Field(description="Existing monitoring/screening system")
    customer_reference: str
    transaction_ids: list[str]
    investigator_notes: str | None = None


class ChargebackInput(_Contract):
    dispute_id: str
    reason_code: str
    respond_by: date
    order_reference: str
    delivery_reference: str | None = None
    refund_reference: str | None = None


class UnderwritingInput(_Contract):
    application_id: str
    lender_policy_version: str
    declared_monthly_income_minor: str
    bank_statement_document_ids: list[str]


class CommunicationInput(_Contract):
    account_reference: str
    channel: str
    draft_text: str = Field(max_length=5000)
    ledger_balance_minor: str
    approved_offer_codes: list[str] = []


class KycInput(_Contract):
    entity_reference: str
    entity_type: str
    document_ids: list[str]
    verification_provider_result_ids: list[str] = []


@dataclass(frozen=True)
class GatedContract:
    input_model: type[BaseModel]
    required_evidence: tuple[str, ...]
    output: str
    boundary: str


CONTRACTS: dict[str, GatedContract] = {
    "aml": GatedContract(
        AmlAlertInput,
        ("Authorized transaction history", "Customer profile", "Screening/monitoring output"),
        "Evidence bundle and an investigator-reviewed draft narrative",
        "A narrative is not a finding of money laundering; no autonomous filing.",
    ),
    "chargebacks": GatedContract(
        ChargebackInput,
        ("Order record", "Carrier/delivery record", "Support and refund records"),
        "Editable evidence packet with deadline tracking",
        "Submission to a provider remains a reviewed, separately approved action.",
    ),
    "underwriting": GatedContract(
        UnderwritingInput,
        ("Lender policy", "Authorized income and bank documents"),
        "Recomputed ratios, contradictions and a reviewer checklist",
        "A complete file is not proof of creditworthiness or fairness.",
    ),
    "communications": GatedContract(
        CommunicationInput,
        ("Account ledger", "Approved communication policy", "Conversation record"),
        "Findings on balance, offers, language and hardship routing",
        "No automatic sending; supervisors review flagged messages.",
    ),
    "kyc": GatedContract(
        KycInput,
        ("Submitted documents", "Beneficial-owner evidence", "Verification provider results"),
        "Evidence summary and reviewer queue",
        "Document summaries are not identity authentication.",
    ),
}
