# ✅ Cloudcube Cleanup Endpoints - Deployed & Tested

**Deployment:** v40  
**Date:** November 23, 2025  
**Status:** ACTIVE ✅

## Two Cleanup Endpoints

### 1. Bulk Cleanup - `/api/cleanup/bulk/`

**Purpose:** Regular maintenance - deletes temp files and old clips

**Features:**
- ✅ Deletes temporary files (uploads, extracted audio, test results)
- ✅ Deletes clips older than retention period
- ✅ Preserves recent clips
- ✅ Runs automatically daily via Celery Beat (2 AM UTC)
- ✅ Can be run manually anytime

**Request:**
```bash
curl -X POST https://www.koolclips.ai/api/cleanup/bulk/ \
  -H "Content-Type: application/json" \
  -d '{"retention_days": 5, "dry_run": false}'
```

**Parameters:**
- `retention_days` (int): Keep clips newer than N days (default: 5)
- `dry_run` (bool): Preview without deleting (default: false)

---

### 2. Clips Cleanup - `/api/cleanup/clips/` ⚠️ NEW

**Purpose:** Complete cleanup - deletes ALL clips regardless of age

**Features:**
- ⚠️ Deletes ALL user-created clips
- ✅ Requires explicit confirmation (`confirm: true`)
- ✅ Dry run mode available
- ❌ NOT scheduled (manual only)
- 🛡️ Safety check prevents accidental deletion

**Request:**
```bash
curl -X POST https://www.koolclips.ai/api/cleanup/clips/ \
  -H "Content-Type: application/json" \
  -d '{"confirm": true, "dry_run": false}'
```

**Parameters:**
- `confirm` (bool): REQUIRED - must be true to delete (safety check)
- `dry_run` (bool): Preview without deleting (default: false)

**Safety Feature:**
If you forget `confirm: true`, you get:
```json
{
  "success": false,
  "error": "This operation will delete ALL clips. Set \"confirm\": true to proceed.",
  "warning": "⚠️ WARNING: This will permanently delete all user-created clips!"
}
```

## Complete Cleanup Workflow

To delete **everything** in Cloudcube:

### Test Results (Dry Run)

**Current storage:** ~40 MB in clips

**Step 1: Bulk cleanup with retention_days=0**
```bash
curl -X POST https://www.koolclips.ai/api/cleanup/bulk/ \
  -H "Content-Type: application/json" \
  -d '{"retention_days": 0, "dry_run": true}'
```

Result: Would delete 13 clips (39.96 MB)

**Step 2: Clips cleanup**
```bash
curl -X POST https://www.koolclips.ai/api/cleanup/clips/ \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}'
```

Result: Would delete 13 clips (39.96 MB)

**Note:** With `retention_days=0`, bulk cleanup would delete all clips anyway. The clips endpoint is useful when you want to preserve temp files but delete all clips, or for situations where clips weren't caught by bulk cleanup.

## Use Cases

### Regular Maintenance (Automated)
**Endpoint:** Bulk cleanup  
**Schedule:** Daily at 2 AM UTC via Celery Beat  
**Config:** 5-day retention

```python
# config/celery.py
'daily-cloudcube-cleanup': {
    'task': 'viral_clips.tasks.scheduled_cloudcube_cleanup',
    'schedule': crontab(hour=2, minute=0),
    'kwargs': {'retention_days': 5},
}
```

**Result:** Automatically maintains storage, keeps recent clips for users

### Development Reset
**Endpoints:** Bulk + Clips  
**Frequency:** As needed  
**Purpose:** Clear all test data

```bash
# Delete everything
curl -X POST https://www.koolclips.ai/api/cleanup/bulk/ \
  -d '{"retention_days": 0, "dry_run": false}'

curl -X POST https://www.koolclips.ai/api/cleanup/clips/ \
  -d '{"confirm": true, "dry_run": false}'
```

### Emergency Storage Cleanup
**Endpoint:** Bulk with retention_days=0  
**Frequency:** When needed  
**Purpose:** Free maximum storage quickly

```bash
curl -X POST https://www.koolclips.ai/api/cleanup/bulk/ \
  -d '{"retention_days": 0, "dry_run": false}'
```

