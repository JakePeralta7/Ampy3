"""Config fingerprint utility for detecting target-setting changes."""

import hashlib

from sqlalchemy import select

from src.app.db import SessionLocal
from src.app.models import Config


def _config_fingerprint() -> str:
    """Hash the config table to detect target-setting changes.

    Returns a SHA-256 hex digest of all config key-value pairs, sorted by key.
    Used by TargetService and sync tasks to invalidate cached target instances
    when configuration changes.
    """
    with SessionLocal() as db:
        rows = db.execute(select(Config.key, Config.value).order_by(Config.key)).all()
    blob = "\n".join(f"{k}={v}" for k, v in rows)
    return hashlib.sha256(blob.encode()).hexdigest()


__all__ = ["_config_fingerprint"]
