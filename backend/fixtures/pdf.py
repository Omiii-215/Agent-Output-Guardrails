"""Minimal text-PDF writer for synthetic fixtures and tests.

Produces a valid single-font PDF whose text pypdf can extract. It exists so the
demo and tests never need real customer documents.
"""

from __future__ import annotations


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def text_pdf(pages: list[list[str]]) -> bytes:
    """Build a PDF with one page per list of text lines."""
    objects: list[bytes] = []
    font_id = 3
    page_ids: list[int] = []
    content_ids: list[int] = []
    next_id = 4
    for _ in pages:
        page_ids.append(next_id)
        content_ids.append(next_id + 1)
        next_id += 2

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for page_lines, content_id in zip(pages, content_ids, strict=True):
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
            ).encode()
        )
        ops = ["BT", "/F1 11 Tf", "14 TL", "50 800 Td"]
        for line in page_lines:
            ops.append(f"({_escape(line)}) Tj T*")
        ops.append("ET")
        stream = "\n".join(ops).encode("latin-1", errors="replace")
        objects.append(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        )

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(out)


def invoice_pdf(
    *,
    vendor: str,
    number: str,
    date: str,
    lines: list[tuple[str, str, str, str]],
    total: str,
    po: str | None = None,
    extra: list[str] | None = None,
) -> bytes:
    """Synthetic invoice. ``lines`` are (description, qty, unit price, tax %)."""
    body = [
        f"{vendor}",
        "TAX INVOICE",
        f"Invoice No: {number}",
        f"Invoice Date: {date}",
    ]
    if po:
        body.append(f"PO Number: {po}")
    body.append("Item | Qty | Unit Price | Tax")
    body += [f"{d} | {q} | {p} | {t}%" for d, q, p, t in lines]
    body.append(f"Grand Total: INR {total}")
    body += extra or []
    return text_pdf([body])
