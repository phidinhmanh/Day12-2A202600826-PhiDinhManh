"""
Redis state management — 06-lab-complete.

Single source of truth for Redis connection.
Used by rate limiter, cost guard, session storage.

Production: Redis is mandatory. Fail-fast at startup if unreachable.
Dev/Staging: In-memory fallback allowed (with warning).
"""
import os
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Module-level state — assigned in init()
_redis_client: Optional["object"] = None
_connected: bool = False
_in_memory_store: dict = {}


def init() -> None:
    """
    Initialize Redis connection. Call from FastAPI lifespan startup.

    Production: raises RuntimeError if Redis unreachable.
    Dev/Staging: falls back to in-memory dict with warning.
    """
    global _redis_client, _connected

    try:
        import redis
        client = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=3)
        client.ping()
        _redis_client = client
        _connected = True
        logger.info(f"Redis connected: {REDIS_URL} (env={ENVIRONMENT})")
    except Exception as e:
        if ENVIRONMENT == "production":
            raise RuntimeError(
                f"Redis required in production but unreachable: {REDIS_URL} ({e})"
            ) from e
        _connected = False
        logger.warning(
            f"Redis unreachable ({e.__class__.__name__}); using in-memory fallback"
        )


def is_connected() -> bool:
    """True if Redis is connected and pingable."""
    if not _connected or _redis_client is None:
        return False
    try:
        return bool(_redis_client.ping())
    except Exception:
        return False


def get_client():
    """Return the raw Redis client (or None if not connected)."""
    return _redis_client


def use_redis() -> bool:
    """True if using Redis (vs in-memory fallback)."""
    return _connected


def get_store() -> dict:
    """In-memory fallback store (only used when Redis is down)."""
    return _in_memory_store


def shutdown() -> None:
    """Close Redis connection gracefully."""
    global _redis_client, _connected
    if _redis_client is not None:
        try:
            _redis_client.close()
        except Exception:
            pass
    _redis_client = None
    _connected = False
