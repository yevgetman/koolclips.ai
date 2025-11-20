import json
import logging
from django.conf import settings
from openai import OpenAI
from anthropic import Anthropic

logger = logging.getLogger(__name__)


class LLMService:
    """Service for analyzing transcripts using LLMs (OpenAI or Anthropic)"""
    
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.model = settings.LLM_MODEL
        
        if self.provider == 'openai':
            if not settings.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY not configured")
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        elif self.provider == 'anthropic':
            if not settings.ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY not configured")
            self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
    
    def analyze_transcript(self, transcript_data, num_segments=5, min_duration=60, max_duration=180):
        """
        Analyze transcript and identify viral segments
        
        Args:
            transcript_data: Transcript data with timestamps
            num_segments: Number of segments to identify
            min_duration: Minimum segment duration in seconds
            max_duration: Maximum segment duration in seconds
            
        Returns:
            list: List of segment dictionaries with title, description, timestamps, etc.
        """
        try:
            prompt = self._build_prompt(transcript_data, num_segments, min_duration, max_duration)
            
            if self.provider == 'openai':
                response = self._call_openai(prompt)
            else:
                response = self._call_anthropic(prompt)
            
            segments = self._parse_response(response)
            logger.info(f"Successfully identified {len(segments)} viral segments")
            
            return segments
            
        except Exception as e:
            logger.error(f"LLM analysis error: {str(e)}")
            raise Exception(f"Failed to analyze transcript: {str(e)}")
    
    def _build_prompt(self, transcript_data, num_segments, min_duration, max_duration):
        """Build the prompt for LLM analysis"""
        
        # Extract key information without sending full word array
        # This reduces token count significantly for long transcripts
        full_text = transcript_data.get('full_text', '')
        duration = transcript_data.get('metadata', {}).get('duration', 0)
        
        # Create simplified representation
        simplified_data = {
            'full_text': full_text,
            'total_duration_seconds': duration,
            'total_duration_minutes': round(duration / 60, 2)
        }
        
        transcript_text = json.dumps(simplified_data, indent=2)
        
        min_minutes = min_duration / 60
        max_minutes = max_duration / 60
        
        prompt = f"""Review the attached transcript of a podcast. 

Use the transcript text to choose {num_segments} segments of dialogue that have the most interesting, provocative, and potentially viral content. 

The segments should:
- Be selected to have a mostly coherent topic and thought
- Be between {min_minutes}-{max_minutes} minutes in length when spoken
- Estimate timing based on typical speech rate (~150 words per minute)
- Have high viral potential (controversial, insightful, emotional, or surprising)

Return ONLY a valid JSON array with {num_segments} segments in the following format:
[
  {{
    "title": "Concise headline for the segment",
    "description": "Brief overview of what is discussed",
    "reasoning": "Why this segment is provocative and potentially viral",
    "start_time": <estimated_start_time_in_seconds>,
    "end_time": <estimated_end_time_in_seconds>
  }}
]

Transcript data:
{transcript_text}

Remember: Return ONLY the JSON array, no additional text or explanation."""
        
        return prompt
    
    def _call_openai(self, prompt):
        """Call OpenAI API"""
        logger.info(f"Calling OpenAI with model {self.model}")
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert at identifying viral and engaging content from long-form podcasts. You always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"} if "gpt" in self.model else None
        )
        
        content = response.choices[0].message.content
        if content is None:
            logger.error(f"OpenAI returned None content. Response: {response}")
            logger.error(f"Finish reason: {response.choices[0].finish_reason}")
            raise ValueError(f"OpenAI returned None content. Finish reason: {response.choices[0].finish_reason}")
        
        return content
    
    def _call_anthropic(self, prompt):
        """Call Anthropic API"""
        logger.info(f"Calling Anthropic with model {self.model}")
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=0.7,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        return response.content[0].text
    
    def _parse_response(self, response_text):
        """
        Parse LLM response and extract segments
        
        Args:
            response_text: Raw text response from LLM
            
        Returns:
            list: List of segment dictionaries
        """
        try:
            # Try to parse as JSON
            data = json.loads(response_text)
            
            # Handle different response formats
            if isinstance(data, list):
                segments = data
            elif isinstance(data, dict):
                # Try common keys
                if 'segments' in data:
                    segments = data['segments']
                elif 'results' in data:
                    segments = data['results']
                elif 'clips' in data:
                    segments = data['clips']
                else:
                    # Assume the dict itself is wrapped, try to find array
                    for value in data.values():
                        if isinstance(value, list):
                            segments = value
                            break
                    else:
                        raise ValueError("Could not find segments array in response")
            else:
                raise ValueError("Unexpected response format")
            
            # Validate and normalize segments
            validated_segments = []
            for i, segment in enumerate(segments):
                validated_segment = {
                    'title': segment.get('title', f'Segment {i+1}'),
                    'description': segment.get('description', ''),
                    'reasoning': segment.get('reasoning', ''),
                    'start_time': float(segment.get('start_time', 0)),
                    'end_time': float(segment.get('end_time', 0)),
                }
                
                # Calculate duration
                validated_segment['duration'] = validated_segment['end_time'] - validated_segment['start_time']
                
                validated_segments.append(validated_segment)
            
            return validated_segments
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Response text: {response_text}")
            raise Exception("LLM did not return valid JSON")
        except Exception as e:
            logger.error(f"Error parsing segments: {e}")
            raise
