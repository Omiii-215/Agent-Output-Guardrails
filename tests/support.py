"""Helpers shared by test modules."""

from __future__ import annotations

import os

import pytest

BACKEND = os.environ.get("FINGUARD_TEST_BACKEND", "postgres")

pg_only = pytest.mark.skipif(BACKEND == "sqlite", reason="row-level security requires PostgreSQL")


def add_member(db, organization_id, subject, roles, *, limit_minor=None):
    from backend.identity.models import Membership

    with db.admin() as session:
        member = Membership(
            organization_id=organization_id,
            identity_subject=subject,
            display_name=subject.split("@")[0].title(),
            roles=list(roles),
            approval_limit_minor=limit_minor,
        )
        session.add(member)
        session.flush()
        return member.id


class ApiClient:
    """Thin wrapper over TestClient that sends dev-stub identity headers."""

    def __init__(self, client):
        self.client = client

    def as_(self, subject, organization_id=None):
        headers = {"X-Dev-User": subject}
        if organization_id is not None:
            headers["X-Organization-Id"] = str(organization_id)
        return _Bound(self.client, headers)


class _Bound:
    def __init__(self, client, headers):
        self.client = client
        self.headers = headers

    def _call(self, method, url, **kwargs):
        headers = {**self.headers, **kwargs.pop("headers", {})}
        return self.client.request(method, url, headers=headers, **kwargs)

    def get(self, url, **kw):
        return self._call("GET", url, **kw)

    def post(self, url, **kw):
        return self._call("POST", url, **kw)

    def patch(self, url, **kw):
        return self._call("PATCH", url, **kw)


def actor_for(db, subject, organization_id):
    from backend.identity.service import resolve_user

    return resolve_user(db, subject, organization_id)


# -- invoice workflow helpers ---------------------------------------------------

STANDARD_LINES = [
    {"description": "Steel brackets", "quantity": "10", "unit_price": "450.00", "tax_rate": "0.18"},
    {"description": "Freight", "quantity": "1", "unit_price": "500.00", "tax_rate": "0.18"},
]
STANDARD_TOTAL = "5900.00"  # (4500 + 500) x 1.18


def make_vendor(world, name="Shree Ganesh Metals", *, verified=True, account="123456789012"):
    operator = world.acme_as("operator")
    vendor = operator.post("/v1/vendors", json={"name": name, "tax_id": "27AAAAA0000A1Z5"})
    assert vendor.status_code == 201, vendor.text
    vendor = vendor.json()
    ben = operator.post(
        f"/v1/vendors/{vendor['id']}/beneficiaries",
        json={"account_holder": name, "account_number": account, "ifsc": "HDFC0001234"},
    ).json()
    if verified:
        resp = world.acme_as("approver").post(
            f"/v1/beneficiaries/{ben['id']}/verification",
            json={"decision": "VERIFIED", "note": "Confirmed by phone with vendor"},
        )
        assert resp.status_code == 200, resp.text
    return vendor["id"], ben["id"]


def make_invoice(
    world, vendor_id, number="INV-1001", total=STANDARD_TOTAL, *, lines=None, headers=None, **fields
):
    body = {
        "vendor_id": vendor_id,
        "fields": {
            "invoice_number": number,
            "invoice_date": "2026-10-01",
            "currency": "INR",
            "total": total,
            "po_number": "PO-77",
            **fields,
        },
        "lines": STANDARD_LINES if lines is None else lines,
    }
    resp = world.acme_as("operator").post("/v1/invoices", json=body, headers=headers or {})
    assert resp.status_code == 201, resp.text
    return resp.json()


def case_detail(world, case_id, persona="operator"):
    resp = world.acme_as(persona).get(f"/v1/cases/{case_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()


def evaluate(world, runtime, case_id):
    from backend.worker import run_once

    revision = case_detail(world, case_id)["case"]["revision"]
    resp = world.acme_as("operator").post(
        f"/v1/cases/{case_id}/evaluations", json={"expected_revision": revision}
    )
    assert resp.status_code == 202, resp.text
    run_once(runtime)
    return case_detail(world, case_id)


def reviewed_case(world, runtime, **invoice_kwargs):
    """A clean invoice evaluated to PASS, ready for a payment proposal."""
    vendor_id, _ = make_vendor(world, name=invoice_kwargs.pop("vendor_name", "Shree Ganesh Metals"))
    created = make_invoice(world, vendor_id, **invoice_kwargs)
    detail = evaluate(world, runtime, created["case_id"])
    assert detail["evaluation"]["outcome"] == "PASS", detail["findings"]
    return detail


def proposal_body(detail, **overrides):
    body = {
        "case_id": detail["case"]["id"],
        "expected_case_revision": detail["case"]["revision"],
        "action_type": "PAYMENT",
        "amount": {
            "amount_minor": detail["invoice"]["total"]["amount_minor"],
            "currency": detail["invoice"]["total"]["currency"],
        },
        "beneficiary_version_id": detail["beneficiary"]["id"],
        "purpose": f"Payment of invoice {detail['invoice']['number']}",
        "mode": "SIMULATED",
    }
    body.update(overrides)
    return body


def propose(world, runtime, detail, persona="operator", **overrides):
    from backend.worker import run_once

    resp = world.acme_as(persona).post(
        "/v1/action-proposals", json=proposal_body(detail, **overrides)
    )
    assert resp.status_code == 201, resp.text
    run_once(runtime)
    return world.acme_as(persona).get(f"/v1/action-proposals/{resp.json()['id']}").json()
