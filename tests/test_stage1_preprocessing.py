"""
Test Stage 1: Preprocessing (Video/Audio to Audio)

Tests the preprocessing service that:
- Accepts video or audio files as input
- Extracts audio from video files
- Returns audio file path for ElevenLabs transcription

Usage:
    python tests/test_stage1_preprocessing.py <input_file>
    
    Or run specific tests:
    python tests/test_stage1_preprocessing.py --test-video <video_file>
    python tests/test_stage1_preprocessing.py --test-audio <audio_file>
    python tests/test_stage1_preprocessing.py --test-info <media_file>
"""

import sys
import os
import argparse
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from viral_clips.services.preprocessing_service import PreprocessingService
from viral_clips.utils import detect_file_type


class Stage1Tester:
    """Test harness for Stage 1: Preprocessing"""
    
    def __init__(self, output_dir=None):
        self.output_dir = output_dir or './test_outputs/stage1'
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        self.service = PreprocessingService(output_dir=self.output_dir)
    
    def test_process_media_file(self, input_path):
        """
        Test processing a media file (video or audio)
        
        Args:
            input_path: Path to input file
            
        Returns:
            dict: Test results
        """
        print(f"\n{'='*60}")
        print(f"STAGE 1 TEST: Process Media File")
        print(f"{'='*60}")
        print(f"Input: {input_path}")
        
        try:
            # Detect file type
            file_type = detect_file_type(input_path)
            print(f"Detected file type: {file_type}")
            
            # Process the file
            result = self.service.process_media_file(input_path)
            
            print(f"\n✓ Processing successful!")
            print(f"\nResults:")
            print(f"  Audio path: {result['audio_path']}")
            print(f"  File type: {result['file_type']}")
            print(f"  Original path: {result['original_path']}")
            print(f"  Audio extracted: {result['extracted']}")
            
            # Verify output file exists
            if not os.path.exists(result['audio_path']):
                raise RuntimeError("Output audio file does not exist!")
            
            file_size = os.path.getsize(result['audio_path'])
            print(f"  Output file size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
            
            # Save result to JSON
            output_json = os.path.join(self.output_dir, 'preprocessing_result.json')
            with open(output_json, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"\n✓ Results saved to: {output_json}")
            
            return {
                'success': True,
                'result': result,
                'error': None
            }
            
        except Exception as e:
            print(f"\n✗ Error: {str(e)}")
            return {
                'success': False,
                'result': None,
                'error': str(e)
            }
    
    def test_video_extraction(self, video_path, output_format='mp3'):
        """
        Test extracting audio from a video file
        
        Args:
            video_path: Path to video file
            output_format: Desired audio format (mp3, wav, m4a)
            
        Returns:
            dict: Test results
        """
        print(f"\n{'='*60}")
        print(f"STAGE 1 TEST: Extract Audio from Video")
        print(f"{'='*60}")
        print(f"Video: {video_path}")
        print(f"Output format: {output_format}")
        
        try:
            # Extract audio
            audio_path = self.service.extract_audio_from_video(video_path, output_format)
            
            print(f"\n✓ Extraction successful!")
            print(f"  Audio saved to: {audio_path}")
            
            # Verify output
            if not os.path.exists(audio_path):
                raise RuntimeError("Output audio file does not exist!")
            
            file_size = os.path.getsize(audio_path)
            print(f"  File size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
            
            return {
                'success': True,
                'audio_path': audio_path,
                'error': None
            }
            
        except Exception as e:
            print(f"\n✗ Error: {str(e)}")
            return {
                'success': False,
                'audio_path': None,
                'error': str(e)
            }
    
    def test_audio_passthrough(self, audio_path):
        """
        Test that audio files pass through without modification
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            dict: Test results
        """
        print(f"\n{'='*60}")
        print(f"STAGE 1 TEST: Audio Passthrough")
        print(f"{'='*60}")
        print(f"Audio: {audio_path}")
        
        try:
            result = self.service.process_media_file(audio_path)
            
            print(f"\n✓ Processing successful!")
            print(f"  Audio path: {result['audio_path']}")
            print(f"  Extracted: {result['extracted']}")
            
            # Verify no extraction occurred
            if result['extracted']:
                raise RuntimeError("Audio file should not be extracted!")
            
            if result['audio_path'] != audio_path:
                raise RuntimeError("Audio path should match input path!")
            
            print(f"\n✓ Audio file correctly passed through without extraction")
            
            return {
                'success': True,
                'result': result,
                'error': None
            }
            
        except Exception as e:
            print(f"\n✗ Error: {str(e)}")
            return {
                'success': False,
                'result': None,
                'error': str(e)
            }
    
    def test_get_media_info(self, file_path):
        """
        Test getting detailed media information
        
        Args:
            file_path: Path to media file
            
        Returns:
            dict: Test results
        """
        print(f"\n{'='*60}")
        print(f"STAGE 1 TEST: Get Media Info")
        print(f"{'='*60}")
        print(f"File: {file_path}")
        
        try:
            info = self.service.get_media_info(file_path)
            
            print(f"\n✓ Media info retrieved!")
            print(f"\nMedia Information:")
            print(f"  Duration: {info['duration']:.2f} seconds ({info['duration']/60:.2f} minutes)")
            print(f"  Size: {info['size']:,} bytes ({info['size']/1024/1024:.2f} MB)")
            print(f"  Format: {info['format']}")
            print(f"  Bit rate: {info['bit_rate']:,} bps")
            print(f"  Has audio: {info['has_audio']}")
            print(f"  Has video: {info['has_video']}")
            print(f"  Audio codec: {info['audio_codec']}")
            print(f"  Video codec: {info['video_codec']}")
            
            # Save info to JSON
            output_json = os.path.join(self.output_dir, 'media_info.json')
            with open(output_json, 'w') as f:
                json.dump(info, f, indent=2)
            print(f"\n✓ Media info saved to: {output_json}")
            
            return {
                'success': True,
                'info': info,
                'error': None
            }
            
        except Exception as e:
            print(f"\n✗ Error: {str(e)}")
            return {
                'success': False,
                'info': None,
                'error': str(e)
            }


def main():
    parser = argparse.ArgumentParser(description='Test Stage 1: Preprocessing')
    parser.add_argument('input_file', nargs='?', help='Input video or audio file')
    parser.add_argument('--test-video', help='Test video extraction with specific video file')
    parser.add_argument('--test-audio', help='Test audio passthrough with specific audio file')
    parser.add_argument('--test-info', help='Test media info retrieval with specific file')
    parser.add_argument('--output-format', default='mp3', choices=['mp3', 'wav', 'm4a'],
                       help='Output audio format (default: mp3)')
    parser.add_argument('--output-dir', default='./test_outputs/stage1',
                       help='Output directory for test results')
    
    args = parser.parse_args()
    
    # Initialize tester
    tester = Stage1Tester(output_dir=args.output_dir)
    
    # Run specific tests
    if args.test_video:
        tester.test_video_extraction(args.test_video, args.output_format)
    elif args.test_audio:
        tester.test_audio_passthrough(args.test_audio)
    elif args.test_info:
        tester.test_get_media_info(args.test_info)
    elif args.input_file:
        tester.test_process_media_file(args.input_file)
    else:
        parser.print_help()
        print("\nExample usage:")
        print("  python tests/test_stage1_preprocessing.py video.mp4")
        print("  python tests/test_stage1_preprocessing.py --test-video video.mp4 --output-format wav")
        print("  python tests/test_stage1_preprocessing.py --test-audio audio.mp3")
        print("  python tests/test_stage1_preprocessing.py --test-info media.mp4")


if __name__ == '__main__':
    main()
