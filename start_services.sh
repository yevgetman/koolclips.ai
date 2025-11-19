#!/bin/bash

# Start Services Script for Viral Clips
# This script starts all necessary services in separate terminal tabs/windows

echo "Starting Viral Clips services..."

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Check if Redis is running
if ! pgrep -x "redis-server" > /dev/null; then
    echo "Starting Redis..."
    redis-server &
    sleep 2
fi

echo "Starting Celery worker..."
celery -A config worker -l info &

sleep 2

echo "Starting Django development server..."
python manage.py runserver

# Note: This script runs Django in foreground.
# To stop all services, press Ctrl+C and run: pkill -f celery
