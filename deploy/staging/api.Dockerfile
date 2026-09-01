FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/apps/api/src

WORKDIR /app

COPY apps/api/requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir -r /tmp/requirements.txt

# --- Business France ScrapeGraphAI fallback (optional, isolated) ---
# Installed in its own venv so its heavy/fast-moving dependency tree
# (langchain, playwright, ...) never touches the main app's dependencies —
# `pip install --dry-run -r apps/api/requirements.txt scrapegraphai` was
# verified to force major upgrades of fastapi/pydantic/httpx/openai/pypdf
# otherwise. Best-effort: a failure here must never break the main API
# image/deploy (see docs/ai/DECISIONS.md R32).
COPY apps/api/requirements-scrape-fallback.txt /tmp/requirements-scrape-fallback.txt
RUN python -m venv /opt/scrape-fallback-venv \
    && /opt/scrape-fallback-venv/bin/pip install --no-cache-dir -r /tmp/requirements-scrape-fallback.txt \
    && /opt/scrape-fallback-venv/bin/playwright install --with-deps chromium \
    || echo "[scrape-fallback] setup failed — fallback stays 'unavailable' at runtime, primary API unaffected"

COPY apps/api /app/apps/api

WORKDIR /app/apps/api

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--root-path", "/api"]
