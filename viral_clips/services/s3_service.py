"""
S3Service for managing uploads, downloads, and presigned URLs

Direct AWS S3 implementation with support for:
- Single and multipart uploads with presigned URLs
- CloudFront CDN integration
- S3 Transfer Acceleration for faster uploads
"""

import boto3
import os
import tempfile
from django.conf import settings
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)


class S3Service:
    """Service for managing S3 uploads and downloads"""
    
    def __init__(self, use_accelerate=False):
        """
        Initialize S3Service with AWS credentials from environment
        
        Args:
            use_accelerate: If True, use S3 Transfer Acceleration for faster uploads
        """
        from botocore.config import Config
        
        # Configure boto3 to use region-specific endpoints for presigned URLs
        config_params = {
            'signature_version': 's3v4',
            's3': {
                'addressing_style': 'virtual'
            }
        }
        
        if use_accelerate:
            # Enable S3 Transfer Acceleration for faster uploads
            config_params['s3']['use_accelerate_endpoint'] = True
        
        config = Config(**config_params)
        
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
            config=config
        )
        self.input_bucket = settings.AWS_STORAGE_BUCKET_NAME
        self.output_bucket = settings.AWS_STORAGE_BUCKET_NAME
        self.region = settings.AWS_S3_REGION_NAME
        self.use_accelerate = use_accelerate
        
        if use_accelerate:
            logger.info("S3 Transfer Acceleration is ENABLED for faster uploads")
        self.cloudfront_domain = settings.AWS_CLOUDFRONT_DOMAIN
    
    def upload_file_content(self, content_bytes, s3_key, bucket=None, content_type=None, public=True):
        """
        Upload byte content directly to S3
        
        Args:
            content_bytes: Bytes content to upload
            s3_key: S3 key (path) for the file
            bucket: S3 bucket name (defaults to input bucket)
            content_type: MIME type (optional)
            public: If True, makes file publicly accessible
        
        Returns:
            str: Public URL of uploaded file
        """
        import io
        
        # Create a file-like object from bytes
        file_obj = io.BytesIO(content_bytes)
        
        # Upload using upload_file method
        result = self.upload_file(file_obj, s3_key, bucket, content_type, public)
        
        # Return the public URL
        return result.get('public_url') or result.get('cloudfront_url') or result.get('s3_url')
    
    def upload_file(self, file_obj, s3_key, bucket=None, content_type=None, public=True):
        """
        Upload a file to S3
        
        Args:
            file_obj: File object or file path to upload
            s3_key: S3 key (path) for the file
            bucket: S3 bucket name (defaults to input bucket)
            content_type: MIME type (optional)
            public: If True, makes file publicly accessible via bucket policy
        
        Returns:
            dict: {
                's3_url': Direct S3 URL,
                'cloudfront_url': CloudFront CDN URL (if configured),
                'public_url': Public URL (CloudFront or S3),
                's3_key': S3 object key,
                'bucket': Bucket name
            }
        """
        bucket = bucket or self.input_bucket
        
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type
        # Note: Public access is controlled by bucket policy, not ACLs
        
        try:
            if isinstance(file_obj, str):
                # File path provided
                self.s3_client.upload_file(file_obj, bucket, s3_key, ExtraArgs=extra_args or None)
            else:
                # File object provided
                self.s3_client.upload_fileobj(file_obj, bucket, s3_key, ExtraArgs=extra_args or None)
            
            # Generate S3 URL
            s3_url = f"https://{bucket}.s3.{self.region}.amazonaws.com/{s3_key}"
            
            # Use CloudFront if configured
            cloudfront_url = f"https://{self.cloudfront_domain}/{s3_key}" if self.cloudfront_domain else s3_url
            public_url = cloudfront_url
            
            logger.info(f"Uploaded to S3: {s3_url}")
            
            return {
                's3_url': s3_url,
                'cloudfront_url': cloudfront_url,
                'public_url': public_url,
                's3_key': s3_key,
                'bucket': bucket
            }
            
        except ClientError as e:
            logger.error(f"Failed to upload to S3: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error uploading to S3: {str(e)}")
            raise
    
    def download_file(self, s3_key, local_path=None, bucket=None):
        """
        Download a file from S3
        
        Args:
            s3_key: S3 key of the file
            local_path: Local path to save (creates temp file if None)
            bucket: S3 bucket name (defaults to input bucket)
        
        Returns:
            str: Path to downloaded file
        """
        bucket = bucket or self.input_bucket
        
        if local_path is None:
            # Create temp file with appropriate extension
            suffix = os.path.splitext(s3_key)[1]
            fd, local_path = tempfile.mkstemp(suffix=suffix)
            os.close(fd)
        
        try:
            self.s3_client.download_file(bucket, s3_key, local_path)
            logger.info(f"Downloaded from S3: {s3_key} -> {local_path}")
            return local_path
        except ClientError as e:
            logger.error(f"Failed to download from S3: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error downloading from S3: {str(e)}")
            raise
    
    def download_from_url(self, url, local_path=None):
        """
        Download file from S3 or CloudFront URL
        
        Args:
            url: S3 or CloudFront URL
            local_path: Local path to save (creates temp file if None)
        
        Returns:
            str: Path to downloaded file
        """
        # Parse bucket and key from URL
        # Support formats:
        # - https://bucket.s3.region.amazonaws.com/key
        # - https://cloudfront-domain.cloudfront.net/key
        
        url = url.replace('https://', '').replace('http://', '')
        parts = url.split('/')
        
        # Determine bucket and key
        if 's3.' in parts[0]:
            # S3 URL format
            bucket = parts[0].split('.')[0]
            s3_key = '/'.join(parts[1:])
        elif 'cloudfront.net' in parts[0] or self.cloudfront_input in parts[0] or self.cloudfront_output in parts[0]:
            # CloudFront URL - need to determine bucket
            s3_key = '/'.join(parts[1:])
            # Try to determine bucket from key structure or use input bucket as default
            bucket = self.input_bucket
        else:
            # Unknown format, try input bucket
            s3_key = '/'.join(parts[1:])
            bucket = self.input_bucket
        
        return self.download_file(s3_key, local_path, bucket)
    
    def delete_file(self, s3_key, bucket=None):
        """
        Delete a file from S3
        
        Args:
            s3_key: S3 key of the file
            bucket: S3 bucket name (defaults to input bucket)
        """
        bucket = bucket or self.input_bucket
        
        try:
            self.s3_client.delete_object(Bucket=bucket, Key=s3_key)
            logger.info(f"Deleted from S3: {bucket}/{s3_key}")
        except ClientError as e:
            logger.error(f"Failed to delete from S3: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error deleting from S3: {str(e)}")
            raise
    
    def generate_presigned_url(self, s3_key, bucket=None, expiration=3600):
        """
        Generate a presigned URL for temporary access (download)
        
        Args:
            s3_key: S3 key of the file
            bucket: S3 bucket name (defaults to input bucket)
            expiration: URL expiration time in seconds (default 3600 = 1 hour)
        
        Returns:
            str: Presigned URL
        """
        bucket = bucket or self.input_bucket
        
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': s3_key},
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error generating presigned URL: {str(e)}")
            raise
    
    def initiate_multipart_upload(self, s3_key, bucket=None, content_type=None, public=True):
        """
        Initiate a multipart upload to S3
        
        Args:
            s3_key: S3 key (path) for the file
            bucket: S3 bucket name (defaults to input bucket)
            content_type: MIME type (optional)
            public: If True, makes file publicly accessible
        
        Returns:
            dict: {
                'upload_id': Upload ID for this multipart upload,
                's3_key': S3 key,
                'bucket': Bucket name
            }
        """
        bucket = bucket or self.input_bucket
        
        try:
            params = {
                'Bucket': bucket,
                'Key': s3_key
            }
            
            if content_type:
                params['ContentType'] = content_type
            # Note: Public access is controlled by bucket policy, not ACLs
            
            # Initiate multipart upload
            response = self.s3_client.create_multipart_upload(**params)
            
            upload_id = response['UploadId']
            logger.info(f"Initiated multipart upload for: {s3_key}, upload_id: {upload_id}")
            
            return {
                'upload_id': upload_id,
                's3_key': s3_key,
                'bucket': bucket
            }
            
        except ClientError as e:
            logger.error(f"Failed to initiate multipart upload: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error initiating multipart upload: {str(e)}")
            raise
    
    def generate_multipart_presigned_urls(self, s3_key, upload_id, num_parts, bucket=None, expiration=3600):
        """
        Generate presigned URLs for each part of a multipart upload
        
        Args:
            s3_key: Full S3 key (with cube prefix)
            upload_id: Upload ID from initiate_multipart_upload
            num_parts: Number of parts to generate URLs for
            bucket: S3 bucket name (defaults to input bucket)
            expiration: URL expiration in seconds (default 3600 = 1 hour)
        
        Returns:
            list: List of dicts with {'part_number': int, 'url': str}
        """
        bucket = bucket or self.input_bucket
        
        try:
            presigned_urls = []
            
            for part_number in range(1, num_parts + 1):
                url = self.s3_client.generate_presigned_url(
                    'upload_part',
                    Params={
                        'Bucket': bucket,
                        'Key': s3_key,
                        'UploadId': upload_id,
                        'PartNumber': part_number
                    },
                    ExpiresIn=expiration
                )
                
                presigned_urls.append({
                    'part_number': part_number,
                    'url': url
                })
            
            logger.info(f"Generated {num_parts} presigned URLs for multipart upload: {upload_id}")
            return presigned_urls
            
        except ClientError as e:
            logger.error(f"Failed to generate multipart presigned URLs: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error generating multipart presigned URLs: {str(e)}")
            raise
    
    def complete_multipart_upload(self, s3_key, upload_id, parts, bucket=None):
        """
        Complete a multipart upload
        
        Args:
            s3_key: Full S3 key (with cube prefix)
            upload_id: Upload ID from initiate_multipart_upload
            parts: List of dicts with {'PartNumber': int, 'ETag': str}
            bucket: S3 bucket name (defaults to input bucket)
        
        Returns:
            dict: Response from S3 with Location, Bucket, Key, ETag
        """
        bucket = bucket or self.input_bucket
        
        try:
            response = self.s3_client.complete_multipart_upload(
                Bucket=bucket,
                Key=s3_key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )
            
            logger.info(f"Completed multipart upload: {s3_key}, upload_id: {upload_id}")
            return response
            
        except ClientError as e:
            logger.error(f"Failed to complete multipart upload: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error completing multipart upload: {str(e)}")
            raise
    
    def abort_multipart_upload(self, s3_key, upload_id, bucket=None):
        """
        Abort a multipart upload and clean up partial uploads
        
        Args:
            s3_key: Full S3 key (with cube prefix)
            upload_id: Upload ID from initiate_multipart_upload
            bucket: S3 bucket name (defaults to input bucket)
        """
        bucket = bucket or self.input_bucket
        
        try:
            self.s3_client.abort_multipart_upload(
                Bucket=bucket,
                Key=s3_key,
                UploadId=upload_id
            )
            
            logger.info(f"Aborted multipart upload: {s3_key}, upload_id: {upload_id}")
            
        except ClientError as e:
            logger.error(f"Failed to abort multipart upload: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error aborting multipart upload: {str(e)}")
            raise
    
    def generate_presigned_upload_url(self, s3_key, bucket=None, content_type=None, expiration=3600, public=True):
        """
        Generate a presigned URL for uploading files directly to S3
        This allows clients to upload large files without going through the server
        
        Args:
            s3_key: S3 key (path) for the file
            bucket: S3 bucket name (defaults to input bucket)
            content_type: MIME type (optional)
            expiration: URL expiration time in seconds (default 3600 = 1 hour)
            public: If True, makes file publicly accessible
        
        Returns:
            dict: {
                'url': Presigned POST URL,
                'fields': Form fields to include in the POST request,
                's3_key': S3 key,
                'bucket': Bucket name
            }
        """
        bucket = bucket or self.input_bucket
        
        # Prepare conditions for presigned POST
        conditions = [
            {'bucket': bucket},
            {'key': s3_key}
        ]
        
        fields = {'key': s3_key}
        
        if content_type:
            conditions.append({'Content-Type': content_type})
            fields['Content-Type'] = content_type
        # Note: Public access is controlled by bucket policy, not ACLs
        
        try:
            # Generate presigned POST
            response = self.s3_client.generate_presigned_post(
                Bucket=bucket,
                Key=s3_key,
                Fields=fields,
                Conditions=conditions,
                ExpiresIn=expiration
            )
            
            response['s3_key'] = s3_key
            response['bucket'] = bucket
            
            logger.info(f"Generated presigned upload URL for: {s3_key}")
            return response
            
        except ClientError as e:
            logger.error(f"Failed to generate presigned upload URL: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error generating presigned upload URL: {str(e)}")
            raise
    
    def file_exists(self, s3_key, bucket=None):
        """
        Check if a file exists in S3
        
        Args:
            s3_key: S3 key of the file
            bucket: S3 bucket name (defaults to input bucket)
        
        Returns:
            bool: True if file exists, False otherwise
        """
        bucket = bucket or self.input_bucket
        
        try:
            self.s3_client.head_object(Bucket=bucket, Key=s3_key)
            return True
        except ClientError:
            return False
    
    def get_s3_key_from_url(self, url):
        """
        Extract S3 key from S3 or CloudFront URL
        
        Args:
            url: S3 or CloudFront URL
        
        Returns:
            str: S3 key
        """
        url = url.replace('https://', '').replace('http://', '')
        parts = url.split('/')
        # Key is everything after the domain
        return '/'.join(parts[1:])
    
    def cleanup_job_files(self, job):
        """
        Clean up all temporary S3 files associated with a job after Stage 4 completes
        Deletes original media file and extracted audio, but preserves final clips
        
        Args:
            job: VideoJob instance
        """
        files_to_delete = []
        
        # Collect all S3 keys to delete (temporary files only)
        if job.media_file and job.media_file.name:
            # Get the actual S3 key (with cube prefix if needed)
            if hasattr(job.media_file, 'storage'):
                s3_key = job.media_file.storage._normalize_name(job.media_file.name)
            else:
                s3_key = job.media_file.name
            files_to_delete.append(s3_key)
        
        if job.extracted_audio_path:
            # Extracted audio file
            if hasattr(job.media_file, 'storage'):
                s3_key = job.media_file.storage._normalize_name(job.extracted_audio_path)
            else:
                s3_key = job.extracted_audio_path
            files_to_delete.append(s3_key)
        
        # Delete each file
        for s3_key in files_to_delete:
            try:
                self.delete_file(s3_key)
                logger.info(f"Cleaned up temporary S3 file for job {job.id}: {s3_key}")
            except Exception as e:
                logger.error(f"Failed to delete S3 file {s3_key} for job {job.id}: {str(e)}")
    
    def get_public_url_from_key(self, s3_key, bucket=None):
        """
        Get the public URL for an S3 key
        
        Args:
            s3_key: S3 key of the file
            bucket: S3 bucket name (defaults to input bucket)
        
        Returns:
            str: Public URL
        """
        bucket = bucket or self.input_bucket
        
        # Use CloudFront if configured
        if self.cloudfront_domain:
            return f"https://{self.cloudfront_domain}/{s3_key}"
        
        # Direct S3 URL
        return f"https://{bucket}.s3.{self.region}.amazonaws.com/{s3_key}"
    
    def list_all_files(self, bucket=None, prefix='', max_keys=1000):
        """
        List all files in S3 bucket with optional prefix filter
        
        Args:
            bucket: S3 bucket name (defaults to input bucket)
            prefix: Prefix to filter files (e.g., 'uploads/' or cube prefix)
            max_keys: Maximum number of keys to return (default 1000)
        
        Returns:
            list: List of dicts with file metadata {
                'key': S3 key,
                'size': File size in bytes,
                'last_modified': Last modified datetime,
                'storage_class': Storage class
            }
        """
        bucket = bucket or self.input_bucket
        
        try:
            files = []
            paginator = self.s3_client.get_paginator('list_objects_v2')
            
            page_iterator = paginator.paginate(
                Bucket=bucket,
                Prefix=prefix,
                PaginationConfig={'MaxItems': max_keys}
            )
            
            for page in page_iterator:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        files.append({
                            'key': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'],
                            'storage_class': obj.get('StorageClass', 'STANDARD')
                        })
            
            logger.info(f"Listed {len(files)} files from S3 bucket {bucket} with prefix '{prefix}'")
            return files
            
        except ClientError as e:
            logger.error(f"Failed to list files from S3: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error listing files from S3: {str(e)}")
            raise
    
    def bulk_cleanup_cloudcube(self, retention_days=5, dry_run=False):
        """
        Bulk cleanup of Cloudcube files
        Deletes all files except:
        - Final clips created within retention_days (default: 5 days)
        
        This should be run periodically (e.g., daily via CRON or manual trigger)
        to clean up temporary files and old clips.
        
        Args:
            retention_days: Number of days to retain final clips (default: 5)
            dry_run: If True, only simulate deletion without actually deleting files
        
        Returns:
            dict: {
                'deleted_count': Number of files deleted,
                'deleted_size': Total size of deleted files in bytes,
                'retained_count': Number of files retained,
                'deleted_files': List of deleted file keys (if dry_run=True, this shows what would be deleted)
            }
        """
        from datetime import timedelta
        from django.utils import timezone as django_timezone
        from viral_clips.models import ClippedVideo
        
        try:
            # Calculate cutoff date for clip retention
            cutoff_date = django_timezone.now() - timedelta(days=retention_days)
            
            # Get all recent clips that should be preserved
            recent_clips = ClippedVideo.objects.filter(
                created_at__gte=cutoff_date,
                status='completed'
            ).values_list('video_file', 'video_s3_url', 'video_cloudfront_url')
            
            # Extract S3 keys from clip URLs and file paths
            preserved_keys = set()
            for video_file, s3_url, cloudfront_url in recent_clips:
                # From video_file field
                if video_file:
                    try:
                        # Handle Django FileField - get storage key
                        from viral_clips.models import ClippedVideo
                        clip = ClippedVideo.objects.filter(video_file=video_file).first()
                        if clip and hasattr(clip.video_file, 'storage'):
                            s3_key = clip.video_file.storage._normalize_name(clip.video_file.name)
                            preserved_keys.add(s3_key)
                        elif clip and clip.video_file.name:
                            preserved_keys.add(clip.video_file.name)
                    except Exception:
                        pass
                
                # From S3 URL
                if s3_url:
                    try:
                        s3_key = self.get_s3_key_from_url(s3_url)
                        preserved_keys.add(s3_key)
                    except Exception:
                        pass
                
                # From CloudFront URL
                if cloudfront_url:
                    try:
                        s3_key = self.get_s3_key_from_url(cloudfront_url)
                        preserved_keys.add(s3_key)
                    except Exception:
                        pass
            
            logger.info(f"Found {len(preserved_keys)} clip files to preserve (created within {retention_days} days)")
            
            # List all files in S3
            all_files = self.list_all_files(prefix='', max_keys=10000)
            
            deleted_files = []
            deleted_size = 0
            retained_count = 0
            
            # Process each file
            for file_info in all_files:
                s3_key = file_info['key']
                file_size = file_info['size']
                
                # Check if this file should be preserved
                should_preserve = False
                
                # Preserve if it's a recent clip
                if s3_key in preserved_keys:
                    should_preserve = True
                    logger.debug(f"Preserving recent clip: {s3_key}")
                
                # Preserve if path contains 'clips/' and file is recent
                elif '/clips/' in s3_key or s3_key.startswith('clips/'):
                    file_modified = file_info['last_modified']
                    if file_modified >= cutoff_date:
                        should_preserve = True
                        logger.debug(f"Preserving recent clip by path: {s3_key}")
                
                if should_preserve:
                    retained_count += 1
                else:
                    # Mark for deletion
                    deleted_files.append(s3_key)
                    deleted_size += file_size
                    
                    if not dry_run:
                        try:
                            self.delete_file(s3_key)
                            logger.info(f"Deleted old file: {s3_key} ({file_size} bytes)")
                        except Exception as e:
                            logger.error(f"Failed to delete {s3_key}: {str(e)}")
            
            result = {
                'deleted_count': len(deleted_files),
                'deleted_size': deleted_size,
                'retained_count': retained_count,
                'deleted_files': deleted_files[:100],  # Limit to first 100 for response
                'total_files_scanned': len(all_files),
                'dry_run': dry_run
            }
            
            if dry_run:
                logger.info(f"DRY RUN: Would delete {len(deleted_files)} files ({deleted_size / (1024*1024):.2f} MB)")
            else:
                logger.info(f"Bulk cleanup completed: Deleted {len(deleted_files)} files ({deleted_size / (1024*1024):.2f} MB), retained {retained_count} files")
            
            return result
            
        except Exception as e:
            logger.error(f"Bulk cleanup failed: {str(e)}")
            raise
    
    def cleanup_all_clips(self, dry_run=False):
        """
        Delete all clips from Cloudcube/S3
        
        WARNING: This deletes ALL user-created clips, regardless of age.
        Use with extreme caution! This is meant for complete storage cleanup.
        
        Args:
            dry_run: If True, only simulate deletion without actually deleting files
        
        Returns:
            dict: {
                'deleted_count': Number of clips deleted,
                'deleted_size': Total size of deleted clips in bytes,
                'deleted_files': List of deleted clip keys
            }
        """
        try:
            # List all files in clips folder
            prefix = "clips/"
            
            all_clips = self.list_all_files(prefix=prefix, max_keys=10000)
            
            deleted_files = []
            deleted_size = 0
            
            # Delete each clip file
            for file_info in all_clips:
                s3_key = file_info['key']
                file_size = file_info['size']
                
                # Skip directory markers
                if s3_key.endswith('/'):
                    continue
                
                deleted_files.append(s3_key)
                deleted_size += file_size
                
                if not dry_run:
                    try:
                        self.delete_file(s3_key)
                        logger.info(f"Deleted clip: {s3_key} ({file_size} bytes)")
                    except Exception as e:
                        logger.error(f"Failed to delete clip {s3_key}: {str(e)}")
            
            result = {
                'deleted_count': len(deleted_files),
                'deleted_size': deleted_size,
                'deleted_files': deleted_files[:100],  # Limit to first 100 for response
                'dry_run': dry_run
            }
            
            if dry_run:
                logger.info(f"DRY RUN: Would delete {len(deleted_files)} clips ({deleted_size / (1024*1024):.2f} MB)")
            else:
                logger.info(f"Clips cleanup completed: Deleted {len(deleted_files)} clips ({deleted_size / (1024*1024):.2f} MB)")
            
            return result
            
        except Exception as e:
            logger.error(f"Clips cleanup failed: {str(e)}")
            raise
    
    @staticmethod
    def is_s3_configured():
        """
        Check if S3 is properly configured
        
        Returns:
            bool: True if AWS credentials are set
        """
        return bool(settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY)
