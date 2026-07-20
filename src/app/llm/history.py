"""Chat history persistence via Valkey.

Provides async functions for storing and retrieving chat messages.
"""
from __future__ import annotations

import json

from src.app.services.valkey import ValkeyService


async def append_message(session_id: str, role: str, content: str) -> None:
    client = ValkeyService.get_client()
    key = f"chat:{session_id}"
    msg = json.dumps({"role": role, "content": content})
    await client.rpush(key, msg)
    await client.expire(key, 604800)


async def get_history(session_id: str, limit: int = 50) -> list[dict]:
    client = ValkeyService.get_client()
    key = f"chat:{session_id}"
    items = await client.lrange(key, -limit, -1)
    return [json.loads(i) for i in items]


async def clear_history(session_id: str) -> None:
    client = ValkeyService.get_client()
    await client.delete(f"chat:{session_id}")
    await client.delete(f"chat:title:{session_id}")


async def set_title(session_id: str, title: str) -> None:
    client = ValkeyService.get_client()
    await client.setex(f"chat:title:{session_id}", 604800, title)


async def get_title(session_id: str) -> str | None:
    client = ValkeyService.get_client()
    title = await client.get(f"chat:title:{session_id}")
    return title.decode() if title else None
