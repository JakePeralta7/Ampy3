"""Celery application configuration."""

import logging
import os

from celery import Celery

from src.app.log_config import setup_logging
from src.app.settings import settings

# Fail closed: production requires a SECRET_KEY so token encryption at
# rest is never keyed from a fixed, well-known value.
if os.environ.get("APP_ENV") == "production" and (
    not settings.secret_key or len(settings.secret_key) < 32
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
)

celery_app.conf.broker_transport_options = {
    "visibility_timeout": 14400,  # 4h — messages become visible to other workers after worker death
}
