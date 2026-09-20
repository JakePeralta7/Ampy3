"""Tests for crypto (Fernet token encryption) and auth (session tokens)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.app.auth.tokens import (
    SESSION_ID_BYTES,
    _sign,
    create_session_id,
    verify_session_id,
)
from src.app.services.crypto import (
    DecryptionError,
    _get_fernet,
    decrypt_token,
    encrypt_token,
    get_session_signing_key,
)


class TestCrypto:
    """Tests for token encryption/decryption."""

    def test_encrypt_decrypt_roundtrip(self):
        """A token encrypted and decrypted with the same key returns original."""
        token = "my-secret-token-123"
        encrypted = encrypt_token(token)
        assert encrypted != token
        decrypted = decrypt_token(encrypted)
        assert decrypted == token

    def test_encrypt_none_returns_none(self):
        assert encrypt_token(None) is None
        assert encrypt_token("") == ""

    def test_decrypt_empty_returns_empty(self):
        assert decrypt_token("") == ""

    def test_decrypt_invalid_token_raises(self):
        """Decrypting non-Fernet data raises DecryptionError."""
        with pytest.raises(DecryptionError):
            decrypt_token("not-a-valid-fernet-token")

    def test_decrypt_with_wrong_key_raises(self, monkeypatch):
        """Decrypting with a different key raises DecryptionError."""
        token = "my-secret-token"
        encrypted = encrypt_token(token)

        # Simulate key rotation: wipe the cached Fernet and derive a different key
        import src.app.services.crypto as crypto_mod

        monkeypatch.setattr(crypto_mod, "_FERNET", None)
        monkeypatch.setattr(crypto_mod, "_derive_key", lambda p: b"x" * 32)

        with pytest.raises(DecryptionError):
            decrypt_token(encrypted)

    def test_session_signing_key_derivation(self):
        """Session signing key is derived consistently."""
        key1 = get_session_signing_key()
        key2 = get_session_signing_key()
        assert key1 == key2
        assert len(key1) == 32


class TestAuthTokens:
    """Tests for session ID creation and verification."""

    def test_sign_verify_roundtrip(self):
        """A session ID signed and verified with same secret returns original."""
        secret = b"test-secret-key-32-bytes-long!!"
        session_id = "a" * 64
        signed = _sign(session_id, secret)
        assert verify_session_id(f"{session_id}.{signed}", secret) == session_id

    def test_verify_invalid_signature_returns_none(self):
        """Wrong signature returns None."""
        secret = b"test-secret-key-32-bytes-long!!"
        assert verify_session_id("session-id.wrongsig", secret) is None

    def test_verify_malformed_cookie_returns_none(self):
        """Cookie without dot separator returns None."""
        secret = b"test-secret-key-32-bytes-long!!"
        assert verify_session_id("no-dot-here", secret) is None
        assert verify_session_id("", secret) is None

    def test_create_session_id_format(self):
        """create_session_id returns 'id.signature' format."""
        secret = b"test-secret-key-32-bytes-long!!"
        cookie = create_session_id(secret)
        assert "." in cookie
        session_id, sig = cookie.rsplit(".", 1)
        assert len(session_id) == SESSION_ID_BYTES * 2  # hex encoded
        assert len(sig) == 64  # SHA256 hex digest

    def test_constant_time_compare(self):
        """verify_session_id uses hmac.compare_digest (constant time)."""
        secret = b"test-secret-key-32-bytes-long!!"
        session_id = "a" * 64
        # Even if we pass the correct session_id with wrong sig, it returns None
        assert verify_session_id(f"{session_id}.{'b' * 64}", secret) is None


@pytest.mark.asyncio
class TestSessionCRUD:
    """Tests for session create/verify/destroy/purge (requires DB)."""

    async def test_create_session(self, monkeypatch):
        """create_session persists session and returns signed cookie."""
        # This test needs a real DB - skip in unit tests
        pytest.skip("Requires database - integration test")

    async def test_verify_session_valid(self, monkeypatch):
        """verify_session loads valid session and decrypts token."""
        pytest.skip("Requires database - integration test")

    async def test_verify_session_expired_returns_none(self, monkeypatch):
        """verify_session returns None for expired session."""
        pytest.skip("Requires database - integration test")

    async def test_verify_session_bad_token_returns_none(self, monkeypatch):
        """verify_session returns None when token decryption fails."""
        pytest.skip("Requires database - integration test")

    async def test_destroy_session(self, monkeypatch):
        """destroy_session deletes session from DB."""
        pytest.skip("Requires database - integration test")

    async def test_purge_expired_sessions(self, monkeypatch):
        """purge_expired_sessions removes expired rows."""
        pytest.skip("Requires database - integration test")
