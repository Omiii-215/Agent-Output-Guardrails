import csv
import io
import threading
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.modules.reconciliation import service as recon
from backend.modules.reconciliation.models import MatchAllocation, SourceTransaction
from backend.worker import run_once
from tests.support import pg_only, upload_bytes

BANK = b"""txn_id,date,narration,ref,amount,ccy
B1,2026-10-02,NEFT Shree Ganesh,UTR1001,-5900.00,INR
B2,2026-10-03,NEFT Kaveri less charges,UTR1002,-1005.00,INR
B3a,2026-10-04,Part 1,UTR1003,-300.00,INR
B3b,2026-10-04,Part 2,UTR1003,-200.00,INR
B4,2026-10-05,Cash deposit,,2500.00,INR
B5,2026-10-06,Import duty,UTR1005,-100.00,USD
B6,2026-10-07,Unknown debit,UTR1006,-42.00,INR
"""
LEDGER = b"""entry,posted,memo,ref,amount
L1,2026-10-02,Shree Ganesh INV-1001,utr-1001,-5900.00
L2,2026-10-03,Kaveri Logistics,UTR 1002,-1000.00
L3,2026-10-04,Supplier X,UTR1003,-500.00
L5,2026-10-06,Customs,UTR1005,-100.00
"""
BANK_MAP = {
    "external_id": "txn_id",
    "booked_on": "date",
    "amount": "amount",
    "reference": "ref",
    "description": "narration",
    "currency": "ccy",
}
LEDGER_MAP = {
    "external_id": "entry",
    "booked_on": "posted",
    "amount": "amount",
    "reference": "ref",
    "description": "memo",
}


def import_file(world, data, side, mapping):
    doc = upload_bytes(world, data)
    resp = world.acme_as("operator").post(
        "/v1/reconciliation/imports",
        json={"document_version_id": doc, "side": side, "mapping": mapping},
    )
    assert resp.status_code == 202, resp.text
    return resp.json()


@pytest.fixture
def imported(world, runtime):
    import_file(world, BANK, "BANK", BANK_MAP)
    import_file(world, LEDGER, "LEDGER", LEDGER_MAP)
    run_once(runtime)
    return world.acme_as("operator")


def test_exact_matches_are_proposed_and_differences_routed(imported):
    matches = imported.get("/v1/reconciliation/matches").json()
    assert len(matches) == 1
    assert {r["external_id"] for r in matches[0]["rows"]} == {"B1", "L1"}
    kinds = {
        e["transaction"]["external_id"]: e["kind"]
        for e in imported.get("/v1/reconciliation/exceptions").json()
    }
    assert kinds == {
        "B2": "AMOUNT_DIFFERENCE",
        "L2": "AMOUNT_DIFFERENCE",
        "B3a": "AMBIGUOUS_REFERENCE",
        "B3b": "AMBIGUOUS_REFERENCE",
        "L3": "SPLIT_PAYMENT_UNSUPPORTED",
        "B4": "NO_REFERENCE",
        "B5": "CURRENCY_DIFFERENCE_UNSUPPORTED",
        "L5": "CURRENCY_DIFFERENCE_UNSUPPORTED",
    }
    unmatched = imported.get("/v1/reconciliation/transactions", params={"status": "UNMATCHED"})
    assert [r["external_id"] for r in unmatched.json()] == ["B6"]
    row = matches[0]["rows"][0]
    assert row["lineage"]["row_number"] == 2 and row["raw_row"]


def test_match_approval_allocates_once(imported):
    match = imported.get("/v1/reconciliation/matches").json()[0]
    ok = imported.post(
        f"/v1/reconciliation/matches/{match['id']}/approve",
        json={"expected_version": match["version"], "reason": "Same UTR and amount"},
    )
    assert ok.status_code == 200 and ok.json()["state"] == "APPROVED"
    assert {r["status"] for r in ok.json()["rows"]} == {"MATCHED"}
    again = imported.post(
        f"/v1/reconciliation/matches/{match['id']}/approve",
        json={"expected_version": ok.json()["version"], "reason": "again"},
    )
    assert again.status_code == 409


def test_rejected_match_returns_rows_to_unmatched(imported):
    match = imported.get("/v1/reconciliation/matches").json()[0]
    resp = imported.post(
        f"/v1/reconciliation/matches/{match['id']}/reject",
        json={"expected_version": match["version"], "reason": "Different vendor"},
    )
    assert {r["status"] for r in resp.json()["rows"]} == {"UNMATCHED"}


