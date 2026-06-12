"""
Redis-backed session storage — stateless design.

Sessions are JSON blobs keyed by session_id, TTL 1h.
Used by /chat endpoint to maintain multi-turn conversation history
across any number of stateless agent instances.
"""
import json
import uuid
from datetime import datetime, timezone

from app import state

SESSION_TTL = 3600
HISTORY_MAX = 20


def _key(session_id: str) -> str:
    return f"session:{session_id}"


def load(session_id: str) -> dict:
    """Load session dict. Empty dict if not found."""
    if state.use_redis():
        raw = state.get_client().get(_key(session_id))
        return json.loads(raw) if raw else {}
    return state.get_store().get("sessions", {}).get(_key(session_id), {})


def save(session_id: str, data: dict, ttl: int = SESSION_TTL) -> None:
    """Save session dict with TTL."""
    if state.use_redis():
        state.get_client().setex(_key(session_id), ttl, json.dumps(data))
    else:
        store = state.get_store()
        if "sessions" not in store:
            store["sessions"] = {}
        store["sessions"][_key(session_id)] = data


def append_message(session_id: str, role: str, content: str) -> list:
    """Append a message to history. Returns the full history list."""
    data = load(session_id)
    history = data.get("history", [])
    history.append({
        "role": role,
        "content": content,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    # Cap at HISTORY_MAX to prevent unbounded growth
    if len(history) > HISTORY_MAX:
        history = history[-HISTORY_MAX:]
    data["history"] = history
    save(session_id, data)
    return history


def get_history(session_id: str) -> list:
    """Get conversation history for a session."""
    return load(session_id).get("history", [])


def delete(session_id: str) -> None:
    """Delete a session."""
    if state.use_redis():
        state.get_client().delete(_key(session_id))
    else:
        store = state.get_store()
        store.get("sessions", {}).pop(_key(session_id), None)


def new_session_id() -> str:
    """Generate a new session ID."""
    return str(uuid.uuid4())
