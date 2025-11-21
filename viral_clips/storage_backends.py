"""
Custom storage backends for S3 with Cloudcube support
"""

from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class CloudcubeStorage(S3Boto3Storage):
    """
    S3 storage backend that handles Cloudcube cube prefixes
    
    Cloudcube requires all files to be prefixed with the cube name.
    For public files, they must be in the cube/public/ folder.
    
    Example:
        File: uploads/video.mp4
        Actual S3 key: mkwcrxocz0mi/public/uploads/video.mp4
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Get cube name from CLOUDCUBE_URL
        cloudcube_url = getattr(settings, 'CLOUDCUBE_URL', '')
        if cloudcube_url:
            # Extract cube name from URL
            # Format: https://cloud-cube.s3.amazonaws.com/CUBE_NAME
            import re
            match = re.search(r's3\.amazonaws\.com/([^/]+)', cloudcube_url)
            if match:
                self.cube_name = match.group(1)
            else:
                self.cube_name = ''
        else:
            self.cube_name = ''
    
    def _normalize_name(self, name):
        """
        Add Cloudcube cube prefix and public folder to file paths
        
        Args:
            name: Original file path (e.g., 'uploads/video.mp4')
        
        Returns:
            Full S3 key with cube prefix (e.g., 'mkwcrxocz0mi/public/uploads/video.mp4')
        """
        # Remove leading slashes
        name = name.lstrip('/')
        
        if self.cube_name:
            # Add cube/public/ prefix for Cloudcube
            return f"{self.cube_name}/public/{name}"
        else:
            # No Cloudcube, return name as-is
            return super()._normalize_name(name)
    
    def url(self, name):
        """
        Generate public URL for a file
        
        For Cloudcube, this returns the direct S3 URL since files in
        /public/ folder are publicly accessible.
        """
        # Get the full S3 key with cube prefix
        name = self._normalize_name(name)
        
        # For Cloudcube, generate direct S3 URL
        if self.cube_name:
            bucket = self.bucket_name
            region = getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
            return f"https://{bucket}.s3.{region}.amazonaws.com/{name}"
        else:
            # Use parent method for non-Cloudcube
            return super().url(name)
