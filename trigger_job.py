#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from viral_clips.tasks import process_video_job

if len(sys.argv) < 2:
    print("Usage: python trigger_job.py <job_id>")
    sys.exit(1)

job_id = sys.argv[1]
process_video_job.delay(job_id)
print(f"✅ Task triggered for job: {job_id}")
