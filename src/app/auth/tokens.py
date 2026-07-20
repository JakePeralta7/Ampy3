"""HMAC-signed session tokens (stateless, like Pronaos).

The cookie value is: base64(JSON payload) + "." + HMAC-SHA256 signature.
No database lookups required — the token is self-contained and tamper-proof.
"""

import base64
import hashlib
import hmac
import json
import time


def sign_session(data: dict, secret: str, ttl_hours: int = 168) -> str:
    """Sign a session payload and return a cookie-safe token string.

    Args:
        data: Payload to sign (must be JSON-serializable).
        secret: Secret key for HMAC.
        ttl_hours: Hours until the token expires.

    Returns:
        Signed token string: ``base64(payload).hex(signature)``.
    """
    payload = {**data, "exp": int(time.time()) + ttl_hours * 3600}
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode().rstrip("=")

    sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()

    return f"{payload_b64}.{sig}"


def verify_session(token: str, secret: str) -> dict | None:
    """Verify a signed session token and return the payload, or ``None``.

    Returns:
        The original payload dict if valid and not expired, ``None`` otherwise.
    """
    try:
        payload_b64, sig = token.rsplit(".", 1)
    except ValueError:
        return None

    expected_sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        return None

    # Restore base64 padding
    padded = payload_b64 + "=" * (4 - len(payload_b64) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded))
    except Exception:
        return None

    if payload.get("exp", 0) < time.time():
        return None

    # Remove expiry from returned data
    payload.pop("exp", None)
    return payload
