FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps needed to build asyncpg/telethon deps on slim image
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Runs as non-root (CIS Docker Benchmark 4.1) — this image previously had
# no USER instruction at all, so backend/worker/bot ran as root inside
# their containers with no reason to (they're a stateless API process,
# a poller, and a Telegram bot — none need root). /app/sessions is where
# the worker's Telegram session file lives (see docker-compose.yml's
# telegram_sessions volume) — owned by this user so it stays writable.
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/sessions \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Default command runs the API; docker-compose overrides this for
# the worker and bot services so all three share this one image.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
