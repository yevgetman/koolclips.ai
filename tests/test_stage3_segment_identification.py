"""
Test Stage 3: Segment Identification (Transcript to Viral Segments)

Tests the LLM service that:
- Accepts transcript JSON with timestamps
- Accepts parameters: num_segments (max 5), min_duration (default 60s), max_duration (max 180s)
- Uses LLM (OpenAI or Anthropic) to identify viral segments
- Returns structured data with title, description, and timestamps for each segment

Usage:
    python tests/test_stage3_segment_identification.py <transcript_json>
    
    Or test with JSON output from Stage 2:
    python tests/test_stage3_segment_identification.py --from-stage2 test_outputs/stage2/transcript.json
    
    Or with custom parameters:
    python tests/test_stage3_segment_identification.py <transcript_json> --num-segments 3 --max-duration 120
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

from viral_clips.services.llm_service import LLMService
from django.conf import settings


class Stage3Tester:
    """Test harness for Stage 3: Segment Identification"""
    
    def __init__(self, output_dir=None):
        self.output_dir = output_dir or './test_outputs/stage3'
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        self.service = LLMService()
        
        print(f"LLM Provider: {self.service.provider}")
        print(f"LLM Model: {self.service.model}")
    
    def test_identify_segments(self, transcript_data, num_segments=5, 
                              min_duration=60, max_duration=180, save_output=True):
        """
        Test identifying viral segments from transcript
        
        Args:
            transcript_data: Transcript data dict or path to JSON file
            num_segments: Number of segments to identify (max 5)
            min_duration: Minimum segment duration in seconds (default 60)
            max_duration: Maximum segment duration in seconds (max 180)
            save_output: Whether to save segments to JSON file
            
        Returns:
            dict: Test results
        """
        print(f"\n{'='*60}")
        print(f"STAGE 3 TEST: Identify Viral Segments")
        print(f"{'='*60}")
        
        # Validate parameters
        if num_segments > 5:
            print(f"Warning: num_segments capped at 5 (requested: {num_segments})")
            num_segments = 5
        
        if max_duration > 180:
            print(f"Warning: max_duration capped at 180s (requested: {max_duration})")
            max_duration = 180
        
        print(f"Parameters:")
        print(f"  Number of segments: {num_segments}")
        print(f"  Min duration: {min_duration}s ({min_duration/60:.1f} min)")
        print(f"  Max duration: {max_duration}s ({max_duration/60:.1f} min)")
        
        try:
            # Load transcript if it's a file path
            if isinstance(transcript_data, str):
                print(f"\nLoading transcript from: {transcript_data}")
                with open(transcript_data, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    transcript_data = data.get('transcript', data)
            
            # Display transcript info
            word_count = len(transcript_data.get('words', []))
            duration = transcript_data.get('metadata', {}).get('duration', 0)
            print(f"\nTranscript info:")
            print(f"  Duration: {duration:.2f}s ({duration/60:.2f} min)")
            print(f"  Word count: {word_count}")
            
            # Analyze transcript
            print(f"\nSending to {self.service.provider} ({self.service.model})...")
            start_time = datetime.now()
            
            segments = self.service.analyze_transcript(
                transcript_data,
                num_segments=num_segments,
                min_duration=min_duration,
                max_duration=max_duration
            )
            
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            print(f"\n✓ Segment identification successful!")
            print(f"  Processing time: {processing_time:.2f} seconds")
            print(f"  Segments found: {len(segments)}")
            
            # Display segments
            self._display_segments(segments)
            
            # Validate segments
            validation = self._validate_segments(segments, min_duration, max_duration)
            if not validation['valid']:
                print(f"\n⚠ Warning: Some segments have validation issues:")
                for issue in validation['issues']:
                    print(f"  - {issue}")
            
            # Save segments if requested
            if save_output:
                output_file = self._save_segments(segments, transcript_data)
                print(f"\n✓ Segments saved to: {output_file}")
            
            return {
                'success': True,
                'segments': segments,
                'processing_time': processing_time,
                'validation': validation,
                'error': None
            }
            
        except Exception as e:
            print(f"\n✗ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'segments': None,
                'error': str(e)
            }
    
    def _display_segments(self, segments):
        """Display segment information"""
        print(f"\n{'='*60}")
        print("IDENTIFIED VIRAL SEGMENTS")
        print(f"{'='*60}")
        
        for i, segment in enumerate(segments, 1):
            print(f"\nSegment {i}: {segment['title']}")
            print(f"  Time: {segment['start_time']:.2f}s - {segment['end_time']:.2f}s")
            print(f"  Duration: {segment['duration']:.2f}s ({segment['duration']/60:.2f} min)")
            print(f"  Description: {segment['description']}")
            if 'reasoning' in segment and segment['reasoning']:
                print(f"  Reasoning: {segment['reasoning']}")
    
    def _validate_segments(self, segments, min_duration, max_duration):
        """
        Validate segment data
        
        Args:
            segments: List of segment dicts
            min_duration: Minimum allowed duration
            max_duration: Maximum allowed duration
            
        Returns:
            dict: Validation results
        """
        issues = []
        
        for i, segment in enumerate(segments, 1):
            # Check required fields
            required_fields = ['title', 'description', 'start_time', 'end_time', 'duration']
            for field in required_fields:
                if field not in segment:
                    issues.append(f"Segment {i}: Missing field '{field}'")
            
            # Check timestamps
            if segment['start_time'] >= segment['end_time']:
                issues.append(f"Segment {i}: start_time >= end_time")
            
            # Check duration consistency
            calculated_duration = segment['end_time'] - segment['start_time']
            if abs(calculated_duration - segment['duration']) > 0.1:
                issues.append(
                    f"Segment {i}: Duration mismatch "
                    f"(calculated: {calculated_duration:.2f}s, stored: {segment['duration']:.2f}s)"
                )
            
            # Check duration bounds
            if segment['duration'] < min_duration:
                issues.append(
                    f"Segment {i}: Duration ({segment['duration']:.2f}s) below minimum ({min_duration}s)"
                )
            if segment['duration'] > max_duration:
                issues.append(
                    f"Segment {i}: Duration ({segment['duration']:.2f}s) above maximum ({max_duration}s)"
                )
            
            # Check for overlaps with previous segments
            if i > 1:
                prev_segment = segments[i-2]
                if segment['start_time'] < prev_segment['end_time']:
                    issues.append(f"Segment {i}: Overlaps with Segment {i-1}")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues
        }
    
    def _save_segments(self, segments, transcript_data):
        """Save segments to JSON file"""
        # Generate output filename
        output_filename = f"viral_segments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_path = os.path.join(self.output_dir, output_filename)
        
        # Prepare output data
        output_data = {
            'timestamp': datetime.now().isoformat(),
            'llm_provider': self.service.provider,
            'llm_model': self.service.model,
            'num_segments': len(segments),
            'segments': segments,
            'transcript_metadata': transcript_data.get('metadata', {})
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        return output_path
    
    def test_from_stage2_output(self, stage2_json_path, num_segments=5, 
                               min_duration=60, max_duration=180):
        """
        Test using output from Stage 2
        
        Args:
            stage2_json_path: Path to Stage 2 output JSON
            num_segments: Number of segments to identify
            min_duration: Minimum segment duration in seconds
            max_duration: Maximum segment duration in seconds
            
        Returns:
            dict: Test results
        """
        print(f"\n{'='*60}")
        print(f"STAGE 3 TEST: Process Stage 2 Output")
        print(f"{'='*60}")
        print(f"Stage 2 output: {stage2_json_path}")
        
        try:
            # Load Stage 2 output
            with open(stage2_json_path, 'r', encoding='utf-8') as f:
                stage2_data = json.load(f)
            
            transcript = stage2_data.get('transcript')
            if not transcript:
                raise ValueError("No transcript found in Stage 2 output")
            
            # Identify segments
            return self.test_identify_segments(
                transcript,
                num_segments=num_segments,
                min_duration=min_duration,
                max_duration=max_duration,
                save_output=True
            )
            
        except Exception as e:
            print(f"\n✗ Error: {str(e)}")
            return {
                'success': False,
                'segments': None,
                'error': str(e)
            }
    
    def test_custom_prompt(self, transcript_data, custom_prompt, save_output=True):
        """
        Test with a custom prompt (for advanced testing)
        
        Args:
            transcript_data: Transcript data dict or path to JSON file
            custom_prompt: Custom prompt text
            save_output: Whether to save output
            
        Returns:
            dict: Test results
        """
        print(f"\n{'='*60}")
        print(f"STAGE 3 TEST: Custom Prompt")
        print(f"{'='*60}")
        print(f"Custom prompt length: {len(custom_prompt)} chars")
        
        # This would require modifying the LLM service to accept custom prompts
        # For now, just show what would be tested
        print("\nNote: Custom prompt testing requires service modification")
        print("Current implementation uses built-in prompt template")
        
        return {
            'success': False,
            'error': 'Custom prompt testing not yet implemented'
        }


def main():
    parser = argparse.ArgumentParser(description='Test Stage 3: Segment Identification')
    parser.add_argument('transcript_json', nargs='?', help='Input transcript JSON file')
    parser.add_argument('--from-stage2', help='Use output JSON from Stage 2')
    parser.add_argument('--num-segments', type=int, default=5,
                       help='Number of segments to identify (max 5, default: 5)')
    parser.add_argument('--min-duration', type=int, default=60,
                       help='Minimum segment duration in seconds (default: 60)')
    parser.add_argument('--max-duration', type=int, default=180,
                       help='Maximum segment duration in seconds (max 180, default: 180)')
    parser.add_argument('--output-dir', default='./test_outputs/stage3',
                       help='Output directory for test results')
    
    args = parser.parse_args()
    
    # Initialize tester
    tester = Stage3Tester(output_dir=args.output_dir)
    
    # Run tests
    if args.from_stage2:
        tester.test_from_stage2_output(
            args.from_stage2,
            num_segments=args.num_segments,
            min_duration=args.min_duration,
            max_duration=args.max_duration
        )
    elif args.transcript_json:
        tester.test_identify_segments(
            args.transcript_json,
            num_segments=args.num_segments,
            min_duration=args.min_duration,
            max_duration=args.max_duration,
            save_output=True
        )
    else:
        parser.print_help()
        print("\nExample usage:")
        print("  python tests/test_stage3_segment_identification.py transcript.json")
        print("  python tests/test_stage3_segment_identification.py --from-stage2 test_outputs/stage2/transcript.json")
        print("  python tests/test_stage3_segment_identification.py transcript.json --num-segments 3 --max-duration 120")


if __name__ == '__main__':
    main()
