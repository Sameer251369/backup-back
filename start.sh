#!/usr/bin/env bash
set -e

python manage.py migrate --noinput
python manage.py loaddata data.json || python manage.py seed_calculator_data
python manage.py seed_vehicle_variants
exec gunicorn carguide.wsgi:application