import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('viral_clips')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Celery Beat schedule for periodic tasks
app.conf.beat_schedule = {
    'daily-cloudcube-cleanup': {
        'task': 'viral_clips.tasks.scheduled_cloudcube_cleanup',
        'schedule': crontab(hour=2, minute=0),  # Run daily at 2:00 AM UTC
        'kwargs': {'retention_days': 5},
    },
}

app.conf.timezone = 'UTC'


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
