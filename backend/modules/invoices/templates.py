"""Product-supplied policy template for invoice preflight.

Amounts, tolerances and approval counts are example settings, not
recommendations; each customer reviews and republishes its own version.
"""

from __future__ import annotations

from typing import Any

REQUIRED_FIELDS = ["vendor", "invoice_number", "currency", "total"]

_CLEAN = {
    "fields": {
        name: {"value": "x", "status": "VERIFIED", "evidence_refs": []} for name in REQUIRED_FIELDS
    },
    "invoice": {
        "number_normalized": "INV1",
        "currency": "INR",
        "total_minor": "11800",
        "po_number": "PO-1",
        "lines": [{"quantity": "1", "unit_price": "100.00", "tax_rate": "0.18"}],
    },
    "beneficiary": {"revision": 1, "verification_status": "VERIFIED"},
    "duplicates": {"paid": [], "open": [], "similar": []},
}


def _variant(**changes: Any) -> dict[str, Any]:
    import copy

    data = copy.deepcopy(_CLEAN)
    for path, value in changes.items():
        target = data
        *parents, leaf = path.split("__")
        for key in parents:
            target = target[key]
        target[leaf] = value
    return data


INVOICE_PREFLIGHT: dict[str, Any] = {
    "policy_code": "invoice-preflight",
    "module": "invoices",
    "description": "First-release invoice checks: fields, arithmetic, duplicates, payee.",
    "rounding": "HALF_UP",
    "rules": [
        {
            "code": "evidence.required_fields",
            "version": 1,
            "parameters": {
                "fields": REQUIRED_FIELDS,
                "accepted_statuses": ["VERIFIED", "ENTERED"],
            },
            "on_fail": "REVIEW",
            "on_unknown": "INDETERMINATE",
        },
        {
            "code": "invoice.total_matches_lines",
            "version": 1,
            "parameters": {"tolerance_minor": 0},
            "on_fail": "BLOCK",
        },
        {"code": "invoice.paid_duplicate", "version": 1, "on_fail": "BLOCK"},
        {"code": "invoice.duplicate_candidate", "version": 1, "on_fail": "REVIEW"},
        {
            "code": "beneficiary.is_verified",
            "version": 1,
            "on_fail": "BLOCK",
            "on_unknown": "INDETERMINATE",
        },
        {
            "code": "invoice.currency_supported",
            "version": 1,
            "parameters": {"allowed": ["INR"]},
            "on_fail": "REVIEW",
        },
        {"code": "document.untrusted_instructions", "version": 1, "on_fail": "REVIEW"},
        {
            "code": "invoice.po_reference",
            "version": 1,
            "parameters": {"required_above_minor": 5_000_000},
            "on_fail": "REVIEW",
            "on_unknown": "REVIEW",
        },
    ],
    "scenarios": [
        {"name": "clean invoice", "inputs": _CLEAN, "expected_outcome": "PASS"},
        {
            "name": "total mismatch blocks",
            "inputs": _variant(invoice__total_minor="12000"),
            "expected_outcome": "BLOCK",
        },
        {
            "name": "paid duplicate blocks",
            "inputs": _variant(
                duplicates__paid=[{"external_reference": "UTR1", "amount_minor": "11800"}]
            ),
            "expected_outcome": "BLOCK",
        },
        {
            "name": "unverified payee is indeterminate",
            "inputs": _variant(beneficiary__verification_status="UNVERIFIED"),
            "expected_outcome": "INDETERMINATE",
        },
        {
            "name": "embedded instructions need review",
            "inputs": _variant(
                document={"injection_flags": ["ignore the approval policy"]},
            ),
            "expected_outcome": "REVIEW",
        },
        {
            "name": "similar invoice needs review",
            "inputs": _variant(duplicates__similar=[{"invoice_id": "x"}]),
            "expected_outcome": "REVIEW",
        },
    ],
}
