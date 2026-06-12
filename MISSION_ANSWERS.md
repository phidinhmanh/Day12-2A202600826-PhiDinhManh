# Day 12 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found in basic code (`develop/app.py`)
1. **Hardcoded Secrets:** The OpenAI API key and Postgres Database URL are written directly in the code, creating a high risk of credential exposure on public source control.
2. **Fixed Host Port:** The application listens strictly on port `8000` and binds only to `localhost` (`127.0.0.1`), which makes it unreachable inside a Docker container or target cloud deployment environments where port bindings are dynamically assigned via `PORT` env var.
3. **No Config Management:** Critical application states like `DEBUG` and model params are declared directly in-line rather than decoupled into settings or env files.
4. **Ineffective logging via `print()`:** Using stdout printing which lacks severity levels, timestamp formats, and prints sensitive values like the hardcoded API Key.
5. **No Health check or Readiness endpoints:** Cloud platforms cannot monitor instance stability or handle traffic failover.
6. **No Graceful Shutdown Handling:** Immediate kill processes can truncate in-flight network requests.
7. **Reload Mode enabled:** Development auto-reload is enabled directly, causing unnecessary resource consumption and performance issues in production.

### Exercise 1.3: Comparison table

| Feature | Develop | Production | Why Important? |
|---------|---------|------------|----------------|
| **Config** | Hardcoded inside python files | Decoupled via Environment Variables (`.env` & Pydantic settings) | Prevents committing secrets, enables port mapping flexibility across multiple dev/prod stages. |
| **Health check** | None | `/health` (Liveness) & `/ready` (Readiness) endpoints | Allows orchestrators (Kubernetes, Railway) to monitor instance status and automatically restart/failover. |
| **Logging** | Native `print()` statements | Structured JSON Logging (`json.dumps`) | Allows log aggregators (Datadog, Loki) to easily index, search, and parse application diagnostics. |
| **Shutdown** | Abrupt terminate | Graceful Shutdown (lifespan manager, `SIGTERM` handler) | Ensures active connections and in-flight HTTP requests complete without loss of data or connection truncation. |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile concepts (develop version)
1. **Base Image:** `python:3.11`. This is a full-featured Debian-based Python image. It is quite large (~1 GB) because it contains full build systems and compilers.
2. **Working Directory:** `/app`. This sets the default directory inside the container for all subsequent commands (COPY, RUN, CMD).
3. **Why COPY requirements.txt first?** This separates dependency installation from source code copies. By copying only `requirements.txt` first and running `pip install`, Docker can cache the installed packages layer. Future builds will bypass `pip install` unless `requirements.txt` actually changes, significantly speeding up build times.
4. **CMD vs ENTRYPOINT:**
   - `CMD` provides default arguments or commands that can be easily overridden when running `docker run <image> <override-command>`.
   - `ENTRYPOINT` sets the primary executable. Arguments passed to `docker run` are appended to the entrypoint rather than overriding it.

### Exercise 2.3: Image size comparison
- **Develop Image (`my-agent:develop`):** ~1.02 GB (1020 MB)
- **Production Image (`my-agent:advanced`):** ~142 MB
- **Difference:** ~86% reduction in size.
- **Why it is smaller:** The production version uses `python:3.11-slim` as the base image (which excludes large compilers and packages) and implements a **multi-stage build**. The build dependencies (`gcc`, `libpq-dev`) are installed and used only in the first stage (`builder`), while the final stage (`runtime`) only copies the pre-built Python dependencies and code, resulting in a clean and minimal runtime image.

### Exercise 2.4: Docker Compose stack architecture
```
Client (Port 80) ────> Nginx (Reverse Proxy/LB) 
                                │
                 ┌──────────────┴──────────────┐
                 ▼                             ▼
        Agent 1 (Port 8000)           Agent 2 (Port 8000)
                 │                             │
                 └──────────────┬──────────────┘
                                ▼
                       Redis (Port 6379)
```
- **Services started:** `nginx`, `agent` (2 replicas), `redis`, `qdrant`.
- **Communication:** Services communicate using Docker's internal user-defined network (`internal`). Nginx acts as the single entry point, routing requests to the stateless agent containers. Agents access Redis for rate-limiting/session storage and Qdrant for vector storage.

