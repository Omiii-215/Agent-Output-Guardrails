from sqlalchemy import select

from backend.modules.invoices.models import BeneficiaryVersion
from tests.support import (
    case_detail,
    evaluate,
    make_invoice,
    make_vendor,
)


def reasons(detail):
    return {f["reason_code"] for f in detail["findings"] if f["effect"]}


def test_clean_invoice_passes_with_traceable_history(world, runtime):
    vendor_id, _ = make_vendor(world)
    created = make_invoice(world, vendor_id)
    assert created["status"] == "READY_TO_EVALUATE"
    detail = evaluate(world, runtime, created["case_id"])
    assert detail["case"]["status"] == "IN_REVIEW"
    assert detail["evaluation"]["outcome"] == "PASS", detail["findings"]
    assert detail["next_actions"] == ["CREATE_PAYMENT_PROPOSAL"]
    assert detail["invoice"]["total"]["amount_minor"] == "590000"
    assert detail["evaluation"]["input_digest"].startswith("sha256:")
    actions = [
        e["action"]
        for e in world.acme_as("auditor").get(f"/v1/cases/{created['case_id']}/history").json()
    ]
    # Case history includes the payee events the decision relied on.
    assert {"case.created", "beneficiary.verified", "evaluation.completed"} <= set(actions)


def test_total_mismatch_blocks_then_correction_passes(world, runtime):
    vendor_id, _ = make_vendor(world)
    created = make_invoice(world, vendor_id, total="5990.00")
    detail = evaluate(world, runtime, created["case_id"])
    assert detail["evaluation"]["outcome"] == "BLOCK"
    mismatch = next(f for f in detail["findings"] if f["reason_code"] == "TOTAL_MISMATCH")
    assert mismatch["observed"]["computed_total_minor"] == "590000"
    assert mismatch["observed"]["stated_total_minor"] == "599000"
    assert "CORRECT_SOURCE" in detail["next_actions"]

    resp = world.acme_as("operator").patch(
        f"/v1/invoices/{created['invoice_id']}",
        json={
            "expected_revision": detail["case"]["revision"],
            "fields": {"total": "5900.00"},
            "reason": "Vendor confirmed typo in total",
        },
    )
    assert resp.status_code == 200 and resp.json()["version"] == 2
    detail = evaluate(world, runtime, created["case_id"])
    assert detail["evaluation"]["outcome"] == "PASS"
    assert detail["invoice"]["version"] == 2


def test_paid_duplicate_blocks(world, runtime):
    vendor_id, _ = make_vendor(world)
    imported = world.acme_as("operator").post(
        "/v1/payment-history",
        json={
            "records": [
                {
                    "vendor_id": vendor_id,
                    "invoice_number": "inv 1001",
                    "amount": "5900.00",
                    "currency": "INR",
                    "paid_on": "2026-09-20",
                    "external_reference": "UTR-555",
                }
            ]
        },
    )
    assert imported.json() == {"created": 1, "skipped": 0}
    created = make_invoice(world, vendor_id, number="INV-1001")
    detail = evaluate(world, runtime, created["case_id"])
    assert detail["evaluation"]["outcome"] == "BLOCK"
    assert "PAID_DUPLICATE" in reasons(detail)


def test_open_duplicate_needs_independent_review(world, runtime):
    vendor_id, _ = make_vendor(world)
    make_invoice(world, vendor_id, number="INV-2000")
    second = make_invoice(world, vendor_id, number="INV/2000")
    detail = evaluate(world, runtime, second["case_id"])
    assert detail["evaluation"]["outcome"] == "REVIEW"
    finding = next(f for f in detail["findings"] if f["reason_code"] == "DUPLICATE_CANDIDATE")
    assert detail["next_actions"] == ["RESOLVE_FINDINGS"]

    # The operator who created the case cannot clear its own finding.
    self_resolve = world.acme_as("operator").post(
        f"/v1/findings/{finding['id']}/resolutions",
        json={"resolution_code": "LEGITIMATE_RECURRING", "reason": "recurring"},
    )
    assert self_resolve.status_code == 403
    ok = world.acme_as("approver").post(
        f"/v1/findings/{finding['id']}/resolutions",
        json={"resolution_code": "LEGITIMATE_RECURRING", "reason": "Monthly rental, confirmed"},
    )
    assert ok.status_code == 201
    assert case_detail(world, second["case_id"])["next_actions"] == ["CREATE_PAYMENT_PROPOSAL"]


def test_similar_amount_is_flagged_for_review(world, runtime):
    vendor_id, _ = make_vendor(world)
    make_invoice(world, vendor_id, number="INV-1", invoice_date="2026-10-01")
    second = make_invoice(world, vendor_id, number="INV-9", invoice_date="2026-10-04")
    detail = evaluate(world, runtime, second["case_id"])
    assert detail["evaluation"]["outcome"] == "REVIEW"
    assert "SIMILAR_INVOICE" in reasons(detail)


