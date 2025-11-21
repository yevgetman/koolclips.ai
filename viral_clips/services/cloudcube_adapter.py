"""
Cloudcube Adapter for Heroku Add-on Integration

This adapter makes our S3Service work seamlessly with Cloudcube,
which requires a cube prefix for all S3 keys.
"""

from django.conf import settings
import re


def is_cloudcube_enabled():
    """Check if Cloudcube is configured"""
    cloudcube_url = getattr(settings, 'CLOUDCUBE_URL', '')
    return bool(cloudcube_url)


def get_cube_name():
    """
    Extract cube name from CLOUDCUBE_URL
    
    CLOUDCUBE_URL format: https://cloud-cube.s3.amazonaws.com/cube-name
    
    Returns:
        str: Cube name or empty string if not using Cloudcube
    """
    cloudcube_url = getattr(settings, 'CLOUDCUBE_URL', '')
    if not cloudcube_url:
        return ''
    
    # Extract cube name from URL
    # Format: https://BUCKET.s3.amazonaws.com/CUBE_NAME
    match = re.search(r's3\.amazonaws\.com/([^/]+)', cloudcube_url)
    if match:
        return match.group(1)
    
    return ''


def get_s3_key(path, public=True):
    """
    Convert a path to Cloudcube S3 key format
    
    Cloudcube requires:
    - All keys prefixed with cube name
    - Public files must be in /public/ folder
    
    Args:
        path: Relative path like "uploads/video.mp4"
        public: If True, puts file in public folder for public access
    
    Returns:
        Full S3 key with cube prefix
        
    Examples:
        >>> get_s3_key("uploads/video.mp4", public=True)
        "abc123/public/uploads/video.mp4"
        
        >>> get_s3_key("private/data.json", public=False)
        "abc123/private/data.json"
    """
    if not is_cloudcube_enabled():
        # Not using Cloudcube, return path as-is
        return path
    
    cube = get_cube_name()
    if not cube:
        return path
    
    # Remove leading slash if present
    path = path.lstrip('/')
    
    if public:
        # Public files: cube/public/path
        return f"{cube}/public/{path}"
    else:
        # Private files: cube/path
        return f"{cube}/{path}"


def strip_cube_prefix(s3_key):
    """
    Remove cube prefix from S3 key to get original path
    
    Args:
        s3_key: Full S3 key with cube prefix
    
    Returns:
        Original path without cube prefix
        
    Example:
        >>> strip_cube_prefix("abc123/public/uploads/video.mp4")
        "uploads/video.mp4"
    """
    if not is_cloudcube_enabled():
        return s3_key
    
    cube = get_cube_name()
    if not cube:
        return s3_key
    
    # Remove cube prefix
    if s3_key.startswith(f"{cube}/public/"):
        return s3_key[len(f"{cube}/public/"):]
    elif s3_key.startswith(f"{cube}/"):
        return s3_key[len(f"{cube}/"):]
    
    return s3_key


def get_public_url(s3_key):
    """
    Get public URL for a file in Cloudcube
    
    Args:
        s3_key: Full S3 key (with cube prefix)
    
    Returns:
        Public HTTPS URL
        
    Example:
        >>> get_public_url("abc123/public/uploads/video.mp4")
        "https://cloud-cube.s3.us-east-1.amazonaws.com/abc123/public/uploads/video.mp4"
    """
    bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'cloud-cube')
    region = getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
    
    return f"https://{bucket}.s3.{region}.amazonaws.com/{s3_key}"


def is_public_key(s3_key):
    """
    Check if an S3 key is for a public file
    
    Args:
        s3_key: S3 key to check
    
    Returns:
        bool: True if key contains /public/ folder
    """
    return '/public/' in s3_key


def get_bucket_name():
    """
    Get the S3 bucket name from Cloudcube URL
    
    Returns:
        str: Bucket name (e.g., 'cloud-cube', 'cloud-cube-eu')
    """
    cloudcube_url = getattr(settings, 'CLOUDCUBE_URL', '')
    if not cloudcube_url:
        return getattr(settings, 'AWS_STORAGE_BUCKET_NAME', '')
    
    # Extract bucket name from URL
    # Format: https://BUCKET.s3.amazonaws.com/CUBE_NAME
    match = re.search(r'https://([^.]+)\.s3', cloudcube_url)
    if match:
        return match.group(1)
    
    return 'cloud-cube'  # Default bucket name


def get_region():
    """
    Get the AWS region from Cloudcube bucket
    
    Returns:
        str: AWS region (e.g., 'us-east-1', 'eu-west-1')
    """
    cloudcube_url = getattr(settings, 'CLOUDCUBE_URL', '')
    
    if not cloudcube_url:
        return getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
    
    # Determine region from bucket name
    bucket = get_bucket_name()
    
    # Cloudcube bucket naming convention
    if 'eu' in bucket:
        return 'eu-west-1'
    elif 'ap' in bucket:
        return 'ap-southeast-1'
    else:
        return 'us-east-1'  # Default region
