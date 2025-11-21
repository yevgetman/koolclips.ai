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
    
    def __init__(self):
        """Initialize S3 client with credentials from settings"""
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )
        self.input_bucket = settings.AWS_STORAGE_BUCKET_NAME
        self.output_bucket = settings.AWS_S3_BUCKET_OUTPUT
        self.cloudfront_input = settings.AWS_CLOUDFRONT_DOMAIN_INPUT
        self.cloudfront_output = settings.AWS_CLOUDFRONT_DOMAIN_OUTPUT
    
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
        Generate a presigned URL for temporary access
        
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
    
    @staticmethod
    def is_s3_configured():
        """
        Check if S3 is properly configured
        
        Returns:
            bool: True if AWS credentials are set
        """
        return bool(settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY)
