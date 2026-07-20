"""Celery task queue service."""
import logging

logger = logging.getLogger(__name__)


class CeleryService:
    """Service for managing Celery app instance (reuses the configured app from tasks.py)."""

    _instance = None

    @classmethod
    def get_app(cls):
        """Get or initialize Celery app instance (lazy singleton)."""
        if cls._instance is None:
            from src.app.tasks import celery_app
            cls._instance = celery_app
            logger.info(f"Using Celery app from src.app.tasks (broker: {celery_app.conf.broker_url})")
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset Celery app instance."""
        cls._instance = None
        logger.info("Celery app reset")
