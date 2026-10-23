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
# The key the process booted with. The ``secret_key`` config row is wrapped
# with this key (the deployment SECRET_KEY), not with the DB-stored working
# key: at boot the row must be decryptable before the working key is known.
# Captured at import, which happens before DB overrides are applied.
_BOOT_SECRET_KEY: str | None = settings.secret_key


def reset_crypto_caches() -> None:
    """Clear cached Fernet and session signing keys so they are re-derived
    when the SECRET_KEY changes (e.g., after rotation).

    The boot key is deliberately preserved: it wraps the ``secret_key`` row
    and must stay stable across working-key rotations.
    """
    global _FERNET, _SESSION_KEY
    _FERNET = None
    _SESSION_KEY = None


def _derive_key(purpose: bytes, secret_key: str | None = None) -> bytes:
    """Derive a 32-byte key from SECRET_KEY using HKDF with domain separation.

    Pass ``secret_key`` to derive from an explicit key instead of the
    current working key.
    """
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=purpose,
    )
    key_material = settings.secret_key if secret_key is None else secret_key
    return hkdf.derive(key_material.encode())


def _fernet_for(secret_key: str) -> Fernet:
    """Build a Fernet cipher for an explicit secret key."""
    key = _derive_key(b"fernet-token-encryption", secret_key)
    return Fernet(base64.urlsafe_b64encode(key))


def _get_boot_fernet() -> Fernet:
    """Get the cipher for the key this process booted with."""
    global _BOOT_SECRET_KEY
    if _BOOT_SECRET_KEY is None:
        _BOOT_SECRET_KEY = settings.secret_key
    return _fernet_for(_BOOT_SECRET_KEY)


def _get_fernet() -> Fernet:
    """Get or create the Fernet cipher using SECRET_KEY as key material.

    The key is derived via HKDF with purpose "fernet-token-encryption".
    """
    global _FERNET
    if _FERNET is None:
        _FERNET = _fernet_for(settings.secret_key)
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
    return _decrypt_with(_get_fernet(), encrypted)


def encrypt_token_with_key(token: str | None, secret_key: str) -> str | None:
    """Encrypt a token with an explicit key (used while rotating the key)."""
    if not token:
        return token
    return _fernet_for(secret_key).encrypt(token.encode()).decode()


def encrypt_boot_token(token: str | None) -> str | None:
    """Encrypt a token with the boot key (wraps the ``secret_key`` row)."""
    if not token:
        return token
    return _get_boot_fernet().encrypt(token.encode()).decode()


def decrypt_boot_token(encrypted: str) -> str:
    """Decrypt a token wrapped with the boot key (the ``secret_key`` row)."""
    if not encrypted:
        return encrypted
    return _decrypt_with(_get_boot_fernet(), encrypted)


def _decrypt_with(fernet: Fernet, encrypted: str) -> str:
    try:
        return fernet.decrypt(encrypted.encode()).decode()
    except InvalidToken:
        raise DecryptionError(
            "Failed to decrypt token: invalid key or corrupted data. "
            "This may indicate SECRET_KEY rotation without re-encryption."
        ) from None


class DecryptionError(Exception):
    """Raised when token decryption fails."""
