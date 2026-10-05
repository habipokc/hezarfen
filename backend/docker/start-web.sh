#!/bin/sh
# Production web entrypoint: apply migrations (Django owns the schema), then serve ASGI.
set -e
python manage.py migrate --noinput
exec uvicorn hezarfen.asgi:application --host 0.0.0.0 --port 8000 --workers "${WEB_WORKERS:-2}" --proxy-headers --forwarded-allow-ips='*'
