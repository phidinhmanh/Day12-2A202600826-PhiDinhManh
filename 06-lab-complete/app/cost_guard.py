"""
Cost guard — Redis-backed daily budget enforcement.

Per-user + global budget. Atomic increment via HINCRBYFLOAT.
TTL 24h on daily keys → auto-cleanup at midnight rollover.
80% warning logged.

Falls back to in-memory dict in dev when Redis is down.
"""
import time
import logging
from datetime import datetime, timezone
from fastapi import HTTPException

from app import state
from app.config import settings

logger = logging.getLogger(__name__)

# GPT-4o-mini pricing (as of 2026)
PRICE_PER_1K_INPUT = 0.00015
PRICE_PER_1K_OUTPUT = 0.0006
WARN_AT_PCT = 0.8


def _calc_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens / 1000) * PRICE_PER_1K_INPUT + (output_tokens / 1000) * PRICE_PER_1K_OUTPUT


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def check_budget(user_id: str) -> None:
    """
    Verify user + global budget. Raises 402 if over.
    Logs warning at 80% threshold.
    """
    today = _today_key()
    user_budget = settings.daily_budget_usd
    global_budget = settings.global_daily_budget_usd

    user_key = f"budget:user:{user_id}:{today}"
    global_key = f"budget:global:{today}"

    if state.use_redis():
        r = state.get_client()
        pipe = r.pipeline()
        pipe.get(user_key)
        pipe.get(global_key)
        user_cost_str, global_cost_str = pipe.execute()
        user_cost = float(user_cost_str) if user_cost_str else 0.0
        global_cost = float(global_cost_str) if global_cost_str else 0.0
    else:
        store = state.get_store()
        if "budget" not in store:
            store["budget"] = {"users": {}, "global": {}}
        user_cost = store["budget"]["users"].get(user_key, 0.0)
        global_cost = store["budget"]["global"].get(global_key, 0.0)

    if global_cost >= global_budget:
        logger.critical(f"GLOBAL BUDGET EXCEEDED: ${global_cost:.4f}/{global_budget}")
        raise HTTPException(503, "Service temporarily unavailable. Budget exhausted.")

    if user_cost >= user_budget:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Daily budget exceeded",
                "used_usd": round(user_cost, 6),
                "budget_usd": user_budget,
                "resets_at": "midnight UTC",
            },
        )

    if user_cost >= user_budget * WARN_AT_PCT:
        logger.warning(
            f"User {user_id} at {user_cost/user_budget*100:.0f}% of daily budget"
        )


def record_usage(user_id: str, input_tokens: int, output_tokens: int) -> float:
    """
    Record token usage after LLM call. Returns the cost in USD for this call.
    Atomic via Redis HINCRBYFLOAT (or pipeline + SET in-memory).
    """
    cost = _calc_cost(input_tokens, output_tokens)
    if cost <= 0:
        return 0.0

    today = _today_key()
    user_key = f"budget:user:{user_id}:{today}"
    global_key = f"budget:global:{today}"
    ttl = 86400  # 24h

    if state.use_redis():
        r = state.get_client()
        pipe = r.pipeline()
        pipe.incrbyfloat(user_key, cost)
        pipe.expire(user_key, ttl)
        pipe.incrbyfloat(global_key, cost)
        pipe.expire(global_key, ttl)
        pipe.execute()
    else:
        store = state.get_store()
        if "budget" not in store:
            store["budget"] = {"users": {}, "global": {}}
        store["budget"]["users"][user_key] = store["budget"]["users"].get(user_key, 0.0) + cost
        store["budget"]["global"][global_key] = store["budget"]["global"].get(global_key, 0.0) + cost

    return cost


def get_usage(user_id: str) -> dict:
    """Read current usage for a user."""
    today = _today_key()
    user_budget = settings.daily_budget_usd
    user_key = f"budget:user:{user_id}:{today}"
    global_key = f"budget:global:{today}"

    if state.use_redis():
        r = state.get_client()
        user_cost_str = r.get(user_key)
        global_cost_str = r.get(global_key)
        user_cost = float(user_cost_str) if user_cost_str else 0.0
        global_cost = float(global_cost_str) if global_cost_str else 0.0
    else:
        store = state.get_store()
        user_cost = store.get("budget", {}).get("users", {}).get(user_key, 0.0)
        global_cost = store.get("budget", {}).get("global", {}).get(global_key, 0.0)

    return {
        "user_id": user_id,
        "date": today,
        "cost_usd": round(user_cost, 6),
        "budget_usd": user_budget,
        "budget_remaining_usd": round(max(0, user_budget - user_cost), 6),
        "budget_used_pct": round(user_cost / user_budget * 100, 1) if user_budget > 0 else 0.0,
        "global_cost_usd": round(global_cost, 6),
    }
