"""Token encryption at rest using MultiFernet (AES-128-CBC + HMAC).

Key rotation is supported via MultiFernet:
- Encryption always uses the PRIMARY (first) key
- Decryption tries all keys in order (newest to oldest)
- Key rotation: add new key to front, call rotate() on existing tokens

The secret_key IS the encryption master key - stored plaintext in config table.
No boot-key chain: secret_key directly derives the Fernet key via HKDF.
"""

import base64

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from src.app.settings import settings

_MULTIFERNET: MultiFernet | None = None
_SESSION_KEY: bytes | None = None


def reset_crypto_caches() -> None:
    """Clear cached MultiFernet and session signing keys so they are re-derived
    when the SECRET_KEY changes (e.g., after rotation)."""
    global _MULTIFERNET, _SESSION_KEY
    _MULTIFERNET = None
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


def _get_multifernet() -> MultiFernet:
    """Get or create the MultiFernet instance using current secret_key.

    The key is derived via HKDF with purpose "fernet-token-encryption".
    For key rotation, this would return MultiFernet([new_key, old_key, ...]).
    Currently returns a single-key MultiFernet; rotation support can be
    added by maintaining a list of historical keys in the config table.
    """
    global _MULTIFERNET
    if _MULTIFERNET is None:
        fernet = _fernet_for(settings.secret_key)
        _MULTIFERNET = MultiFernet([fernet])
    return _MULTIFERNET


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
    multifernet = _get_multifernet()
    return multifernet.encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    """Decrypt a token from the database.

    All stored tokens are Fernet-encrypted; an invalid key or corrupted
    payload raises DecryptionError to fail loudly on key rotation
    or misconfiguration.
    """
    if not encrypted:
        return encrypted
    return _decrypt_with(_get_multifernet(), encrypted)


def rotate_token(encrypted: str) -> str:
    """Re-encrypt an existing token with the current primary key.

    Used during key rotation to migrate tokens to the newest key.
    """
    if not encrypted:
        return encrypted
    multifernet = _get_multifernet()
    return multifernet.rotate(encrypted.encode()).decode()


def _decrypt_with(multifernet: MultiFernet, encrypted: str) -> str:
    try:
        return multifernet.decrypt(encrypted.encode()).decode()
    except InvalidToken:
        raise DecryptionError(
            "Failed to decrypt token: invalid key or corrupted data. "
            "This may indicate the secret_key was rotated without re-encryption. "
            "Re-enter the credential in Settings, or run key rotation."
        ) from None


class DecryptionError(Exception):
    """Raised when token decryption fails."""
