"""Celery application configuration."""

import logging
import os
import sys

from celery import Celery

from src.app.log_config import setup_logging
from src.app.settings import settings


def _load_db_settings_overrides() -> bool | None:
    """Best-effort load of DB-backed settings before the worker starts.

    The worker does not run the FastAPI lifespan, so without this it would
    only ever see environment defaults (ignoring UI-configured values such as
    ``celery_worker_concurrency`` and ``celery_log_level``). Failures are
    non-fatal: a worker must still boot before the schema exists.

    Returns whether the instance has been set up (a ``secret_key`` row
    exists), or ``None`` when that cannot be determined.
    """
    try:
        from sqlalchemy import select

        from src.app.db import SessionLocal
        from src.app.models import Config

        with SessionLocal() as session:
            rows = session.execute(select(Config)).scalars().all()
        overrides = {row.key: row.value for row in rows}
        if overrides:
            settings.load_overrides(overrides)
        return "secret_key" in overrides
    except Exception as exc:  # pragma: no cover - startup best effort
        logging.getLogger(__name__).warning("Could not load settings overrides: %s", exc)
        return None


def _is_worker_process() -> bool:
    """Whether this module is being imported by the Celery worker CLI.

    ``app.worker.app`` is also imported by the API (services → target →
    worker session). Startup work must not run there: the schema may not exist
    yet (fresh install) and the API enforces its own gate in the lifespan.
    """
    return os.path.basename(sys.argv[0]).lower().startswith("celery")


if _is_worker_process():
    configured = _load_db_settings_overrides()

    # Fail closed: production requires a SECRET_KEY so token encryption at
    # rest is never keyed from a fixed, well-known value. A fresh install (no
    # secret_key row yet) may keep the worker up until the setup wizard stores
    # one; an unknown config state (e.g. schema not migrated yet) does not.
    if (
        configured is not False
        and settings.app_env == "production"
        and (not settings.secret_key or len(settings.secret_key) < 32)
    ):
        raise RuntimeError(
            "APP_ENV=production requires SECRET_KEY (at least 32 characters). "
            'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
        )

    # Fail closed: REQUIRE_AUTH=true without SECRET_KEY is a hard error
    if settings.require_auth and (not settings.secret_key or len(settings.secret_key) < 32):
        raise RuntimeError(
            "REQUIRE_AUTH=true requires SECRET_KEY (at least 32 characters). "
            'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
        )

setup_logging(level=settings.celery_log_level, log_format=settings.log_format)

logger = logging.getLogger(__name__)

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
