release: python manage.py migrate --noinput
web: gunicorn config.asgi:application --bind 0.0.0.0:$PORT --worker-class uvicorn_worker.UvicornWorker --workers ${WEB_CONCURRENCY:-2} --timeout 30 --graceful-timeout 30 --access-logfile - --error-logfile -
worker: python manage.py flows_worker
scheduler: python manage.py run_scheduler
