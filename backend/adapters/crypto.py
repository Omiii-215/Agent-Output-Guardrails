"""Field-level encryption for restricted values (ADR README data classes).

Values are encrypted with Fernet (AES-128-CBC + HMAC) under a key derived from
configuration; a keyed hash supports equality checks (has the bank account
changed?) without decrypting. Production keys come from Secrets Manager/KMS.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet


class FieldCipher:
    def __init__(self, secret: str):
        material = hashlib.sha256(("enc:" + secret).encode()).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(material))
        self._mac_key = hashlib.sha256(("mac:" + secret).encode()).digest()

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, token: str) -> str:
        return self._fernet.decrypt(token.encode()).decode()

    def fingerprint(self, value: str) -> str:
        return "hmac:" + hmac.new(self._mac_key, value.encode(), hashlib.sha256).hexdigest()


def mask(value: str, visible: int = 4) -> str:
    return "•" * max(0, len(value) - visible) + value[-visible:]
