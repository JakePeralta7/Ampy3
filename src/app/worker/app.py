"""Celery application configuration."""

import logging
import os
import sys
from typing import Any

from celery import Celery
from celery.signals import worker_init

from src.app.log_config import setup_logging
from src.app.settings import settings


def _load_db_settings_overrides() -> bool:
    """Load DB-backed settings.

    Worker starts after receiving 'app:configured' signal, so DB is guaranteed
    to be ready and configured. This function loads settings from DB.
    """
    try:
        import os
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import Session

        # Build database URL from environment variables directly
        # to avoid any issues with imported engine state
        db_user = os.getenv("DATABASE_USERNAME", "ampy3")
        db_pass = os.getenv("DATABASE_PASSWORD", "ampy3")
        db_host = os.getenv("DATABASE_HOST", "postgres")
        db_port = os.getenv("DATABASE_PORT", "5432")
        db_name = os.getenv("DATABASE_NAME", "ampy3")
        database_url = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

        # Create a brand new engine each time with no pool
        engine = create_engine(database_url, poolclass=None)

        with Session(engine) as session:
            # Count rows with raw SQL
            result = session.execute(text("SELECT count(*) FROM config"))
            count = result.scalar()

            # Try selecting actual data
            result = session.execute(text("SELECT key, value FROM config"))
            rows = result.fetchall()

            # Now try ORM
            from src.app.models import Config as ConfigModel
            from sqlalchemy.orm import sessionmaker
            from sqlalchemy import select
            SessionFactory = sessionmaker(bind=engine)
            with SessionFactory() as orm_session:
                orm_rows = orm_session.execute(select(ConfigModel)).scalars().all()
                overrides = {row.key: row.value for row in orm_rows}

        engine.dispose()

        if overrides:
            settings.load_overrides(overrides)
        return True
    except Exception as exc:
        logging.getLogger(__name__).error("Failed to load settings overrides: %s", exc)
        raise RuntimeError(f"Failed to load settings from database: {exc}") from exc


def _validate_startup() -> None:
    """Validate required settings after DB overrides are loaded.

    Worker only starts after 'app:configured' signal, so secret_key
    is guaranteed to be available.
    """
    # Configured instance in production: require usable SECRET_KEY
    if settings.app_env == "production":
        if not settings.secret_key or len(settings.secret_key) < 32:
            raise RuntimeError(
                "APP_ENV=production requires SECRET_KEY (at least 32 characters). "
                'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
            )

    # REQUIRE_AUTH requires a secret key (either from env or DB)
    if settings.require_auth and (not settings.secret_key or len(settings.secret_key) < 32):
        raise RuntimeError(
            "REQUIRE_AUTH=true requires SECRET_KEY (at least 32 characters). "
            'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
        )


# Celery signal handlers
@worker_init.connect
def _on_worker_init(**kwargs: Any) -> None:
    """Load DB settings when worker process starts (after fork)."""
    # Load settings from DB (worker only starts after app:configured signal)
    _load_db_settings_overrides()
    _validate_startup()

    # Reconfigure logging now that celery_log_level may have changed
    setup_logging(level=settings.celery_log_level, log_format=settings.log_format)


# Initialize Celery app (no module-level side effects)
celery_app = Celery(
    "ampy3",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    result_expires=604800,  # 7 days — finished tasks must stay queryable, not flip back to PENDING
    task_acks_late=True,
    task_acks_on_failure_or_timeout=True,
    task_reject_on_worker_lost=True,
    task_time_limit=3600,
    task_soft_time_limit=3480,
    worker_prefetch_multiplier=1,
    worker_cancel_long_running_tasks_on_connection_loss=True,
    worker_hijack_root_logger=False,
    worker_log_color=False,
    worker_concurrency=settings.celery_worker_concurrency,
)

celery_app.conf.broker_transport_options = {
    "visibility_timeout": 14400,  # 4h — messages become visible to other workers after worker death
}