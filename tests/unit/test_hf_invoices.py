"""Dataset normalisation, IBAN checks and multi-currency extraction.

The rows below are copied from katanaml-org/invoices-donut-data-v1 (test split),
whose companies are generated, so the suite runs offline.
"""

import json

import pytest

from backend.adapters.models.fake import FakeModelProvider
from backend.adapters.ocr.text import extract_text
from backend.ai import gateway
from backend.fixtures.hf_invoices import (
    bank_code,
    normalise,
    parse_amount,
    parse_date,
    render_pdf,
    split_party,
)
from backend.modules.invoices.service import iban_problem

ROW_0 = {
    "gt_parse": {
        "header": {
            "invoice_no": "97159829",
            "invoice_date": "09/18/2015",
            "seller": "Bradley-Andrade 9879 Elizabeth Common Lake Jonathan, RI 12335",
            "client": "Castro PLC Unit 9678 Box 9664 DPO AP 69387",
            "seller_tax_id": "985-73-8194",
            "client_tax_id": "994-72-1270",
            "iban": "GB81LZWO32519172531418",
        },
        "items": [
            {
                "item_desc": '12" Marble Lapis Inlay Chess Table Top W537',
                "item_qty": "2,00",
                "item_net_price": "444,60",
                "item_net_worth": "889,20",
                "item_vat": "10%",
                "item_gross_worth": "978,12",
            }
        ],
        "summary": {
            "total_net_worth": "$ 889,20",
            "total_vat": "$ 88,92",
            "total_gross_worth": "$ 978,12",
        },
    }
}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("$ 978,12", "978.12"),
        ("$ 1579 929,37", "1579929.37"),  # the dataset's stray-digit total, kept as labelled
        ("$13 717,81", "13717.81"),
        ("2,00", "2"),
        ("10,00", "10"),
        ("1.234", "1234"),
        ("", None),
    ],
)
def test_parse_amount(raw, expected):
    assert parse_amount(raw) == expected


def test_parse_date_and_party():
    assert parse_date("09/18/2015") == "2015-09-18"
    assert parse_date("18.09.2015") is None
    assert split_party("Sims PLC USS Kramer FPO AA 81651") == (
        "Sims PLC",
        "USS Kramer FPO AA 81651",
    )
    assert bank_code("GB81LZWO32519172531418") == "LZWOGBXXXXX"


def test_shifted_seller_label_is_reported_not_guessed():
    row = json.loads(json.dumps(ROW_0))
    row["gt_parse"]["header"]["seller"] = "907-77-8965"
    del row["gt_parse"]["header"]["seller_tax_id"]
    inv = normalise("test", 22, json.dumps(row))
    assert inv.seller == "" and inv.seller_tax_id == "907-77-8965"
    assert "seller label holds a tax ID, not a name" in inv.issues


def test_rendered_invoice_extracts_in_usd():
    inv = normalise("test", 0, json.dumps(ROW_0))
    text = extract_text(render_pdf(inv), "application/pdf")
    out = gateway.extract_invoice(
        FakeModelProvider(), [(p.page, p.text) for p in text.pages], max_chars=20_000
    )
    fields = {f.name: f.value for f in out.fields}
    assert fields == {
        "invoice_number": "97159829",
        "invoice_date": "2015-09-18",
        "currency": "USD",
        "total": "978.12",
    }
    assert [(line.quantity, line.unit_price, line.tax_rate) for line in out.lines] == [
        ("2", "444.60", "0.1")
    ]


@pytest.mark.parametrize(
    ("iban", "problem"),
    [
        ("GB81LZWO32519172531418", None),
        ("GB31LZX520242755934691", "check digits"),  # dataset row 1
        ("GB10YCPS61791791374226282", "22 characters"),  # dataset row 7: checksum passes
        ("12AB", "country code"),
    ],
)
def test_iban_validation(iban, problem):
    result = iban_problem(iban)
    assert result is None if problem is None else problem in result
