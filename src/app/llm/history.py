"""Chat history persistence via Valkey.

Provides async functions for storing and retrieving chat messages.
"""
from __future__ import annotations

import json

from src.app.services.valkey import ValkeyService


async def append_message(
    session_id: str, role: str, content: str, flow_items: list[dict] | None = None
) -> None:
    client = ValkeyService.get_instance()
    key = f"chat:{session_id}"
    msg: dict = {"role": role, "content": content}
    if flow_items:
        msg["flow_items"] = flow_items
    await client.rpush(key, json.dumps(msg))
    await client.expire(key, 604800)


async def get_history(session_id: str, limit: int = 50) -> list[dict]:
    client = ValkeyService.get_instance()
    key = f"chat:{session_id}"
    items = await client.lrange(key, -limit, -1)
    return [json.loads(i) for i in items]


async def clear_history(session_id: str) -> None:
    client = ValkeyService.get_instance()
    await client.delete(f"chat:{session_id}")
    await client.delete(f"chat:title:{session_id}")


async def set_title(session_id: str, title: str) -> None:
    client = ValkeyService.get_instance()
    await client.setex(f"chat:title:{session_id}", 604800, title)


async def get_title(session_id: str) -> str | None:
    client = ValkeyService.get_instance()
    title = await client.get(f"chat:title:{session_id}")
    return title if title else None
