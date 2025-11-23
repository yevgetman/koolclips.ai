# Complete Cloudcube Cleanup Guide

This guide explains how to perform a complete cleanup of all files in Cloudcube using the two cleanup endpoints.

## Two-Step Complete Cleanup

To delete **everything** in Cloudcube, run these endpoints in succession:

### Step 1: Bulk Cleanup (Temp Files + Old Clips)

Deletes temporary files and clips older than the retention period:

```bash
curl -X POST https://www.koolclips.ai/api/cleanup/bulk/ \
  -H "Content-Type: application/json" \
  -d '{"retention_days": 5, "dry_run": false}'
```

**This removes:**
- ✅ Original uploaded media files
- ✅ Extracted audio files
- ✅ Test result JSON files
- ✅ Clips older than 5 days

**This preserves:**
- 📦 Recent clips (created within last 5 days)

### Step 2: Clips Cleanup (All Remaining Clips)

⚠️ **WARNING:** Deletes ALL clips regardless of age:

```bash
curl -X POST https://www.koolclips.ai/api/cleanup/clips/ \
  -H "Content-Type: application/json" \
  -d '{"confirm": true, "dry_run": false}'
```

**This removes:**
- ✅ ALL clips in the `clips/` folder

**Result:** Cloudcube is now completely empty! 🧹

## Clips Cleanup Endpoint

### Endpoint

```
POST /api/cleanup/clips/
```

### Request Body

```json
{
  "dry_run": false,  // Optional, default false (set true to preview)
  "confirm": true    // REQUIRED for actual deletion (safety check)
}
```

### Safety Features

1. **Confirmation Required:** Must set `"confirm": true` to actually delete
2. **Dry Run Mode:** Preview what would be deleted without deleting
3. **Explicit Warning:** Returns error if confirmation not provided

### Response

```json
{
  "success": true,
  "message": "Deleted 13 clips (156.78 MB)",
  "deleted_count": 13,
  "deleted_size_mb": 156.78,
  "dry_run": false,
  "deleted_files_sample": [
    "mkwcrxocz0mi/public/clips/job-id/segment-id/clip.mp4",
    "..."
  ],
  "warning": "⚠️ All clips have been deleted!"
}
```

## Usage Examples

### Example 1: Preview Complete Cleanup

**Step 1: Preview bulk cleanup**
```bash
curl -X POST https://www.koolclips.ai/api/cleanup/bulk/ \
  -H "Content-Type: application/json" \
  -d '{"retention_days": 5, "dry_run": true}'
```

**Step 2: Preview clips cleanup**
```bash
curl -X POST https://www.koolclips.ai/api/cleanup/clips/ \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}'
```

Review both results, then proceed if satisfied.

### Example 2: Execute Complete Cleanup

**Step 1: Run bulk cleanup**
```bash
curl -X POST https://www.koolclips.ai/api/cleanup/bulk/ \
  -H "Content-Type: application/json" \
  -d '{"retention_days": 0, "dry_run": false}'
```
*Note: Set `retention_days: 0` to delete all clips older than today*

**Step 2: Run clips cleanup**
```bash
curl -X POST https://www.koolclips.ai/api/cleanup/clips/ \
  -H "Content-Type: application/json" \
  -d '{"confirm": true, "dry_run": false}'
```

### Example 3: Clips Cleanup Without Confirmation

If you forget to set `confirm: true`:

```bash
curl -X POST https://www.koolclips.ai/api/cleanup/clips/ \
  -H "Content-Type: application/json" \
  -d '{"dry_run": false}'
```

**Response:**
```json
{
  "success": false,
  "error": "This operation will delete ALL clips. Set \"confirm\": true to proceed.",
  "warning": "⚠️ WARNING: This will permanently delete all user-created clips!"
}
```

### Example 4: Using Python

```python
import requests

API_URL = "https://www.koolclips.ai"

# Step 1: Dry run to preview
response = requests.post(
    f"{API_URL}/api/cleanup/clips/",
    json={"dry_run": True}
)
result = response.json()
print(f"Would delete {result['deleted_count']} clips ({result['deleted_size_mb']} MB)")

# Step 2: Confirm and execute
if input("Delete all clips? (yes/no): ").lower() == 'yes':
    response = requests.post(
        f"{API_URL}/api/cleanup/clips/",
        json={"confirm": True, "dry_run": False}
    )
    print(response.json()['message'])
```

## Complete Cleanup Script

Create a script to automate the complete cleanup:

