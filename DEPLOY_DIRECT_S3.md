# Deploy with Direct AWS S3 - Complete Guide

This guide covers the complete migration from CloudCube to direct AWS S3.

## What Changed

### Removed
- ❌ CloudCube add-on dependency
- ❌ `cloudcube_adapter.py` (no longer needed)
- ❌ `storage_backends.py` CloudCube storage class
- ❌ All cube prefix logic throughout the codebase

### Simplified
- ✅ Direct S3 uploads with presigned URLs
- ✅ Single CloudFront domain configuration  
- ✅ Cleaner S3Service with no adapter layer
- ✅ Better CORS support for browser uploads

## Prerequisites

1. **AWS Account** with access to create S3 buckets
2. **IAM User** with S3 permissions
3. **S3 Bucket** with CORS configured

## Step 1: Create AWS S3 Bucket

```bash
# Using AWS CLI (or use AWS Console)
aws s3 mb s3://koolclips-media --region us-east-1
```

**Or via AWS Console:**
1. Go to https://s3.console.aws.amazon.com/
2. Click "Create bucket"
3. **Bucket name**: `koolclips-media` (must be globally unique)
4. **Region**: `us-east-1`
5. **Block Public Access**: UNCHECK "Block all public access"
6. Click "Create bucket"

## Step 2: Configure CORS on S3 Bucket

This is **CRITICAL** for browser uploads to work!

### Via AWS Console:
1. Open your bucket → **Permissions** tab
2. Scroll to **Cross-origin resource sharing (CORS)**
3. Click "Edit" and paste:

```json
[
    {
        "AllowedHeaders": ["*"],
        "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
        "AllowedOrigins": [
            "https://www.koolclips.ai",
            "https://koolclips.ai",
            "https://koolclips-ed69bc2e07f2.herokuapp.com",
            "http://localhost:8000"
        ],
        "ExposeHeaders": ["ETag", "x-amz-request-id"],
        "MaxAgeSeconds": 3600
    }
]
```

### Via AWS CLI:
```bash
cat > cors.json << 'EOF'
{
    "CORSRules": [
        {
            "AllowedHeaders": ["*"],
            "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
            "AllowedOrigins": [
                "https://www.koolclips.ai",
                "https://koolclips.ai",
                "https://koolclips-ed69bc2e07f2.herokuapp.com",
                "http://localhost:8000"
            ],
            "ExposeHeaders": ["ETag", "x-amz-request-id"],
            "MaxAgeSeconds": 3600
        }
    ]
}
EOF

aws s3api put-bucket-cors --bucket koolclips-media --cors-configuration file://cors.json
```

## Step 3: Set Bucket Policy for Public Read

```bash
cat > policy.json << 'EOF'
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::koolclips-media/*"
        }
    ]
}
EOF

aws s3api put-bucket-policy --bucket koolclips-media --policy file://policy.json
```

## Step 4: Create IAM User with S3 Access

### Via AWS Console:
1. Go to https://console.aws.amazon.com/iam/
2. Click **Users** → **Create user**
3. **User name**: `koolclips-s3-uploader`
4. Click **Next**
5. **Permissions**: Click "Attach policies directly"
6. Search and select: **AmazonS3FullAccess**
7. Click **Next** → **Create user**
8. Click on the user → **Security credentials** tab
9. Click **Create access key**
10. Choose: **Application running outside AWS**
11. **Copy the Access Key ID and Secret Access Key**

### Via AWS CLI:
```bash
# Create IAM user
aws iam create-user --user-name koolclips-s3-uploader

# Attach S3 full access policy
aws iam attach-user-policy \
    --user-name koolclips-s3-uploader \
    --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

# Create access key
aws iam create-access-key --user-name koolclips-s3-uploader
```

## Step 5: Update Heroku Configuration

