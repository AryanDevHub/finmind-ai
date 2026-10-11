"""encryption.py — envelope encryption (AES-256-GCM) for sensitive data at rest.

Used to encrypt consent tokens, external reference IDs, and merchant details
before database writes. The data encryption key (DEK) is derived from the
master key via HKDF, and each encryption uses a random 96-bit nonce.
"""
from __future__ import annotations

import base64
import os
from functools import lru_cache

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from backend.settings import get_settings


@lru_cache(maxsize=1)
def _derive_key() -> bytes:
    """Derive a 256-bit DEK from the master secret using HKDF-SHA256."""
    master = get_settings().secret_key.encode()
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"finmind-envelope-v1",
        info=b"data-encryption-key",
    ).derive(master)


def encrypt(plaintext: str) -> str:
    """AES-256-GCM encrypt -> base64 string (nonce + ciphertext + tag)."""
    if not isinstance(plaintext, str):
        raise TypeError("Plaintext must be a string")

    key = _derive_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # AESGCM.encrypt appends 16-byte authentication tag to ciphertext
    payload = nonce + ciphertext
    return base64.b64encode(payload).decode("ascii")


def decrypt(token: str) -> str:
    """Reverse of encrypt(). Raises ValueError on tampered data."""
    if not isinstance(token, str):
        raise ValueError("Token must be a string")

    try:
        payload = base64.b64decode(token, validate=True)
    except Exception as e:
        raise ValueError("Invalid base64 encoding") from e

    # Nonce is 12 bytes, AESGCM tag is 16 bytes -> minimum payload length is 28 bytes
    if len(payload) < 28:
        raise ValueError("Invalid ciphertext: payload too short")

    nonce = payload[:12]
    ciphertext = payload[12:]
    key = _derive_key()
    aesgcm = AESGCM(key)

    try:
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext_bytes.decode("utf-8")
    except Exception as e:
        raise ValueError("Decryption failed: corrupted or tampered ciphertext") from e


def encrypt_if_present(value: str | None) -> str | None:
    """Convenience: encrypt if not None."""
    if value is None:
        return None
    return encrypt(value)


def decrypt_if_present(value: str | None) -> str | None:
    """Convenience: decrypt if not None."""
    if value is None:
        return None
    return decrypt(value)
