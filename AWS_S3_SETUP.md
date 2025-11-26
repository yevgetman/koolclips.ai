# AWS S3 Setup for Direct Browser Uploads

CloudCube doesn't support CORS configuration, which is required for browser uploads. You need to set up a standalone AWS S3 bucket.

## Step 1: Create an AWS S3 Bucket

1. Go to [AWS S3 Console](https://s3.console.aws.amazon.com/)
2. Click "Create bucket"
3. **Bucket name**: Choose a unique name (e.g., `koolclips-uploads`)
4. **Region**: Choose `us-east-1` (or your preferred region)
5. **Block Public Access**: UNCHECK "Block all public access" (we need public read for final clips)
6. Click "Create bucket"

## Step 2: Configure CORS on the Bucket

**IMPORTANT**: CORS configuration is NOT the same as bucket policy. Paste this in the CORS section, NOT the bucket policy section.

1. Open your bucket
2. Go to **Permissions** tab
3. Scroll down to **Cross-origin resource sharing (CORS)** section (NOT "Bucket policy")
4. Click "Edit" and paste this CORS configuration:

```json
[
    {
        "AllowedHeaders": [
            "*"
        ],
        "AllowedMethods": [
            "GET",
            "PUT",
            "POST",
            "DELETE",
            "HEAD"
        ],
        "AllowedOrigins": [
            "https://www.koolclips.ai",
            "https://koolclips.ai",
            "https://koolclips-ed69bc2e07f2.herokuapp.com",
            "http://localhost:8000",
            "http://127.0.0.1:8000"
        ],
        "ExposeHeaders": [
            "ETag",
            "x-amz-request-id"
        ],
        "MaxAgeSeconds": 3600
    }
]
```

5. Click "Save changes"

## Step 3: Configure Bucket Policy (for Public Read Access)

**IMPORTANT**: This is a separate configuration from CORS. This allows public read access to your uploaded clips.

1. In your bucket, stay on the **Permissions** tab
2. Scroll down to **Bucket policy** section
3. Click "Edit" and paste this policy (replace `your-bucket-name` with your actual bucket name):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::your-bucket-name/*"
        }
    ]
}
```

4. Replace `your-bucket-name` with your actual bucket name (e.g., `koolclips-uploads`)
5. Click "Save changes"

## Step 4: Create IAM User with S3 Access

1. Go to [IAM Console](https://console.aws.amazon.com/iam/)
2. Click "Users" → "Add users"
3. **User name**: `koolclips-uploader`
4. Click "Next"
5. **Permissions**: Click "Attach policies directly"
6. Search for and select: `AmazonS3FullAccess` (or create a custom policy)
7. Click "Next" → "Create user"
8. Click on the user → "Security credentials" tab
9. Click "Create access key"
10. Choose "Application running outside AWS"
11. **Save the Access Key ID and Secret Access Key** (you'll need these next)

## Step 5: Update Heroku Config

Run these commands to update your Heroku configuration:

```bash
# Set AWS credentials
heroku config:set AWS_ACCESS_KEY_ID="your-access-key-id" -a koolclips
heroku config:set AWS_SECRET_ACCESS_KEY="your-secret-access-key" -a koolclips

# Set bucket configuration
heroku config:set AWS_STORAGE_BUCKET_NAME="your-bucket-name" -a koolclips
heroku config:set AWS_S3_REGION_NAME="us-east-1" -a koolclips

# Disable CloudCube (optional - keeps CloudCube URL but uses AWS S3)
heroku config:unset CLOUDCUBE_URL -a koolclips
```

## Step 6: Optional - CloudFront CDN

For faster downloads, set up CloudFront:

1. Go to [CloudFront Console](https://console.aws.amazon.com/cloudfront/)
2. Create a distribution with your S3 bucket as origin
3. Add the CloudFront domain to Heroku:

```bash
heroku config:set AWS_CLOUDFRONT_DOMAIN_INPUT="d123456abcdef.cloudfront.net" -a koolclips
```

## Step 7: Restart Heroku

```bash
heroku restart -a koolclips
```

## Testing

After setup:
1. Go to https://www.koolclips.ai/test/stage1/
2. Select a video file
3. Upload should work without CORS errors!

## Alternative: Simple Single-Part Upload Test

If you want to test quickly with small files (<100MB), I can create a simpler single-part upload page that doesn't require multipart and works with CloudCube.
