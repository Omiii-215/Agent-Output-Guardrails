"""Quarantine inspection: content sniffing and malware scanning.

Uploaded bytes stay quarantined until their actual size, hash and sniffed type
match what was declared and a scanner reports them clean. The signature
scanner recognises the EICAR test file; production deployments plug in a real
scanning service behind the same protocol.
"""

from __future__ import annotations

from typing import Protocol

EICAR_MARKER = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"


class Scanner(Protocol):
    def scan(self, data: bytes) -> str | None:
        """Return a threat name, or ``None`` when clean."""


class SignatureScanner:
    def scan(self, data: bytes) -> str | None:
        if EICAR_MARKER in data:
            return "EICAR-Test-File"
        return None


def sniff_media_type(data: bytes) -> str | None:
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if b"\x00" in data[:4096]:
        return None
    try:
        data[:65536].decode("utf-8")
    except UnicodeDecodeError:
        return None
    return "text/plain"


def media_type_matches(declared: str, sniffed: str | None) -> bool:
    if sniffed is None:
        return False
    if declared == sniffed:
        return True
    # CSV is text; its structure is validated later by the import mapping.
    return declared == "text/csv" and sniffed == "text/plain"
