#!/bin/bash
set -o errexit

echo "Starting Django application..."

python manage.py collectstatic --noinput
python manage.py migrate --noinput

exec gunicorn bookmyseat.wsgi:application --bind 0.0.0.0:$PORT