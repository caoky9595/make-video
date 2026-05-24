---
name: Coding DevOps
description: Xử lý containerization (Docker), CI/CD pipelines, deployment scripts, và observability (logging, metrics, monitoring). Kích hoạt khi user cần deploy, setup Docker, cấu hình GitHub Actions, hoặc thêm monitoring vào app.
sources:
  - PatrickJS/awesome-cursorrules (36,900+ stars) — Docker rules
  - jwadow/agentic-prompts — Observer/Observability role
---

# DevOps Agent

## QUICK REFERENCE — Read This First

```
DOCKER CHECKLIST:
□ Base image: pinned version (python:3.12.3-slim), NEVER :latest
□ Multi-stage build (builder → runtime)
□ Layer order: COPY requirements → RUN install → COPY code
□ Non-root user: RUN useradd -r appuser && USER appuser
□ HEALTHCHECK directive present
□ .dockerignore exists (excludes .env, .git, node_modules, __pycache__)
□ No secrets in Dockerfile or image

CI/CD CHECKLIST:
□ Pipeline: Lint → Test → Security Scan → Build Image → Deploy
□ Tests run on every PR
□ Security scan with trivy or bandit

OBSERVABILITY CHECKLIST:
□ Structured JSON logging (not print())
□ /health endpoint exists
□ /ready endpoint checks dependencies
□ Secrets from env vars, validated at startup

SECURITY CHECKLIST:
□ No hardcoded secrets (grep -rn "api_key\s*=" . --include="*.py")
□ .env.example exists (template without real values)
□ Dependencies scanned (safety check / npm audit)

After completing any DevOps task, verify:
□ docker build succeeds
□ docker run + healthcheck passes
□ CI pipeline runs green
```

---

<details>
<summary><strong>📖 Detailed Examples & Templates (expand)</strong></summary>

### Dockerfile Best Practices

```dockerfile
# ✅ Good — pinned, multi-stage, non-root
FROM python:3.12.3-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user -r requirements.txt

FROM python:3.12.3-slim AS runtime
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
RUN groupadd -r appuser && useradd -r -g appuser appuser
USER appuser
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl --fail http://localhost:8080/health || exit 1
CMD ["python", "main.py"]
```

**Forbidden patterns**:
```dockerfile
# ❌ NEVER
FROM python:latest        # unpredictable
USER root                 # security risk
ADD . /app                # use COPY instead
COPY .env /app/.env       # secrets in image!
```

### .dockerignore
```
.git
.env
.env.*
*.log
__pycache__
*.pyc
node_modules
.pytest_cache
venv/
tests/
```

### docker-compose (production)
```yaml
services:
  app:
    image: myapp:${APP_VERSION:-latest}
    environment:
      - PEXELS_API_KEY=${PEXELS_API_KEY}
    volumes:
      - app_output:/app/output
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### GitHub Actions CI/CD
```yaml
name: CI/CD Pipeline
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'
      - run: pip install -r requirements.txt
      - run: ruff check . && ruff format --check .
      - run: pytest --cov=. -v
      - run: bandit -r . -ll --exclude venv
```

### Structured Logging
```python
import logging, json

class StructuredLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def info(self, event: str, **kwargs):
        self.logger.info(json.dumps({"event": event, "level": "INFO", **kwargs}))

logger = StructuredLogger(__name__)
logger.info("video_created", title="Story Part 1", duration=45.2)
```

### Health Check Endpoint
```python
@app.get("/health")
def health_check():
    return {"status": "healthy", "version": os.getenv("APP_VERSION", "unknown")}

@app.get("/ready")
def readiness_check():
    checks = {
        "api_key_configured": bool(os.getenv("PEXELS_API_KEY")),
        "output_dir_writable": os.access("output/", os.W_OK),
    }
    return {"ready": all(checks.values()), "checks": checks}
```

### Secrets Validation at Startup
```python
def get_required_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Required env var '{key}' is not set")
    return value

PEXELS_API_KEY = get_required_env("PEXELS_API_KEY")
```

</details>
