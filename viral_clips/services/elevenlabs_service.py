import logging
from django.conf import settings
from elevenlabs import ElevenLabs

logger = logging.getLogger(__name__)


class ElevenLabsService:
    """Service for interacting with ElevenLabs API for speech-to-text transcription"""
    
    def __init__(self):
        self.api_key = settings.ELEVENLABS_API_KEY
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY not configured")
        
        # Initialize ElevenLabs client with API key
        self.client = ElevenLabs(api_key=self.api_key)
    
    def transcribe_video(self, video_file_path):
        """
        Transcribe a video file using ElevenLabs Speech-to-Text API
        
        Args:
            video_file_path: Path to the video file
            
        Returns:
            dict: Formatted transcript data with timestamps and metadata
        """
        try:
            logger.info(f"Sending transcription request to ElevenLabs for {video_file_path}")
            
            # Open the file and send to ElevenLabs API
            with open(video_file_path, 'rb') as audio_file:
                # Use the speech_to_text.convert method from the SDK
                # Parameters:
                # - file: the audio/video file
                # - model_id: required model selection (eleven_multilingual_v2 is default)
                # - language_code: optional language hint
                # - timestamps_granularity: 'word' for word-level timestamps
                response = self.client.speech_to_text.convert(
                    file=audio_file,
                    model_id='scribe_v2',  # Use latest scribe model
                    timestamps_granularity='word'  # Get word-level timestamps
                )
            
            logger.info("Transcription successful from ElevenLabs")
            
            # Format the response according to our internal structure
            return self._format_transcript(response)
                
        except Exception as e:
            logger.error(f"ElevenLabs API error: {str(e)}")
            raise Exception(f"Failed to transcribe video: {str(e)}")
    
    def _format_transcript(self, raw_response):
        """
        Format the raw transcript data from ElevenLabs API
        
        Args:
            raw_response: Raw response from ElevenLabs speech_to_text.convert()
            
        Returns:
            dict: Formatted transcript with timestamps and segments
            
        Expected ElevenLabs response structure:
        {
            "language_code": "en",
            "language_probability": 0.99,
            "text": "Full transcript text...",
            "words": [
                {
                    "text": "word",
                    "start": 0.5,
                    "end": 0.8,
                    "type": "word",
                    "speaker_id": null
                },
                ...
            ],
            "transcription_id": "abc123"
        }
        """
        # Handle both dict and object responses
        if hasattr(raw_response, '__dict__'):
            data = raw_response.__dict__
        else:
            data = raw_response
        
        # Extract full text
        full_text = data.get('text', '')
        
        # Extract words with timestamps
        words = data.get('words', [])
        
        # Convert word objects to dicts if needed
        formatted_words = []
        for word in words:
            if hasattr(word, '__dict__'):
                word_dict = word.__dict__
            else:
                word_dict = word
            
            formatted_words.append({
                'text': word_dict.get('text', ''),
                'start': word_dict.get('start', 0),
                'end': word_dict.get('end', 0),
                'speaker_id': word_dict.get('speaker_id', None)
            })
        
        # Calculate total duration from last word's end time
        duration = 0.0
        if formatted_words and formatted_words[-1]['end']:
            duration = formatted_words[-1]['end']
        
        # Return formatted structure
        return {
            'full_text': full_text,
            'words': formatted_words,
            'metadata': {
                'duration': duration,
                'language': data.get('language_code', 'en'),
                'language_probability': data.get('language_probability', 0),
                'transcription_id': data.get('transcription_id', None)
            }
        }
    
    def get_transcript_duration(self, transcript_data):
        """
        Extract the total duration from transcript data
        
        Args:
            transcript_data: Formatted transcript data
            
        Returns:
            float: Duration in seconds
        """
        # Try to get from metadata first
        if 'metadata' in transcript_data and 'duration' in transcript_data['metadata']:
            return transcript_data['metadata']['duration']
        
        # Fallback: calculate from words
        if 'words' in transcript_data and transcript_data['words']:
            last_word = transcript_data['words'][-1]
            if 'end' in last_word and last_word['end']:
                return last_word['end']
        
        return 0.0
