# Deploying Large File Upload Support

## What Was Changed

### New Features
1. **Presigned S3 URLs** - Direct client-to-S3 uploads bypassing Heroku timeout
2. **Automatic S3 Cleanup** - Removes temporary files after all clips complete
3. **Large File Support** - Files up to 2GB can now be uploaded

### Files Modified

#### New Endpoints (`viral_clips/views.py`)
- `get_presigned_upload_url()` - Generate presigned URL for upload
- `create_job_from_s3()` - Create job after S3 upload completes

#### Enhanced S3Service (`viral_clips/services/s3_service.py`)
- `generate_presigned_upload_url()` - Create presigned POST URLs
- `cleanup_job_files()` - Delete media files after processing
- `get_public_url_from_key()` - Get public URL for S3 key

#### Updated Tasks (`viral_clips/tasks.py`)
- `cleanup_job_files()` - New Celery task for cleanup
- `check_render_status()` - Modified to trigger cleanup when all clips complete

#### URL Routes (`viral_clips/urls.py`)
- `/api/upload/presigned-url/` - Get presigned upload URL
- `/api/upload/create-job/` - Create job from S3 file

#### Test Scripts
- `test_large_file_upload.py` - Test presigned URL uploads

#### Documentation
- `docs/LARGE_FILE_UPLOAD.md` - Complete implementation guide
- `STAGE1_TEST_RESULTS.md` - Original test results showing issue

---

## Deployment Steps

### 1. Commit Changes

```bash
git add -A
git commit -m "Add presigned URL support for large file uploads and automatic S3 cleanup"
```

### 2. Deploy to Heroku

```bash
git push heroku main
```

### 3. Verify Deployment

```bash
# Check if deployment succeeded
heroku ps

# Check environment variables
heroku config:get CLOUDCUBE_URL

# Check logs for any errors
heroku logs --tail
```

### 4. Test New Endpoints

```bash
# Test presigned URL endpoint
curl -X POST https://koolclips-ed69bc2e07f2.herokuapp.com/api/upload/presigned-url/ \
  -H "Content-Type: application/json" \
  -d '{"filename": "test.mp4", "file_size": 1000000, "content_type": "video/mp4"}'
```

### 5. Test Large File Upload

```bash
# Test with 40MB file
python test_large_file_upload.py \
  --file demo_files/test_video_30s.mp4 \
  --url https://koolclips-ed69bc2e07f2.herokuapp.com \
  --segments 3 \
  --monitor

# Test with 4GB file
python test_large_file_upload.py \
  --file demo_files/diazreport2.mp4 \
  --url https://koolclips-ed69bc2e07f2.herokuapp.com \
  --segments 5
```

---

## Verification Checklist

- [ ] Code deployed successfully
- [ ] New API endpoints accessible
- [ ] Presigned URLs generated correctly
- [ ] Files upload to S3 successfully
- [ ] Jobs created and processed
- [ ] Cleanup triggers after clips complete
- [ ] No errors in Heroku logs

---

## Monitoring

### Check Upload Success

```bash
# Monitor API logs
heroku logs --tail --source app

# Monitor Celery worker logs  
heroku logs --tail --source worker

# Filter for cleanup events
heroku logs --tail | grep "cleanup"
```

### Expected Log Messages

**Successful Upload:**
```
Generated presigned upload URL for: uploads/direct/{job_id}/{filename}
File uploaded to S3 successfully
Job created: {job_id}
```

**Successful Cleanup:**
```
All clips completed for job {job_id}. Initiating S3 cleanup...
Cleaned up S3 file for job {job_id}: {s3_key}
Successfully cleaned up S3 files for job {job_id}
```

---

## Rollback Plan

If issues occur:

```bash
# Rollback to previous version
heroku rollback

# Or rollback to specific version
heroku releases
heroku rollback v123
```

The old HTTP upload method (for files <100MB) is still available and will continue working.

---

## API Backward Compatibility

✅ **Old upload method still works** - Existing clients using `POST /api/jobs/` with multipart form data will continue functioning for files under ~100MB.

✅ **New method is optional** - Clients can choose which upload method to use based on file size.

**Recommended approach:**
- Files < 100MB: Use existing `POST /api/jobs/` endpoint
- Files > 100MB: Use new presigned URL workflow

---

## Next Steps After Deployment

1. **Update frontend/client** to use presigned URLs for large files
2. **Monitor cleanup jobs** to ensure they're running correctly
3. **Check S3 storage usage** to verify cleanup is freeing space
4. **Update API documentation** with new endpoints
5. **Test end-to-end** with actual large files

---

## Configuration

No new environment variables required! The feature uses existing S3/Cloudcube configuration:

- `CLOUDCUBE_URL` (or standalone AWS credentials)
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_STORAGE_BUCKET_NAME`
- `AWS_S3_REGION_NAME`

---

## Success Metrics

After deployment, monitor:

1. **Upload Success Rate** - Should be ~100% for large files now
2. **S3 Storage Usage** - Should stabilize or decrease with cleanup
3. **Job Completion Rate** - Should improve for large file jobs
4. **Error Logs** - Should see fewer timeout errors

---

## Troubleshooting

### Issue: Presigned URL generation fails

**Check:**
```bash
heroku config | grep AWS
heroku config | grep CLOUDCUBE
```

**Solution:** Ensure S3/Cloudcube credentials are set

### Issue: Upload to S3 fails

**Check:** S3 bucket permissions and CORS settings

**For Cloudcube:** Should work out of the box (public folder is writable)

### Issue: Cleanup not triggering

**Check:** Celery workers are running
```bash
heroku ps
```

**Solution:** Ensure worker dyno is active
```bash
heroku ps:scale worker=1
```

---

## Cost Impact

**Positive:**
- ✅ Reduced S3 storage costs (automatic cleanup)
- ✅ Reduced bandwidth costs (direct upload to S3)
- ✅ Fewer failed uploads (better success rate)

**Neutral:**
- Same Celery worker usage
- Same API request costs

---

## Documentation Updated

- ✅ `docs/LARGE_FILE_UPLOAD.md` - Implementation guide
- ✅ `DEPLOY_LARGE_FILE_SUPPORT.md` - This deployment guide  
- ✅ `test_large_file_upload.py` - Test script with examples

---

## Support

If you encounter issues:

1. Check Heroku logs: `heroku logs --tail`
2. Review S3 bucket configuration
3. Test with smaller files first
4. Verify Celery workers are running

---

**Ready to deploy!** Follow the steps above to enable large file upload support.
