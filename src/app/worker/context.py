"""SyncContext — shared state and dependency container for sync operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from src.app.worker.session import run_async, session_scope

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from src.app.core.targets.base import BaseTarget


@dataclass
class MatchResult:
    """Result of matching a single source track against a target library."""

    matched: bool
    message: str = ""
    item_id: str | None = None
    title: str | None = None
    artist_name: str | None = None
    album_name: str | None = None
    duration: int | None = None
    rule_id: int | None = None


@dataclass
class SyncContext:
    """Shared state and dependencies for a sync operation.

    Constructed once per sync invocation and passed to all pipeline phases
    and worker objects. Owns session lifecycle and lazy target resolution.
    """

    sync_id: int
    target_id: str
    playlist_title: str = ""
    source_url: str = ""
    source: str = ""

    _target: BaseTarget | None = field(default=None, repr=False)

    @property
    def target(self) -> BaseTarget:
        """Lazy-load the target adapter (async → sync bridge)."""
        if self._target is None:
            from src.app.services import get_sync_target

            self._target = run_async(get_sync_target(self.target_id))
        assert self._target is not None
        return self._target

    def session(self):  # noqa: ANN201
        """Return a session_scope context manager."""
        return session_scope()
