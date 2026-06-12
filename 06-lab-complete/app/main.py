"""
Production AI Agent — 06-lab-complete
Full assembly of Day 12 Parts 1-5:

  Part 1: Config (Pydantic-style dataclass + validate), JSON logging,
          health/ready probes, SIGTERM graceful shutdown.
  Part 2: Multi-stage slim Dockerfile, non-root user, healthcheck.
  Part 3: railway.toml + render.yaml for cloud deploys.
  Part 4: API Key + JWT auth, sliding-window rate limit, cost guard (80% warn).
  Part 5: Redis stateless sessions, in-flight request tracking,
          /ready dep check, lifespan drain on SIGTERM.
"""
import os
import time
import signal
import logging
import json
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Security, Depends, Request, Response
from fastapi.security.api_key import APIKeyHeader
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from app import state, auth as jwt_auth
from app.rate_limiter import check_rate_limit
from app.cost_guard import check_budget, record_usage, get_usage
from app import sessions
from app.config import settings

# Mock LLM (replace with OpenAI/Anthropic in production)
from utils.mock_llm import ask as llm_ask

# ─────────────────────────────────────────────────────────
# Logging — JSON structured (Part 1)
# ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.debug else settings.log_level,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
INSTANCE_ID = os.getenv("INSTANCE_ID", f"instance-{uuid.uuid4().hex[:6]}")
_is_ready = False
_request_count = 0
_error_count = 0
_in_flight_requests = 0

# ─────────────────────────────────────────────────────────
# Auth dependencies
# ─────────────────────────────────────────────────────────
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    if not api_key or api_key != settings.agent_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Include header: X-API-Key: <key>",
        )
    return api_key


def identify_user(
    api_key: Optional[str] = Security(api_key_header),
    creds: Optional[HTTPAuthorizationCredentials] = Security(HTTPBearer(auto_error=False)),
) -> str:
    """
    Return a stable user identifier for rate limit + cost guard keying.
    Prefers JWT subject, falls back to API key prefix.
    """
    if creds:
        try:
            payload = jwt_auth.verify_jwt(creds)
            return f"jwt:{payload['username']}"
        except HTTPException:
            pass
    if api_key and api_key == settings.agent_api_key:
        return f"key:{api_key[:8]}"
    raise HTTPException(401, "Authentication required (X-API-Key or Bearer JWT)")


# ─────────────────────────────────────────────────────────
# Lifespan — Part 1 + Part 5 (graceful drain on shutdown)
# ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(json.dumps({
        "event": "startup",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "instance_id": INSTANCE_ID,
    }))

    # Init Redis (Part 5: fail-fast in production, fallback in dev)
    try:
        state.init()
    except RuntimeError as e:
        logger.error(json.dumps({"event": "redis_init_failed", "error": str(e)}))
        raise  # halt startup in production

    # Simulate init work
    time.sleep(0.1)
    _is_ready = True
    logger.info(json.dumps({
        "event": "ready",
        "redis": state.use_redis(),
    }))

    yield

    # Shutdown — Part 5: drain in-flight requests up to 30s
    _is_ready = False
    deadline = time.time() + 30
    while _in_flight_requests > 0 and time.time() < deadline:
        logger.info(json.dumps({
            "event": "draining",
            "in_flight": _in_flight_requests,
        }))
        time.sleep(0.5)

    state.shutdown()
    logger.info(json.dumps({
        "event": "shutdown",
        "instance_id": INSTANCE_ID,
    }))


# ─────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    """Part 5: track in-flight requests for graceful drain."""
    global _request_count, _error_count, _in_flight_requests
    start = time.time()
    _request_count += 1
    _in_flight_requests += 1
    try:
        response: Response = await call_next(request)
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Instance-Id"] = INSTANCE_ID
        if "server" in response.headers:
            del response.headers["server"]
        duration = round((time.time() - start) * 1000, 1)
        logger.info(json.dumps({
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": duration,
        }))
        return response
    except Exception:
        _error_count += 1
        raise
    finally:
        _in_flight_requests -= 1


# ─────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000,
                          description="Your question for the agent")


class AskResponse(BaseModel):
    question: str
    answer: str
    model: str
    user: str
    timestamp: str
    rate_limit: dict


class TokenRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    question: str
    answer: str
    turn: int
    served_by: str
    storage: str


