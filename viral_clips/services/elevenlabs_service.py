import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class ElevenLabsService:
    """Service for interacting with Eleven Labs API for transcription"""
    
    BASE_URL = "https://api.elevenlabs.io/v1"
    
    def __init__(self):
        self.api_key = settings.ELEVENLABS_API_KEY
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY not configured")
    
    def get_headers(self):
        """Get headers for API requests"""
        return {
            "xi-api-key": self.api_key,
        }
    
    def transcribe_video(self, video_file_path):
        """
        Transcribe a video file and return transcript with timestamps
        
        Args:
            video_file_path: Path to the video file
            
        Returns:
            dict: Transcript data with timestamps
        """
        try:
            # Eleven Labs API endpoint for speech-to-text (dubbing/audio-intelligence)
            # Note: This may require a specific plan or feature access
            url = f"{self.BASE_URL}/audio-intelligence"
            
            with open(video_file_path, 'rb') as f:
                files = {
                    'audio': f
                }
                headers = self.get_headers()
                
                logger.info(f"Sending transcription request to Eleven Labs for {video_file_path}")
                response = requests.post(url, headers=headers, files=files, timeout=300)
                response.raise_for_status()
                
                transcript_data = response.json()
                logger.info("Transcription successful")
                
                return self._format_transcript(transcript_data)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Eleven Labs API error: {str(e)}")
            raise Exception(f"Failed to transcribe video: {str(e)}")
    
    def _format_transcript(self, raw_data):
        """
        Format the raw transcript data from Eleven Labs
        
        Args:
            raw_data: Raw response from Eleven Labs API
            
        Returns:
            dict: Formatted transcript with timestamps
        """
        # Note: The actual format depends on Eleven Labs API response
        # This is a placeholder structure that should be adjusted based on actual API response
        
        if 'text' in raw_data:
            # Simple format
            return {
                'full_text': raw_data.get('text', ''),
                'segments': raw_data.get('segments', []),
                'metadata': {
                    'duration': raw_data.get('duration', 0),
                    'language': raw_data.get('language', 'en')
                }
            }
        else:
            # Return as-is if format is unknown
            return raw_data
    
    def get_transcript_duration(self, transcript_data):
        """
        Extract the total duration from transcript data
        
        Args:
            transcript_data: Formatted transcript data
            
        Returns:
            float: Duration in seconds
        """
        if 'metadata' in transcript_data and 'duration' in transcript_data['metadata']:
            return transcript_data['metadata']['duration']
        
        # Fallback: calculate from segments
        if 'segments' in transcript_data and transcript_data['segments']:
            last_segment = transcript_data['segments'][-1]
            if 'end' in last_segment:
                return last_segment['end']
        
        return 0.0
