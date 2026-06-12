import json
import subprocess
import sys

BASE = "http://localhost:8000"
KEY = "staging-key-abc123"

def call(method, path, body=None, headers=None):
    cmd = ["curl.exe", "-s", "-o", "/dev/null", "-w", "%{http_code}",
           "-X", method, BASE + path]
    if headers:
        for k, v in headers.items():
            cmd += ["-H", f"{k}: {v}"]
    if body is not None:
        cmd += ["-d", json.dumps(body)]
    rc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return rc.stdout

def call_full(method, path, body=None, headers=None):
    cmd = ["curl.exe", "-s", "-X", method, BASE + path]
    if headers:
        for k, v in headers.items():
            cmd += ["-H", f"{k}: {v}"]
    if body is not None:
        cmd += ["-d", json.dumps(body)]
    rc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return rc.stdout

results = []

# /health
r = call("GET", "/health")
results.append(("GET /health", r, "200"))

# /ready
r = call("GET", "/ready")
results.append(("GET /ready", r, "200"))

# / (root)
r = call("GET", "/")
results.append(("GET /", r, "200"))

# /auth/token — issue JWT
tok_body = call_full("POST", "/auth/token", {"username": "student", "password": "demo123"}, {"Content-Type": "application/json"})
tok_data = json.loads(tok_body) if tok_body else {}
TOKEN = tok_data.get("access_token", "")
results.append(("POST /auth/token", "200" if TOKEN else "FAIL", "200"))

# POST /ask no auth → 401
r = call("POST", "/ask", {"question": "hi"})
results.append(("POST /ask (no auth)", r, "401"))

# POST /ask empty body → 422
r = call("POST", "/ask", {}, {"X-API-Key": KEY, "Content-Type": "application/json"})
results.append(("POST /ask empty {}", r, "422"))

# POST /ask 2001 chars → 422
r = call("POST", "/ask", {"question": "a" * 2001}, {"X-API-Key": KEY, "Content-Type": "application/json"})
results.append(("POST /ask 2001 chars", r, "422"))

# POST /ask valid → 200
r = call("POST", "/ask", {"question": "Explain Docker in one sentence"}, {"X-API-Key": KEY, "Content-Type": "application/json"})
results.append(("POST /ask valid", r, "200"))

# POST /chat valid → 200 (stateless session)
chat_body = call_full("POST", "/chat", {"question": "Hi I'm Phi Manh"}, {"X-API-Key": KEY, "Content-Type": "application/json"})
chat_data = json.loads(chat_body) if chat_body else {}
SID = chat_data.get("session_id", "")
results.append(("POST /chat valid", "200" if SID else "FAIL", "200"))

# GET /chat/{sid}/history → 200
r = call("GET", f"/chat/{SID}/history", headers={"X-API-Key": KEY})
results.append((f"GET /chat/{SID[:8]}/history", r, "200"))

# POST /chat follow-up → 200
r = call("POST", "/chat", {"question": "And K8s?", "session_id": SID}, {"X-API-Key": KEY, "Content-Type": "application/json"})
results.append(("POST /chat follow-up", r, "200"))

# GET /usage/{user} → 200
r = call("GET", "/usage/key:staging-", headers={"X-API-Key": KEY})
results.append(("GET /usage", r, "200"))

# GET /metrics → 200
r = call("GET", "/metrics", headers={"X-API-Key": KEY})
results.append(("GET /metrics", r, "200"))

# GET /nonexistent → 404
r = call("GET", "/nonexistent")
results.append(("GET /nonexistent", r, "404"))

# DELETE /chat/{sid} → 200
r = call("DELETE", f"/chat/{SID}", headers={"X-API-Key": KEY})
results.append(("DELETE /chat/{sid}", r, "200"))

# Print results
print()
print(f"{'Test':<35} {'Got':<8} {'Expected':<8} {'OK'}")
print("-" * 70)
ok_count = 0
for name, got, expected in results:
    ok = got == expected
    if ok:
        ok_count += 1
    print(f"{name:<35} {got:<8} {expected:<8} {'✅' if ok else '❌'}")
print()
print(f"Result: {ok_count}/{len(results)} passed")
