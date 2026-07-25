"""Celery task queue service."""

import logging

from src.app.services.base import ServiceBase

logger = logging.getLogger(__name__)


class CeleryService(ServiceBase):
    """Service for managing Celery app instance."""

    @classmethod
    def create(cls):
        from src.app.worker.app import celery_app

        logger.info("Using Celery app from src.app.tasks (broker: %s)", celery_app.conf.broker_url)
        return celery_app
