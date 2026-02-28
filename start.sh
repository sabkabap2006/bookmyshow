#!/bin/bash
set -o errexit

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec gunicorn bookmyseat.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 120