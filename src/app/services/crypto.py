"""Token encryption at rest using Fernet (AES-128-CBC + HMAC).

Encryption key is derived from SECRET_KEY via HKDF with domain separation.
This ensures tokens in the database (plex_token, jellyfin_api_key, etc.)
are encrypted at rest while remaining accessible to the application.
"""

import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from src.app.settings import settings

_FERNET: Fernet | None = None
_SESSION_KEY: bytes | None = None


def _derive_key(purpose: bytes) -> bytes:
    """Derive a 32-byte key from SECRET_KEY using HKDF with domain separation."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=purpose,
    )
    return hkdf.derive(settings.secret_key.encode())


def _get_fernet() -> Fernet:
    """Get or create the Fernet cipher using SECRET_KEY as key material.

    The key is derived via HKDF with purpose "fernet-token-encryption".
    """
    global _FERNET
    if _FERNET is None:
        key = _derive_key(b"fernet-token-encryption")
        _FERNET = Fernet(base64.urlsafe_b64encode(key))
    return _FERNET


def get_session_signing_key() -> bytes:
    """Get the session signing key derived via HKDF.

    Used for HMAC-SHA256 session cookie signing.
    """
    global _SESSION_KEY
    if _SESSION_KEY is None:
        _SESSION_KEY = _derive_key(b"session-signing")
    return _SESSION_KEY


def encrypt_token(token: str | None) -> str | None:
    """Encrypt a token for storage in the database.

    Returns a URL-safe base64-encoded Fernet token.
    """
    if not token:
        return token
    fernet = _get_fernet()
    return fernet.encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    """Decrypt a token from the database.

    All stored tokens are Fernet-encrypted; a non-Fernet value or an
    invalid key/corrupted payload raises DecryptionError to fail loudly
    on key rotation or misconfiguration.
    """
    if not encrypted:
        return encrypted
    fernet = _get_fernet()
    try:
        return fernet.decrypt(encrypted.encode()).decode()
    except InvalidToken:
        raise DecryptionError(
            "Failed to decrypt token: invalid key or corrupted data. "
            "This may indicate SECRET_KEY rotation without re-encryption."
        ) from None


class DecryptionError(Exception):
    """Raised when token decryption fails."""
