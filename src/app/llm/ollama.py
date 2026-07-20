from __future__ import annotations

import httpx
from langchain_ollama import ChatOllama

from src.app.settings import settings


def get_llm(**kwargs) -> ChatOllama:
    return ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_host,
        temperature=kwargs.pop("temperature", 0.1),
        num_predict=kwargs.pop("max_tokens", 4096),
        timeout=settings.ollama_timeout,
        **kwargs,
    )


def get_async_streaming_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.ollama_host,
        timeout=settings.ollama_timeout,
    )


async def health_check() -> dict:
    async with httpx.AsyncClient(base_url=settings.ollama_host, timeout=10) as client:
        resp = await client.get("/api/tags")
        resp.raise_for_status()
        tags = resp.json()
        return tags
