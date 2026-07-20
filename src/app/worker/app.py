"""Celery application configuration."""

import logging

from celery import Celery

from src.app.settings import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    'ampy3',
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer='json',
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    result_expires=3600,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_cancel_long_running_tasks_on_connection_loss=True,
)

celery_app.conf.broker_transport_options = {
    'visibility_timeout': 14400,  # 4h — messages become visible to other workers after worker death
}
