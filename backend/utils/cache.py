import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Module-level state so the connection is created once per process
_client = None
_unavailable = False


async def _redis():
    """Return a live Redis client, or None if Redis is unreachable."""
    global _client, _unavailable
    if _unavailable:
        return None
    if _client is not None:
        return _client
    try:
        import redis.asyncio as redis
        url = os.getenv("REDIS_URL", "redis://localhost:6379")
        _client = redis.from_url(url, decode_responses=True)
        await _client.ping()
    except Exception as e:
        logger.warning("Redis unavailable (%s) — caching disabled for this session", e)
        _unavailable = True
        _client = None
    return _client


async def get_cached(key: str) -> dict | None:
    client = await _redis()
    if client is None:
        return None
    try:
        value = await client.get(key)
        return json.loads(value) if value else None
    except Exception as e:
        logger.warning("Redis get failed for %s: %s", key, e)
        return None


async def set_cached(key: str, value: Any, ttl_seconds: int) -> None:
    client = await _redis()
    if client is None:
        return
    try:
        await client.set(key, json.dumps(value), ex=ttl_seconds)
    except Exception as e:
        logger.warning("Redis set failed for %s: %s", key, e)