def test_unverified_beneficiary_holds_until_independent_verification(world, runtime):
    vendor_id, _ = make_vendor(world, verified=False)
    created = make_invoice(world, vendor_id)
    detail = evaluate(world, runtime, created["case_id"])
    assert detail["evaluation"]["outcome"] == "INDETERMINATE"
    assert "REQUEST_BENEFICIARY_VERIFICATION" in detail["next_actions"]

    # A person holding both roles still cannot verify details they entered.
    from tests.support import add_member

    add_member(
        world_db(world), world.acme, "both@acme.test", ["finance_operator", "finance_approver"]
    )
    both = world.api.as_("both@acme.test", world.acme)
    ben = both.post(
        f"/v1/vendors/{vendor_id}/beneficiaries",
        json={
            "account_holder": "Shree Ganesh",
            "account_number": "998877665544",
            "ifsc": "ICIC0004321",
        },
    )
    assert ben.status_code == 201, ben.text
    ben = ben.json()
    own = both.post(
        f"/v1/beneficiaries/{ben['id']}/verification",
        json={"decision": "VERIFIED", "note": "self check"},
    )
    assert own.status_code == 403 and own.json()["error"]["code"] == "SELF_VERIFICATION"

    world.acme_as("approver").post(
        f"/v1/beneficiaries/{ben['id']}/verification",
        json={"decision": "VERIFIED", "note": "Called vendor on known number"},
    )
    # The payee change put the case back to READY_TO_EVALUATE automatically.
    assert case_detail(world, created["case_id"])["case"]["status"] == "READY_TO_EVALUATE"
    detail = evaluate(world, runtime, created["case_id"])
    assert detail["evaluation"]["outcome"] == "PASS"
    assert detail["beneficiary"]["revision"] == 2


def world_db(world):
    return world.api.client.app.state.db


def test_beneficiary_change_after_evaluation_requires_reevaluation(world, runtime):
    vendor_id, _ = make_vendor(world)
    created = make_invoice(world, vendor_id)
    assert evaluate(world, runtime, created["case_id"])["evaluation"]["outcome"] == "PASS"
    world.acme_as("operator").post(
        f"/v1/vendors/{vendor_id}/beneficiaries",
        json={
            "account_holder": "New Payee",
            "account_number": "111122223333",
            "ifsc": "SBIN0000001",
        },
    )
    detail = case_detail(world, created["case_id"])
    assert detail["case"]["status"] == "READY_TO_EVALUATE"
    assert detail["next_actions"][0] == "RUN_EVALUATION"


def test_missing_critical_fields_need_information(world, runtime):
    vendor_id, _ = make_vendor(world)
    resp = world.acme_as("operator").post(
        "/v1/invoices", json={"vendor_id": vendor_id, "fields": {"invoice_number": "X-1"}}
    )
    case_id = resp.json()["case_id"]
    assert resp.json()["status"] == "NEEDS_INFORMATION"
    refused = world.acme_as("operator").post(
        f"/v1/cases/{case_id}/evaluations", json={"expected_revision": resp.json()["revision"]}
    )
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "NOT_READY_TO_EVALUATE"


def test_repeated_submission_with_idempotency_key_creates_one_case(world):
    vendor_id, _ = make_vendor(world)
    headers = {"Idempotency-Key": "upload-INV-1001-attempt"}
    first = make_invoice(world, vendor_id, headers=headers)
    second = make_invoice(world, vendor_id, headers=headers)
    assert first == second
    items = world.acme_as("operator").get("/v1/cases").json()["items"]
    assert len(items) == 1


def test_stale_correction_is_rejected(world, runtime):
    vendor_id, _ = make_vendor(world)
    created = make_invoice(world, vendor_id)
    resp = world.acme_as("operator").patch(
        f"/v1/invoices/{created['invoice_id']}",
        json={"expected_revision": 1, "fields": {"po_number": "PO-1"}, "reason": "update"},
    )
    assert resp.status_code == 409


def test_bank_details_are_encrypted_and_masked(world, db):
    make_vendor(world, account="123456789012")
    listed = world.acme_as("operator").get("/v1/vendors").json()
    assert listed[0]["beneficiary"]["account_masked"] == "•••• 9012"
    assert "123456789012" not in str(listed)
    with db.admin() as s:
        row = s.scalars(select(BeneficiaryVersion)).one()
    assert "123456789012" not in row.account_ciphertext
    assert (
        world.api.client.app.state.runtime.cipher.decrypt(row.account_ciphertext) == "123456789012"
    )


def test_invoices_are_tenant_isolated(world):
    vendor_id, _ = make_vendor(world)
    created = make_invoice(world, vendor_id)
    globex = world.globex_as("operator")
    resp = globex.post(
        "/v1/invoices",
        json={"vendor_id": vendor_id, "fields": {"invoice_number": "X"}},
    )
    assert resp.status_code == 404
    assert globex.get(f"/v1/cases/{created['case_id']}").status_code == 404
    assert (
        globex.patch(
            f"/v1/invoices/{created['invoice_id']}",
            json={"expected_revision": 1, "fields": {}, "reason": "probe"},
        ).status_code
        == 404
    )
    assert globex.get("/v1/vendors").json() == []
