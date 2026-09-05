"""SECRET_KEY length is enforced only when REQUIRE_AUTH is enabled."""

import pytest
from pydantic import ValidationError

from src.app.settings import Settings


def test_require_auth_true_with_short_key_raises() -> None:
    with pytest.raises(ValidationError):
        Settings(require_auth=True, secret_key="short")


def test_require_auth_true_with_empty_key_is_deferred_to_startup() -> None:
    # Empty key passes the validator; startup (main.py lifespan) is what
    # refuses to boot with REQUIRE_AUTH=true and no SECRET_KEY.
    Settings(require_auth=True, secret_key="")


def test_require_auth_true_with_long_key_is_accepted() -> None:
    settings = Settings(require_auth=True, secret_key="k" * 32)
    assert settings.secret_key == "k" * 32


def test_require_auth_false_with_short_key_is_accepted() -> None:
    settings = Settings(require_auth=False, secret_key="short")
    assert settings.secret_key == "short"


def test_require_auth_false_with_empty_key_is_accepted() -> None:
    settings = Settings(require_auth=False, secret_key="")
    assert settings.secret_key == ""