# ─────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────
@app.get("/", tags=["Info"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "instance_id": INSTANCE_ID,
        "endpoints": {
            "ask": "POST /ask (X-API-Key)",
            "chat": "POST /chat (X-API-Key, stateless multi-turn)",
            "history": "GET /chat/{session_id}/history",
            "auth_token": "POST /auth/token",
            "health": "GET /health",
            "ready": "GET /ready",
            "metrics": "GET /metrics (X-API-Key)",
        },
    }


# ─── Part 4: JWT token endpoint ─────────────────────────
@app.post("/auth/token", response_model=TokenResponse, tags=["Auth"])
def issue_token(body: TokenRequest):
    user = jwt_auth.authenticate_user(body.username, body.password)
    token, minutes = jwt_auth.create_token(user["username"], user["role"])
    return TokenResponse(access_token=token, expires_in_minutes=minutes)


# ─── Part 4: Simple ask with API Key + rate limit + cost guard
@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    request: Request,
    _key: str = Depends(verify_api_key),
):
    """
    Send a question to the AI agent.

    **Authentication:** `X-API-Key: <your-key>`
    """
    user = identify_user(api_key=_key, creds=None)
    rl_info = check_rate_limit(user)
    check_budget(user)

    logger.info(json.dumps({
        "event": "agent_call",
        "user": user,
        "q_len": len(body.question),
    }))

    answer = llm_ask(body.question)

    in_tok = len(body.question.split()) * 2
    out_tok = len(answer.split()) * 2
    record_usage(user, in_tok, out_tok)

    return AskResponse(
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        user=user,
        timestamp=datetime.now(timezone.utc).isoformat(),
        rate_limit={
            "limit": rl_info["limit"],
            "remaining": rl_info["remaining"],
            "reset_at": rl_info["reset_at"],
        },
    )


# ─── Part 5: Stateless multi-turn chat ─────────────────
@app.post("/chat", response_model=ChatResponse, tags=["Agent"])
async def chat(
    body: ChatRequest,
    _key: str = Depends(verify_api_key),
):
    """
    Multi-turn conversation with Redis-backed session storage.
    Send the same `session_id` across requests to maintain context.
    Stateless — any instance can serve any session.
    """
    user = identify_user(api_key=_key, creds=None)
    check_rate_limit(user)
    check_budget(user)

    session_id = body.session_id or sessions.new_session_id()
    sessions.append_message(session_id, "user", body.question)

    answer = llm_ask(body.question)
    history = sessions.append_message(session_id, "assistant", answer)

    in_tok = len(body.question.split()) * 2
    out_tok = len(answer.split()) * 2
    record_usage(user, in_tok, out_tok)

    return ChatResponse(
        session_id=session_id,
        question=body.question,
        answer=answer,
        turn=len([m for m in history if m["role"] == "user"]),
        served_by=INSTANCE_ID,
        storage="redis" if state.use_redis() else "in-memory",
    )


@app.get("/chat/{session_id}/history", tags=["Agent"])
def get_chat_history(session_id: str, _key: str = Depends(verify_api_key)):
    history = sessions.get_history(session_id)
    if not history:
        raise HTTPException(404, f"Session {session_id} not found or expired")
    return {"session_id": session_id, "count": len(history), "messages": history}


@app.delete("/chat/{session_id}", tags=["Agent"])
def delete_chat_session(session_id: str, _key: str = Depends(verify_api_key)):
    sessions.delete(session_id)
    return {"deleted": session_id}


# ─── Part 1: Probes ─────────────────────────────────────
@app.get("/health", tags=["Operations"])
def health():
    """Liveness probe — platform restarts container if this fails."""
    checks = {
        "llm": "mock" if not settings.openai_api_key else "openai",
        "redis": "connected" if state.is_connected() else ("fallback" if settings.environment != "production" else "down"),
    }
    return {
        "status": "ok",
        "instance_id": INSTANCE_ID,
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "in_flight_requests": _in_flight_requests,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
def ready():
    """Readiness probe — load balancer stops routing if this fails."""
    if not _is_ready:
        raise HTTPException(503, "Not ready")
    # Part 5: in production, also verify Redis is alive
    if settings.environment == "production" and not state.is_connected():
        raise HTTPException(503, "Redis dependency unavailable")
    return {
        "ready": True,
        "instance_id": INSTANCE_ID,
        "in_flight_requests": _in_flight_requests,
    }


@app.get("/metrics", tags=["Operations"])
def metrics(_key: str = Depends(verify_api_key)):
    """Metrics (protected)."""
    return {
        "instance_id": INSTANCE_ID,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
        "in_flight_requests": _in_flight_requests,
        "storage": "redis" if state.use_redis() else "in-memory",
    }


# ─── Cost guard metrics ─────────────────────────────────
@app.get("/usage/{user_id}", tags=["Operations"])
def user_usage(user_id: str, _key: str = Depends(verify_api_key)):
    return get_usage(user_id)


# ─────────────────────────────────────────────────────────
# Graceful shutdown — Part 1 + Part 5
# ─────────────────────────────────────────────────────────
def _handle_signal(signum, _frame):
    logger.info(json.dumps({"event": "signal_received", "signum": signum}))


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


if __name__ == "__main__":
    logger.info(f"Starting {settings.app_name} on {settings.host}:{settings.port}")
    logger.info(f"Environment: {settings.environment} | Instance: {INSTANCE_ID}")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
