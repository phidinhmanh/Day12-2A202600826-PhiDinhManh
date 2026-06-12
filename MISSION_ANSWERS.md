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

