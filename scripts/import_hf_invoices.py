"""Run a public Hugging Face invoice dataset through the running FinGuard stack.

    PYTHONPATH=. uv run python scripts/import_hf_invoices.py [--limit 26]

Needs the API (``--api``, default http://localhost:8000) and the worker running.
Data: https://huggingface.co/datasets/katanaml-org/invoices-donut-data-v1 — the
labelled fields only (no images) are fetched once through the Hugging Face
datasets-server API and cached in ``var/hf/``.

What it does, all through the same endpoints the web app uses:
1. provisions "Harbor Lane Supply Co." (USD) with one persona per role;
2. publishes USD versions of the invoice and payment policies (author drafts,
   an independent publisher publishes);
3. creates one vendor per seller with its IBAN as the payee account;
4. uploads each invoice, lets the worker extract it, checks the extracted values
   against the dataset labels, confirms them and runs the checks;
5. runs a payment batch (simulated) for invoices that passed, until the daily
   spend limit stops it;
6. replays one paid invoice as a vendor resubmission;
7. imports a bank statement and ledger for the paid invoices for reconciliation.

Steps 6 and 7 are staged around the dataset: the bank and ledger rows are built
from the simulated payments, and the resubmission is a copy of a real row.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import time
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select

from backend.actions.templates import PAYMENT_PREFLIGHT
from backend.config import get_settings
from backend.fixtures.hf_invoices import (
    CURRENCY,
    DATASET,
    DATASET_URL,
    HfInvoice,
    bank_code,
    normalise,
    render_pdf,
)
from backend.identity.models import Membership, Organization
from backend.modules.invoices.templates import INVOICE_PREFLIGHT
from backend.onboarding import provision_organization
from backend.persistence.database import Database

ORG_NAME = "Harbor Lane Supply Co."
DOMAIN = "harbor.test"
ROWS_API = "https://datasets-server.huggingface.co/rows"
CACHE = Path("var/hf")

# (roles, approval limit in cents)
PERSONAS = {
    "admin": (["org_admin"], None),
    "operator": (["finance_operator"], None),
    "approver": (["finance_approver"], 5_000_000),  # $50,000
    "approver2": (["finance_approver"], 250_000),  # $2,500
    "controller": (["finance_approver"], 10_000_000),  # $100,000
    "auditor": (["auditor"], None),
    "author": (["policy_author"], None),
    "publisher": (["policy_publisher"], None),
}
TOLERANCE_CENTS = 2  # issuers that round once at the end differ from per-line sums by a cent
PO_REQUIRED_ABOVE = 1_000_000  # $10,000
DAILY_LIMIT = 2_000_000  # $20,000
TWO_APPROVALS_ABOVE = 500_000  # $5,000


# -- dataset -------------------------------------------------------------------------


def load_rows(split: str, limit: int, refresh: bool) -> list[HfInvoice]:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{split}.json"
    if refresh or not path.exists():
        rows, offset = [], 0
        while True:
            resp = httpx.get(
                ROWS_API,
                params={
                    "dataset": DATASET,
                    "config": "default",
                    "split": split,
                    "offset": offset,
                    "length": 100,
                },
                timeout=60,
            )
            resp.raise_for_status()
            page = resp.json()
            # Keep the labels only; the scans are not needed until OCR exists.
            rows += [
                {"row_idx": r["row_idx"], "ground_truth": r["row"]["ground_truth"]}
                for r in page["rows"]
            ]
            offset += len(page["rows"])
            if not page["rows"] or offset >= page["num_rows_total"]:
                break
        path.write_text(json.dumps({"dataset": DATASET, "split": split, "rows": rows}))
        print(f"Fetched {len(rows)} rows from {DATASET_URL} ({split})")
    data = json.loads(path.read_text())["rows"]
    return [normalise(split, r["row_idx"], r["ground_truth"]) for r in data[:limit]]


# -- API helpers ---------------------------------------------------------------------


class Api:
    def __init__(self, base: str, org: str):
        self.http = httpx.Client(base_url=base, timeout=30)
        self.org = org

    def as_(self, persona: str) -> Persona:
        return Persona(self, f"{persona}@{DOMAIN}")


class Persona:
    def __init__(self, api: Api, subject: str):
        self.api, self.subject = api, subject
        self.headers = {"X-Dev-User": subject, "X-Organization-Id": api.org}

    def call(self, method: str, url: str, *, ok=(200, 201, 202, 204), **kw) -> Any:
        resp = self.api.http.request(method, url, headers=self.headers, **kw)
        if resp.status_code not in ok:
            raise ApiError(resp.status_code, resp.text)
        return resp.json() if "json" in resp.headers.get("content-type", "") else None

    def get(self, url: str, **kw) -> Any:
        return self.call("GET", url, **kw)

    def post(self, url: str, body: Any = None, **kw) -> Any:
        return self.call("POST", url, json=body, **kw)

    def patch(self, url: str, body: Any) -> Any:
        return self.call("PATCH", url, json=body)

    def upload(self, data: bytes, media_type: str, name: str) -> dict:
        created = self.post(
            "/v1/uploads",
            {
                "filename": name,
                "media_type": media_type,
                "size": len(data),
                "declared_sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
            },
        )
        self.call("PUT", created["upload_url"], content=data)
        return self.post(f"/v1/uploads/{created['document_version_id']}/complete")


class ApiError(Exception):
    def __init__(self, status: int, body: str):
        super().__init__(f"{status} {body}")
        self.status = status
        try:
            self.detail = json.loads(body)
        except ValueError:
            self.detail = {"message": body}

    @property
    def message(self) -> str:
        err = self.detail.get("error", self.detail)
        return f"{err.get('code', self.status)}: {err.get('message', '')}".strip()


def wait(fetch, done, *, timeout: float = 90, what: str = "worker") -> Any:
    deadline = time.monotonic() + timeout
    while True:
        value = fetch()
        if done(value):
            return value
        if time.monotonic() > deadline:
            sys.exit(f"Timed out waiting for the {what}. Is the worker running?")
        time.sleep(0.4)


def money(cents: int | str) -> str:
    return f"${int(cents) / 100:,.2f}"


# -- setup ---------------------------------------------------------------------------


def provision(db: Database) -> str:
    with db.admin() as s:
        existing = s.scalars(select(Organization).where(Organization.name == ORG_NAME)).first()
        if existing is not None:
            sys.exit(
                f"{ORG_NAME} already exists, so the dataset was imported before. "
                "Delete var/ and run scripts/seed_demo.py to start again."
            )
    org = provision_organization(
        db, name=ORG_NAME, legal_entity_reference=f"{ORG_NAME} LLC", base_currency=CURRENCY
    )
    with db.admin() as s:
        for persona, (roles, limit) in PERSONAS.items():
            s.add(
                Membership(
                    organization_id=org,
                    identity_subject=f"{persona}@{DOMAIN}",
                    display_name=f"{persona.title()} (Harbor Lane)",
                    roles=roles,
                    approval_limit_minor=limit,
                )
            )
    return str(org)


def usd(document: dict) -> dict:
    """The product template with every INR example and limit switched to USD."""
    return json.loads(json.dumps(copy.deepcopy(document)).replace('"INR"', f'"{CURRENCY}"'))


def publish_policies(api: Api) -> None:
    author, publisher = api.as_("author"), api.as_("publisher")
    invoice = usd(INVOICE_PREFLIGHT)
    for rule in invoice["rules"]:
        if rule["code"] == "invoice.total_matches_lines":
            rule["parameters"]["tolerance_minor"] = TOLERANCE_CENTS
        if rule["code"] == "invoice.po_reference":
            rule["parameters"]["required_above_minor"] = PO_REQUIRED_ABOVE
    payment = usd(PAYMENT_PREFLIGHT)
    payment["spend_limits"] = [{"currency": CURRENCY, "window": "DAY", "limit_minor": DAILY_LIMIT}]
    payment["approval"]["tiers"] = [{"above_minor": TWO_APPROVALS_ABOVE, "count": 2}]
    for document, reason in (
        (invoice, "USD scope; 2-cent rounding tolerance; PO required above $10,000"),
        (payment, "USD daily limit $20,000; two approvals above $5,000"),
    ):
        draft = author.post("/v1/policies", {"document": document})
        validated = author.post(f"/v1/policies/{draft['id']}/validate")
        if validated["lifecycle"] != "VALIDATED":
            sys.exit(f"Policy {document['policy_code']} failed: {validated['validation_errors']}")
        publisher.post(f"/v1/policies/{draft['id']}/publish", {"reason": reason})
        print(f"  published {document['policy_code']} v{validated['version']}: {reason}")


def create_vendors(api: Api, invoices: list[HfInvoice]) -> dict[str, dict]:
    op, ap = api.as_("operator"), api.as_("approver")
    vendors: dict[str, dict] = {}
    for inv in invoices:
        key = vendor_key(inv)
        if key in vendors:
            continue
        name = inv.seller or f"Unidentified seller, tax ID {inv.seller_tax_id}"
        vendor = op.post("/v1/vendors", {"name": name[:200], "tax_id": inv.seller_tax_id})
        entry = {"id": vendor["id"], "name": name, "verified": False, "rejected": None}
        if inv.iban and bank_code(inv.iban):
            try:
                ben = op.post(
                    f"/v1/vendors/{vendor['id']}/beneficiaries",
                    {
                        "account_holder": name[:200],
                        "account_number": inv.iban,
                        "ifsc": bank_code(inv.iban),
                    },
                )
            except ApiError as exc:
                # A mistyped IBAN never becomes a payee; the invoice waits for a correct one.
                entry["rejected"] = f"{inv.iban}: {exc.message}"
                vendors[key] = entry
                continue
            # A payee whose name is not on the invoice cannot be called back, so it
            # stays unverified; every other IBAN is confirmed for the demo.
            if inv.seller:
                ap.post(
                    f"/v1/beneficiaries/{ben['id']}/verification",
                    {
                        "decision": "VERIFIED",
                        "note": "Dataset demo: IBAN confirmed against the vendor master",
                    },
                )
                entry["verified"] = True
        vendors[key] = entry
    return vendors


def vendor_key(inv: HfInvoice) -> str:
    return inv.seller or f"tax:{inv.seller_tax_id}"


# -- invoices ------------------------------------------------------------------------


def case_detail(op: Persona, case_id: str) -> dict:
    return op.get(f"/v1/cases/{case_id}")


def submit(op: Persona, inv: HfInvoice, vendor_id: str, *, name: str | None = None) -> dict:
    doc = op.upload(render_pdf(inv), "application/pdf", name or f"hf-{inv.split}-{inv.row}.pdf")
    if doc["status"] != "CLEAN":
        raise ApiError(422, json.dumps({"message": f"upload rejected: {doc}"}))
    return op.post(
        "/v1/invoices",
        {"vendor_id": vendor_id, "document_version_id": doc["id"], "extract": True},
    )


def confirm(op: Persona, inv: HfInvoice, created: dict, accuracy: Counter) -> dict:
    """Compare what the extractor read with the dataset labels, then confirm."""
    detail = wait(
        lambda: case_detail(op, created["case_id"]),
        lambda d: d["case"]["status"] != "EXTRACTING",
        what="extraction job",
    )
    got = detail["invoice"]
    expected = {
        "invoice_number": (got["number"], inv.number),
        "invoice_date": (got["invoice_date"], inv.date),
        "currency": (got["currency"], CURRENCY),
        "total": (
            got["total"]["amount_minor"] if got["total"] else None,
            str(int(Decimal(inv.total) * 100)) if inv.total else None,
        ),
    }
    verify, corrections = [], {}
    for name, (value, label) in expected.items():
        if label is None:
            continue
        accuracy["checked"] += 1
        if value is not None and str(value) == str(label):
            accuracy["matched"] += 1
            verify.append(name)
        else:
            corrections[name] = inv.total if name == "total" else label
    accuracy["lines_expected"] += len(inv.lines)
    accuracy["lines_read"] += len(got["lines"])
    body: dict[str, Any] = {
        "expected_revision": detail["case"]["revision"],
        "verify": verify + list(corrections),
        "reason": "Checked against the Hugging Face dataset labels",
    }
    if corrections:
        body["fields"] = corrections
    op.patch(f"/v1/invoices/{created['invoice_id']}", body)
    return case_detail(op, created["case_id"])


def evaluate(op: Persona, case_id: str) -> dict:
    detail = case_detail(op, case_id)
    op.post(f"/v1/cases/{case_id}/evaluations", {"expected_revision": detail["case"]["revision"]})
    return wait(
        lambda: case_detail(op, case_id),
        lambda d: d["evaluation"] is not None and d["case"]["status"] not in ("EVALUATING",),
        what="evaluation job",
    )


def flagged(detail: dict) -> list[str]:
    return [f"{f['effect']}: {f['message']}" for f in detail["findings"] if f["effect"] is not None]


# -- payments ------------------------------------------------------------------------


def pay(api: Api, detail: dict, purpose: str) -> dict:
    """Propose, approve, execute and settle one simulated payment. Returns a log."""
    op = api.as_("operator")
    log: dict[str, Any] = {"steps": []}
    proposal = op.post(
        "/v1/action-proposals",
        {
            "case_id": detail["case"]["id"],
            "expected_case_revision": detail["case"]["revision"],
            "amount": {
                "amount_minor": detail["invoice"]["total"]["amount_minor"],
                "currency": CURRENCY,
            },
            "beneficiary_version_id": detail["beneficiary"]["id"],
            "purpose": purpose,
        },
    )
    proposal = wait(
        lambda: op.get(f"/v1/action-proposals/{proposal['id']}"),
        lambda p: p["state"] != "PREFLIGHT_PENDING",
        what="payment preflight",
    )
    if proposal["state"] != "READY_FOR_APPROVAL":
        reasons = [
            f["message"]
            for f in (proposal.get("preflight") or {}).get("findings", [])
            if f.get("effect")
        ]
        log["result"] = f"{proposal['state']}: {'; '.join(reasons) or proposal['state_reason']}"
        return log

    request = op.post("/v1/approval-requests", {"proposal_id": proposal["id"]})
    log["steps"].append(f"needs {request['required_count']} approval(s)")
    for persona in ("approver", "approver2", "controller"):
        if request["approved_count"] >= request["required_count"]:
            break
        try:
            request = api.as_(persona).post(
                f"/v1/approval-requests/{request['id']}/decisions",
                {
                    "decision": "APPROVE",
                    "reason": "Invoice checks passed; payee IBAN verified",
                    "expected_revision": request["revision"],
                },
            )
            log["steps"].append(f"{persona} approved")
        except ApiError as exc:
            log["steps"].append(f"{persona} refused ({exc.message})")
    intent = op.post(
        "/v1/action-intents",
        {"proposal_id": proposal["id"], "approval_request_id": request["id"]},
    )
    intent = wait(
        lambda: op.get(f"/v1/action-intents/{intent['id']}"),
        lambda i: i["execution"]["state"] in ("ACCEPTED", "SETTLED", "FAILED", "UNKNOWN"),
        what="payment execution",
    )
    if intent["execution"]["state"] == "ACCEPTED":
        # The bank confirms later through a signed webhook; the dev simulator sends it now.
        op.post(f"/v1/simulator/intents/{intent['id']}/advance", {"state": "SETTLED"})
        intent = wait(
            lambda: op.get(f"/v1/action-intents/{intent['id']}"),
            lambda i: i["execution"]["state"] in ("SETTLED", "FAILED", "REVERSED"),
            what="settlement webhook",
        )
    log["result"] = intent["execution"]["state"]
    log["reference"] = intent["provider"]["reference"]
    log["amount_minor"] = int(intent["amount_minor"])
    return log


# -- reconciliation ------------------------------------------------------------------


def reconcile(op: Persona, paid: list[tuple[HfInvoice, str, dict]]) -> None:
    today = date.today().strftime("%m/%d/%Y")
    bank = ["txn_id,date,narration,ref,amount"]
    ledger = ["entry,posted,memo,ref,amount"]
    for n, (inv, vendor, log) in enumerate(paid, start=1):
        amount = f"{-log['amount_minor'] / 100:.2f}"
        payee = vendor[:40].replace(",", "")
        bank.append(f"WIRE-{n:04d},{today},WIRE OUT {payee},{log['reference']},{amount}")
        # Ledger references are typed by hand: lower case and spaced.
        ref = log["reference"].lower().replace("-", " ")
        ledger.append(
            f"AP-{n:04d},{today},Pay {vendor[:30].replace(',', '')} inv {inv.number},{ref},{amount}"
        )
    bank.append(f"FEE-0001,{today},OUTGOING WIRE FEES {len(paid)} x $15,,{-15 * len(paid):.2f}")
    for side, rows, mapping in (
        (
            "BANK",
            bank,
            {
                "external_id": "txn_id",
                "booked_on": "date",
                "amount": "amount",
                "reference": "ref",
                "description": "narration",
            },
        ),
        (
            "LEDGER",
            ledger,
            {
                "external_id": "entry",
                "booked_on": "posted",
                "amount": "amount",
                "reference": "ref",
                "description": "memo",
            },
        ),
    ):
        data = ("\n".join(rows) + "\n").encode()
        doc = op.upload(data, "text/csv", f"harbor-{side.lower()}-{date.today()}.csv")
        op.post(
            "/v1/reconciliation/imports",
            {
                "document_version_id": doc["id"],
                "side": side,
                "mapping": {**mapping, "date_format": "%m/%d/%Y", "default_currency": CURRENCY},
            },
        )
    wait(
        lambda: op.get("/v1/reconciliation/imports"),
        lambda b: (
            len(b) >= 2
            and all(x["state"] != "PENDING" and x["state"] != "IMPORTING" for x in b[:2])
        ),
        what="reconciliation import",
    )
    matches = wait(
        lambda: op.get("/v1/reconciliation/matches"),
        lambda m: len(m) > 0,
        timeout=30,
        what="matching job",
    )
    exceptions = op.get("/v1/reconciliation/exceptions")
    print(f"  {len(bank) - 1} bank rows, {len(ledger) - 1} ledger rows")
    print(f"  {len(matches)} exact matches proposed for review")
    for e in exceptions:
        t = e["transaction"]
        kind = e["kind"].lower().replace("_", " ")
        print(f"  exception: {kind} · {t['side']} {t['external_id']} {t['amount']['formatted']}")


# -- main ----------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--split", default="test", choices=["train", "validation", "test"])
    parser.add_argument("--limit", type=int, default=26)
    parser.add_argument("--refresh", action="store_true", help="fetch the rows again")
    args = parser.parse_args()

    settings = get_settings()
    if settings.env not in ("development", "test"):
        sys.exit("The dataset demo only runs in development or test environments.")
    try:
        httpx.get(f"{args.api}/healthz", timeout=5).raise_for_status()
    except httpx.HTTPError:
        sys.exit(f"The API is not reachable at {args.api}. Start it and the worker first.")

    invoices = load_rows(args.split, args.limit, args.refresh)
    print(f"Loaded {len(invoices)} invoices from {DATASET} ({args.split})")

    from apps.api.main import create_app

    db = create_app(settings).state.db
    api = Api(args.api, provision(db))
    print(f"\n1. Provisioned {ORG_NAME} ({CURRENCY}); sign in as operator@{DOMAIN}")
    print("2. Policies")
    publish_policies(api)
    vendors = create_vendors(api, invoices)
    verified = sum(v["verified"] for v in vendors.values())
    print(f"3. {len(vendors)} vendors, {verified} payees verified")
    for v in vendors.values():
        if v["rejected"]:
            print(f"   bank details refused for {v['name']}: {v['rejected']}")

    op = api.as_("operator")
    accuracy: Counter = Counter()
    created = [(inv, submit(op, inv, vendors[vendor_key(inv)]["id"])) for inv in invoices]
    results = []
    for inv, c in created:
        confirm(op, inv, c, accuracy)
        results.append((inv, evaluate(op, c["case_id"])))

    print(
        f"4. Extraction matched {accuracy['matched']}/{accuracy['checked']} labelled fields; "
        f"read {accuracy['lines_read']}/{accuracy['lines_expected']} lines"
    )
    outcomes = Counter(d["evaluation"]["outcome"] for _, d in results)
    print("   Outcomes: " + ", ".join(f"{k} {v}" for k, v in outcomes.most_common()))
    for inv, d in results:
        total = d["invoice"]["total"]["formatted"] if d["invoice"]["total"] else "?"
        outcome = d["evaluation"]["outcome"]
        print(f"   row {inv.row:>2} {d['vendor']['name'][:28]:<28} {total:>16}  {outcome}")
        for line in flagged(d):
            print(f"          {line}")
        for issue in inv.issues:
            print(f"          label defect: {issue}")

    print("\n5. Payment run (simulated, no money moves)")
    paid: list[tuple[HfInvoice, str, dict]] = []
    for inv, d in results:
        if d["evaluation"]["outcome"] != "PASS":
            continue
        d = case_detail(op, d["case"]["id"])
        log = pay(api, d, f"Payment of invoice {inv.number}")
        steps = "; ".join(log["steps"])
        amount = d["invoice"]["total"]["formatted"]
        print(f"   row {inv.row:>2} {amount:>14}  {log['result']}  {steps}")
        if log["result"] == "SETTLED":
            paid.append((inv, d["vendor"]["name"], log))
        elif "spend limit" in log["result"].lower() or log["result"].startswith("BLOCKED"):
            print("   Stopped the batch: the rest stay ready for tomorrow's run.")
            break

    if paid:
        first = paid[0][0]
        print(f"\n6. Vendor resends row {first.row} (invoice {first.number}) after it was paid")
        resent = submit(op, first, vendors[vendor_key(first)]["id"], name=f"resend-{first.row}.pdf")
        confirm(op, first, resent, Counter())
        d = evaluate(op, resent["case_id"])
        print(f"   {d['evaluation']['outcome']}: " + "; ".join(flagged(d)))

        print("\n7. Reconciliation")
        reconcile(op, paid)

    print(f"\nDone. Open the web app and sign in as operator@{DOMAIN} (or approver, auditor).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