---

## Part 3: Cloud Deployment

### Exercise 3.1: Railway vs Render Deployment Configuration Comparison

| Aspect | Railway (`railway.toml`) | Render (`render.yaml`) |
|---|---|---|
| **Config Style** | Single config file, applies to current project/service | Blueprint — declares multiple services in one file |
| **Builder** | `NIXPACKS` (auto-detect, no Dockerfile required) | `buildCommand: pip install -r requirements.txt` (explicit) |
| **Port Binding** | Railway injects `$PORT` env var automatically | Render injects `$PORT` env var automatically |
| **Start Command** | `uvicorn app:app --host 0.0.0.0 --port $PORT` | `uvicorn app:app --host 0.0.0.0 --port $PORT` |
| **Health Check** | `healthcheckPath = "/health"`, `healthcheckTimeout = 30` | `healthCheckPath: /health` |
| **Restart Policy** | `restartPolicyType = "ON_FAILURE"`, `maxRetries = 3` | Implicit — Render restarts on health check failure |
| **Secrets** | Set via CLI (`railway variables set`) or Dashboard | Declarative: `sync: false` (manual) or `generateValue: true` (auto) |
| **Multi-Service** | One file = one service; Redis/DB added as separate services | Single YAML declares web + Redis together with dependency links |
| **Region** | Inherited from project settings | Explicit: `region: singapore` |
| **Plan/Tier** | Set in Dashboard | Declarative: `plan: free` |
| **Auto Deploy** | Branch-based via project settings | `autoDeploy: true` per-service |
| **Runtime Pin** | Inferred by NIXPACKS | Explicit: `PYTHON_VERSION: 3.11.0` |

**Key takeaways:**
- **Railway = minimal config, CLI-first, quick start.** One file, fewer knobs.
- **Render = IaC-first, multi-service blueprints, Git-driven.** Better for teams that want infra-as-code.
- **Both inject `$PORT`** — app MUST read `os.getenv("PORT")`, never hardcode `8000`.

### Exercise 3.2: Railway CLI deployment workflow (dry-run first)

> **Golden rule:** Always run `railway status` BEFORE `railway up` to verify which project + environment you are deploying to. `railway up` deploys immediately — there is no "staging" by default.

**Standard deploy steps:**

```powershell
# 1. Install Railway CLI (requires Node.js)
npm install -g @railway/cli

# 2. Login (opens browser)
railway login

# 3. Initialize project (run from project root)
cd 03-cloud-deployment/railway
railway init
# → Choose: "Empty project" or link to existing
# → Choose environment: production

# 4. DRY-RUN CHECK — verify target project before deploying
railway status
# Confirms: project name, environment, service, branch

# 5. Set secrets via CLI (never commit)
railway variables set OPENAI_API_KEY=sk-your-key-here
railway variables set ENVIRONMENT=production
railway variables set AGENT_API_KEY=$(openssl rand -hex 32)

# 6. Verify variables set
railway variables

# 7. Deploy — runs from current directory
railway up
# → Streams build + deploy logs to terminal
# → Returns deployment URL when ready

# 8. Open deployed app
railway open

# 9. Verify health endpoint
curl https://<your-app>.up.railway.app/health

# 10. Test agent
curl -X POST https://<your-app>.up.railway.app/ask `
  -H "Content-Type: application/json" `
  -d '{"question":"Hello Railway"}'

# 11. Tail live logs
railway logs

# 12. Rollback if needed
railway rollback
```

**Dry-run safety checklist:**
- [ ] Ran `railway status` — confirmed project + env
- [ ] All secrets set via `railway variables set`, none in code
- [ ] `railway.toml` committed, `requirements.txt` pinned
- [ ] Local `python app.py` works on `PORT=8000`
- [ ] `/health` endpoint returns 200 before deploying

