# Cloudcube Cleanup System

This document describes the automatic and manual cleanup functionality for Cloudcube storage to minimize storage costs while preserving user-generated clips.

## Overview

Cloudcube is used as temporary storage for:
- Original uploaded media files
- Extracted audio files
- Processing artifacts

The only files that should persist long-term are the **final user-created clips**, which are retained for **5 days** (configurable) to allow users time to download them.

## Automatic Cleanup (After Stage 4)

When all clips for a job are successfully completed (Stage 4), the system automatically triggers cleanup of temporary files:

### What Gets Deleted
- Original media file (video or audio)
- Extracted audio file (for video uploads)

### What Gets Preserved
- All final clips in the `clips/` folder

### Implementation

The automatic cleanup is triggered in `tasks.py` by the `check_render_status` task:

```python
# After all clips complete for a job
if total_clips > 0 and completed_clips == total_clips:
    logger.info(f"All clips completed for job {job.id}. Initiating S3 cleanup...")
    cleanup_job_files.delay(str(job.id))
```

The `cleanup_job_files` task calls `S3Service.cleanup_job_files(job)` which:
1. Collects S3 keys for the original media file and extracted audio
2. Deletes each file from S3/Cloudcube
3. Logs the cleanup actions

## Bulk Cleanup API Endpoint

For periodic cleanup of all files including old clips, use the bulk cleanup endpoint.

### Endpoint

```
POST /api/cleanup/bulk/
```

### Request Body

```json
{
  "retention_days": 5,  // Optional, default 5 days
  "dry_run": false      // Optional, default false (set true to preview without deleting)
}
```

### Parameters

- **retention_days** (integer, optional, default: 5): Number of days to retain final clips. Clips older than this will be deleted.
- **dry_run** (boolean, optional, default: false): If true, the API will simulate the cleanup and return what would be deleted without actually deleting anything.

### Response

```json
{
  "success": true,
  "message": "Deleted 150 files (1234.56 MB), retained 25 recent clips",
  "deleted_count": 150,
  "deleted_size_mb": 1234.56,
  "retained_count": 25,
  "total_files_scanned": 175,
  "dry_run": false,
  "deleted_files_sample": ["file1.mp4", "file2.mp3", "..."],
  "retention_days": 5
}
```

### What Gets Deleted

The bulk cleanup deletes:
- All temporary files (uploads, extracted audio, etc.)
- Clips older than `retention_days`

### What Gets Preserved

The bulk cleanup preserves:
- Clips created within the last `retention_days` (default 5 days)
- Files in the `clips/` folder that are newer than the retention period

### Logic

1. Query database for all completed clips created within `retention_days`
2. Build a set of S3 keys to preserve
3. List all files in Cloudcube bucket
4. For each file:
   - Check if it's a preserved clip (by S3 key match)
   - Check if it's in `clips/` folder and created within retention period
   - If neither, mark for deletion
5. Delete all marked files (unless `dry_run=true`)

## Usage Examples

### Manual Cleanup (Dry Run First)

Test the cleanup without deleting anything:

```bash
curl -X POST https://your-app.herokuapp.com/api/cleanup/bulk/ \
  -H "Content-Type: application/json" \
  -d '{
    "retention_days": 5,
    "dry_run": true
  }'
```

Then perform the actual cleanup:

```bash
curl -X POST https://your-app.herokuapp.com/api/cleanup/bulk/ \
  -H "Content-Type: application/json" \
  -d '{
    "retention_days": 5,
    "dry_run": false
  }'
```

### CRON Job (if paid scheduler available)

If you have access to Heroku Scheduler or another CRON service, schedule daily cleanup:

```bash
# Run daily at 2 AM
curl -X POST https://your-app.herokuapp.com/api/cleanup/bulk/ \
  -H "Content-Type: application/json" \
  -d '{"retention_days": 5}'
```

### Using Python Requests

```python
import requests

# Dry run first
response = requests.post(
    'https://your-app.herokuapp.com/api/cleanup/bulk/',
    json={
        'retention_days': 5,
        'dry_run': True
    }
)

result = response.json()
print(f"Would delete {result['deleted_count']} files ({result['deleted_size_mb']} MB)")
print(f"Would retain {result['retained_count']} recent clips")

# If satisfied, run for real
if input("Proceed with cleanup? (y/n): ").lower() == 'y':
    response = requests.post(
        'https://your-app.herokuapp.com/api/cleanup/bulk/',
        json={
            'retention_days': 5,
            'dry_run': False
        }
    )
    print(response.json()['message'])
```

## Recommended Cleanup Schedule

### Option 1: Manual Cleanup
- Run cleanup manually once per week
- Use `dry_run=true` first to preview
- Adjust `retention_days` based on user needs

### Option 2: Automated Cleanup (with CRON)
- Schedule daily cleanup at off-peak hours (e.g., 2 AM)
- Set `retention_days=5` to give users 5 days to download clips
- Monitor logs to ensure cleanup is working correctly

### Option 3: On-Demand Cleanup
- Trigger cleanup when approaching storage limits
- Use Cloudcube dashboard to monitor storage usage
- Run cleanup with `dry_run=true` first to estimate space savings

## Storage Cost Optimization

### Current Behavior
- ✅ Automatic cleanup of temporary files after Stage 4
- ✅ Clips retained for 5 days by default
- ✅ Bulk cleanup endpoint for manual/scheduled cleanup

### Best Practices
1. **Monitor Storage**: Check Cloudcube dashboard regularly
2. **Set Retention Period**: Balance user convenience vs. storage costs
3. **Test First**: Always use `dry_run=true` before running cleanup
4. **Log Review**: Check logs to ensure cleanup is working correctly
5. **User Communication**: Inform users that clips expire after N days

## Troubleshooting

### Cleanup Not Deleting Files

1. Check S3 configuration:
   ```python
   from viral_clips.services.s3_service import S3Service
   print(S3Service.is_s3_configured())  # Should be True
   ```

2. Check Cloudcube connection:
   ```bash
   heroku config:get CLOUDCUBE_URL
   ```

3. Review logs for errors:
   ```bash
   heroku logs --tail | grep cleanup
   ```

### Too Many Files Being Deleted

1. Run with `dry_run=true` first
2. Check `retention_days` setting
3. Verify clip `created_at` dates in database
4. Check if clips are marked as `completed` in database

### Clips Still Appear After Retention Period

- The bulk cleanup only runs when triggered
- Use CRON or manual trigger to run cleanup
- Check that the endpoint is being called successfully

## Implementation Details

### S3Service Methods

#### `cleanup_job_files(job)`
Automatic cleanup after Stage 4 completion for a specific job.

#### `bulk_cleanup_cloudcube(retention_days, dry_run)`
Bulk cleanup of all files with retention policy.

#### `list_all_files(bucket, prefix, max_keys)`
Lists all files in S3/Cloudcube for processing.

### Database Queries

The bulk cleanup queries the `ClippedVideo` model:
```python
recent_clips = ClippedVideo.objects.filter(
    created_at__gte=cutoff_date,
    status='completed'
)
```

This ensures only completed clips within the retention period are preserved.

## Security Considerations

- The cleanup endpoint has no authentication by default
- **Recommended**: Add authentication/authorization before deploying to production
- Consider rate limiting to prevent abuse
- Monitor cleanup logs for suspicious activity

## Future Enhancements

Potential improvements:
- Add authentication to bulk cleanup endpoint
- Email notifications after cleanup with summary
- Configurable retention periods per user/job
- Scheduled cleanup via Celery periodic tasks
- Storage usage analytics dashboard
- Automatic cleanup triggers based on storage thresholds
