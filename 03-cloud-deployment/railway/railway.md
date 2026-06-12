# Railway Deployment Guide

> Hướng dẫn deploy FastAPI AI Agent lên [Railway](https://railway.app) — từ zero đến production URL trong ~10 phút.

---

## 1. Tại sao chọn Railway?

| Ưu điểm | Mô tả |
|---|---|
| **Zero Dockerfile** | NIXPACKS tự detect Python + install dependencies |
| **Auto HTTPS** | Free SSL cert cho mọi subdomain `.up.railway.app` |
| **Auto `$PORT` injection** | Không cần config port mapping thủ công |
| **Git-based deploy** | Push code → tự build → tự deploy |
| **Free tier** | $5 credit/tháng cho mỗi account mới |

---

## 2. Chuẩn bị

### 2.1. Cài Railway CLI (yêu cầu Node.js)

```powershell
npm install -g @railway/cli
```

Verify:

```powershell
railway --version
```

### 2.2. Login

```powershell
railway login
```

→ Trình duyệt mở → authorize CLI → quay lại terminal.

### 2.3. Cấu trúc thư mục tối thiểu

```
project/
├── app.py              # FastAPI app, đọc PORT từ env
├── requirements.txt    # Pinned dependencies
├── railway.toml        # Config (optional nhưng recommended)
└── utils/
    └── mock_llm.py
```

> **Lưu ý:** Không cần `Dockerfile` — NIXPACKS tự build. Tuy nhiên, nên commit `railway.toml` để pin health check + restart policy.

---

## 3. Cấu hình `app.py` cho Railway

Railway inject biến `$PORT` ngẫu nhiên khi chạy. **PHẢI** đọc từ env, không hardcode:

```python
import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))   # ✅ Default local = 8000
    uvicorn.run(app, host="0.0.0.0", port=port)
```

> **Lỗi phổ biến:** Hardcode `port=8000` → Railway gán port khác → app crash vì bind sai.

### Health check endpoint (bắt buộc)

```python
@app.get("/health")
def health():
    return {"status": "ok"}
```

Nếu `/health` trả về non-200 trong 30s, Railway restart container.

---

## 4. File `railway.toml`

```toml
[build]
builder = "NIXPACKS"

[deploy]
startCommand = "uvicorn app:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 30
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

| Field | Ý nghĩa |
|---|---|
| `builder` | `NIXPACKS` (auto) hoặc `DOCKERFILE` (custom) |
| `startCommand` | Command chạy khi container start |
| `healthcheckPath` | Endpoint Railway gọi định kỳ để verify alive |
| `healthcheckTimeout` | Timeout (giây) cho mỗi health check call |
| `restartPolicyType` | `ON_FAILURE` = chỉ restart khi crash, `ALWAYS` = restart cả khi manual stop |
| `restartPolicyMaxRetries` | Số lần retry tối đa trước khi mark deployment failed |

---

## 5. Quy trình deploy (CLI)

### 5.1. Khởi tạo project

```powershell
cd 03-cloud-deployment/railway
railway init
```

→ Chọn **"Empty Project"** (tạo mới) hoặc **link tới project có sẵn**.
→ Đặt tên project (vd: `ai-agent-day12`).
→ Chọn environment: `production`.

### 5.2. **DRY-RUN CHECK** (BẮT BUỘC)

```powershell
railway status
```

Output mẫu:

```
Project: ai-agent-day12
Environment: production
Service: (none linked)
```

> **⚠️ Nếu project name không đúng → dừng lại.** `railway up` deploy ngay lập tức, không có staging mặc định.

### 5.3. Set environment variables (secrets)

```powershell
# Set từng biến
railway variables set OPENAI_API_KEY=sk-your-key-here
railway variables set ENVIRONMENT=production
railway variables set AGENT_API_KEY=secret-key-123

# Hoặc set hàng loạt từ file .env (KHÔNG commit .env)
railway variables set --from-env-file .env
```

Verify:

```powershell
railway variables
```

### 5.4. Deploy

```powershell
railway up
```

→ CLI stream build logs + deploy logs.
→ Khi xong, in ra URL: `https://ai-agent-day12.up.railway.app`.

### 5.5. Test deployment

```powershell
# Health check
curl https://ai-agent-day12.up.railway.app/health

# Query agent
curl -X POST https://ai-agent-day12.up.railway.app/ask `
  -H "Content-Type: application/json" `
  -d '{"question":"Hello Railway"}'
```

---

## 6. Quản lý sau deploy

| Task | Command |
|---|---|
| Mở dashboard | `railway open` |
| Xem logs realtime | `railway logs` |
| Xem logs 100 dòng cuối | `railway logs --tail 100` |
| Rollback về deploy trước | `railway rollback` |
| Tạo service mới (vd: Redis) | `railway add` → chọn Redis template |
| Link service vào project | `railway link` |
| Unlink | `railway unlink` |
| Xem biến môi trường | `railway variables` |
| Xóa biến | `railway variables delete KEY_NAME` |
| SSH vào container | `railway shell` |
| Chạy lệnh trong container | `railway run <cmd>` |

---

## 7. Thêm Redis (stateless session)

Nếu agent cần Redis để share state giữa các container:

```powershell
railway add
```

→ Chọn **"Redis"** → Railway provision Redis instance + tự inject `REDIS_URL` vào environment.

Trong app:

```python
import os
import redis

r = redis.Redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)
```

> **Không cần code thay đổi gì thêm** — Railway tự inject connection string.

---

## 8. Custom domain

Trong Railway Dashboard:

1. Vào service → **Settings** → **Domains**
2. Click **"+ Custom Domain"**
3. Nhập domain: `agent.yourdomain.com`
4. Railway cấp CNAME record → thêm vào DNS provider
5. SSL tự động provision trong ~2 phút

CLI không support custom domain — phải dùng Dashboard.

---

## 9. Monitoring & scaling

### Metrics
Dashboard → Service → **Metrics** tab:
- CPU usage
- Memory usage
- Network I/O
- Request count

### Vertical scaling
Dashboard → Service → **Settings** → **Resources**:
- Tăng RAM (256 MB → 8 GB)
- Tăng CPU share

### Horizontal scaling
Railway free tier: **1 instance per service**. Plan trả phí: enable **replicas** trong Settings.

> **Lưu ý:** Để horizontal scale hiệu quả, app **PHẢI** stateless (lưu state ở Redis, không lưu trong memory).

---

## 10. Troubleshooting

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| `Application failed to respond on $PORT` | Hardcode `port=8000` | Đổi thành `os.getenv("PORT")` |
| `Health check failed` | Không có `/health` route hoặc trả 500 | Thêm endpoint, test local trước |
| `Module not found` | Missing dependency trong `requirements.txt` | `pip freeze > requirements.txt` |
| `Build timeout` | Quá nhiều deps hoặc download lớn | Dùng `requirements.txt` pin version, cache layer |
| `OpenAI API key not found` | Chưa set env var | `railway variables set OPENAI_API_KEY=...` |
| `502 Bad Gateway` | App crash ngay khi start | `railway logs` xem traceback |
| `Deploy mãi không xong` | Build process treo | Cancel + check `requirements.txt` có circular dep không |

---

## 11. So sánh Railway vs Render

| Tiêu chí | Railway | Render |
|---|---|---|
| Config style | 1 file, CLI-first | Blueprint (multi-service YAML) |
| Free tier | $5 credit/tháng | Free web service (sleeps sau 15 min idle) |
| Custom domain | ✅ | ✅ |
| Auto SSL | ✅ | ✅ |
| Cold start | ~2s | ~30s (free tier) |
| Build time | NIXPACKS nhanh | pip install chậm hơn |
| Best for | Hackathon, MVP, prototype | Production multi-service infra |

**Khuyến nghị:** Chọn Railway khi cần deploy nhanh + ít config. Chọn Render khi muốn IaC-first + multi-service rõ ràng.

---

## 12. Best practices checklist

- [ ] App đọc port từ `os.getenv("PORT")`, không hardcode
- [ ] `/health` endpoint trả 200 + JSON status
- [ ] Tất cả secrets qua `railway variables set`, không commit
- [ ] `requirements.txt` pin version chính xác
- [ ] Không lưu state local — dùng Redis hoặc external DB
- [ ] Set `ENVIRONMENT=production` để app tự disable debug mode
- [ ] `railway status` trước mỗi `railway up`
- [ ] Test local với `python app.py` trước khi deploy
- [ ] `railway logs --tail 100` sau deploy để verify không có error
- [ ] Setup custom domain + SSL cho production URL

---

## 13. Tài liệu tham khảo

- [Railway Docs](https://docs.railway.com)
- [Config-as-Code reference](https://docs.railway.com/reference/config-as-code)
- [Railway CLI reference](https://docs.railway.com/reference/cli-api)
- [NIXPACKS auto-detect](https://docs.railway.com/reference/nixpacks)
- [Health check best practices](https://docs.railway.com/deploy/healthchecks)