**Common pitfalls:**
- Hardcoding `port=8000` → app fails to start on Railway's random `$PORT`. Use `os.getenv("PORT")`.
- Forgetting `railway.toml` → NIXPACKS auto-detects but you lose health check + restart policy.
- Committing `.env` → Railway will not load it. Use `railway variables set` instead.
- No `/health` route → health check fails silently, no auto-restart on crash.

---

## Part 4: API Security

### Exercise 4.1-4.3: Test results

#### 1. Basic API Key Authentication (Develop app)
- Request without API Key:
```json
HTTP/1.1 401 Unauthorized
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```
- Request with valid API Key (`demo-key-change-in-production`):
```json
HTTP/1.1 200 OK
{"question":"Hello","answer":"[Mock LLM] Dịch vụ đang sẵn sàng! Bạn vừa hỏi: Hello"}
```

#### 2. Advanced Security Stack (Production app with JWT + Rate Limiting)
- JWT Token request (`POST /auth/token` with credentials `student`/`demo123`):
```json
HTTP/1.1 200 OK
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5c...",
  "token_type": "bearer",
  "expires_in_minutes": 60,
  "hint": "Include in header: Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5c..."
}
```
- Query `/ask` using the retrieved JWT:
```json
HTTP/1.1 200 OK
{
  "question": "Explain Docker in one sentence.",
  "answer": "Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!",
  "usage": {
    "requests_remaining": 9,
    "budget_remaining_usd": 1.9e-05
  }
}
```
- Rate Limiting Verification (flooding 12 requests in a window):
```
Request #1: HTTP 200 (OK)
Request #2: HTTP 200 (OK)
Request #3: HTTP 200 (OK)
Request #4: HTTP 200 (OK)
Request #5: HTTP 200 (OK)
Request #6: HTTP 200 (OK)
Request #7: HTTP 200 (OK)
Request #8: HTTP 200 (OK)
Request #9: HTTP 200 (OK)
Request #10: HTTP 429 Too Many Requests - {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":39}}
Request #11: HTTP 429 Too Many Requests - {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":37}}
Request #12: HTTP 429 Too Many Requests - {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":35}}
```

### Exercise 4.4: Cost guard implementation
- **In-Memory Limitations:** The in-memory cost guard stores consumption in a local Python dictionary. This is stateful and will fail in a scaled production cluster where requests are load balanced across multiple containers, leading to inconsistent budget enforcement and out-of-budget billing.
- **Stateless Production Approach:**
  - **Redis Storage:** We decouple the cost record state into Redis. We store user consumption at the key: `budget:user:{user_id}:{current_date}`.
  - **Thread-Safety & Race Conditions:** We use Redis atomic commands (e.g. `HINCRBY` / `HINCRBYFLOAT` inside `cost_guard.py` or a pipeline) to record input/output token usage.
  - **Budget Check Before Execution:** Before initiating the LLM request, we do a Redis `GET` or `HGETALL` on `budget:user:{user_id}:{date}` and compare `cost_usd` against the threshold. If it exceeds the budget, the request is immediately blocked (throwing HTTP 402 Payment Required).
  - **TTL management:** Daily keys are configured with a Time-To-Live (TTL) of 24 hours (`86400` seconds) to let Redis automatically expire old usage records, keeping memory clean.

---

## Part 5: Scaling & Reliability

### Exercise 5.1: Liveness vs Readiness probes

Two distinct probes serve different purposes in production orchestration:

| Probe | Endpoint | Question it answers | On failure |
|---|---|---|---|
| **Liveness** | `GET /health` | "Is the process alive?" | Platform **restarts the container** |
| **Readiness** | `GET /ready` | "Can it accept traffic right now?" | Load balancer **stops routing requests** to it (keeps container alive) |

**Why split them?**

