"""SECRET_KEY length is enforced at startup gate; presence is checked after DB load."""

import pytest

from src.app.settings import Settings


def test_secret_key_empty_by_default() -> None:
    settings = Settings()
    assert settings.secret_key == ""


def test_secret_key_can_be_set_directly() -> None:
    settings = Settings(secret_key="k" * 32)
    assert settings.secret_key == "k" * 32


def test_secret_key_short_is_accepted_at_construction() -> None:
    # Validation moved to startup gate (after DB load)
    settings = Settings(secret_key="short")
    assert settings.secret_key == "short"
