"""
Test Stage 2: Transcription (Audio to Transcript with Timestamps)

Tests the ElevenLabs transcription service that:
- Accepts an audio file as input
- Sends it to ElevenLabs API for transcription
- Returns structured JSON with transcribed text and word-level timestamps

Usage:
    python tests/test_stage2_transcription.py <audio_file>
    
    Or test with JSON output from Stage 1:
    python tests/test_stage2_transcription.py --from-stage1 test_outputs/stage1/preprocessing_result.json
"""

import sys
import os
import argparse
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from viral_clips.services.elevenlabs_service import ElevenLabsService


class Stage2Tester:
    """Test harness for Stage 2: Transcription"""
    
    def __init__(self, output_dir=None):
        self.output_dir = output_dir or './test_outputs/stage2'
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        self.service = ElevenLabsService()
    
    def test_transcribe_audio(self, audio_path, save_output=True):
        """
        Test transcribing an audio file
        
        Args:
            audio_path: Path to audio file
            save_output: Whether to save the transcript to a JSON file
            
        Returns:
            dict: Test results
        """
        print(f"\n{'='*60}")
        print(f"STAGE 2 TEST: Transcribe Audio")
        print(f"{'='*60}")
        print(f"Audio file: {audio_path}")
        
        if not os.path.exists(audio_path):
            print(f"\n✗ Error: Audio file not found: {audio_path}")
            return {
                'success': False,
                'transcript': None,
                'error': 'File not found'
            }
        
        file_size = os.path.getsize(audio_path)
        print(f"File size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
        
        try:
            print(f"\nSending transcription request to ElevenLabs...")
            start_time = datetime.now()
            
            # Transcribe the audio
            transcript = self.service.transcribe_video(audio_path)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            print(f"\n✓ Transcription successful!")
            print(f"  Processing time: {duration:.2f} seconds")
            
            # Display transcript information
            self._display_transcript_info(transcript)
            
            # Save transcript if requested
            if save_output:
                output_file = self._save_transcript(transcript, audio_path)
                print(f"\n✓ Transcript saved to: {output_file}")
            
            return {
                'success': True,
                'transcript': transcript,
                'processing_time': duration,
                'error': None
            }
            
        except Exception as e:
            print(f"\n✗ Error: {str(e)}")
            return {
                'success': False,
                'transcript': None,
                'error': str(e)
            }
    
    def _display_transcript_info(self, transcript):
        """Display transcript information"""
        print(f"\nTranscript Information:")
        print(f"  Language: {transcript['metadata']['language']}")
        print(f"  Language probability: {transcript['metadata']['language_probability']:.2%}")
        print(f"  Duration: {transcript['metadata']['duration']:.2f} seconds")
        print(f"  Word count: {len(transcript['words'])}")
        print(f"  Transcription ID: {transcript['metadata'].get('transcription_id', 'N/A')}")
        
        # Display first few words
        print(f"\nFirst 10 words:")
        for i, word in enumerate(transcript['words'][:10]):
            print(f"    {i+1}. \"{word['text']}\" at {word['start']:.2f}s - {word['end']:.2f}s")
        
        # Display full text preview
        full_text = transcript['full_text']
        preview_length = 200
        if len(full_text) > preview_length:
            print(f"\nFull text preview (first {preview_length} chars):")
            print(f"  {full_text[:preview_length]}...")
        else:
            print(f"\nFull text:")
            print(f"  {full_text}")
    
    def _save_transcript(self, transcript, audio_path):
        """Save transcript to JSON file"""
        # Generate output filename based on audio file
        audio_filename = os.path.basename(audio_path)
        name_without_ext = os.path.splitext(audio_filename)[0]
        output_filename = f"{name_without_ext}_transcript.json"
        output_path = os.path.join(self.output_dir, output_filename)
        
        # Add metadata
        output_data = {
            'source_audio': audio_path,
            'timestamp': datetime.now().isoformat(),
            'transcript': transcript
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        return output_path
    
    def test_transcript_duration(self, transcript_data):
        """
        Test extracting duration from transcript data
        
        Args:
            transcript_data: Transcript data dict or path to JSON file
            
        Returns:
            dict: Test results
        """
        print(f"\n{'='*60}")
        print(f"STAGE 2 TEST: Get Transcript Duration")
        print(f"{'='*60}")
        
        try:
            # Load transcript if it's a file path
            if isinstance(transcript_data, str):
                print(f"Loading transcript from: {transcript_data}")
                with open(transcript_data, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    transcript_data = data.get('transcript', data)
            
            duration = self.service.get_transcript_duration(transcript_data)
            
            print(f"\n✓ Duration extracted!")
            print(f"  Duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
            
            return {
                'success': True,
                'duration': duration,
                'error': None
            }
            
        except Exception as e:
            print(f"\n✗ Error: {str(e)}")
            return {
                'success': False,
                'duration': None,
                'error': str(e)
            }
    
    def test_from_stage1_output(self, stage1_json_path):
        """
        Test using output from Stage 1
        
        Args:
            stage1_json_path: Path to Stage 1 output JSON
            
        Returns:
            dict: Test results
        """
        print(f"\n{'='*60}")
        print(f"STAGE 2 TEST: Process Stage 1 Output")
        print(f"{'='*60}")
        print(f"Stage 1 output: {stage1_json_path}")
        
        try:
            # Load Stage 1 output
            with open(stage1_json_path, 'r') as f:
                stage1_data = json.load(f)
            
            audio_path = stage1_data.get('audio_path')
            if not audio_path:
                raise ValueError("No audio_path found in Stage 1 output")
            
            print(f"Audio path from Stage 1: {audio_path}")
            
            # Transcribe the audio
            return self.test_transcribe_audio(audio_path, save_output=True)
            
        except Exception as e:
            print(f"\n✗ Error: {str(e)}")
            return {
                'success': False,
                'transcript': None,
                'error': str(e)
            }
    
    def validate_transcript_structure(self, transcript):
        """
        Validate the structure of a transcript
        
        Args:
            transcript: Transcript data to validate
            
        Returns:
            dict: Validation results
        """
        print(f"\n{'='*60}")
        print(f"STAGE 2 TEST: Validate Transcript Structure")
        print(f"{'='*60}")
        
        issues = []
        
        # Check required keys
        required_keys = ['full_text', 'words', 'metadata']
        for key in required_keys:
            if key not in transcript:
                issues.append(f"Missing required key: {key}")
        
        # Check metadata structure
        if 'metadata' in transcript:
            required_metadata = ['duration', 'language']
            for key in required_metadata:
                if key not in transcript['metadata']:
                    issues.append(f"Missing metadata key: {key}")
        
        # Check words structure
        if 'words' in transcript and transcript['words']:
            first_word = transcript['words'][0]
            required_word_keys = ['text', 'start', 'end']
            for key in required_word_keys:
                if key not in first_word:
                    issues.append(f"Missing word key: {key}")
        
        # Check timestamp ordering
        if 'words' in transcript:
            for i, word in enumerate(transcript['words']):
                if word['start'] > word['end']:
                    issues.append(f"Word {i}: start time > end time")
                if i > 0 and word['start'] < transcript['words'][i-1]['end']:
                    issues.append(f"Word {i}: overlapping timestamps")
        
        if issues:
            print(f"\n✗ Validation failed!")
            for issue in issues:
                print(f"  - {issue}")
            return {
                'valid': False,
                'issues': issues
            }
        else:
            print(f"\n✓ Transcript structure is valid!")
            return {
                'valid': True,
                'issues': []
            }


def main():
    parser = argparse.ArgumentParser(description='Test Stage 2: Transcription')
    parser.add_argument('audio_file', nargs='?', help='Input audio file')
    parser.add_argument('--from-stage1', help='Use output JSON from Stage 1')
    parser.add_argument('--validate', help='Validate transcript structure from JSON file')
    parser.add_argument('--duration', help='Get duration from transcript JSON file')
    parser.add_argument('--output-dir', default='./test_outputs/stage2',
                       help='Output directory for test results')
    
    args = parser.parse_args()
    
    # Initialize tester
    tester = Stage2Tester(output_dir=args.output_dir)
    
    # Run specific tests
    if args.from_stage1:
        tester.test_from_stage1_output(args.from_stage1)
    elif args.validate:
        with open(args.validate, 'r') as f:
            data = json.load(f)
            transcript = data.get('transcript', data)
        tester.validate_transcript_structure(transcript)
    elif args.duration:
        tester.test_transcript_duration(args.duration)
    elif args.audio_file:
        tester.test_transcribe_audio(args.audio_file)
    else:
        parser.print_help()
        print("\nExample usage:")
        print("  python tests/test_stage2_transcription.py audio.mp3")
        print("  python tests/test_stage2_transcription.py --from-stage1 test_outputs/stage1/preprocessing_result.json")
        print("  python tests/test_stage2_transcription.py --validate test_outputs/stage2/transcript.json")
        print("  python tests/test_stage2_transcription.py --duration test_outputs/stage2/transcript.json")


if __name__ == '__main__':
    main()
