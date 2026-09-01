FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# --- Business France ScrapeGraphAI fallback (optional, isolated) ---
# Installed in its own venv so its heavy/fast-moving dependency tree
# (langchain, playwright, ...) never touches the main app's dependencies —
# `pip install --dry-run -r requirements.txt scrapegraphai` was verified to
# force major upgrades of fastapi/pydantic/httpx/openai/pypdf otherwise.
# Best-effort: a failure here must never break the main API image/deploy.
COPY requirements-scrape-fallback.txt .
RUN python -m venv /opt/scrape-fallback-venv \
    && /opt/scrape-fallback-venv/bin/pip install --no-cache-dir -r requirements-scrape-fallback.txt \
    && /opt/scrape-fallback-venv/bin/playwright install --with-deps chromium \
    || echo "[scrape-fallback] setup failed — fallback stays 'unavailable' at runtime, primary API unaffected"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
