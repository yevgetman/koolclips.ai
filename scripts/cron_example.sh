#!/bin/bash
#
# Example CRON job script for Cloudcube cleanup
#
# This script can be scheduled to run daily via CRON or Heroku Scheduler
# to automatically clean up old files from Cloudcube.
#
# Setup for CRON (runs daily at 2 AM):
#   0 2 * * * /path/to/viral-clips/scripts/cron_example.sh >> /var/log/cloudcube-cleanup.log 2>&1
#
# Setup for Heroku Scheduler:
#   1. Add Heroku Scheduler add-on (requires paid dynos)
#   2. Create a new job with command: bash scripts/cron_example.sh
#   3. Set frequency to "Daily" at desired time

# Set your app's URL (replace with your actual app URL)
API_URL="${API_URL:-https://your-app.herokuapp.com}"

# Set retention period (days)
RETENTION_DAYS="${RETENTION_DAYS:-5}"

# Log timestamp
echo "========================================="
echo "Cloudcube Cleanup - $(date)"
echo "========================================="

# Call the cleanup API endpoint
curl -X POST "${API_URL}/api/cleanup/bulk/" \
  -H "Content-Type: application/json" \
  -d "{\"retention_days\": ${RETENTION_DAYS}, \"dry_run\": false}" \
  -w "\nHTTP Status: %{http_code}\n" \
  -s

# Check exit status
if [ $? -eq 0 ]; then
  echo "✅ Cleanup completed successfully"
else
  echo "❌ Cleanup failed"
  exit 1
fi

echo "========================================="
echo ""
