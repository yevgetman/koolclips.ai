# Celery Beat Setup for Scheduled Tasks

This document explains how to set up and manage Celery Beat for automated periodic cleanup tasks.

## Overview

Celery Beat is a scheduler that kicks off tasks at regular intervals. We use it for automated daily cleanup of Cloudcube storage.

## Configuration

### Schedule Configuration

The schedule is defined in `config/celery.py`:

```python
app.conf.beat_schedule = {
    'daily-cloudcube-cleanup': {
        'task': 'viral_clips.tasks.scheduled_cloudcube_cleanup',
        'schedule': crontab(hour=2, minute=0),  # Run daily at 2:00 AM UTC
        'kwargs': {'retention_days': 5},
    },
}
```

### Task Definition

The scheduled task is in `viral_clips/tasks.py`:

```python
@shared_task
def scheduled_cloudcube_cleanup(retention_days=5):
    """
    Scheduled bulk cleanup of Cloudcube storage
    
    This task is executed periodically by Celery Beat (default: daily at 2 AM UTC).
    """
    # ... cleanup logic ...
```

## Heroku Deployment

### Process Types

The `Procfile` defines three process types:

```
web: gunicorn config.wsgi --log-file - --timeout 180 --workers 2 --threads 4
worker: celery -A config worker --loglevel=info
beat: celery -A config beat --loglevel=info
```

### Scaling Dynos

**Important:** You need to scale the `beat` dyno to 1 instance:

```bash
# Check current dyno configuration
heroku ps --app koolclips

# Scale beat dyno to 1 instance
heroku ps:scale beat=1 --app koolclips

# Verify
heroku ps --app koolclips
```

**Note:** Beat dyno should only have **1 instance** to avoid duplicate scheduled tasks.

### Typical Dyno Configuration

```
web=1      # Web server
worker=1   # Celery worker for async tasks
beat=1     # Celery beat for scheduled tasks
```

## Monitoring

### Check Beat Status

```bash
# View all running dynos
heroku ps --app koolclips

# View beat dyno logs
heroku logs --tail --ps beat --app koolclips

# View worker logs (to see when scheduled tasks execute)
heroku logs --tail --ps worker --app koolclips
```

### Log Messages to Look For

**Beat scheduler starting:**
```
[INFO/Beat] beat: Starting...
[INFO/Beat] Scheduler: Sending due task daily-cloudcube-cleanup
```

**Task execution:**
```
[INFO] Task viral_clips.tasks.scheduled_cloudcube_cleanup[...] received
[INFO] Starting scheduled Cloudcube cleanup (retention: 5 days)
[INFO] Scheduled cleanup completed: Deleted X files (Y MB), retained Z recent clips
```

## Customizing the Schedule

### Change Cleanup Time

Edit `config/celery.py`:

```python
# Run at 3:30 AM UTC
'schedule': crontab(hour=3, minute=30),

# Run every 12 hours
'schedule': crontab(hour='*/12', minute=0),

# Run weekly on Sunday at 2 AM
'schedule': crontab(hour=2, minute=0, day_of_week=0),
```

### Change Retention Period

Edit `config/celery.py`:

```python
'kwargs': {'retention_days': 7},  # Keep clips for 7 days instead of 5
```

### Add More Scheduled Tasks

Add to `beat_schedule` in `config/celery.py`:

```python
app.conf.beat_schedule = {
    'daily-cloudcube-cleanup': {
        'task': 'viral_clips.tasks.scheduled_cloudcube_cleanup',
        'schedule': crontab(hour=2, minute=0),
        'kwargs': {'retention_days': 5},
    },
    'weekly-report': {
        'task': 'viral_clips.tasks.send_weekly_report',
        'schedule': crontab(hour=9, minute=0, day_of_week=1),  # Monday 9 AM
    },
}
```

## Testing Locally

### Run Beat Locally

```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start Celery worker
celery -A config worker --loglevel=info

# Terminal 3: Start Celery beat
celery -A config beat --loglevel=info
```

### Trigger Task Manually

```python
# In Django shell
python manage.py shell

from viral_clips.tasks import scheduled_cloudcube_cleanup
result = scheduled_cloudcube_cleanup.delay(retention_days=5)
```

### Test Schedule Without Waiting

Temporarily change the schedule to run every minute:

```python
# In config/celery.py (for testing only)
'schedule': crontab(minute='*'),  # Run every minute
```

**Remember to revert after testing!**

## Troubleshooting

### Beat Not Starting

**Issue:** Beat dyno not running

```bash
# Check dyno status
heroku ps --app koolclips

# Should show:
# beat.1: up for 1h
```

**Solution:** Scale beat dyno to 1

```bash
heroku ps:scale beat=1 --app koolclips
```

### Tasks Not Executing

**Issue:** Beat is running but tasks aren't executing

**Checks:**
1. Verify worker dyno is running: `heroku ps --app koolclips`
2. Check beat logs: `heroku logs --tail --ps beat --app koolclips`
3. Check worker logs: `heroku logs --tail --ps worker --app koolclips`
4. Verify Redis connection: `heroku config:get REDIS_URL --app koolclips`

### Duplicate Task Executions

**Issue:** Cleanup running multiple times

**Cause:** Multiple beat dynos running

**Solution:** Ensure only 1 beat dyno:

```bash
heroku ps:scale beat=1 --app koolclips
```

### S3 Errors in Scheduled Tasks

**Issue:** Cleanup fails with S3 errors

**Checks:**
1. Verify S3 credentials: `heroku config --app koolclips | grep AWS`
2. Check Cloudcube status: `heroku addons:info cloudcube --app koolclips`
3. Review logs: `heroku logs --tail --app koolclips | grep cleanup`

## Cost Considerations

### Dyno Costs

- **Eco dynos:** ~$5/month per dyno
- **Basic dynos:** ~$7/month per dyno
- **Standard dynos:** ~$25/month per dyno

**Typical setup:**
```
web (Eco): $5/month
worker (Eco): $5/month
beat (Eco): $5/month
Total: ~$15/month
```

### Alternative: Combined Worker + Beat

To save costs, you can run beat and worker in the same dyno:

**Update Procfile:**
```
web: gunicorn config.wsgi --log-file - --timeout 180 --workers 2 --threads 4
worker: celery -A config worker --beat --loglevel=info
```

**Scale dynos:**
```bash
heroku ps:scale web=1 worker=1 beat=0 --app koolclips
```

**Trade-offs:**
- ✅ Saves ~$5/month (one less dyno)
- ❌ Worker restarts will interrupt scheduled tasks
- ❌ Less separation of concerns

## Best Practices

1. **Always run only 1 beat dyno** to avoid duplicate executions
2. **Monitor logs** after deployment to ensure cleanup is running
3. **Test with dry_run first** when changing retention policies
4. **Keep beat and worker separate** for production reliability
5. **Set up alerting** for failed cleanup tasks

## References

- [Celery Beat Documentation](https://docs.celeryproject.org/en/stable/userguide/periodic-tasks.html)
- [Heroku Celery Guide](https://devcenter.heroku.com/articles/celery-heroku)
- [Crontab Schedule Syntax](https://crontab.guru/)