def test_reimport_is_idempotent_and_conflicts_keep_originals(world, runtime, imported):
    first = imported.get("/v1/reconciliation/imports").json()
    import_file(world, BANK, "BANK", BANK_MAP)  # same bytes again
    assert len(imported.get("/v1/reconciliation/imports").json()) == len(first)

    conflicting = b"txn_id,date,narration,ref,amount,ccy\nB1,2026-10-02,changed,UTR1001,-1.00,INR\n"
    import_file(world, conflicting, "BANK", BANK_MAP)
    run_once(runtime)
    latest = imported.get("/v1/reconciliation/imports").json()[0]
    assert latest["imported_count"] == 0
    assert "conflicts with an earlier import" in latest["errors"][0]
    b1 = next(
        r
        for r in imported.get("/v1/reconciliation/transactions").json()
        if r["external_id"] == "B1"
    )
    assert b1["amount"]["amount_minor"] == "-590000"


def test_bad_mapping_fails_visibly(world, runtime):
    import_file(world, LEDGER, "LEDGER", {**LEDGER_MAP, "amount": "missing_column"})
    run_once(runtime)
    batch = world.acme_as("operator").get("/v1/reconciliation/imports").json()[0]
    assert batch["state"] == "FAILED" and "missing_column" in batch["errors"][0]


def test_exception_resolution_and_export(imported, world):
    match = imported.get("/v1/reconciliation/matches").json()[0]
    imported.post(
        f"/v1/reconciliation/matches/{match['id']}/approve",
        json={"expected_version": match["version"], "reason": "Exact"},
    )
    exc = next(
        e
        for e in imported.get("/v1/reconciliation/exceptions").json()
        if e["transaction"]["external_id"] == "B2"
    )
    case = imported.get(f"/v1/cases/{exc['case_id']}").json()
    assert case["exception"]["kind"] == "AMOUNT_DIFFERENCE"
    assert case["counterparts"][0]["external_id"] == "L2"
    resolved = imported.post(
        f"/v1/reconciliation/exceptions/{exc['id']}/resolve",
        json={"resolution_code": "BANK_CHARGES", "note": "Rs 5 NEFT charge; book to fees"},
    )
    assert resolved.json()["state"] == "RESOLVED"
    assert imported.get(f"/v1/cases/{exc['case_id']}").json()["case"]["status"] == "RESOLVED"

    export = world.acme_as("auditor").get("/v1/reconciliation/export")
    rows = list(csv.DictReader(io.StringIO(export.text)))
    assert {(r["record_type"], r["disposition"]) for r in rows} == {
        ("MATCH", "MATCHED"),
        ("EXCEPTION", "AMOUNT_DIFFERENCE:BANK_CHARGES"),
    }


def test_database_allows_one_active_allocation_per_row(imported, db, world):
    match = imported.get("/v1/reconciliation/matches").json()[0]
    imported.post(
        f"/v1/reconciliation/matches/{match['id']}/approve",
        json={"expected_version": match["version"], "reason": "Exact"},
    )
    with db.admin() as s:
        alloc = s.scalars(select(MatchAllocation).where(MatchAllocation.active)).first()
    with pytest.raises(IntegrityError), db.tenant(world.acme) as tx:
        tx.add(
            MatchAllocation(
                group_id=alloc.group_id,
                source_transaction_id=alloc.source_transaction_id,
                side=alloc.side,
                allocated_minor=1,
                active=True,
            )
        )
        tx.flush()


@pg_only
def test_concurrent_match_approvals_allocate_once(imported, db, world):
    from tests.support import actor_for

    match = imported.get("/v1/reconciliation/matches").json()[0]
    actors = [actor_for(db, s, world.acme) for s in ("operator@acme.test", "approver@acme.test")]
    barrier, results = threading.Barrier(2), []

    def approve(actor):
        barrier.wait()
        try:
            with db.tenant(world.acme, actor=actor) as tx:
                recon.decide_match(
                    tx,
                    actor,
                    uuid.UUID(match["id"]),
                    approve=True,
                    expected_version=match["version"],
                    reason="race",
                )
            results.append("ok")
        except Exception as exc:
            results.append(type(exc).__name__)

    threads = [threading.Thread(target=approve, args=(a,)) for a in actors]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["Conflict", "ok"]
    with db.admin() as s:
        rows = s.scalars(select(SourceTransaction).where(SourceTransaction.status == "MATCHED"))
        assert all(r.allocated_minor == r.amount_minor for r in rows)


def test_reconciliation_is_tenant_isolated(imported, world):
    match = imported.get("/v1/reconciliation/matches").json()[0]
    globex = world.globex_as("operator")
    assert globex.get("/v1/reconciliation/matches").json() == []
    assert globex.get("/v1/reconciliation/transactions").json() == []
    assert (
        globex.post(
            f"/v1/reconciliation/matches/{match['id']}/approve",
            json={"expected_version": 1, "reason": "probe"},
        ).status_code
        == 404
    )
