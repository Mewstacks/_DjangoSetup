#!/bin/sh
# One image, several roles. The first argument picks what this container is:
#   web        gunicorn + uvicorn workers (default)
#   worker     Temporal worker (flows, activities, tasks)
#   scheduler  cron-style jobs when Temporal is off (run exactly one)
#   migrate    apply migrations (and sync Temporal schedules when enabled), then exit
#   job NAME   run one job and exit (for cron / CronJob)
#   manage ... python manage.py ...
# Anything else is executed as given.
set -eu

role="${1:-web}"
[ "$#" -gt 0 ] && shift

case "$role" in
  web)
    exec gunicorn config.asgi:application \
      --bind "0.0.0.0:${PORT:-8000}" \
      --worker-class uvicorn_worker.UvicornWorker \
      --workers "${WEB_CONCURRENCY:-2}" \
      --timeout "${WEB_TIMEOUT:-30}" \
      --graceful-timeout 30 \
      --max-requests 1000 --max-requests-jitter 100 \
      --access-logfile - --error-logfile -
    ;;
  worker)
    exec python manage.py flows_worker "$@"
    ;;
  scheduler)
    exec python manage.py run_scheduler "$@"
    ;;
  migrate)
    python manage.py migrate --noinput
    if [ "${TEMPORAL_ENABLED:-false}" = "true" ]; then
      python manage.py flows_sync
    fi
    ;;
  job)
    exec python manage.py run_job "$@"
    ;;
  manage)
    exec python manage.py "$@"
    ;;
  *)
    exec "$role" "$@"
    ;;
esac