```bash
# Remove CloudCube add-on (if installed)
heroku addons:destroy cloudcube -a koolclips --confirm koolclips

# Remove old CloudCube env vars
heroku config:unset CLOUDCUBE_URL CLOUDCUBE_ACCESS_KEY_ID CLOUDCUBE_SECRET_ACCESS_KEY -a koolclips

# Set new AWS S3 credentials
heroku config:set AWS_ACCESS_KEY_ID="YOUR_ACCESS_KEY_ID" -a koolclips
heroku config:set AWS_SECRET_ACCESS_KEY="YOUR_SECRET_ACCESS_KEY" -a koolclips

# Set bucket configuration
heroku config:set AWS_STORAGE_BUCKET_NAME="koolclips-media" -a koolclips
heroku config:set AWS_S3_REGION_NAME="us-east-1" -a koolclips

# Optional: Set CloudFront CDN domain (if you set one up)
# heroku config:set AWS_CLOUDFRONT_DOMAIN="d123456abcdef.cloudfront.net" -a koolclips
```

## Step 6: Deploy Updated Code

```bash
# Commit all changes
git add -A
git commit -m "Migrate from CloudCube to direct AWS S3"

# Push to Heroku
git push heroku master

# Restart app
heroku restart -a koolclips
```

## Step 7: Test the Upload

1. Go to https://www.koolclips.ai/test/stage1/
2. Select a video file (start with something small, like 50MB)
3. Set part size to 10MB
4. Click "Start Upload"
5. You should see:
   - ✅ Upload progress with speed/ETA
   - ✅ Parts uploading successfully  
   - ✅ Public URL displayed after completion
   - ✅ NO CORS errors in browser console

## Optional: Enable S3 Transfer Acceleration

For even faster uploads from distant locations:

```bash
# Enable on bucket
aws s3api put-bucket-accelerate-configuration \
    --bucket koolclips-media \
    --accelerate-configuration Status=Enabled

# Update Heroku config
heroku config:set AWS_S3_USE_ACCELERATE=true -a koolclips
```

## Optional: Set Up CloudFront CDN

For faster downloads worldwide:

1. Go to https://console.aws.cloudfront.com/
2. Create a distribution
3. **Origin domain**: Select your S3 bucket
4. **Origin access**: Public
5. **Viewer protocol policy**: Redirect HTTP to HTTPS
6. Create distribution
7. Copy the distribution domain (e.g., `d123456abcdef.cloudfront.net`)
8. Update Heroku:
```bash
heroku config:set AWS_CLOUDFRONT_DOMAIN="d123456abcdef.cloudfront.net" -a koolclips
```

## Troubleshooting

### CORS Errors
- **Problem**: Browser shows CORS policy error
- **Solution**: Verify CORS configuration on S3 bucket includes your domain
- **Test**: `aws s3api get-bucket-cors --bucket koolclips-media`

### 403 Forbidden
- **Problem**: Can't read uploaded files
- **Solution**: Check bucket policy allows public read (`s3:GetObject`)

### Upload Timeout
- **Problem**: Large chunks timeout on Heroku
- **Solution**: Use smaller chunk sizes (10MB default in test page)

### Invalid Credentials
- **Problem**: Upload fails immediately
- **Solution**: Verify `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are set correctly

## Key Benefits of Direct S3

✅ **CORS Support** - Browser uploads work without proxy
✅ **Faster Uploads** - Direct to S3, no Heroku middleman
✅ **Cheaper** - No CloudCube add-on costs ($7-39/month)
✅ **More Control** - Full access to configure S3 bucket
✅ **Transfer Acceleration** - Optional faster uploads
✅ **CloudFront CDN** - Optional faster downloads

## Migration Checklist

- [ ] AWS S3 bucket created
- [ ] CORS configured on bucket
- [ ] Bucket policy set for public read
- [ ] IAM user created with S3 access
- [ ] Access keys generated
- [ ] Heroku config updated
- [ ] CloudCube add-on removed
- [ ] Code deployed to Heroku
- [ ] Test upload works
- [ ] No CORS errors in browser
- [ ] Files are publicly accessible

## Support

If you encounter issues:
1. Check Heroku logs: `heroku logs --tail -a koolclips`
2. Check browser console for errors
3. Verify S3 bucket configuration
4. Test with small files first (< 100MB)
