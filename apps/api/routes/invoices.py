from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from apps.api.deps import get_runtime, require, tenant_tx
from backend.identity.actor import Actor
from backend.identity.roles import Capability
from backend.modules.invoices import service as invoices
from backend.modules.invoices.models import BeneficiaryVersion, Vendor
from backend.persistence import idempotency
from backend.runtime import Runtime

router = APIRouter(prefix="/v1", tags=["invoices"])


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VendorIn(Strict):
    name: str = Field(min_length=2, max_length=200)
    tax_id: str | None = Field(default=None, max_length=30)


class BeneficiaryIn(Strict):
    account_holder: str = Field(min_length=2, max_length=200)
    account_number: str = Field(min_length=6, max_length=30)
    ifsc: str = Field(min_length=11, max_length=11)


class VerificationIn(Strict):
    decision: str = Field(pattern="^(VERIFIED|REJECTED)$")
    note: str = Field(min_length=3, max_length=1000)


class LineIn(Strict):
    description: str = ""
    quantity: str
    unit_price: str
    tax_rate: str = "0"


class InvoiceFields(Strict):
    invoice_number: str | None = Field(default=None, max_length=100)
    invoice_date: str | None = None
    due_date: str | None = None
    currency: str | None = None
    subtotal: str | None = None
    tax: str | None = None
    total: str | None = None
    po_number: str | None = None


class InvoiceIn(Strict):
    vendor_id: uuid.UUID
    document_version_id: uuid.UUID | None = None
    fields: InvoiceFields = InvoiceFields()
    lines: list[LineIn] = Field(default_factory=list, max_length=500)
    extract: bool = False


class CorrectionIn(Strict):
    expected_revision: int
    fields: InvoiceFields = InvoiceFields()
    lines: list[LineIn] | None = None
    verify: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=3, max_length=1000)


class EvaluationIn(Strict):
    expected_revision: int


class PaymentHistoryRecord(Strict):
    vendor_id: uuid.UUID
    invoice_number: str
    amount: str
    currency: str
    paid_on: date
    external_reference: str = Field(min_length=1, max_length=200)


class PaymentHistoryIn(Strict):
    records: list[PaymentHistoryRecord] = Field(max_length=5000)


def _vendor_out(v: Vendor, ben: BeneficiaryVersion | None) -> dict[str, Any]:
    return {
        "id": str(v.id),
        "name": v.name,
        "tax_id": v.tax_id,
        "status": v.status,
        "beneficiary": _ben_out(ben) if ben else None,
    }


def _ben_out(b: BeneficiaryVersion) -> dict[str, Any]:
    return {
        "id": str(b.id),
        "revision": b.revision,
        "account_holder": b.account_holder,
        "account_masked": "•••• " + b.account_last4,
        "ifsc": b.ifsc,
        "verification_status": b.verification_status,
        "created_by": b.created_by,
        "verified_by": b.verified_by,
    }


def _set_fields(fields: InvoiceFields) -> invoices.FieldInput:
    return invoices.FieldInput(values=fields.model_dump(exclude_unset=True), lines=None)


@router.get("/vendors")
def list_vendors(
    actor: Actor = Depends(require(Capability.CASE_READ)), rt: Runtime = Depends(get_runtime)
):
    with tenant_tx(rt.db, actor) as tx:
        out = []
        for v in tx.scalars(tx.select(Vendor).order_by(Vendor.name)):
            ben = (
                tx.find(BeneficiaryVersion, v.current_beneficiary_id)
                if v.current_beneficiary_id
                else None
            )
            out.append(_vendor_out(v, ben))
        return out


@router.post("/vendors", status_code=201)
def create_vendor(
    body: VendorIn,
    actor: Actor = Depends(require(Capability.VENDOR_WRITE)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        return _vendor_out(
            invoices.create_vendor(tx, actor, name=body.name, tax_id=body.tax_id), None
        )


@router.post("/vendors/{vendor_id}/beneficiaries", status_code=201)
def add_beneficiary(
    vendor_id: uuid.UUID,
    body: BeneficiaryIn,
    actor: Actor = Depends(require(Capability.VENDOR_WRITE)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        return _ben_out(
            invoices.add_beneficiary(
                tx,
                actor,
                rt.cipher,
                vendor_id,
                account_holder=body.account_holder,
                account_number=body.account_number,
                ifsc=body.ifsc,
            )
        )


@router.post("/beneficiaries/{beneficiary_id}/verification")
def verify_beneficiary(
    beneficiary_id: uuid.UUID,
    body: VerificationIn,
    actor: Actor = Depends(require(Capability.BENEFICIARY_VERIFY)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        return _ben_out(
            invoices.verify_beneficiary(
                tx, actor, beneficiary_id, decision=body.decision, note=body.note
            )
        )


@router.post("/payment-history", status_code=201)
def import_payment_history(
    body: PaymentHistoryIn,
    actor: Actor = Depends(require(Capability.RECON_IMPORT)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        return invoices.import_payment_history(tx, actor, [r.model_dump() for r in body.records])


@router.post("/invoices", status_code=201)
def create_invoice(
    body: InvoiceIn,
    actor: Actor = Depends(require(Capability.CASE_WRITE)),
    rt: Runtime = Depends(get_runtime),
    idempotency_key: str | None = Header(default=None),
):
    def operation(tx):
        fields = _set_fields(body.fields)
        fields.lines = [line.model_dump() for line in body.lines]
        case, invoice = invoices.create_invoice(
            tx,
            actor,
            vendor_id=body.vendor_id,
            document_version_id=body.document_version_id,
            fields=fields,
            extract=body.extract,
        )
        return 201, {
            "case_id": str(case.id),
            "invoice_id": str(invoice.id),
            "status": case.status,
            "revision": case.revision,
        }

    result = idempotency.run(
        rt.db,
        actor,
        route="POST /v1/invoices",
        key=idempotency_key,
        body=body.model_dump(mode="json"),
        operation=operation,
    )
    return JSONResponse(status_code=result.status, content=result.body)


@router.patch("/invoices/{invoice_id}")
def correct_invoice(
    invoice_id: uuid.UUID,
    body: CorrectionIn,
    actor: Actor = Depends(require(Capability.CASE_WRITE)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        fields = _set_fields(body.fields)
        if body.lines is not None:
            fields.lines = [line.model_dump() for line in body.lines]
        version = invoices.correct_invoice(
            tx,
            actor,
            invoice_id,
            expected_revision=body.expected_revision,
            fields=fields,
            verify=body.verify,
            reason=body.reason,
        )
        return {"invoice_id": str(invoice_id), "version": version.version}


@router.post("/cases/{case_id}/evaluations", status_code=202)
def request_evaluation(
    case_id: uuid.UUID,
    body: EvaluationIn,
    actor: Actor = Depends(require(Capability.EVALUATION_RUN)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        job = invoices.request_evaluation(tx, actor, case_id, body.expected_revision)
        return {"job_id": str(job.id), "state": job.state}
