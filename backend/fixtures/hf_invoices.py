"""Rows of a public Hugging Face invoice dataset, normalised for the demo importer.

Dataset: ``katanaml-org/invoices-donut-data-v1`` — scanned invoices (JPEG) with
labelled fields ("ground truth"). The companies, people and addresses in it are
generated, not real businesses, and it carries no personal data of real people.

The labels are imperfect in the ways real documents are: one total carries a
stray digit, several totals differ from their lines by a cent because the issuer
rounded once at the end, and some lines have no VAT rate. Those defects are kept
on purpose so the guardrails meet them; they are reported, never repaired.

There is no OCR engine yet, so the importer renders each row's labels into a
text PDF (what OCR would hand the extractor) and sends that through the normal
upload, quarantine, extraction and confirmation path.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

from .pdf import text_pdf

DATASET = "katanaml-org/invoices-donut-data-v1"
DATASET_URL = f"https://huggingface.co/datasets/{DATASET}"
CURRENCY = "USD"  # every row is priced in US dollars ("$ 978,12")

# Tokens that start a postal address in the generated data (US military mail).
_ADDRESS_TOKENS = {"USNS", "USNV", "USS", "USCGC", "PSC", "UNIT", "FPO", "APO", "DPO"}


@dataclass(frozen=True)
class HfLine:
    description: str
    quantity: str  # plain decimal, e.g. "2"
    unit_price: str  # plain decimal with two places, e.g. "444.60"
    tax_percent: str | None  # "10"; None when the label has no VAT rate


@dataclass(frozen=True)
class HfInvoice:
    split: str
    row: int
    number: str | None
    date: str | None  # ISO 8601
    seller: str
    seller_address: str
    seller_tax_id: str | None
    client: str | None
    iban: str | None
    lines: tuple[HfLine, ...]
    total: str | None  # plain decimal, e.g. "978.12"
    raw_total: str | None  # as labelled, e.g. "$ 978,12"
    issues: tuple[str, ...] = field(default=())

    @property
    def source(self) -> str:
        return f"{DATASET} {self.split} row {self.row}"

    @property
    def source_url(self) -> str:
        return f"{DATASET_URL}/viewer/default/{self.split}?row={self.row}"

    @property
    def tax_rates(self) -> list[str | None]:
        return [
            None if line.tax_percent is None else _plain(Decimal(line.tax_percent) / 100)
            for line in self.lines
        ]


def parse_amount(text: str | None) -> str | None:
    """'$ 1579 929,37' -> '1579929.37'. The last ',' or '.' is the decimal mark."""
    if not text:
        return None
    digits = re.sub(r"[^0-9.,]", "", text)
    if not digits:
        return None
    mark = max(digits.rfind(","), digits.rfind("."))
    if mark != -1 and len(digits) - mark - 1 in (1, 2):
        whole, frac = digits[:mark], digits[mark + 1 :]
    else:
        whole, frac = digits, ""
    whole = re.sub(r"[.,]", "", whole) or "0"
    try:
        value = Decimal(f"{whole}.{frac}" if frac else whole)
    except InvalidOperation:
        return None
    return _plain(value)


def parse_date(text: str | None) -> str | None:
    """Dataset dates are US style, '09/18/2015'."""
    if not text:
        return None
    try:
        return datetime.strptime(text.strip(), "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


def split_party(text: str) -> tuple[str, str]:
    """'Bradley-Andrade 9879 Elizabeth Common ...' -> ('Bradley-Andrade', '9879 ...')."""
    tokens = text.split()
    for i, token in enumerate(tokens):
        if i and (token[0].isdigit() or token.upper().strip(",") in _ADDRESS_TOKENS):
            return " ".join(tokens[:i]).strip(" ,"), " ".join(tokens[i:])
    return text.strip(), ""


def bank_code(iban: str | None) -> str | None:
    """An 11-character BIC-style routing code from the IBAN's bank and country codes.

    The beneficiary form stores an 11-character routing code (IFSC in India). The
    dataset only has IBANs, so the code is derived, not looked up.
    """
    if not iban or len(iban) < 8:
        return None
    return f"{iban[4:8]}{iban[:2]}XXXXX".upper()


def normalise(split: str, row: int, ground_truth: str) -> HfInvoice:
    parsed = json.loads(ground_truth).get("gt_parse", {})
    header = parsed.get("header") or {}
    summary = parsed.get("summary") or {}
    items = parsed.get("items") or []
    if isinstance(items, dict):
        items = [items]
    issues: list[str] = []

    seller, address = split_party(header.get("seller") or "")
    tax_id = (header.get("seller_tax_id") or "").strip() or None
    if seller and not re.search(r"[A-Za-z]", seller):
        # Shifted labels: the seller field holds the tax ID and the name is missing.
        issues.append("seller label holds a tax ID, not a name")
        tax_id = tax_id or seller
        seller = ""
    if not seller:
        issues.append("seller name missing")
    client = split_party(header["client"])[0] if header.get("client") else None

    lines = []
    for item in items:
        qty = parse_amount(item.get("item_qty"))
        price = parse_amount(item.get("item_net_price"))
        if qty is None or price is None:
            issues.append("line without quantity or price")
            continue
        vat = (item.get("item_vat") or "").strip().rstrip("%").strip()
        if not vat:
            issues.append("line without a VAT rate")
        description = (item.get("item_desc") or "Item").replace("|", "/").strip()
        lines.append(
            HfLine(description, qty, f"{Decimal(price):.2f}", parse_amount(vat) if vat else None)
        )

    raw_total = summary.get("total_gross_worth")
    total = parse_amount(raw_total)
    if total is None:
        issues.append("total not labelled")
    date = parse_date(header.get("invoice_date"))
    if header.get("invoice_date") and date is None:
        issues.append("unreadable date")
    iban = (header.get("iban") or "").replace(" ", "") or None
    if iban is None:
        issues.append("no IBAN")

    return HfInvoice(
        split=split,
        row=row,
        number=(header.get("invoice_no") or "").strip() or None,
        date=date,
        seller=seller,
        seller_address=address,
        seller_tax_id=tax_id[:30] if tax_id else None,
        client=client,
        iban=iban[:30] if iban else None,
        lines=tuple(lines),
        total=total,
        raw_total=raw_total,
        issues=tuple(issues),
    )


def render_pdf(inv: HfInvoice) -> bytes:
    """The labelled fields as a text PDF in the layout the extractor reads."""
    body = [inv.seller or "(seller name not labelled)", inv.seller_address, "TAX INVOICE"]
    if inv.number:
        body.append(f"Invoice No: {inv.number}")
    if inv.date:
        body.append(f"Invoice Date: {inv.date}")
    body.append(f"Currency: {CURRENCY}")
    if inv.seller_tax_id:
        body.append(f"Seller tax ID: {inv.seller_tax_id}")
    if inv.client:
        body.append(f"Bill to: {inv.client}")
    if inv.iban:
        body.append(f"Pay to IBAN: {inv.iban}")
    body.append("Item | Qty | Unit Price | Tax")
    for line in inv.lines:
        tax = f"{line.tax_percent}%" if line.tax_percent is not None else "VAT not stated"
        body.append(f"{line.description[:90]} | {line.quantity} | {line.unit_price} | {tax}")
    if inv.total is not None:
        body.append(f"Grand Total: {CURRENCY} {Decimal(inv.total):,.2f}")
    body.append(f"Source: Hugging Face {inv.source}")
    return text_pdf([body])


def _plain(value: Decimal) -> str:
    return format(value.normalize(), "f")
