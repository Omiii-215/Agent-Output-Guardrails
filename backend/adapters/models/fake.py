"""Deterministic stand-in for a model provider.

Used for local development, tests and demos so no paid model calls or real
documents are needed. It reads the synthetic invoice layout with regular
expressions and returns the same typed, cited output a real provider must.
"""

from __future__ import annotations

import re
from decimal import Decimal

from .base import (
    Citation,
    Explanation,
    ExtractedField,
    ExtractedLine,
    FindingSummaryInput,
    InvoiceExtraction,
    ModelUnavailable,
)

_PATTERNS: dict[str, re.Pattern[str]] = {
    "invoice_number": re.compile(
        r"Invoice\s*(?:No\.?|Number|#)\s*[:\-]?\s*([A-Z0-9][A-Z0-9/\-]*)", re.I
    ),
    "invoice_date": re.compile(r"Invoice\s*Date\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})", re.I),
    "due_date": re.compile(r"Due\s*Date\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})", re.I),
    "po_number": re.compile(r"PO\s*(?:No\.?|Number|#)\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-]*)", re.I),
    "total": re.compile(r"Grand\s*Total\s*[:\-]?\s*(?:INR|Rs\.?|₹)?\s*([\d,]+\.\d{2})", re.I),
}
_CURRENCY = re.compile(r"\b(INR)\b|₹")
_LINE = re.compile(
    r"^(?P<desc>[^|\n]+?)\s*\|\s*(?P<qty>\d+(?:\.\d+)?)\s*\|\s*(?P<price>[\d,]+\.\d{2})"
    r"\s*\|\s*(?P<tax>\d+(?:\.\d+)?)%\s*$",
    re.M,
)


class FakeModelProvider:
    name = "fake"
    model_version = "fake-extractor-1"

    def __init__(self, *, fail: bool = False, fabricate_citation: bool = False):
        self.fail = fail
        self.fabricate_citation = fabricate_citation

    def extract_invoice(self, pages: list[tuple[int, str]]) -> InvoiceExtraction:
        if self.fail:
            raise ModelUnavailable("fake provider configured to fail")
        fields: list[ExtractedField] = []
        lines: list[ExtractedLine] = []
        for page, text in pages:
            for name, pattern in _PATTERNS.items():
                if any(f.name == name for f in fields):
                    continue
                m = pattern.search(text)
                if m:
                    value = m.group(1).replace(",", "") if name == "total" else m.group(1)
                    fields.append(
                        ExtractedField(
                            name=name,
                            value=value,
                            citation=Citation(page=page, start=m.start(1), end=m.end(1)),
                            confidence=0.9,
                        )
                    )
            c = _CURRENCY.search(text)
            if c and not any(f.name == "currency" for f in fields):
                fields.append(
                    ExtractedField(
                        name="currency",
                        value="INR",
                        citation=Citation(page=page, start=c.start(), end=c.end()),
                        confidence=0.8,
                    )
                )
            for m in _LINE.finditer(text):
                if m.group("desc").strip().lower().startswith("item"):
                    continue
                lines.append(
                    ExtractedLine(
                        description=m.group("desc").strip(),
                        quantity=m.group("qty"),
                        unit_price=m.group("price").replace(",", ""),
                        tax_rate=_pct(m.group("tax")),
                        citation=Citation(page=page, start=m.start(), end=m.end()),
                    )
                )
        if self.fabricate_citation and fields:
            first = fields[0]
            fields[0] = first.model_copy(
                update={"citation": Citation(page=99, start=0, end=5), "value": "9999999"}
            )
        return InvoiceExtraction(fields=fields, lines=lines)

    def explain(self, outcome: str, findings: list[FindingSummaryInput]) -> Explanation:
        if self.fail:
            raise ModelUnavailable("fake provider configured to fail")
        flagged = [f for f in findings if f.effect]
        if not flagged:
            return Explanation(summary=f"Outcome {outcome}: every selected check passed.")
        parts = [f"{f.message} ({f.rule_code})" for f in flagged]
        return Explanation(
            summary=f"Outcome {outcome}. " + " ".join(parts),
            cited_rules=[f.rule_code for f in flagged],
        )


def _pct(text: str) -> str:
    return str((Decimal(text) / Decimal(100)).normalize())
