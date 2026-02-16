#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate --noinput
# python manage.py loaddata tender_dump.json

python manage.py collectstatic --noinput
