import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("rep")

async def main():
    logger.info("Starting Ampy3 API...")
    from src.app.db import init_db
    try:
        await init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.warning("Could not initialize database on startup: %s", e)

    from src.app.auth.tokens import purge_expired_sessions
    try:
        await purge_expired_sessions()
        logger.info("purge done")
    except Exception as e:
        logger.warning("purge failed: %s", e)

    try:
        from src.app.services import get_sync_target
        plex_target = await get_sync_target("Plex")
        sections = await plex_target.get_sections()
        logger.info("Plex sections: %d", len(sections))
    except Exception as e:
        logger.warning("Plex init failed: %s", e)

    try:
        from src.app.services.scheduler import SchedulerService
        await SchedulerService.start()
        logger.info("scheduler started")
    except Exception as e:
        logger.warning("scheduler failed: %s", e)

    logger.info("ALL STARTUP STEPS DONE")

asyncio.run(main())
