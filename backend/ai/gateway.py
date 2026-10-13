"""AI gateway: the only path from application code to a model.

Each bounded operation minimises and size-limits its input, treats document
text as untrusted, validates the typed output and checks every citation
against the source text. Rejected values never reach a record; they become
warnings that route the case to a person.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from backend.adapters.models.base import (
    ExtractedField,
    ExtractedLine,
    FindingSummaryInput,
    ModelProvider,
)

# Phrases that try to steer an assistant. Flagging them makes the document
# reviewable; nothing in the document is ever executed or obeyed.
_INJECTION_PATTERNS = (
    re.compile(
        r"ignore\s+(all\s+|any\s+|the\s+|previous\s+|prior\s+)*(instructions|rules|polic)", re.I
    ),
    re.compile(r"(approve|release|pay)\s+(this|immediately|without)", re.I),
    re.compile(r"(bypass|skip|disable)\s+(the\s+)?(approval|review|check|verification)", re.I),
    re.compile(r"(you\s+are\s+now|act\s+as|system\s+prompt|developer\s+mode)", re.I),
    re.compile(r"change\s+(the\s+)?(bank|account|beneficiary)\s+(details|number)", re.I),
)


def injection_flags(text: str) -> list[str]:
    flags = []
    for pattern in _INJECTION_PATTERNS:
        m = pattern.search(text)
        if m:
            flags.append(m.group(0)[:120])
    return flags


@dataclass
class AcceptedField:
    name: str
    value: str
    page: int
    start: int
    end: int
    excerpt: str


@dataclass
class AcceptedLine:
    description: str
    quantity: str
    unit_price: str
    tax_rate: str
    page: int
    start: int
    end: int
    excerpt: str


@dataclass
class ExtractionOutcome:
    fields: list[AcceptedField] = field(default_factory=list)
    lines: list[AcceptedLine] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    injection_flags: list[str] = field(default_factory=list)
    model_version: str = ""
    truncated: bool = False


def _norm(value: str) -> str:
    return re.sub(r"[\s,₹]", "", value).upper()


def _excerpt(text: str, start: int, end: int, pad: int = 40) -> str:
    return text[max(0, start - pad) : min(len(text), end + pad)].strip()


def _citation_ok(pages: dict[int, str], page: int, start: int, end: int, value: str) -> bool:
    text = pages.get(page)
    if text is None or not 0 <= start < end <= len(text):
        return False
    return _norm(value) in _norm(text[start:end])


def _value_ok(name: str, value: str) -> bool:
    try:
        if name in ("invoice_date", "due_date"):
            date.fromisoformat(value)
        elif name == "total":
            return Decimal(value.replace(",", "")) >= 0
        elif name == "currency":
            return value in ("INR",)
    except (ValueError, InvalidOperation):
        return False
    return True


def extract_invoice(
    provider: ModelProvider, pages: list[tuple[int, str]], *, max_chars: int
) -> ExtractionOutcome:
    """Run bounded extraction. Raises ``ModelUnavailable`` on provider failure."""
    outcome = ExtractionOutcome(model_version=provider.model_version)
    budget, bounded = max_chars, []
    for number, text in pages:
        if budget <= 0:
            outcome.truncated = True
            break
        if len(text) > budget:
            outcome.truncated = True
        bounded.append((number, text[:budget]))
        budget -= len(text)
    page_map = dict(bounded)
    for _, text in bounded:
        outcome.injection_flags.extend(injection_flags(text))
    if outcome.truncated:
        outcome.warnings.append("DOCUMENT_TRUNCATED")

    result = provider.extract_invoice(bounded)

    seen: set[str] = set()
    for f in result.fields:
        if f.name in seen:
            outcome.warnings.append(f"DUPLICATE_FIELD:{f.name}")
            continue
        if not _accept(f, page_map, outcome):
            continue
        seen.add(f.name)
    for line in result.lines:
        _accept_line(line, page_map, outcome)
    return outcome


def _accept(f: ExtractedField, pages: dict[int, str], outcome: ExtractionOutcome) -> bool:
    c = f.citation
    value = f.value.replace(",", "") if f.name == "total" else f.value.strip()
    if not _citation_ok(pages, c.page, c.start, c.end, f.value):
        outcome.warnings.append(f"CITATION_INVALID:{f.name}")
        return False
    if not _value_ok(f.name, value):
        outcome.warnings.append(f"VALUE_INVALID:{f.name}")
        return False
    outcome.fields.append(
        AcceptedField(
            f.name, value, c.page, c.start, c.end, _excerpt(pages[c.page], c.start, c.end)
        )
    )
    return True


def _accept_line(line: ExtractedLine, pages: dict[int, str], outcome: ExtractionOutcome) -> None:
    c = line.citation
    text = pages.get(c.page)
    if (
        text is None
        or not 0 <= c.start < c.end <= len(text)
        or _norm(line.unit_price) not in _norm(text[c.start : c.end])
    ):
        outcome.warnings.append("CITATION_INVALID:line")
        return
    try:
        for value in (line.quantity, line.unit_price, line.tax_rate):
            if Decimal(value) < 0:
                raise InvalidOperation
    except InvalidOperation:
        outcome.warnings.append("VALUE_INVALID:line")
        return
    outcome.lines.append(
        AcceptedLine(
            line.description,
            line.quantity,
            line.unit_price,
            line.tax_rate,
            c.page,
            c.start,
            c.end,
            text[c.start : c.end].strip(),
        )
    )


def explain(
    provider: ModelProvider, outcome: str, findings: list[FindingSummaryInput]
) -> tuple[str, list[str]]:
    """Plain-language summary of saved findings. Never changes the outcome."""
    known = {f.rule_code for f in findings}
    result = provider.explain(outcome, findings)
    cited = [r for r in result.cited_rules if r in known]
    if len(cited) != len(result.cited_rules):
        raise ValueError("Explanation cited rules that were not evaluated")
    return result.summary.strip(), cited
