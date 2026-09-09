"""Regression tests for schedule target replacement in the schedules API."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.app.api.schedules import _replace_schedule_targets
from src.app.db import Base
from src.app.models import ScheduledPlaylistSync, ScheduleTarget


async def _make_session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = session_factory()
    session.add(
        ScheduledPlaylistSync(
            id=1,
            source="youtube_music",
            source_url="https://music.youtube.com/playlist?list=test",
            target_playlist_name="Test Playlist",
            schedule_interval="daily",
            next_sync_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    session.add(ScheduleTarget(sync_id=1, target_id="Plex"))
    await session.commit()
    return session


async def _selected_targets(session: AsyncSession) -> list[str]:
    from sqlalchemy import select

    result = await session.execute(select(ScheduleTarget).where(ScheduleTarget.sync_id == 1))
    return sorted(st.target_id for st in result.scalars().all())


@pytest.mark.asyncio
async def test_adds_new_target_and_keeps_existing():
    session = await _make_session()
    await _replace_schedule_targets(session, 1, ["Plex", "Jellyfin"])
    await session.commit()
    assert await _selected_targets(session) == ["Jellyfin", "Plex"]
    await session.close()


@pytest.mark.asyncio
async def test_removes_deselected_target():
    session = await _make_session()
    await _replace_schedule_targets(session, 1, ["Jellyfin"])
    await session.commit()
    assert await _selected_targets(session) == ["Jellyfin"]
    await session.close()


@pytest.mark.asyncio
async def test_reselecting_existing_target_is_idempotent():
    session = await _make_session()
    await _replace_schedule_targets(session, 1, ["Plex", "Jellyfin"])
    await session.commit()
    await _replace_schedule_targets(session, 1, ["Plex", "Jellyfin"])
    await session.commit()
    assert await _selected_targets(session) == ["Jellyfin", "Plex"]
    await session.close()
