#!/bin/sh
set -eu

: "${DATABASE_URL:?DATABASE_URL must be configured for Render}"
: "${ALLOWED_HOSTS:?ALLOWED_HOSTS must be configured for Render}"
case "$DATABASE_URL" in
    postgres://*|postgresql://*) ;;
    *) echo "DATABASE_URL must point to a PostgreSQL database." >&2; exit 1 ;;
esac

python manage.py migrate --noinput
python manage.py load_public_demo_catalog --database default
python manage.py collectstatic --noinput

exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-10000}" \
    --workers 2 \
    --threads 2 \
    --timeout 120
