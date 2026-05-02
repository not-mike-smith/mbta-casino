#!/bin/sh
set -e

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Starting Gunicorn..."
exec gunicorn mbta_casino.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --timeout 30 \
    --access-logfile -
