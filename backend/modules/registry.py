"""The eight workflow modules and their release state.

All modules are designed; only those validated for the first release are
enabled. Disabled modules expose a description of future scope and nothing
that looks like a working result (flows §1).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.errors import Forbidden


class ModuleCode(StrEnum):
    INVOICES = "invoices"
    RECONCILIATION = "reconciliation"
    AML = "aml"
    CHARGEBACKS = "chargebacks"
    PAYMENT_GATEWAY = "payment_gateway"
    UNDERWRITING = "underwriting"
    COMMUNICATIONS = "communications"
    KYC = "kyc"


@dataclass(frozen=True)
class ModuleInfo:
    code: ModuleCode
    number: int
    name: str
    stage: str
    enabled: bool
    simulation_only: bool
    summary: str
    activation_gate: str


MODULES: tuple[ModuleInfo, ...] = (
    ModuleInfo(
        code=ModuleCode.INVOICES,
        number=1,
        name="Invoice and payment preflight",
        stage="First release",
        enabled=True,
        simulation_only=False,
        summary=(
            "Extract invoice fields; compare with vendor, PO and payment records; produce "
            "pass/block/review findings with source references."
        ),
        activation_gate="Enabled.",
    ),
    ModuleInfo(
        code=ModuleCode.RECONCILIATION,
        number=2,
        name="Reconciliation investigation",
        stage="First release",
        enabled=True,
        simulation_only=False,
        summary=(
            "Import bank and accounting records, propose exact one-to-one matches and route "
            "every other difference to an exception queue."
        ),
        activation_gate="Enabled for one-to-one, full-amount matching only.",
    ),
    ModuleInfo(
        code=ModuleCode.AML,
        number=3,
        name="AML investigation evidence",
        stage="Later regulated-domain release",
        enabled=False,
        simulation_only=False,
        summary=(
            "Would assemble an existing alert's evidence timeline and an investigator- "
            "reviewed draft."
        ),
        activation_gate=(
            "Authorized data, qualified reviewers, reproducible evidence and approved procedures."
        ),
    ),
    ModuleInfo(
        code=ModuleCode.CHARGEBACKS,
        number=4,
        name="Chargeback evidence",
        stage="Adjacent module after buyer validation",
        enabled=False,
        simulation_only=False,
        summary=(
            "Would organize order, delivery, support and refund records into an editable packet."
        ),
        activation_gate=(
            "Merchant partner verifies completeness and claims; submission remains reviewed."
        ),
    ),
    ModuleInfo(
        code=ModuleCode.PAYMENT_GATEWAY,
        number=5,
        name="Agent payment control gateway",
        stage="Simulator first",
        enabled=True,
        simulation_only=True,
        summary=(
            "Evaluates proposed actions against scoped authority, approvals, limits and "
            "duplicates, then executes through the payment simulator."
        ),
        activation_gate="Live connectors need provider, concurrency, recovery and security gates.",
    ),
    ModuleInfo(
        code=ModuleCode.UNDERWRITING,
        number=6,
        name="Underwriting evidence validator",
        stage="Later regulated-domain release",
        enabled=False,
        simulation_only=False,
        summary="Would check loan-file evidence and calculations against one lender policy.",
        activation_gate=(
            "Lender validates calculations, reasons and boundaries; separate fairness review."
        ),
    ),
    ModuleInfo(
        code=ModuleCode.COMMUNICATIONS,
        number=7,
        name="Collections communication QA",
        stage="After lender/servicer validation",
        enabled=False,
        simulation_only=False,
        summary="Would compare draft messages with verified balances and approved policy.",
        activation_gate=(
            "Servicer policy owner validates findings, escalation and language coverage."
        ),
    ),
    ModuleInfo(
        code=ModuleCode.KYC,
        number=8,
        name="KYC/KYB review",
        stage="Later regulated-domain release",
        enabled=False,
        simulation_only=False,
        summary=(
            "Would organize identity-review evidence and integrate one verification provider."
        ),
        activation_gate=(
            "Identity/compliance partner validates provider semantics and exception workflow."
        ),
    ),
)

_BY_CODE = {m.code: m for m in MODULES}


def module_info(code: str) -> ModuleInfo:
    return _BY_CODE[ModuleCode(code)]


def require_enabled(code: str) -> ModuleInfo:
    info = module_info(code)
    if not info.enabled:
        raise Forbidden(f"Module '{info.name}' is not enabled", code="MODULE_DISABLED")
    return info
