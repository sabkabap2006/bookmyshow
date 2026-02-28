#!/bin/bash
set -e

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Celery Worker..."
celery -A bookmyseat worker -l info &

echo "Starting Celery Beat..."
celery -A bookmyseat beat -l info &

echo "Starting Gunicorn..."
exec gunicorn bookmyseat.wsgi:application \
  --bind 0.0.0.0:$PORT \
  --workers 3 \
  --timeout 120
