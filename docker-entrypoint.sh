#!/bin/bash

echo "Collect static files"
python manage.py collectstatic --noinput

echo "Apply database migrations"
python manage.py migrate

echo "Starting server"
uvicorn config.asgi:application --port 8000 --host 0.0.0.0 --workers 1
