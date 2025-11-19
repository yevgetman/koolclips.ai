"""Utility functions for viral_clips app"""

import mimetypes
import os


def detect_file_type(file_path):
    """
    Detect if a file is video or audio based on its MIME type
    
    Args:
        file_path: Path to the file or file name
        
    Returns:
        str: 'video', 'audio', or 'unknown'
    """
    # Initialize mimetypes
    mimetypes.init()
    
    # Get MIME type
    mime_type, _ = mimetypes.guess_type(file_path)
    
    if mime_type:
        if mime_type.startswith('video/'):
            return 'video'
        elif mime_type.startswith('audio/'):
            return 'audio'
    
    # Fallback to extension-based detection
    ext = os.path.splitext(file_path)[1].lower()
    
    video_extensions = {
        '.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.webm',
        '.m4v', '.mpg', '.mpeg', '.3gp', '.ogv'
    }
    
    audio_extensions = {
        '.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac', '.wma',
        '.opus', '.oga', '.aiff', '.alac'
    }
    
    if ext in video_extensions:
        return 'video'
    elif ext in audio_extensions:
        return 'audio'
    
    return 'unknown'


def validate_media_file(file):
    """
    Validate that the uploaded file is a supported media type
    
    Args:
        file: Django UploadedFile object
        
    Returns:
        tuple: (is_valid, file_type, error_message)
    """
    file_type = detect_file_type(file.name)
    
    if file_type == 'unknown':
        return False, None, "Unsupported file type. Please upload a video or audio file."
    
    # Check file size (limit to 2GB)
    max_size = 2 * 1024 * 1024 * 1024  # 2GB in bytes
    if file.size > max_size:
        return False, None, f"File too large. Maximum size is 2GB."
    
    return True, file_type, None


def get_supported_formats():
    """Return list of supported file formats"""
    return {
        'video': ['mp4', 'mov', 'avi', 'mkv', 'flv', 'wmv', 'webm', 'm4v', 'mpg', 'mpeg', '3gp', 'ogv'],
        'audio': ['mp3', 'wav', 'm4a', 'aac', 'ogg', 'flac', 'wma', 'opus', 'oga', 'aiff', 'alac']
    }
