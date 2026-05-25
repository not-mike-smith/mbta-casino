#!/bin/sh
set -e

echo "Running database migrations..."
python manage.py migrate --noinput

# Seed stations on first boot if the table is empty.
# In a mature CD pipeline this would be a dedicated migration/deploy step,
# but the command is idempotent so running it conditionally here is safe.
STATION_COUNT=$(python manage.py shell -c "from stations.models import Station; print(Station.objects.count())")
if [ "$STATION_COUNT" = "0" ]; then
    echo "Seeding stations from MBTA API..."
    python manage.py sync_stations
else
    echo "Stations already seeded ($STATION_COUNT records), skipping."
fi

echo "Starting Gunicorn..."
exec gunicorn mbta_casino.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --timeout 30 \
    --access-logfile -