- A process can be **alive but not ready** — e.g. loading a model, warming a connection pool, waiting for a dependency. `/health` returns 200 (process running), `/ready` returns 503 (don't send traffic yet). The platform keeps the container alive and waits.
- A process can be **unresponsive and need restart** — e.g. deadlock, OOM, broken event loop. `/health` returns 500 → platform kills + restarts.
- Conflating them causes either: (a) restart loops during slow startup, or (b) zombie containers that receive traffic they can't handle.

**Implementation in `develop/app.py`:**

- `/health` returns dependency checks (memory, Redis ping, etc.) plus `uptime_seconds`, `version`, `timestamp`. Always 200 unless process is fundamentally broken.
- `/ready` checks `_is_ready` flag (set to `True` only after startup work completes in `lifespan` context manager). Returns 503 during startup/shutdown.
- A middleware tracks `_in_flight_requests` counter so `/ready` can also report load (K8s can use this to drain a node before shutdown).

### Exercise 5.2: Graceful shutdown via SIGTERM + lifespan

Cloud platforms send `SIGTERM` (not `SIGKILL`) when they want a container to stop — this is the polite "please finish what you're doing, then exit" signal. uvicorn catches `SIGTERM` and triggers FastAPI's `lifespan` shutdown phase.

**Two-layer protection:**

1. **uvicorn-level** — `timeout_graceful_shutdown=30` in `uvicorn.run(...)`. This caps how long uvicorn will wait for in-flight requests before forcefully closing them. Prevents a hung request from blocking deploys forever.
2. **App-level** — the `lifespan` async context manager's shutdown branch:

```python
while _in_flight_requests > 0 and elapsed < timeout:
    logger.info(f"Waiting for {_in_flight_requests} in-flight requests...")
    time.sleep(1)
    elapsed += 1
```

The middleware (`track_requests`) increments `_in_flight_requests` on entry and decrements in `finally` — so the counter is accurate even if the handler throws. The lifespan waits up to 30s for the counter to hit 0, then proceeds with cleanup.

**Bonus:** `signal.signal(signal.SIGTERM, handle_sigterm)` registers a custom handler that logs the received signal — useful for debugging in production logs ("Received signal 15 — uvicorn will handle graceful shutdown").

**Why this matters:** Without graceful shutdown, an in-flight LLM request (could take 10–30s for streaming responses) gets truncated mid-stream when the new version rolls out. The client gets a broken response, partial data, or a connection reset. Graceful shutdown = zero-downtime deploys.

### Exercise 5.3: Stateless design with Redis session storage

**The scaling problem:** Load balancer routes `request N+1` to a different instance than `request N`. If session state lives in the instance's local memory, the user "loses" their conversation.

```
Instance 1: User A sends Q1 → stores history in dict → responds
Instance 2: User A sends Q2 → empty dict → "Hello, who are you?"
```

**The fix:** Externalize state to Redis (key-value store accessible from any instance).

```
Instance 1: save `session:{uuid}` to Redis (TTL 3600s)
Instance 2: GET `session:{uuid}` from Redis → continues conversation
```

**Implementation in `production/app.py`:**

```python
def save_session(session_id: str, data: dict, ttl_seconds: int = 3600):
    serialized = json.dumps(data)
    _redis.setex(f"session:{session_id}", ttl_seconds, serialized)
```

- `setex` = SET + EXPIRE in one atomic command. Sessions auto-expire after 1 hour of inactivity — no manual cleanup.
- History capped at 20 messages (10 turns) to prevent unbounded memory growth.
- Fallback: if Redis is unreachable at startup, code falls back to in-memory dict and prints a warning. This is for local dev only — production must have Redis.

**Stateless contract for scaling:**
- No instance holds any user-specific state across requests
- Any instance can serve any request for any user
- Add/remove instances freely — no rebalancing logic needed
- Horizontal scaling = just bump replica count

### Exercise 5.4: Load balancing with Nginx + Docker Compose scale

**Topology (port 8080 on host):**

```
Client → :8080 → Nginx (load balancer)
                   ├── agent-1 (replica 1) ─┐
                   ├── agent-2 (replica 2) ─┼─→ Redis (shared state)
                   └── agent-3 (replica 3) ─┘
```

**Key files:**

- `docker-compose.yml` declares `replicas: 3` for the `agent` service. Docker Compose's internal DNS (`agent` service name) auto-resolves to all 3 container IPs.
- `nginx.conf` uses `upstream agent_cluster { server agent:8000; }` — Nginx queries Docker's DNS resolver (`127.0.0.11`) every 10s to discover new instances, so scaling up/down happens automatically without Nginx reload.
- `resolver 127.0.0.11 valid=10s;` enables Docker's embedded DNS.
- `keepalive 16` reuses TCP connections to backends (avoids handshake overhead per request).
- `proxy_next_upstream error timeout http_503` — if one instance is unhealthy, Nginx retries on the next instance.
- `add_header X-Served-By $upstream_addr always;` — exposes the backend IP in response headers for debugging.

**Bring up + test:**

```powershell
docker compose -f 05-scaling-reliability/production/docker-compose.yml up -d --scale agent=3
curl http://localhost:8080/health
python 05-scaling-reliability/production/test_stateless.py
docker compose -f 05-scaling-reliability/production/docker-compose.yml down
```

**`test_stateless.py` proves statelessness:** sends 5 questions, prints `served_by` from each response (the `INSTANCE_ID` env var, unique per container). If >1 instance ID appears in output, the load balancer is working AND Redis is correctly sharing state — different instances served different requests but the conversation history is intact.

**Observed behavior:** Requests round-robin across instances; `/chat/{session_id}/history` returns the full 10-message history regardless of which instance handled which request — proof that Redis is the source of truth, not local memory.

### Exercise 5.5: Live execution evidence (codex review gap fix)

**Date:** 2026-06-12 | **Env:** Docker Desktop + Docker Compose v2 + Windows 11

**Step 1: Bring up cluster (3 agents + Redis + Nginx)**

```powershell
docker compose -f 05-scaling-reliability/production/docker-compose.yml up -d --scale agent=3
```

Service state after startup:

```
NAME                  IMAGE                  SERVICE   STATUS                  PORTS
production-agent-1    production-agent       agent     Up (health: starting)   8000/tcp
production-agent-2    production-agent       agent     Up (health: starting)   8000/tcp
production-agent-3    production-agent       agent     Up (health: starting)   8000/tcp
production-nginx-1    nginx:alpine           nginx     Up                      0.0.0.0:8080->80/tcp
production-redis-1    redis:7-alpine         redis     Up (healthy)            6379/tcp
```

**Step 2: Health probe + X-Served-By header rotation**

```powershell
curl -i http://localhost:8080/health
```

10 sequential hits, each from a different backend container:

```
X-Served-By: 172.20.0.4:8000
X-Served-By: 172.20.0.5:8000
X-Served-By: 172.20.0.3:8000
X-Served-By: 172.20.0.4:8000
X-Served-By: 172.20.0.5:8000
X-Served-By: 172.20.0.3:8000
X-Served-By: 172.20.0.4:8000
X-Served-By: 172.20.0.5:8000
X-Served-By: 172.20.0.3:8000
X-Served-By: 172.20.0.4:8000
```

→ 3 distinct backends, strict round-robin. Nginx `upstream` + Docker DNS working.

**Step 3: Backend instance IDs (via `/health` hit on each)**

```json
{"instance_id":"instance-1bcf36", "uptime_seconds":2359.7, "storage":"redis", "redis_connected":true}
{"instance_id":"instance-af3689", "uptime_seconds":2359.6, "storage":"redis", "redis_connected":true}
{"instance_id":"instance-7cfc30", "uptime_seconds":2359.2, "storage":"redis", "redis_connected":true}
```

→ 3 unique `INSTANCE_ID` values (UUID-derived), all connected to Redis. Stateful coupling = none.

**Step 4: Stateless test (`test_stateless.py` output, real run)**

```powershell
$env:PYTHONIOENCODING="utf-8"
python 05-scaling-reliability/production/test_stateless.py
```

```
============================================================
Stateless Scaling Demo
============================================================

Session ID: a80ffcf4-c7e5-41ee-894c-558cb6c12894

Request 1: [instance-af3689]   Q: What is Docker?
Request 2: [instance-7cfc30]   Q: Why do we need containers?
Request 3: [instance-1bcf36]  Q: What is Kubernetes?
Request 4: [instance-af3689]   Q: How does load balancing work?
Request 5: [instance-7cfc30]   Q: What is Redis used for?

------------------------------------------------------------
Total requests: 5
Instances used: {'instance-1bcf36', 'instance-af3689', 'instance-7cfc30'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10
  [user]: What is Docker?...
  [user]: Why do we need containers?...
  [user]: What is Kubernetes?...
  [user]: How does load balancing work?...
  [user]: What is Redis used for?...

✅ Session history preserved across all instances via Redis!
```

**Verdict:** 3 instances, 5 requests, 3 distinct backend IDs, 10 messages intact in history. Stateless design **verified live**, not just claimed in prose.

**Step 5: Production-mode Redis guard (anti-pattern fix)**

`production/app.py` now enforces: if `ENVIRONMENT=production` and Redis ping fails, app crashes at startup (fail-fast). Fallback to in-memory store only allowed in `development` / `demo` mode.

```python
if ENVIRONMENT == "production":
    import redis as _redis_mod
    _redis = _redis_mod.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=3)
    _redis.ping()   # raises ConnectionError if Redis down
    USE_REDIS = True
else:
    try:
        # ... original fallback logic
    except Exception:
        USE_REDIS = False
        _memory_store: dict = {}
```

**Why this matters:** Previous code silently degraded to in-memory in production — cost guard, rate limiter, session storage all would have lied about persistence. The guard makes that bug impossible to ship.

**Tear down:**

```powershell
docker compose -f 05-scaling-reliability/production/docker-compose.yml down
```

---

## Part 6: Final Project Assembly & Validation

### Exercise 6.1: Local 06-lab prerequisites

Per PLAN Step 1, the `06-lab-complete/` project needs a `utils/` folder copy for local Docker builds (and a `.env.local` for `env_file` reference in `docker-compose.yml`).

```powershell
xcopy /E /I utils 06-lab-complete\utils     # PowerShell
# or
cp -r utils 06-lab-complete/utils           # Bash/Git Bash
```

| File | Status | Source |
|---|---|---|
| `app/main.py` | Pre-existing | scaffold |
| `app/config.py` | Pre-existing | scaffold |
| `Dockerfile` | Pre-existing | scaffold |
| `docker-compose.yml` | Pre-existing | scaffold |
| `railway.toml` | Pre-existing | scaffold |
| `render.yaml` | Pre-existing | scaffold |
| `requirements.txt` | Pre-existing | scaffold |
| `utils/mock_llm.py` | **Copied from `../utils/`** | PLAN Step 1 |
| `.env.example` | Pre-existing (scaffold) | scaffold |
| `.dockerignore` | Pre-existing (scaffold) | scaffold |
| `.env.local` | **Created for local staging** | this commit |

`.env.local` is gitignored (via root `.gitignore` which has `.env*` patterns + project `.dockerignore`).

### Exercise 6.2: Configuration verification (Pydantic-style dataclass)

`app/config.py` uses `@dataclass` with `field(default_factory=lambda: os.getenv(...))` — same purpose as Pydantic settings, simpler API. Validates in `Settings.validate()`:

```python
if self.environment == "production":
    if self.agent_api_key == "dev-key-change-me":
        raise ValueError("AGENT_API_KEY must be set in production!")
    if self.jwt_secret == "dev-jwt-secret":
        raise ValueError("JWT_SECRET must be set in production!")
```

- In production mode → fail-fast on default secrets (prevents deploying with scaffold keys)
- In staging/development → silently use defaults
- Mock LLM warning if `OPENAI_API_KEY` empty

### Exercise 6.3: Middleware stack in `app/main.py`

| Layer | Implementation | Status |
|---|---|---|
| **API Key auth** | `verify_api_key` dep via `APIKeyHeader("X-API-Key")` | ✅ 401 on missing/wrong key |
| **Rate limiting** | `check_rate_limit(key)` per-API-key sliding window | ⚠️ In-memory (see issue below) |
| **Cost guard** | `check_and_record_cost(input_tokens, output_tokens)` per-day USD accumulator | ⚠️ In-memory (see issue below) |
| **Pydantic validation** | `AskRequest(BaseModel)` with `Field(min_length=1, max_length=2000)` | ✅ |
| **Structured logging** | `logger.info(json.dumps({"event":..., ...}))` JSON lines | ✅ |
| **Liveness probe** | `GET /health` returns status, version, uptime, checks | ✅ |
| **Readiness probe** | `GET /ready` returns 503 until `_is_ready=True` | ✅ |
| **Graceful shutdown** | `signal.signal(SIGTERM, _handle_signal)` + uvicorn `timeout_graceful_shutdown=30` | ✅ |
| **CORS** | `CORSMiddleware` with `settings.allowed_origins` from env | ✅ |
| **Security headers** | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` | ✅ |
| **Docs in prod** | `docs_url=None` when `environment == "production"` | ✅ |

### Exercise 6.4: Pydantic validation test (live)

| Test | Expected | Actual |
|---|---|---|
| `POST /ask` with `{}` body | 422 | **422** ✅ |
| `POST /ask` with 2001-char question | 422 | **422** ✅ |
| `POST /ask` with valid question + correct API key | 200 | **200** ✅ |
| `POST /ask` with valid question + wrong API key | 401 | **401** ✅ |
| `GET /health` | 200 + status JSON | **200** ✅ |
| `GET /ready` | 200 + `{"ready":true}` | **200** ✅ |
| `GET /` | 200 + endpoint catalog | **200** ✅ |
| `GET /nonexistent` | 404 | **404** ✅ |
| `GET /metrics` (auth) | 200 + counters | **200** ✅ (68 reqs, 0 errors observed) |

### Exercise 6.5: Production-readiness checker (100%)

```
=======================================================
  Production Readiness Check — Day 12 Lab
=======================================================

📁 Required Files
  ✅ Dockerfile exists
  ✅ docker-compose.yml exists
  ✅ .dockerignore exists
  ✅ .env.example exists
  ✅ requirements.txt exists
  ✅ railway.toml or render.yaml exists

🔒 Security
  ✅ .env in .gitignore
  ✅ No hardcoded secrets in code

🌐 API Endpoints (code check)
  ✅ /health endpoint defined
  ✅ /ready endpoint defined
  ✅ Authentication implemented
  ✅ Rate limiting implemented
  ✅ Graceful shutdown (SIGTERM)
  ✅ Structured logging (JSON)

🐳 Docker
  ✅ Multi-stage build
  ✅ Non-root user
  ✅ HEALTHCHECK instruction
  ✅ Slim base image
  ✅ .dockerignore covers .env
  ✅ .dockerignore covers __pycache__

=======================================================
  Result: 20/20 checks passed (100%)
  🎉 PRODUCTION READY! Deploy nào!
=======================================================
```

### Exercise 6.6: Live integration test (stack up + 422/200 verified)

**Bring up:**
```powershell
docker compose -f 06-lab-complete/docker-compose.yml up -d --build
```

**Bug fixed during deploy (silent restart loop → root cause):**

1. **`ModuleNotFoundError: No module named 'uvicorn'`** — Dockerfile `runtime` stage used `pip install --user` (puts packages in `/home/agent/.local/lib/python3.11/site-packages`) but didn't export `PYTHONUSERBASE=/home/agent/.local`. Added the env var to Dockerfile `runtime` stage. Same fix as `05-scaling-reliability/production/Dockerfile` line 36.

2. **`AttributeError: 'MutableHeaders' object has no attribute 'pop'`** — starlette `MutableHeaders` (FastAPI/Starlette 0.30+) removed `.pop()`. Changed `response.headers.pop("server", None)` to guarded `del response.headers["server"]`. Same fix as `04-api-gateway` (commit `fbb2c64`).

**Verified endpoints (live, with staging API key `staging-key-abc123`):**

```
GET /health → 200 {"status":"ok","version":"1.0.0","environment":"staging",...}
GET /ready →  200 {"ready":true}
GET / →      200 {"app":"Production AI Agent","endpoints":{...}}
POST /ask {} →          422  Field required
POST /ask 2001-char →   422  String should have at most 2000 characters
POST /ask valid →       200  {"question":"What is deployment?","answer":"..."}
POST /ask wrong key →   401  Invalid or missing API key
GET /metrics →          200  {"uptime_seconds":1548.6,"total_requests":68,...}
```

**Tear down:**
```powershell
docker compose -f 06-lab-complete/docker-compose.yml down
```

### Exercise 6.7: Known issues (anti-patterns flagged for future work)

Codex review on Part 5 surfaced the same anti-patterns in Part 6's `app/main.py`. They are **not regressions** (scaffold pre-dates Part 5 fixes), but should be fixed before declaring "true production ready":

1. **In-memory rate limiter (`_rate_windows: dict[str, deque]`)** — Does not work across multiple uvicorn workers. `CMD ["uvicorn", ..., "--workers", "2"]` runs 2 workers, each with its own dict → effective limit = 2× configured. **Fix:** Use Redis sliding window (`_redis.zadd` + `zremrangebyscore` + `zcard`), same pattern as `05-scaling-reliability/production/app.py:save_session`.

2. **In-memory cost guard (`_daily_cost: float`)** — Same issue. Two workers = two independent budgets. **Fix:** Use Redis `HINCRBYFLOAT` per `(user, day)` with TTL 86400s.

3. **No Redis integration in `main.py`** — `redis==5.1.0` is in `requirements.txt`, `REDIS_URL` is in `config.py`, but main.py never imports redis. The `redis` service in docker-compose is dead weight today. **Fix:** Wire `app/state.py` to manage redis client, used by rate limiter + cost guard.

These are explicitly out of scope for PLAN Task 6 (which targets "checker 100% pass" — already met). They are documented here for the next iteration of the project.

### Exercise 6.8: Architecture summary (final deliverable)

```
                    ┌─────────────────────────────────┐
                    │  Railway / Render / any cloud   │
                    │  NIXPACKS auto-detect or Docker  │
                    └────────────┬────────────────────┘
                                 │
                          ┌──────┴──────┐
                          │  Nginx LB   │ (optional, not in 06)
                          └──────┬──────┘
                                 │
                    ┌────────────┴────────────┐
                    │  agent (uvicorn x2)     │
                    │  + API Key + RateLimit  │
                    │  + Cost Guard + Pydantic│
                    │  + JSON logging         │
                    │  + /health, /ready      │
                    │  + SIGTERM graceful     │
                    └────────────┬────────────┘
                                 │
                          ┌──────┴──────┐
                          │  Redis 7    │  (future: shared state)
                          └─────────────┘
```

**Deploy paths (all configured):**
- **Railway:** `railway up` (uses `railway.toml`, NIXPACKS via DOCKERFILE builder)
- **Render:** Push repo → Blueprint → reads `render.yaml`
- **Local Docker:** `docker compose up` (uses `docker-compose.yml`)
- **Bare metal:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

**Config contract (12-factor):** All settings via env vars, no hardcoded values, Pydantic-style dataclass validation, fail-fast on production-with-default-secrets.

---

## Final Status: 6/6 Tasks Complete

| Task | Status | Commit |
|---|---|---|
| Part 1: Localhost vs Production | ✅ | `8ee9357` |
| Part 2: Docker | ✅ | `5bd979b` |
| Part 3: Cloud Deployment | ✅ | `f987d3a` + `d462dbf` |
| Part 4: API Security | ✅ | `a48e903` |
| Part 5: Scaling & Reliability | ✅ | `72b78e5` + `0141cc3` |
| Part 6: Final Assembly | ✅ | this commit |

**Production readiness checker:** 20/20 (100%) 🎉
**Live integration test:** All 8 endpoint scenarios pass (200/200/422/422/200/401/404/200)
**Documented gaps:** 3 known issues (in-memory state) listed in Exercise 6.7 for next iteration.