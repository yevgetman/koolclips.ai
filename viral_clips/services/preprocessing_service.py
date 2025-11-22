"""
Service for preprocessing media files (Stage 1)
Handles audio extraction from video files and validation of audio files
"""

import os
import logging
import subprocess
from pathlib import Path
from ..utils import detect_file_type

logger = logging.getLogger(__name__)


class PreprocessingService:
    """Service for preprocessing video/audio files before transcription"""
    
    def __init__(self, output_dir=None):
        """
        Initialize preprocessing service
        
        Args:
            output_dir: Directory to save extracted audio files (optional)
        """
        self.output_dir = output_dir or '/tmp/viral_clips_audio'
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        
        # Check if ffmpeg is available
        self._check_ffmpeg()
    
    def _check_ffmpeg(self):
        """Check if ffmpeg is installed and available"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=30  # Increased timeout to 30 seconds
            )
            if result.returncode != 0:
                raise RuntimeError("ffmpeg is not functioning properly")
            logger.info("ffmpeg is available")
        except FileNotFoundError:
            raise RuntimeError(
                "ffmpeg is not installed. Please install ffmpeg: "
                "https://ffmpeg.org/download.html"
            )
        except subprocess.TimeoutExpired:
            # If check times out, just log warning and continue
            logger.warning("ffmpeg check timed out, but will proceed anyway")
            pass
    
    def process_media_file(self, input_path):
        """
        Process a media file (video or audio) and return path to audio file
        
        Args:
            input_path: Path to input video or audio file
            
        Returns:
            dict: {
                'audio_path': Path to the audio file,
                'file_type': 'video' or 'audio',
                'original_path': Path to original file,
                'extracted': Boolean indicating if audio was extracted
            }
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        file_type = detect_file_type(input_path)
        
        if file_type == 'unknown':
            raise ValueError(f"Unsupported file type: {input_path}")
        
        if file_type == 'audio':
            logger.info(f"Input is already audio: {input_path}")
            return {
                'audio_path': input_path,
                'file_type': 'audio',
                'original_path': input_path,
                'extracted': False
            }
        
        # Extract audio from video
        logger.info(f"Extracting audio from video: {input_path}")
        audio_path = self.extract_audio_from_video(input_path)
        
        return {
            'audio_path': audio_path,
            'file_type': 'video',
            'original_path': input_path,
            'extracted': True
        }
    
    def extract_audio_from_video(self, video_path, output_format='mp3'):
        """
        Extract audio from a video file using ffmpeg
        
        Args:
            video_path: Path to the video file
            output_format: Output audio format (mp3, wav, m4a, etc.)
            
        Returns:
            str: Path to the extracted audio file
        """
        # Generate output filename
        video_filename = os.path.basename(video_path)
        name_without_ext = os.path.splitext(video_filename)[0]
        output_filename = f"{name_without_ext}.{output_format}"
        output_path = os.path.join(self.output_dir, output_filename)
        
        # Build ffmpeg command
        # -i: input file
        # -vn: no video
        # -acodec: audio codec (libmp3lame for mp3)
        # -ab: audio bitrate
        # -ar: audio sampling rate
        # -y: overwrite output file if exists
        
        if output_format == 'mp3':
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-vn',  # No video
                '-acodec', 'libmp3lame',
                '-ab', '192k',
                '-ar', '44100',
                '-y',
                output_path
            ]
        elif output_format == 'wav':
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-vn',
                '-acodec', 'pcm_s16le',
                '-ar', '44100',
                '-y',
                output_path
            ]
        elif output_format == 'm4a':
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-vn',
                '-acodec', 'aac',
                '-ab', '192k',
                '-ar', '44100',
                '-y',
                output_path
            ]
        else:
            raise ValueError(f"Unsupported output format: {output_format}")
        
        try:
            logger.info(f"Running ffmpeg command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                logger.error(f"ffmpeg error: {result.stderr}")
                raise RuntimeError(f"Audio extraction failed: {result.stderr}")
            
            if not os.path.exists(output_path):
                raise RuntimeError(f"Audio extraction failed: output file not created")
            
            logger.info(f"Audio extracted successfully: {output_path}")
            return output_path
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("Audio extraction timed out (max 5 minutes)")
        except Exception as e:
            logger.error(f"Error extracting audio: {str(e)}")
            raise
    
    def get_media_info(self, file_path):
        """
        Get detailed information about a media file using ffprobe
        
        Args:
            file_path: Path to media file
            
        Returns:
            dict: Media information (duration, codec, bitrate, etc.)
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                file_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"ffprobe error: {result.stderr}")
            
            import json
            info = json.loads(result.stdout)
            
            # Extract key information
            format_info = info.get('format', {})
            streams = info.get('streams', [])
            
            audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), None)
            video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
            
            return {
                'duration': float(format_info.get('duration', 0)),
                'size': int(format_info.get('size', 0)),
                'format': format_info.get('format_name', ''),
                'bit_rate': int(format_info.get('bit_rate', 0)),
                'has_audio': audio_stream is not None,
                'has_video': video_stream is not None,
                'audio_codec': audio_stream.get('codec_name') if audio_stream else None,
                'video_codec': video_stream.get('codec_name') if video_stream else None,
            }
            
        except Exception as e:
            logger.error(f"Error getting media info: {str(e)}")
            raise
    
    def cleanup_extracted_files(self):
        """Remove all extracted audio files from the output directory"""
        try:
            import shutil
            if os.path.exists(self.output_dir):
                shutil.rmtree(self.output_dir)
                Path(self.output_dir).mkdir(parents=True, exist_ok=True)
                logger.info(f"Cleaned up extracted files in {self.output_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up files: {str(e)}")
