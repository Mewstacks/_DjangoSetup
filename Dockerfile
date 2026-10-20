# syntax=docker/dockerfile:1.7
# Base images are pinned by tag and bumped by Dependabot; pin by digest in your own registry
# mirror if you need byte-for-byte rebuilds.
FROM python:3.12-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN python -m pip install --no-cache-dir uv==0.13.3

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH=/app/.venv/bin:$PATH \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    PORT=8000

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv

COPY --chown=app:app manage.py ./
COPY --chown=app:app src ./src
COPY --chown=app:app deploy/docker/healthcheck.py ./deploy/docker/healthcheck.py
COPY deploy/docker/entrypoint.sh /usr/local/bin/entrypoint
RUN chmod 0755 /usr/local/bin/entrypoint

# Collecting static files needs settings but no secrets or services.
RUN DJANGO_SETTINGS_MODULE=config.settings.test python manage.py collectstatic --noinput

USER 10001:10001
EXPOSE 8000

# Probes the web role only (CONTAINER_ROLE defaults to web); worker/scheduler containers pass.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "/app/deploy/docker/healthcheck.py"]

# `exec` in the entrypoint keeps the role's process as PID 1 so SIGTERM drains it gracefully.
ENTRYPOINT ["/usr/local/bin/entrypoint"]
CMD ["web"]
