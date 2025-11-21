web: gunicorn config.wsgi --log-file - --timeout 180 --workers 2 --threads 4
worker: celery -A config worker --loglevel=info
