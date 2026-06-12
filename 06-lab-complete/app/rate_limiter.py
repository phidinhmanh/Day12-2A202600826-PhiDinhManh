"""
Sliding-window rate limiter — Redis-backed for stateless scaling.

Algorithm: Sorted Set per (key, window).
- ZADD now now (member=unique_id, score=timestamp)
- ZREMRANGEBYSCORE -inf (now-window) — drop expired
- ZCARD — count active
- EXPIRE window — auto-cleanup if key idle

Atomic via Redis pipeline.
Falls back to in-memory deque in dev when Redis is down.
"""
import time
import uuid
from collections import defaultdict, deque
from fastapi import HTTPException

from app import state
from app.config import settings


def _now() -> float:
    return time.time()


def check_rate_limit(key: str) -> dict:
    """
    Check + record 1 request for `key`.
    Raises HTTPException 429 if over limit.

    Returns dict with limit/remaining/reset info.
    """
    window = 60  # 1 minute window
    limit = settings.rate_limit_per_minute
    now = _now()
    reset_at = int(now) + window
    redis_key = f"rl:{key}"

    if state.use_redis():
        r = state.get_client()
        member = f"{now}:{uuid.uuid4().hex[:6]}"
        pipe = r.pipeline()
        pipe.zremrangebyscore(redis_key, "-inf", now - window)
        pipe.zadd(redis_key, {member: now})
        pipe.zcard(redis_key)
        pipe.expire(redis_key, window + 1)
        _, _, count, _ = pipe.execute()
    else:
        # In-memory fallback
        store = state.get_store()
        if "rate" not in store:
            store["rate"] = defaultdict(deque)
        bucket = store["rate"][redis_key]
        while bucket and bucket[0] < now - window:
            bucket.popleft()
        bucket.append(now)
        count = len(bucket)

    if count > limit:
        retry_after = int(window) + 1
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "limit": limit,
                "window_seconds": window,
                "retry_after_seconds": retry_after,
            },
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_at),
                "Retry-After": str(retry_after),
            },
        )

    return {
        "limit": limit,
        "remaining": max(0, limit - count),
        "reset_at": reset_at,
    }
