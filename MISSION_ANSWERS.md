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


