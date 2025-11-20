import requests
import logging
import time
from django.conf import settings

logger = logging.getLogger(__name__)


class ShotstackService:
    """Service for creating video clips using Shotstack API"""
    
    BASE_URL = "https://api.shotstack.io"
    
    def __init__(self):
        self.api_key = settings.SHOTSTACK_API_KEY
        if not self.api_key:
            raise ValueError("SHOTSTACK_API_KEY not configured")
        
        # Use 'stage' for sandbox, 'v1' for production
        self.env = getattr(settings, 'SHOTSTACK_ENV', 'sandbox')
        self.stage = 'stage' if self.env == 'sandbox' else 'v1'
        
        logger.info(f"Shotstack service initialized in {self.env} mode (stage: {self.stage})")
    
    def get_headers(self):
        """Get headers for API requests"""
        return {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
    
    def create_clip(self, media_url, start_time, end_time, is_audio_only=False, output_format='mp4'):
        """
        Create a clip from a video or audio file
        
        Args:
            media_url: URL to the source video or audio file
            start_time: Start time in seconds
            end_time: End time in seconds
            is_audio_only: If True, create video with waveform visualization
            output_format: Output format (default: mp4)
            
        Returns:
            str: Render ID for tracking the clip creation
        """
        try:
            url = f"{self.BASE_URL}/edit/{self.stage}/render"
            
            # Calculate trim values
            trim_start = start_time
            trim_length = end_time - start_time
            
            if is_audio_only:
                # For audio files, create a video with waveform visualization
                payload = self._build_audio_payload(media_url, trim_start, trim_length, output_format)
                logger.info(f"Creating audio clip with waveform: {start_time}s - {end_time}s")
            else:
                # For video files, use standard video clip
                payload = self._build_video_payload(media_url, trim_start, trim_length, output_format)
                logger.info(f"Creating video clip: {start_time}s - {end_time}s")
            
            response = requests.post(url, json=payload, headers=self.get_headers())
            response.raise_for_status()
            
            result = response.json()
            render_id = result['response']['id']
            
            logger.info(f"Clip creation initiated, render ID: {render_id}")
            return render_id
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Shotstack API error: {str(e)}")
            raise Exception(f"Failed to create clip: {str(e)}")
    
    def _build_video_payload(self, video_url, trim_start, trim_length, output_format):
        """Build payload for video clip"""
        return {
            "timeline": {
                "tracks": [
                    {
                        "clips": [
                            {
                                "asset": {
                                    "type": "video",
                                    "src": video_url,
                                    "trim": trim_start
                                },
                                "start": 0,
                                "length": trim_length
                            }
                        ]
                    }
                ]
            },
            "output": {
                "format": output_format,
                "resolution": "hd"
            }
        }
    
    def _build_audio_payload(self, audio_url, trim_start, trim_length, output_format):
        """Build payload for audio file with waveform visualization"""
        return {
            "timeline": {
                "soundtrack": {
                    "src": audio_url,
                    "effect": "fadeInFadeOut",
                    "volume": 1.0
                },
                "tracks": [
                    {
                        "clips": [
                            {
                                "asset": {
                                    "type": "audio",
                                    "src": audio_url,
                                    "trim": trim_start,
                                    "volume": 1.0
                                },
                                "start": 0,
                                "length": trim_length,
                                "effect": "waveform"
                            }
                        ]
                    }
                ],
                "background": "#000000"
            },
            "output": {
                "format": output_format,
                "resolution": "hd",
                "size": {
                    "width": 1920,
                    "height": 1080
                }
            }
        }
    
    def get_render_status(self, render_id):
        """
        Check the status of a render job
        
        Args:
            render_id: The render ID returned from create_clip
            
        Returns:
            dict: Status information including URL when complete
        """
        try:
            url = f"{self.BASE_URL}/edit/{self.stage}/render/{render_id}"
            
            response = requests.get(url, headers=self.get_headers())
            response.raise_for_status()
            
            result = response.json()
            status_data = result['response']
            
            return {
                'status': status_data['status'],  # queued, rendering, done, failed
                'url': status_data.get('url'),
                'error': status_data.get('error'),
                'progress': status_data.get('progress', 0)
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Shotstack API error: {str(e)}")
            raise Exception(f"Failed to get render status: {str(e)}")
    
    def wait_for_render(self, render_id, max_wait=300, check_interval=5):
        """
        Wait for a render to complete
        
        Args:
            render_id: The render ID
            max_wait: Maximum time to wait in seconds
            check_interval: How often to check status in seconds
            
        Returns:
            dict: Final status with video URL
        """
        elapsed = 0
        
        while elapsed < max_wait:
            status = self.get_render_status(render_id)
            
            if status['status'] == 'done':
                logger.info(f"Render {render_id} completed successfully")
                return status
            elif status['status'] == 'failed':
                error_msg = status.get('error', 'Unknown error')
                logger.error(f"Render {render_id} failed: {error_msg}")
                raise Exception(f"Render failed: {error_msg}")
            
            logger.info(f"Render {render_id} status: {status['status']}, progress: {status.get('progress', 0)}%")
            time.sleep(check_interval)
            elapsed += check_interval
        
        raise Exception(f"Render timed out after {max_wait} seconds")
    
    def download_clip(self, video_url, output_path):
        """
        Download a rendered clip to a local file
        
        Args:
            video_url: URL of the rendered video
            output_path: Local path to save the video
            
        Returns:
            str: Path to the downloaded file
        """
        try:
            logger.info(f"Downloading clip from {video_url}")
            response = requests.get(video_url, stream=True)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"Clip downloaded to {output_path}")
            return output_path
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download clip: {str(e)}")
            raise Exception(f"Failed to download clip: {str(e)}")
