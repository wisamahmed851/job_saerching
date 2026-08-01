"""
Encryption Service
==================
Symmetric encryption/decryption for sensitive stored values (e.g. SMTP passwords).
Uses Fernet (AES-128-CBC + HMAC-SHA256) from the cryptography package.

The key is read from settings.ENCRYPTION_KEY which must be a valid 32-byte
URL-safe base64-encoded key generated with Fernet.generate_key().
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _get_fernet() -> Fernet:
    key = settings.ENCRYPTION_KEY
    if not key:
        raise ValueError(
            "ENCRYPTION_KEY is not set in .env. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_password(plain_password: str) -> str:
    """Encrypt a plain-text password. Returns a URL-safe base64 string."""
    f = _get_fernet()
    return f.encrypt(plain_password.encode()).decode()


def decrypt_password(encrypted_password: str) -> str:
    """
    Decrypt an encrypted password back to plain text.
    Raises InvalidToken if the value is corrupted or the key changed.
    """
    f = _get_fernet()
    try:
        return f.decrypt(encrypted_password.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Could not decrypt SMTP password — key may have changed.") from exc
