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
