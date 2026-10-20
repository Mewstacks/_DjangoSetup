# syntax=docker/dockerfile:1.7
FROM python:3.12-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN python -m pip install --no-cache-dir uv==0.12.0

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH=/app/.venv/bin:$PATH \
    PORT=8000

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv

COPY --chown=app:app manage.py ./
COPY --chown=app:app src ./src

RUN DJANGO_SETTINGS_MODULE=config.settings.test python manage.py collectstatic --noinput

USER 10001:10001
EXPOSE 8000

# Bind to $PORT so the image runs on any host that injects a port (Heroku, Render, Railway,
# Cloud Run, …); defaults to 8000 elsewhere. `exec` keeps gunicorn as PID 1 so SIGTERM is
# delivered for graceful shutdown.
CMD ["sh", "-c", "exec gunicorn config.asgi:application --bind 0.0.0.0:${PORT:-8000} --worker-class uvicorn_worker.UvicornWorker --workers 2 --timeout 30 --graceful-timeout 30 --max-requests 1000 --max-requests-jitter 100 --access-logfile - --error-logfile -"]
