"""SECRET_KEY length is enforced at construction; presence is checked at startup."""

import pytest
from pydantic import ValidationError

from src.app.settings import Settings


def test_require_auth_true_with_short_key_raises() -> None:
    with pytest.raises(ValidationError):
        Settings(require_auth=True, secret_key="short")


def test_require_auth_true_with_empty_key_is_deferred_to_startup() -> None:
    # The key may still come from the config table, so construction accepts
    # an empty value; main.enforce_startup_gate() rejects it after loading.
    settings = Settings(require_auth=True, secret_key="")
    assert settings.secret_key == ""


def test_production_with_short_key_raises() -> None:
    with pytest.raises(ValidationError, match="APP_ENV=production requires SECRET_KEY"):
        Settings(app_env="production", secret_key="short")


def test_production_with_empty_key_is_deferred_to_startup() -> None:
    # A fresh production install must be able to boot into the setup wizard.
    settings = Settings(app_env="production", secret_key="")
    assert settings.secret_key == ""


def test_require_auth_true_with_long_key_is_accepted() -> None:
    settings = Settings(require_auth=True, secret_key="k" * 32)
    assert settings.secret_key == "k" * 32


def test_require_auth_false_with_short_key_is_accepted() -> None:
    settings = Settings(require_auth=False, secret_key="short")
    assert settings.secret_key == "short"


def test_require_auth_false_with_empty_key_is_accepted() -> None:
    settings = Settings(require_auth=False, secret_key="")
    assert settings.secret_key == ""
