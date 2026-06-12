# Day 12 Cloud Infrastructure & Deployment Lab Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete all exercises (Parts 1-5) and prepare/verify the final production-ready AI Agent project (Part 6) for the Day 12 Lab, ensuring a 100% passing rate on the production readiness check.

**Architecture:** A multi-instance Docker containerized FastAPI agent utilizing Redis for stateless session storage, fronted by an Nginx Load Balancer, secured by API Key auth, rate limiting, and a daily budget Cost Guard.

**Tech Stack:** FastAPI, Docker & Docker Compose, Redis, Nginx, Pydantic, Python 3.11+

---

## 🛠 Prerequisites & Local Environment Setup

Before starting the tasks, ensure the following are installed and running on your local machine:
- [ ] **Python 3.11+** installed (`python --version`)
- [ ] **Docker Desktop** installed and running (`docker ps`)
- [ ] **Node.js** (required for Railway CLI commands if deploying, `node --version`)
- [ ] **Git** installed and configured (`git --version`)

---

### Task 1: Localhost vs Production (Part 1)

**Files:**
- Create: `MISSION_ANSWERS.md`
- Inspect: [develop/app.py](file:///D:/Work/project/VINAI/day12_ha-tang-cloud_va_deployment/01-localhost-vs-production/develop/app.py)
- Inspect: [production/app.py](file:///D:/Work/project/VINAI/day12_ha-tang-cloud_va_deployment/01-localhost-vs-production/production/app.py)
- Inspect: [production/config.py](file:///D:/Work/project/VINAI/day12_ha-tang-cloud_va_deployment/01-localhost-vs-production/production/config.py)

**Step 1: Identify Anti-patterns in Basic Code**
- Open [01-localhost-vs-production/develop/app.py](file:///D:/Work/project/VINAI/day12_ha-tang-cloud_va_deployment/01-localhost-vs-production/develop/app.py) and list 5+ anti-patterns:
  1. Hardcoded API secrets.
  2. Fixed host port (`8000`) instead of pulling from `PORT` env var.
  3. Running with `debug=True` in production.
  4. No `/health` or `/ready` endpoints.
  5. No graceful shutdown signal handling.
  6. Standard `print()` statements instead of structured JSON logging.

**Step 2: Run and test the basic version**
- Navigate to the project root directory.
- Verify `uvicorn` and `fastapi` are defined in `01-localhost-vs-production/develop/requirements.txt`.
- Install dependencies:
  ```powershell
  pip install -r 01-localhost-vs-production/develop/requirements.txt
  ```
- Run the basic app:
  ```powershell
  python 01-localhost-vs-production/develop/app.py
  ```
- In another terminal, run a test query:
  ```powershell
  curl http://localhost:8000/ask -X POST -H "Content-Type: application/json" -d "{\"question\": \"Hello\"}"
  ```
- Verify response and stop the process (Ctrl+C).

**Step 3: Run and test the production version**
- Copy configuration template inside `01-localhost-vs-production/production/`:
  ```powershell
  cp 01-localhost-vs-production/production/.env.example 01-localhost-vs-production/production/.env
  ```
- Install production dependencies:
  ```powershell
  pip install -r 01-localhost-vs-production/production/requirements.txt
  ```
- Run the production app:
  ```powershell
  python 01-localhost-vs-production/production/app.py
  ```
- Verify uvicorn starts and logs JSON format output.

**Step 4: Document Answers**
- Create [MISSION_ANSWERS.md](file:///D:/Work/project/VINAI/day12_ha-tang-cloud_va_deployment/MISSION_ANSWERS.md) in the project root and fill out the comparison table mapping Config, Health check, Logging, and Shutdown differences between Develop and Production.

---

### Task 2: Docker Containerization (Part 2)

**Files:**
- Modify: `MISSION_ANSWERS.md`
- Inspect: [02-docker/develop/Dockerfile](file:///D:/Work/project/VINAI/day12_ha-tang-cloud_va_deployment/02-docker/develop/Dockerfile)
- Inspect: [02-docker/production/Dockerfile](file:///D:/Work/project/VINAI/day12_ha-tang-cloud_va_deployment/02-docker/production/Dockerfile)
- Inspect: [02-docker/production/docker-compose.yml](file:///D:/Work/project/VINAI/day12_ha-tang-cloud_va_deployment/02-docker/production/docker-compose.yml)

**Step 1: Verify Single-Stage Dockerfile Concepts**
- Read [02-docker/develop/Dockerfile](file:///D:/Work/project/VINAI/day12_ha-tang-cloud_va_deployment/02-docker/develop/Dockerfile).
- Answer the 4 questions in `MISSION_ANSWERS.md` (Base image, working directory, caching layer, CMD vs ENTRYPOINT).

**Step 2: Build and Measure basic container**
- Build from the project root context so files copied in the Dockerfile (`utils/mock_llm.py`) are within the build context:
  ```powershell
  docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
  ```
- Run container:
  ```powershell
  docker run -d -p 8000:8000 --name agent-dev my-agent:develop
  ```
- Check image size using:
  ```powershell
  docker images my-agent:develop
  ```
- Record size in `MISSION_ANSWERS.md`. Stop/remove container:
  ```powershell
  docker stop agent-dev
  docker rm agent-dev
  ```

**Step 3: Build and Measure Multi-Stage Optimized Container**
- Build production multi-stage container (from project root context):
  ```powershell
  docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
  ```
- Record the size of `my-agent:advanced` and calculate size reduction percentage vs develop.

**Step 4: Deploy Docker Compose Stack**
- Navigate to `02-docker/production/` and run the compose stack:
  ```powershell
  docker compose up -d
  ```
- Verify services running: `docker compose ps`
- Run health checks:
  ```powershell
  curl http://localhost/health
  ```
- Query agent:
  ```powershell
  curl http://localhost/ask -X POST -H "Content-Type: application/json" -d "{\"question\": \"Explain microservices\"}"
  ```
- Stop the stack:
  ```powershell
  docker compose down
  ```

---

### Task 3: Cloud Deployment (Part 3)

**Files:**
- Modify: `MISSION_ANSWERS.md`
- Inspect: [03-cloud-deployment/railway/railway.toml](file:///D:/Work/project/VINAI/day12_ha-tang-cloud_va_deployment/03-cloud-deployment/railway/railway.toml)
- Inspect: [03-cloud-deployment/render/render.yaml](file:///D:/Work/project/VINAI/day12_ha-tang-cloud_va_deployment/03-cloud-deployment/render/render.yaml)

**Step 1: Compare Deployment Configs**
- Read `railway.toml` and `render.yaml`. Document major differences (port bindings, health paths, instance configurations) in `MISSION_ANSWERS.md`.

**Step 2: Document CLI Deployments**
- Document dry-run practices: before running `railway up` (which deploys immediately), run `railway status` to verify current active project. Add standard Railway CLI deployment steps to answers.

---

### Task 4: API Security (Part 4)

**Files:**
- Modify: `MISSION_ANSWERS.md`
- Inspect: [04-api-gateway/develop/app.py](file:///D:/Work/project/VINAI/day12_ha-tang-cloud_va_deployment/04-api-gateway/develop/app.py)
- Inspect: [04-api-gateway/production/auth.py](file:///D:/Work/project/VINAI/day12_ha-tang-cloud_va_deployment/04-api-gateway/production/auth.py)
- Inspect: [04-api-gateway/production/rate_limiter.py](file:///D:/Work/project/VINAI/day12_ha-tang-cloud_va_deployment/04-api-gateway/production/rate_limiter.py)
- Inspect: [04-api-gateway/production/cost_guard.py](file:///D:/Work/project/VINAI/day12_ha-tang-cloud_va_deployment/04-api-gateway/production/cost_guard.py)

**Step 1: Test API Key Authentication**
- Run `python 04-api-gateway/develop/app.py`.
- Test without API Key (Expected: `401 Unauthorized`/`403 Forbidden`):
  ```powershell
  curl http://localhost:8000/ask -X POST -H "Content-Type: application/json" -d "{\"question\": \"Hello\"}"
  ```
- Test with valid key:
  ```powershell
  curl http://localhost:8000/ask -X POST -H "X-API-Key: secret-key-123" -H "Content-Type: application/json" -d "{\"question\": \"Hello\"}"
  ```
- Stop app.

**Step 2: Test JWT Authentication Flow**
- Run `python 04-api-gateway/production/app.py`.
- Request JWT token using corrected endpoint path `/auth/token`:
  ```powershell
  curl -X POST http://localhost:8000/auth/token -H "Content-Type: application/json" -d "{\"username\": \"student\", \"password\": \"demo123\"}"
  ```
- Copy the returned token and query the agent:
  ```powershell
  curl http://localhost:8000/ask -X POST -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" -d "{\"question\": \"Explain JWT\"}"
  ```

**Step 3: Validate Rate Limiting**
- Call the `/ask` endpoint 12 times inside a 60-second window. Verify that the 11th request triggers a `429 Too Many Requests` response.

**Step 4: Analyze Cost Guard Architecture**
- Open [04-api-gateway/production/cost_guard.py](file:///D:/Work/project/VINAI/day12_ha-tang-cloud_va_deployment/04-api-gateway/production/cost_guard.py).
- Study how the `CostGuard` class manages per-user daily limits, global limits, warning thresholds (80%), and transaction safety. Do not downgrade it to a simple script; understand its structure to adapt for the stateless Redis final project.

---

### Task 5: Scaling & Reliability (Part 5)

**Files:**
- Modify: `MISSION_ANSWERS.md`
- Inspect: [05-scaling-reliability/develop/app.py](file:///D:/Work/project/VINAI/day12_ha-tang-cloud_va_deployment/05-scaling-reliability/develop/app.py)
- Inspect: [05-scaling-reliability/production/app.py](file:///D:/Work/project/VINAI/day12_ha-tang-cloud_va_deployment/05-scaling-reliability/production/app.py)
- Inspect: [05-scaling-reliability/production/docker-compose.yml](file:///D:/Work/project/VINAI/day12_ha-tang-cloud_va_deployment/05-scaling-reliability/production/docker-compose.yml)
- Test: [05-scaling-reliability/production/test_stateless.py](file:///D:/Work/project/VINAI/day12_ha-tang-cloud_va_deployment/05-scaling-reliability/production/test_stateless.py)

**Step 1: Analyze Existing Probes & Graceful Shutdown**
- Inspect [05-scaling-reliability/develop/app.py](file:///D:/Work/project/VINAI/day12_ha-tang-cloud_va_deployment/05-scaling-reliability/develop/app.py).
- Note that `/health` (liveness) and `/ready` (readiness) endpoints are already fully implemented.
- Note how uvicorn handles `SIGTERM` gracefully using `timeout_graceful_shutdown=30` and tracks `_in_flight_requests` in lifespan context manager. Verify how it waits for request count to drop to 0.

**Step 2: Analyze Stateless Design**
- Open [05-scaling-reliability/production/app.py](file:///D:/Work/project/VINAI/day12_ha-tang-cloud_va_deployment/05-scaling-reliability/production/app.py) and study how it saves/loads user session states directly in Redis, bypassing local node memory.

**Step 3: Load Balance & Scale up with Docker Compose v2**
- Start the Redis-backed cluster:
  ```powershell
  docker compose -f 05-scaling-reliability/production/docker-compose.yml up -d --scale agent=3
  ```
- Check logs: `docker compose -f 05-scaling-reliability/production/docker-compose.yml logs agent`
- Note that Nginx maps port **8080** on the host. Run health checks:
  ```powershell
  curl http://localhost:8080/health
  ```

**Step 4: Execute Stateless Test Suite**
- Run test:
  ```powershell
  python 05-scaling-reliability/production/test_stateless.py
  ```
- Verify that request logs show different backend server instances serving responses while maintaining unified conversation history from Redis.
- Tear down:
  ```powershell
  docker compose -f 05-scaling-reliability/production/docker-compose.yml down
  ```

---

### Task 6: Final Project Assembly & Validation (Part 6)

**Files:**
- Modify: [06-lab-complete/app/config.py](file:///D:/Work/project/VINAI/day12_ha-tang-cloud_va_deployment/06-lab-complete/app/config.py)
- Modify: [06-lab-complete/app/main.py](file:///D:/Work/project/VINAI/day12_ha-tang-cloud_va_deployment/06-lab-complete/app/main.py)
- Test: [06-lab-complete/check_production_ready.py](file:///D:/Work/project/VINAI/day12_ha-tang-cloud_va_deployment/06-lab-complete/check_production_ready.py)

**Step 1: Prerequisite for Local 06-lab Testing**
- Copy `utils/` folder into `06-lab-complete/` so the Docker build context can resolve it locally:
  ```powershell
  xcopy /E /I utils 06-lab-complete\utils
  ```

**Step 2: Configuration & Environment Verification**
- Verify `06-lab-complete/app/config.py` uses Pydantic/dataclasses to pull configuration. Ensure settings validates correctly (e.g. throws `ValueError` in production if API keys are default).

**Step 3: Verify Middleware and Security Injections**
- In `06-lab-complete/app/main.py`, verify JWT/API Key auth, sliding-window rate limiters, and cost guards are active.
- Run `docker compose -f 06-lab-complete/docker-compose.yml up -d` to spin up the final application container.

**Step 4: Test Pydantic Validation Constraints**
- Test invalid empty payload:
  ```powershell
  curl http://localhost:8000/ask -X POST -H "X-API-Key: dev-key-change-me" -H "Content-Type: application/json" -d "{}"
  # Expected: 422 Unprocessable Entity
  ```
- Test question length exceeding 2000 character limit:
  ```powershell
  curl http://localhost:8000/ask -X POST -H "X-API-Key: dev-key-change-me" -H "Content-Type: application/json" -d "{\"question\": \"$(python -c 'print(\"a\"*2001)')\"}"
  # Expected: 422 Unprocessable Entity
  ```

**Step 5: Run Production Readiness Checker**
- Run checker:
  ```powershell
  python 06-lab-complete/check_production_ready.py
  ```
- Confirm all checks pass (100% SUCCESS).
- **Troubleshooting failed checks:**
  - *No hardcoded secrets:* Verify `.env` keys aren't committed or defined inline.
  - *Health/Readiness fail:* Verify `main.py` has active `/health` and `/ready` routes.
  - *Graceful shutdown fail:* Verify uvicorn has `timeout_graceful_shutdown` set and uvicorn is importing app correctly.
- Tear down:
  ```powershell
  docker compose -f 06-lab-complete/docker-compose.yml down
  ```
