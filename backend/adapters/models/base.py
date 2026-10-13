"""Model provider contract for bounded AI operations (ADR 0005).

Providers receive minimised, size-limited input and must answer with the typed
schemas below. They hold no credentials beyond their own API access and have
no tools that can reach application state.
"""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

FieldName = Literal[
    "invoice_number", "invoice_date", "due_date", "currency", "total", "po_number", "vendor_name"
]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Citation(Strict):
    page: int = Field(ge=1)
    start: int = Field(ge=0)
    end: int = Field(ge=1)


class ExtractedField(Strict):
    name: FieldName
    value: str = Field(min_length=1, max_length=200)
    citation: Citation
    confidence: float | None = Field(default=None, ge=0, le=1)  # diagnostic only


class ExtractedLine(Strict):
    description: str = Field(max_length=300)
    quantity: str
    unit_price: str
    tax_rate: str
    citation: Citation


class InvoiceExtraction(Strict):
    fields: list[ExtractedField] = Field(max_length=20)
    lines: list[ExtractedLine] = Field(default_factory=list, max_length=200)


class FindingSummaryInput(Strict):
    rule_code: str
    effect: str | None
    reason_code: str
    message: str


class Explanation(Strict):
    summary: str = Field(min_length=1, max_length=1500)
    cited_rules: list[str] = Field(default_factory=list, max_length=50)


class ModelUnavailable(RuntimeError):
    """Provider timeout, throttling or outage. Never treated as a pass."""


class ModelProvider(Protocol):
    name: str
    model_version: str

    def extract_invoice(self, pages: list[tuple[int, str]]) -> InvoiceExtraction: ...

    def explain(self, outcome: str, findings: list[FindingSummaryInput]) -> Explanation: ...
