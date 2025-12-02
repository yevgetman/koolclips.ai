"""
URL Import Service for downloading videos from external sources

Supports:
- YouTube (via yt-dlp)
- Google Drive (direct download links)
- Dropbox (direct download links)
- Direct video URLs
"""

import os
import re
import tempfile
import logging
import requests
from typing import Optional
from urllib.parse import urlparse, parse_qs

from .s3_service import S3Service

logger = logging.getLogger(__name__)


class URLImportService:
    """Service for importing videos from external URLs"""
    
    # Supported source types
    SOURCE_YOUTUBE = 'youtube'
    SOURCE_GDRIVE = 'gdrive'
    SOURCE_DROPBOX = 'dropbox'
    SOURCE_DIRECT = 'direct'
    
    # File size limit (5GB)
    MAX_FILE_SIZE = 5 * 1024 * 1024 * 1024
    
    # Download timeout (30 minutes for large files)
    DOWNLOAD_TIMEOUT = 1800
    
    def __init__(self):
        self.s3_service = S3Service()
    
    def detect_source(self, url: str) -> str:
        """
        Detect the source type from URL
        
        Args:
            url: The URL to analyze
            
        Returns:
            str: Source type (youtube, gdrive, dropbox, direct)
        """
        url_lower = url.lower()
        
        if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
            return self.SOURCE_YOUTUBE
        elif 'drive.google.com' in url_lower:
            return self.SOURCE_GDRIVE
        elif 'dropbox.com' in url_lower or 'dropboxusercontent.com' in url_lower:
            return self.SOURCE_DROPBOX
        else:
            return self.SOURCE_DIRECT
    
    def import_video(self, url: str, job_id: str, progress_callback=None) -> dict:
        """
        Import video from URL and upload to S3
        
        Args:
            url: Source URL
            job_id: Job ID for S3 path
            progress_callback: Optional callback for progress updates
            
        Returns:
            dict: {
                'success': bool,
                's3_key': str,
                'public_url': str,
                'filename': str,
                'file_size': int,
                'duration': float (if available),
                'title': str (if available),
                'source': str
            }
        """
        source = self.detect_source(url)
        logger.info(f"Importing video from {source}: {url}")
        
        try:
            if source == self.SOURCE_YOUTUBE:
                return self._import_from_youtube(url, job_id, progress_callback)
            elif source == self.SOURCE_GDRIVE:
                return self._import_from_gdrive(url, job_id, progress_callback)
            elif source == self.SOURCE_DROPBOX:
                return self._import_from_dropbox(url, job_id, progress_callback)
            else:
                return self._import_from_direct_url(url, job_id, progress_callback)
        except Exception as e:
            logger.error(f"Failed to import video from {url}: {str(e)}")
            raise
    
    def _import_from_youtube(self, url: str, job_id: str, progress_callback=None) -> dict:
        """
        Download video from YouTube using yt-dlp
        
        Note: This is for personal/authorized content only.
        Downloading copyrighted content may violate YouTube ToS.
        """
        import yt_dlp
        
        # Create temp directory for download
        temp_dir = tempfile.mkdtemp()
        output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')
        
        # Progress hook for yt-dlp
        def yt_progress_hook(d):
            if d['status'] == 'downloading' and progress_callback:
                try:
                    downloaded = d.get('downloaded_bytes', 0)
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    if total > 0:
                        percent = (downloaded / total) * 50  # YouTube download is 50% of total
                        progress_callback({
                            'stage': 'downloading',
                            'percent': percent,
                            'downloaded': downloaded,
                            'total': total
                        })
                except Exception:
                    pass
            elif d['status'] == 'finished' and progress_callback:
                progress_callback({
                    'stage': 'processing',
                    'percent': 50,
                    'message': 'Download complete, uploading to storage...'
                })
        
        ydl_opts = {
            'format': 'best[ext=mp4]/best',  # Prefer mp4
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [yt_progress_hook],
            # Limit file size
            'max_filesize': self.MAX_FILE_SIZE,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info first to get metadata
                info = ydl.extract_info(url, download=False)
                
                if info.get('is_live'):
                    raise ValueError("Cannot import live streams")
                
                # Check estimated file size
                filesize = info.get('filesize') or info.get('filesize_approx', 0)
                if filesize > self.MAX_FILE_SIZE:
                    raise ValueError(f"Video too large: {filesize / 1024 / 1024 / 1024:.2f}GB (max 5GB)")
                
                # Download the video
                ydl.download([url])
                
                # Find the downloaded file
                filename = ydl.prepare_filename(info)
                
                # Handle potential format conversion
                if not os.path.exists(filename):
                    # Try with .mp4 extension
                    base = os.path.splitext(filename)[0]
                    for ext in ['.mp4', '.webm', '.mkv']:
                        if os.path.exists(base + ext):
                            filename = base + ext
                            break
                
                if not os.path.exists(filename):
                    raise FileNotFoundError(f"Downloaded file not found: {filename}")
                
                # Get actual file size
                file_size = os.path.getsize(filename)
                
                # Clean title for S3 key
                title = self._sanitize_filename(info.get('title', 'video'))
                ext = os.path.splitext(filename)[1] or '.mp4'
                
                # Upload to S3
                s3_key = f"uploads/import/{job_id}/{title}{ext}"
                
                if progress_callback:
                    progress_callback({
                        'stage': 'uploading',
                        'percent': 60,
                        'message': 'Uploading to storage...'
                    })
                
                result = self.s3_service.upload_file(
                    filename,
                    s3_key,
                    content_type=self._get_content_type(ext)
                )
                
                if progress_callback:
                    progress_callback({
                        'stage': 'complete',
                        'percent': 100,
                        'message': 'Import complete'
                    })
                
                return {
                    'success': True,
                    's3_key': s3_key,
                    'public_url': result['public_url'],
                    'cloudfront_url': result.get('cloudfront_url'),
                    's3_url': result.get('s3_url'),
                    'filename': f"{title}{ext}",
                    'file_size': file_size,
                    'duration': info.get('duration'),
                    'title': info.get('title'),
                    'source': self.SOURCE_YOUTUBE,
                    'thumbnail': info.get('thumbnail'),
                    'original_url': url
                }
                
        finally:
            # Cleanup temp directory
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _import_from_gdrive(self, url: str, job_id: str, progress_callback=None) -> dict:
        """
        Download video from Google Drive
        
        Supports:
        - https://drive.google.com/file/d/FILE_ID/view
        - https://drive.google.com/open?id=FILE_ID
        """
        # Extract file ID from URL
        file_id = self._extract_gdrive_file_id(url)
        if not file_id:
            raise ValueError("Could not extract Google Drive file ID from URL")
        
        # Convert to direct download URL
        download_url = f'https://drive.google.com/uc?export=download&id={file_id}'
        
        return self._download_and_upload(
            download_url,
            job_id,
            source=self.SOURCE_GDRIVE,
            original_url=url,
            progress_callback=progress_callback,
            handle_gdrive_confirm=True
        )
    
    def _import_from_dropbox(self, url: str, job_id: str, progress_callback=None) -> dict:
        """
        Download video from Dropbox
        
        Converts sharing links to direct download links
        """
        # Convert to direct download URL
        download_url = self._convert_dropbox_url(url)
        
        return self._download_and_upload(
            download_url,
            job_id,
            source=self.SOURCE_DROPBOX,
            original_url=url,
            progress_callback=progress_callback
        )
    
    def _import_from_direct_url(self, url: str, job_id: str, progress_callback=None) -> dict:
        """
        Download video from direct URL
        """
        return self._download_and_upload(
            url,
            job_id,
            source=self.SOURCE_DIRECT,
            original_url=url,
            progress_callback=progress_callback
        )
    
    def _download_and_upload(
        self,
        url: str,
        job_id: str,
        source: str,
        original_url: str,
        progress_callback=None,
        handle_gdrive_confirm: bool = False
    ) -> dict:
        """
        Download file from URL and upload to S3
        """
        temp_file = None
        
        try:
            # Start request with streaming
            session = requests.Session()
            response = session.get(url, stream=True, timeout=30, allow_redirects=True)
            
            # Handle Google Drive virus scan confirmation
            if handle_gdrive_confirm:
                for key, value in response.cookies.items():
                    if key.startswith('download_warning'):
                        # Large file, need to confirm download
                        confirm_url = f"{url}&confirm={value}"
                        response = session.get(confirm_url, stream=True, timeout=30)
                        break
            
            response.raise_for_status()
            
            # Get file info from headers
            content_length = int(response.headers.get('content-length', 0))
            content_type = response.headers.get('content-type', 'video/mp4')
            
            # Check file size
            if content_length > self.MAX_FILE_SIZE:
                raise ValueError(f"File too large: {content_length / 1024 / 1024 / 1024:.2f}GB (max 5GB)")
            
            # Extract filename from Content-Disposition or URL
            filename = self._extract_filename_from_response(response, original_url)
            
            # Create temp file
            suffix = os.path.splitext(filename)[1] or '.mp4'
            fd, temp_file = tempfile.mkstemp(suffix=suffix)
            os.close(fd)
            
            # Download with progress
            downloaded = 0
            chunk_size = 1024 * 1024  # 1MB chunks
            
            if progress_callback:
                progress_callback({
                    'stage': 'downloading',
                    'percent': 0,
                    'downloaded': 0,
                    'total': content_length
                })
            
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback and content_length > 0:
                            percent = (downloaded / content_length) * 50  # Download is 50%
                            progress_callback({
                                'stage': 'downloading',
                                'percent': percent,
                                'downloaded': downloaded,
                                'total': content_length
                            })
            
            # Get actual file size
            file_size = os.path.getsize(temp_file)
            
            # Sanitize filename for S3
            safe_filename = self._sanitize_filename(os.path.splitext(filename)[0])
            ext = os.path.splitext(filename)[1] or '.mp4'
            
            # Upload to S3
            s3_key = f"uploads/import/{job_id}/{safe_filename}{ext}"
            
            if progress_callback:
                progress_callback({
                    'stage': 'uploading',
                    'percent': 60,
                    'message': 'Uploading to storage...'
                })
            
            result = self.s3_service.upload_file(
                temp_file,
                s3_key,
                content_type=self._get_content_type(ext) or content_type
            )
            
            if progress_callback:
                progress_callback({
                    'stage': 'complete',
                    'percent': 100,
                    'message': 'Import complete'
                })
            
            return {
                'success': True,
                's3_key': s3_key,
                'public_url': result['public_url'],
                'cloudfront_url': result.get('cloudfront_url'),
                's3_url': result.get('s3_url'),
                'filename': f"{safe_filename}{ext}",
                'file_size': file_size,
                'source': source,
                'original_url': original_url
            }
            
        finally:
            # Cleanup temp file
            if temp_file and os.path.exists(temp_file):
                os.remove(temp_file)
    
    def _extract_gdrive_file_id(self, url: str) -> Optional[str]:
        """Extract file ID from Google Drive URL"""
        # Pattern: /file/d/FILE_ID/
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
        if match:
            return match.group(1)
        
        # Pattern: id=FILE_ID
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if 'id' in params:
            return params['id'][0]
        
        return None
    
    def _convert_dropbox_url(self, url: str) -> str:
        """Convert Dropbox sharing URL to direct download URL"""
        # Replace dl=0 with dl=1
        if 'dl=0' in url:
            url = url.replace('dl=0', 'dl=1')
        elif 'dl=1' not in url:
            # Add dl=1 parameter
            if '?' in url:
                url += '&dl=1'
            else:
                url += '?dl=1'
        
        # Replace www.dropbox.com with dl.dropboxusercontent.com for better download
        url = url.replace('www.dropbox.com', 'dl.dropboxusercontent.com')
        
        return url
    
    def _extract_filename_from_response(self, response, url: str) -> str:
        """Extract filename from response headers or URL"""
        # Try Content-Disposition header
        content_disposition = response.headers.get('content-disposition', '')
        if 'filename=' in content_disposition:
            match = re.search(r'filename[*]?=["\']?([^"\';]+)', content_disposition)
            if match:
                return match.group(1).strip()
        
        # Try URL path
        parsed = urlparse(url)
        path = parsed.path
        if path:
            filename = os.path.basename(path)
            if filename and '.' in filename:
                return filename
        
        # Default filename
        return 'video.mp4'
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for S3 key"""
        # Remove or replace problematic characters
        filename = re.sub(r'[^\w\s\-.]', '', filename)
        filename = re.sub(r'\s+', '_', filename)
        filename = filename.strip('._')
        
        # Limit length
        if len(filename) > 100:
            filename = filename[:100]
        
        return filename or 'video'
    
    def _get_content_type(self, extension: str) -> str:
        """Get content type from file extension"""
        content_types = {
            '.mp4': 'video/mp4',
            '.webm': 'video/webm',
            '.mkv': 'video/x-matroska',
            '.mov': 'video/quicktime',
            '.avi': 'video/x-msvideo',
            '.wmv': 'video/x-ms-wmv',
            '.flv': 'video/x-flv',
            '.m4v': 'video/x-m4v',
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.m4a': 'audio/mp4',
            '.aac': 'audio/aac',
            '.ogg': 'audio/ogg',
        }
        return content_types.get(extension.lower(), 'video/mp4')
    
    def validate_url(self, url: str) -> dict:
        """
        Validate URL before import
        
        Returns:
            dict: {
                'valid': bool,
                'source': str,
                'error': str (if invalid)
            }
        """
        if not url:
            return {'valid': False, 'error': 'URL is required'}
        
        # Basic URL validation
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https'):
                return {'valid': False, 'error': 'URL must use http or https'}
            if not parsed.netloc:
                return {'valid': False, 'error': 'Invalid URL format'}
        except Exception:
            return {'valid': False, 'error': 'Invalid URL format'}
        
        source = self.detect_source(url)
        
        # Source-specific validation
        if source == self.SOURCE_YOUTUBE:
            # Check if it's a valid YouTube URL
            if not re.search(r'(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)', url):
                return {'valid': False, 'error': 'Invalid YouTube URL format'}
        
        elif source == self.SOURCE_GDRIVE:
            file_id = self._extract_gdrive_file_id(url)
            if not file_id:
                return {'valid': False, 'error': 'Could not extract Google Drive file ID'}
        
        return {
            'valid': True,
            'source': source
        }
