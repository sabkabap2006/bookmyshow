#!/bin/bash

echo "Starting Django application..."

python manage.py collectstatic --noinput
python manage.py migrate --noinput

gunicorn bookmyseat.wsgi:application --bind 0.0.0.0:$PORT