"""
S3 Service for managing file uploads and downloads with AWS S3

Supports both standalone AWS S3 and Cloudcube Heroku add-on.
Cloudcube automatically detected and configured.
"""

import boto3
import os
import tempfile
from django.conf import settings
from botocore.exceptions import ClientError
import logging

try:
    from .cloudcube_adapter import (
        is_cloudcube_enabled,
        get_s3_key,
        get_public_url,
        strip_cube_prefix
    )
except ImportError:
    # Fallback if cloudcube_adapter not available
    def is_cloudcube_enabled():
        return False
    
    def get_s3_key(path, public=True):
        return path
    
    def get_public_url(s3_key):
        return None
    
    def strip_cube_prefix(s3_key):
        return s3_key

logger = logging.getLogger(__name__)


class S3Service:
    """Service for managing S3 uploads and downloads"""
    
    def __init__(self, use_accelerate=True):
        """
        Initialize S3Service with AWS credentials from environment
        
        Args:
            use_accelerate: If True, use S3 Transfer Acceleration for faster uploads
        """
        config = None
        if use_accelerate:
            # Enable S3 Transfer Acceleration for faster uploads
            from botocore.config import Config
            config = Config(
                s3={'use_accelerate_endpoint': True}
            )
        
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
            config=config
        )
        self.input_bucket = settings.AWS_STORAGE_BUCKET_NAME
        self.output_bucket = settings.AWS_STORAGE_BUCKET_NAME
        self.use_accelerate = use_accelerate
        
        if use_accelerate:
            logger.info("S3 Transfer Acceleration is ENABLED for faster uploads")
        self.cloudfront_input = settings.AWS_CLOUDFRONT_DOMAIN_INPUT
        self.cloudfront_output = settings.AWS_CLOUDFRONT_DOMAIN_OUTPUT
    
    def upload_file_content(self, content_bytes, s3_key, bucket=None, content_type=None, public=True):
        """
        Upload byte content directly to S3 (with automatic Cloudcube support)
        
        Args:
            content_bytes: Bytes content to upload
            s3_key: S3 key (path) for the file - will be automatically prefixed for Cloudcube
            bucket: S3 bucket name (defaults to input bucket)
            content_type: MIME type (optional)
            public: If True, makes file publicly accessible (important for Cloudcube)
        
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
        Upload a file to S3 (with automatic Cloudcube support)
        
        Args:
            file_obj: File object or file path to upload
            s3_key: S3 key (path) for the file - will be automatically prefixed for Cloudcube
            bucket: S3 bucket name (defaults to input bucket)
            content_type: MIME type (optional)
            public: If True, makes file publicly accessible (important for Cloudcube)
        
        Returns:
            dict: {
                's3_url': Direct S3 URL,
                'cloudfront_url': CloudFront CDN URL or public URL (Cloudcube),
                's3_key': Full S3 object key (with cube prefix if Cloudcube),
                'bucket': Bucket name,
                'public_url': Public URL if using Cloudcube
            }
        """
        bucket = bucket or self.input_bucket
        
        # Convert to Cloudcube format if needed (adds cube/public/ prefix)
        full_s3_key = get_s3_key(s3_key, public=public)
        
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type
        
        try:
            if isinstance(file_obj, str):
                # File path provided
                self.s3_client.upload_file(file_obj, bucket, full_s3_key, ExtraArgs=extra_args or None)
            else:
                # File object provided
                self.s3_client.upload_fileobj(file_obj, bucket, full_s3_key, ExtraArgs=extra_args or None)
            
            # Generate S3 URL
            s3_url = f"https://{bucket}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{full_s3_key}"
            
            # For Cloudcube, generate public URL
            if is_cloudcube_enabled() and public:
                public_url = get_public_url(full_s3_key)
                logger.info(f"Uploaded to Cloudcube: {public_url}")
                
                return {
                    's3_url': s3_url,
                    'cloudfront_url': public_url,  # Use public URL for Cloudcube
                    'public_url': public_url,
                    's3_key': full_s3_key,
                    'bucket': bucket
                }
            
            # For standalone AWS, use CloudFront if configured
            cloudfront_domain = (
                self.cloudfront_output 
                if bucket == self.output_bucket 
                else self.cloudfront_input
            )
            cloudfront_url = f"https://{cloudfront_domain}/{full_s3_key}" if cloudfront_domain else s3_url
            
            logger.info(f"Uploaded to S3: {s3_url}")
            
            return {
                's3_url': s3_url,
                'cloudfront_url': cloudfront_url,
                's3_key': full_s3_key,
                'bucket': bucket
            }
            
        except ClientError as e:
            logger.error(f"Failed to upload to S3: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error uploading to S3: {str(e)}")
            raise
    
    def download_file(self, s3_key, local_path=None, bucket=None, normalize_key=False):
        """
        Download a file from S3 (with automatic Cloudcube support)
        
        Args:
            s3_key: S3 key of the file (should already include cube prefix if from storage backend)
            local_path: Local path to save (creates temp file if None)
            bucket: S3 bucket name (defaults to input bucket)
            normalize_key: If True, add Cloudcube prefix (only use if s3_key doesn't have it)
        
        Returns:
            str: Path to downloaded file
        """
        bucket = bucket or self.input_bucket
        
        # Only add cube prefix if explicitly requested (for backwards compatibility)
        if normalize_key:
            s3_key = get_s3_key(s3_key, public=True)
        
        if local_path is None:
            # Create temp file with appropriate extension
            # Use original path (without cube prefix) for extension
            original_path = strip_cube_prefix(s3_key)
            suffix = os.path.splitext(original_path)[1]
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
            s3_key: S3 key (path) for the file - will be automatically prefixed for Cloudcube
            bucket: S3 bucket name (defaults to input bucket)
            content_type: MIME type (optional)
            public: If True, makes file publicly accessible
        
        Returns:
            dict: {
                'upload_id': Upload ID for this multipart upload,
                's3_key': Full S3 key (with cube prefix),
                'bucket': Bucket name
            }
        """
        bucket = bucket or self.input_bucket
        
        # Convert to Cloudcube format if needed
        full_s3_key = get_s3_key(s3_key, public=public)
        
        try:
            params = {
                'Bucket': bucket,
                'Key': full_s3_key
            }
            
            if content_type:
                params['ContentType'] = content_type
            
            # Initiate multipart upload
            response = self.s3_client.create_multipart_upload(**params)
            
            upload_id = response['UploadId']
            logger.info(f"Initiated multipart upload for: {full_s3_key}, upload_id: {upload_id}")
            
            return {
                'upload_id': upload_id,
                's3_key': full_s3_key,
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
            s3_key: S3 key (path) for the file - will be automatically prefixed for Cloudcube
            bucket: S3 bucket name (defaults to input bucket)
            content_type: MIME type (optional)
            expiration: URL expiration time in seconds (default 3600 = 1 hour)
            public: If True, makes file publicly accessible (important for Cloudcube)
        
        Returns:
            dict: {
                'url': Presigned POST URL,
                'fields': Form fields to include in the POST request,
                's3_key': Full S3 key (with cube prefix if using Cloudcube),
                'bucket': Bucket name
            }
        """
        bucket = bucket or self.input_bucket
        
        # Convert to Cloudcube format if needed (adds cube/public/ prefix)
        full_s3_key = get_s3_key(s3_key, public=public)
        
        # Prepare conditions for presigned POST
        conditions = [
            {'bucket': bucket},
            {'key': full_s3_key}
        ]
        
        fields = {'key': full_s3_key}
        
        if content_type:
            conditions.append({'Content-Type': content_type})
            fields['Content-Type'] = content_type
        
        try:
            # Generate presigned POST
            response = self.s3_client.generate_presigned_post(
                Bucket=bucket,
                Key=full_s3_key,
                Fields=fields,
                Conditions=conditions,
                ExpiresIn=expiration
            )
            
            response['s3_key'] = full_s3_key
            response['bucket'] = bucket
            
            logger.info(f"Generated presigned upload URL for: {full_s3_key}")
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
        Clean up all S3 files associated with a job
        Should be called after Stage 4 completes successfully
        
        Args:
            job: VideoJob instance
        """
        files_to_delete = []
        
        # Collect all S3 keys to delete
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
                logger.info(f"Cleaned up S3 file for job {job.id}: {s3_key}")
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
        
        # For Cloudcube, use the public URL
        if is_cloudcube_enabled():
            return get_public_url(s3_key)
        
        # For standalone AWS with CloudFront
        if self.cloudfront_input:
            return f"https://{self.cloudfront_input}/{s3_key}"
        
        # Direct S3 URL
        return f"https://{bucket}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{s3_key}"
    
    @staticmethod
    def is_s3_configured():
        """
        Check if S3 is properly configured
        
        Returns:
            bool: True if AWS credentials are set
        """
        return bool(settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY)
