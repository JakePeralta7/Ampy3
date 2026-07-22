"""Shared API error handling utilities."""
from __future__ import annotations

import functools
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from fastapi import HTTPException

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def handle_api_errors(
    default_status: int = 500,
    log_level: int = logging.ERROR,
) -> Callable[[F], F]:
    """Decorator that catches exceptions in async endpoint functions and
    re-raises them as :class:`HTTPException`.

    Re-raises :class:`HTTPException` unchanged so explicit error
    responses from the endpoint body are preserved.

    Usage::

        @router.get("/things")
        @handle_api_errors()
        async def list_things():
            ...
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await fn(*args, **kwargs)
            except HTTPException:
                raise
            except Exception as exc:
                logger.log(
                    log_level,
                    "Error in %s.%s: %s",
                    fn.__module__,
                    fn.__qualname__,
                    exc,
                )
                raise HTTPException(
                    status_code=default_status,
                    detail=f"Internal error: {exc}",
                ) from exc

        return wrapper  # type: ignore[return-value]

    return decorator
