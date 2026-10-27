"""Tests for the Celery worker's fail-closed startup validation.

The worker does not run the FastAPI lifespan, so it re-implements the
secret-key gate after loading DB-backed settings. These tests pin the
tri-state contract: ``configured=True`` blocks without a usable key, while
``False``/``None`` (fresh install or unknown DB state) allow boot.
"""

import pytest

from src.app.core.startup import validate_worker_startup
from src.app.settings import Settings


def _settings(**overrides):
    values = {
        "_env_file": None,
        "app_env": "production",
        "require_auth": False,
        "secret_key": "",
        "database_username": "test",
        "database_password": "test",
    }
    values.update(overrides)
    return Settings(**values)


def test_configured_worker_without_secret_key_fails():
    with pytest.raises(RuntimeError, match="APP_ENV=production requires SECRET_KEY"):
        validate_worker_startup(True, _settings())


def test_unconfigured_or_unknown_state_may_boot():
    validate_worker_startup(False, _settings())
    validate_worker_startup(None, _settings())


def test_configured_worker_with_usable_secret_key_passes():
    validate_worker_startup(True, _settings(secret_key="k" * 32))


def test_require_auth_always_requires_a_secret_key():
    with pytest.raises(RuntimeError, match="REQUIRE_AUTH=true requires SECRET_KEY"):
        validate_worker_startup(None, _settings(require_auth=True))
