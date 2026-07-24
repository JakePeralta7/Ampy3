"""Load default match rules from bundled YAML files.

Default rules live under ``src/app/match_rules/defaults/`` and are
versioned alongside the codebase. They are seeded (or refreshed) into
the database once at startup via :func:`seed_default_rules`.

Rules are identified by their ``name`` field. On each startup:
- If a rule with that name does not exist, it is inserted.
- If it already exists **and** the YAML has changed, it is updated.
- Default rules are never deleted automatically.
"""
from __future__ import annotations

import logging
from pathlib import Path

import yaml

from src.app.match_rules.validator import validate_rule_yaml

logger = logging.getLogger(__name__)

DEFAULTS_DIR = Path(__file__).parent / "defaults"


def _load_yaml_files() -> list[tuple[int, str, str]]:
    """Return (priority, name, yaml_content) sorted by filename."""
    results = []
    for i, path in enumerate(sorted(DEFAULTS_DIR.glob("*.yaml"))):
        content = path.read_text(encoding="utf-8")
        try:
            rule_def = validate_rule_yaml(content)
        except Exception as exc:
            logger.error("Default rule %s failed validation: %s", path.name, exc)
            raise
        results.append((i, rule_def.name, content))
    return results


async def seed_default_rules() -> None:
    """Upsert default rules into the database.

    Called once during application startup after Alembic migrations.
    Uses the async session factory so it runs in the FastAPI event loop.
    """
    from sqlalchemy import select

    from src.app.db import AsyncSessionLocal
    from src.app.models import MatchRule

    default_rules = _load_yaml_files()
    if not default_rules:
        logger.warning("No default rule YAML files found in %s", DEFAULTS_DIR)
        return

    async with AsyncSessionLocal() as session:
        for priority, name, yaml_content in default_rules:
            stmt = select(MatchRule).where(MatchRule.name == name, MatchRule.is_default.is_(True))
            existing = (await session.execute(stmt)).scalars().first()

            if existing is None:
                rule = MatchRule(
                    name=name,
                    priority=priority,
                    is_active=True,
                    is_default=True,
                    yaml_content=yaml_content,
                )
                session.add(rule)
                logger.info("Seeded default rule: %s (priority=%d)", name, priority)
            elif existing.yaml_content != yaml_content:
                existing.yaml_content = yaml_content
                existing.priority = priority
                logger.info("Updated default rule: %s", name)
            else:
                logger.debug("Default rule unchanged: %s", name)

        await session.commit()
