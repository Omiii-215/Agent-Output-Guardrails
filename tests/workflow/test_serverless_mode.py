"""Serverless hosting mode: documents in PostgreSQL and jobs processed inline.

These are the settings used on hosts without a shared disk or a long-lived
worker (for example Vercel functions with Neon). The workflow must behave the
same as with the separate worker and the filesystem object store.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from backend.adapters.object_store.db_store import DatabaseObjectStore
from backend.adapters.object_store.store import object_key
from backend.config import Settings
from backend.errors import NotFound
from backend.fixtures.pdf import text_pdf
from tests.conftest import World
from tests.support import BACKEND, ApiClient, case_detail, make_vendor, upload_bytes


def test_database_object_store_round_trip_and_tenant_isolation(db, two_orgs):
    acme, globex = two_orgs
    store = DatabaseObjectStore(db)
    key = object_key(acme, "documents", "doc-1", "original")

    assert not store.exists(acme, key)
    store.put(acme, key, b"first")
    store.put(acme, key, b"second version")  # overwrite keeps one row
    assert store.exists(acme, key)
    assert store.get(acme, key) == b"second version"

    # Another organization cannot read it, even with the exact key.
    with pytest.raises(NotFound):
        store.get(globex, key)
    assert not store.exists(globex, object_key(globex, "documents", "doc-1", "original"))


@pytest.fixture
def serverless_world(db, world: World) -> World:
    """Same organizations and members, served by an app in serverless mode."""
    app = create_app(Settings(env="test", object_store="database", inline_jobs=True), db=db)
    return World(acme=world.acme, globex=world.globex, api=ApiClient(TestClient(app)))


@pytest.mark.skipif(BACKEND == "sqlite", reason="the database object store is for PostgreSQL")
def test_uploaded_pdf_is_extracted_without_a_worker(serverless_world: World):
    w = serverless_world
    vendor_id, _ = make_vendor(w)
    pdf = text_pdf(
        [
            [
                "Shree Ganesh Metals",
                "TAX INVOICE",
                "Invoice No: SGM/2026/0099",
                "Invoice Date: 2026-10-01",
                "PO Number: PO-77",
                "Currency: INR",
                "Steel rods | 10 | 500.00 | 18%",
                "Grand Total: INR 5,900.00",
            ]
        ]
    )
    doc = upload_bytes(w, pdf, media_type="application/pdf", filename="invoice.pdf")
    resp = w.acme_as("operator").post(
        "/v1/invoices", json={"vendor_id": vendor_id, "document_version_id": doc, "extract": True}
    )
    assert resp.status_code == 201, resp.text

    # No run_once here: the API processed the extraction job before answering.
    detail = case_detail(w, resp.json()["case_id"])
    invoice = detail["invoice"]
    assert invoice["number"] == "SGM/2026/0099"
    assert invoice["total"]["amount_minor"] == "590000"
    assert invoice["field_status"]["total"]["status"] == "EXTRACTED"

    # The original document is still downloadable from the database store.
    grant = w.acme_as("operator").post(f"/v1/documents/{doc}/download-grants").json()
    assert w.api.client.get(grant["download_url"]).content == pdf