### Delete Only Clips (Keep Processing Files)
**Endpoint:** Clips cleanup only  
**Frequency:** As needed  
**Purpose:** Remove user clips but keep temp files

```bash
curl -X POST https://www.koolclips.ai/api/cleanup/clips/ \
  -d '{"confirm": true, "dry_run": false}'
```

## Comparison Table

| Feature | Bulk Cleanup | Clips Cleanup |
|---------|-------------|---------------|
| **Target** | Temp files + old clips | All clips only |
| **Endpoint** | `/api/cleanup/bulk/` | `/api/cleanup/clips/` |
| **Age filter** | ✅ Yes (retention_days) | ❌ No (deletes all) |
| **Safety check** | ❌ No | ✅ Yes (confirm required) |
| **Automated** | ✅ Yes (Celery Beat) | ❌ No (manual only) |
| **Dry run** | ✅ Yes | ✅ Yes |
| **Preserves clips** | ✅ Recent ones | ❌ None |
| **Use case** | Regular maintenance | Complete cleanup |

## Quick Reference

### Preview Everything That Would Be Deleted

```bash
# Bulk cleanup preview
curl -X POST https://www.koolclips.ai/api/cleanup/bulk/ \
  -H "Content-Type: application/json" \
  -d '{"retention_days": 0, "dry_run": true}' | jq

# Clips cleanup preview
curl -X POST https://www.koolclips.ai/api/cleanup/clips/ \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}' | jq
```

### Execute Complete Cleanup

```bash
# Step 1: Delete temp files and old clips
curl -X POST https://www.koolclips.ai/api/cleanup/bulk/ \
  -H "Content-Type: application/json" \
  -d '{"retention_days": 0, "dry_run": false}'

# Step 2: Delete all remaining clips (if any)
curl -X POST https://www.koolclips.ai/api/cleanup/clips/ \
  -H "Content-Type: application/json" \
  -d '{"confirm": true, "dry_run": false}'
```

### Check Current Storage

```bash
# See what bulk cleanup would delete
curl -X POST https://www.koolclips.ai/api/cleanup/bulk/ \
  -d '{"retention_days": 5, "dry_run": true}' | jq '.deleted_size_mb'

# See how many clips exist
curl -X POST https://www.koolclips.ai/api/cleanup/clips/ \
  -d '{"dry_run": true}' | jq '.deleted_count'
```

## Monitoring

### View Cleanup Logs

```bash
# Scheduled cleanup (Celery Beat)
heroku logs --tail --app koolclips | grep "scheduled_cloudcube_cleanup"

# Manual cleanup
heroku logs --tail --app koolclips | grep "cleanup"

# Clips deletion
heroku logs --tail --app koolclips | grep "Deleted clip"
```

### Check Celery Beat Status

```bash
heroku ps --app koolclips | grep beat
```

## Storage Saved So Far

**First cleanup (Nov 23, 2025):**
- 🗑️ Deleted: 55 files
- 💾 Freed: 8,660.75 MB (~8.6 GB)
- 📦 Retained: 13 recent clips

**Current storage:** ~40 MB (13 clips)

## Documentation

- **[CLOUDCUBE_CLEANUP.md](docs/CLOUDCUBE_CLEANUP.md)** - Bulk cleanup system
- **[COMPLETE_CLEANUP_GUIDE.md](docs/COMPLETE_CLEANUP_GUIDE.md)** - Complete cleanup workflow
- **[CELERY_BEAT_SETUP.md](docs/CELERY_BEAT_SETUP.md)** - Celery Beat configuration

## Summary

✅ **Two cleanup endpoints deployed and tested**

1. **Bulk cleanup** - Automated daily maintenance with retention period
2. **Clips cleanup** - Manual complete cleanup with safety confirmation

Together they provide:
- 🔄 Automatic daily cleanup
- 🛡️ Safe manual cleanup with confirmation
- 🧹 Complete storage cleanup capability
- 📊 Full logging and monitoring
- 💰 Significant cost savings

**Next cleanup:** Tomorrow at 2:00 AM UTC (automated) 🚀