```bash
#!/bin/bash
# complete_cleanup.sh - Delete everything in Cloudcube

API_URL="https://www.koolclips.ai"

echo "========================================="
echo "Complete Cloudcube Cleanup"
echo "========================================="
echo ""
echo "⚠️  WARNING: This will delete ALL files!"
echo ""
read -p "Are you sure? Type 'yes' to continue: " confirm

if [ "$confirm" != "yes" ]; then
  echo "Cleanup cancelled."
  exit 0
fi

echo ""
echo "Step 1/2: Running bulk cleanup..."
curl -X POST "${API_URL}/api/cleanup/bulk/" \
  -H "Content-Type: application/json" \
  -d '{"retention_days": 0, "dry_run": false}' \
  -s | python3 -m json.tool

echo ""
echo "Step 2/2: Running clips cleanup..."
curl -X POST "${API_URL}/api/cleanup/clips/" \
  -H "Content-Type: application/json" \
  -d '{"confirm": true, "dry_run": false}' \
  -s | python3 -m json.tool

echo ""
echo "✅ Complete cleanup finished!"
```

**Usage:**
```bash
chmod +x complete_cleanup.sh
./complete_cleanup.sh
```

## Use Cases

### 1. Development/Testing Reset
Delete all test data to start fresh:
```bash
# Preview first
curl -X POST https://www.koolclips.ai/api/cleanup/bulk/ \
  -H "Content-Type: application/json" \
  -d '{"retention_days": 0, "dry_run": true}'

curl -X POST https://www.koolclips.ai/api/cleanup/clips/ \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}'

# Execute
# ... (run with dry_run: false)
```

### 2. Cost Reduction
Completely clear Cloudcube to minimize storage costs:
```bash
# Run complete cleanup to free maximum storage
./complete_cleanup.sh
```

### 3. Migration Preparation
Clear all data before migrating to a new storage solution:
```bash
# Backup clips first
# Then run complete cleanup
```

### 4. Periodic Full Cleanup
If you don't need any persistent storage, schedule complete cleanup weekly:
```bash
# Weekly CRON job
0 0 * * 0 /path/to/complete_cleanup.sh
```

## Comparison: Bulk vs Clips Cleanup

| Feature | Bulk Cleanup | Clips Cleanup |
|---------|-------------|---------------|
| **Target** | Temp files + old clips | All clips |
| **Age filter** | ✅ Retention period | ❌ Deletes all |
| **Preserves clips** | ✅ Recent ones | ❌ None |
| **Safety check** | ❌ None | ✅ Requires confirm |
| **Scheduled** | ✅ Daily via Celery Beat | ❌ Manual only |
| **Use case** | Regular maintenance | Complete cleanup |

## Safety Considerations

### Clips Cleanup Safeguards

1. **Explicit Confirmation Required**
   - Must set `"confirm": true` in request body
   - Prevents accidental deletion via simple API calls

2. **Dry Run Mode**
   - Always available to preview deletion
   - No confirmation needed for dry runs

3. **Clear Warnings**
   - API returns explicit warnings
   - Logs all deletions

4. **No Scheduled Execution**
   - Not included in Celery Beat schedule
   - Must be triggered manually

### Recommended Safety Practices

1. **Always dry run first:**
   ```bash
   # Step 1: Preview
   curl ... -d '{"dry_run": true}'
   
   # Step 2: Review output
   # Step 3: Execute if satisfied
   curl ... -d '{"confirm": true, "dry_run": false}'
   ```

2. **Backup important clips** before complete cleanup

3. **Use with caution** in production

4. **Document cleanup operations** in maintenance logs

5. **Notify users** if clips will be deleted

## Monitoring

### Check Current Storage Usage

```bash
# List all files before cleanup
curl https://www.koolclips.ai/api/cleanup/bulk/ \
  -H "Content-Type: application/json" \
  -d '{"retention_days": 0, "dry_run": true}' | jq

curl https://www.koolclips.ai/api/cleanup/clips/ \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}' | jq
```

### View Cleanup Logs

```bash
# View cleanup execution logs
heroku logs --tail --app koolclips | grep "cleanup"

# View clips deletion logs
heroku logs --tail --app koolclips | grep "Deleted clip"
```

## Troubleshooting

### Issue: Clips Cleanup Returns 400 Error

**Cause:** Missing `confirm: true` parameter

**Solution:** Add confirmation to request:
```json
{"confirm": true, "dry_run": false}
```

### Issue: Some Files Not Deleted

**Cause:** Permissions or S3 errors

**Solution:** Check logs:
```bash
heroku logs --app koolclips | grep "Failed to delete"
```

### Issue: Want to Delete Only Clips (Keep Temp Files)

**Solution:** Only run Step 2 (clips cleanup):
```bash
curl -X POST https://www.koolclips.ai/api/cleanup/clips/ \
  -H "Content-Type: application/json" \
  -d '{"confirm": true, "dry_run": false}'
```

## Summary

**Two endpoints for complete cleanup:**

1. **Bulk Cleanup** (`/api/cleanup/bulk/`)
   - Deletes temp files + old clips
   - Preserves recent clips based on retention period
   - Runs automatically daily via Celery Beat

2. **Clips Cleanup** (`/api/cleanup/clips/`)
   - Deletes ALL clips (no retention period)
   - Requires explicit confirmation
   - Manual execution only

**Together, they provide complete Cloudcube cleanup capability! 🧹**
