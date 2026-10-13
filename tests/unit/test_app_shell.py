import logging

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from backend.config import Settings
from backend.telemetry.tracing import RedactingFilter, redact


def test_health_and_meta():
    client = TestClient(create_app(Settings(env="test")))
    assert client.get("/healthz").json() == {"status": "ok"}
    meta = client.get("/v1/meta")
    assert meta.json()["simulation_only"] is True
    assert meta.headers["X-Trace-Id"]


def test_trace_id_is_propagated_when_well_formed():
    client = TestClient(create_app(Settings(env="test")))
    resp = client.get("/healthz", headers={"X-Trace-Id": "abc12345-trace"})
    assert resp.headers["X-Trace-Id"] == "abc12345-trace"
    resp = client.get("/healthz", headers={"X-Trace-Id": "bad id with spaces"})
    assert resp.headers["X-Trace-Id"] != "bad id with spaces"


@pytest.mark.parametrize("env", ["staging", "production"])
def test_dev_identity_stub_cannot_be_enabled_outside_dev(env):
    with pytest.raises(ValueError, match="identity stub"):
        Settings(env=env, dev_identity_enabled=True)


def test_redaction_masks_account_numbers_and_ifsc():
    assert redact("acct 123456789012 ifsc HDFC0001234") == "acct [REDACTED] ifsc [REDACTED]"
    record = logging.LogRecord("finguard", logging.INFO, "", 0, "paid %s", ("998877665544",), None)
    RedactingFilter().filter(record)
    assert record.args == ("[REDACTED]",)
