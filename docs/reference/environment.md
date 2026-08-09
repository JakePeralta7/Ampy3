# Environment

Every runtime knob lives in [`Settings`][app.settings.Settings] — a Pydantic `BaseSettings` singleton. The authoritative list of fields and defaults is below; the prose walkthrough is in [Getting started → Configuration](../getting-started/configuration.md).

## Settings class

::: app.settings
    options:
      show_source: true
      members:
        - Settings
        - settings

## Where to look next

- [Getting started → Configuration](../getting-started/configuration.md)
- [Auth](../guides/auth.md) — `REQUIRE_AUTH`, `SECRET_KEY`, `APP_URL` in detail
- [Local setup](../development/local-setup.md) — development overrides