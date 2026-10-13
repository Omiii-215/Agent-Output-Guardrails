"""Text extraction from verified documents.

Digital PDFs are read with pypdf. Pages without a text layer are reported as
needing OCR; the pilot plugs Tesseract or Textract in behind ``OcrEngine``
after benchmarking. Parsing runs only on documents that passed quarantine.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Protocol

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_PAGES = 50


@dataclass(frozen=True)
class PageText:
    page: int  # 1-based
    text: str


@dataclass(frozen=True)
class TextExtraction:
    status: str  # OK | NEEDS_OCR | UNREADABLE | TOO_LARGE
    pages: tuple[PageText, ...] = ()
    extractor: str = "pypdf"


class OcrEngine(Protocol):
    def recognise(self, data: bytes, media_type: str) -> TextExtraction: ...


def extract_text(data: bytes, media_type: str, ocr: OcrEngine | None = None) -> TextExtraction:
    if media_type in ("text/plain", "text/csv"):
        return TextExtraction("OK", (PageText(1, data.decode("utf-8", errors="replace")),), "text")
    if media_type in ("image/png", "image/jpeg"):
        return ocr.recognise(data, media_type) if ocr else TextExtraction("NEEDS_OCR")
    if media_type != "application/pdf":
        return TextExtraction("UNREADABLE")
    try:
        reader = PdfReader(io.BytesIO(data))
        if len(reader.pages) > MAX_PAGES:
            return TextExtraction("TOO_LARGE")
        pages = tuple(
            PageText(i, (page.extract_text() or "").strip())
            for i, page in enumerate(reader.pages, start=1)
        )
    except (PdfReadError, ValueError, KeyError):
        return TextExtraction("UNREADABLE")
    if not any(p.text for p in pages):
        return ocr.recognise(data, media_type) if ocr else TextExtraction("NEEDS_OCR")
    return TextExtraction("OK", pages)
