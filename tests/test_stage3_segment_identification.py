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
    
    def test_identify_segments(self, transcript_data, num_segments=3, 
                              max_duration=300, custom_instructions=None, save_output=True):
        """
        Test segment identification from transcript data
        
        Args:
            transcript_data: Transcript data dict or path to JSON file
            num_segments: Number of segments to identify (default 3)
            max_duration: Maximum segment duration in seconds (default 300s = 5 minutes)
            custom_instructions: Optional custom instructions for segment selection
            save_output: Whether to save output to file
            
        Returns:
            dict: Test results with segments and validation
        """
        print(f"\n{'='*60}")
        print(f"STAGE 3 TEST: Identify Segments")
        print(f"{'='*60}")
        
        # Validate parameters
        if num_segments > 5:
            print(f"Warning: num_segments capped at 5 (requested: {num_segments})")
            num_segments = 5
        
        if max_duration > 300:
            print(f"Warning: max_duration capped at 300s (requested: {max_duration})")
            max_duration = 300
        
        print(f"Parameters:")
        print(f"  Number of segments: {num_segments}")
        print(f"  Max duration: {max_duration}s ({max_duration/60:.2f} min)")
        if custom_instructions:
            print(f"  Custom criteria: {custom_instructions}")
        else:
            print(f"  Criteria: Viral content (default)")
        
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
                max_duration=max_duration,
                custom_instructions=custom_instructions
            )
            
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            print(f"\n✓ Segment identification successful!")
            print(f"  Processing time: {processing_time:.2f} seconds")
            print(f"  Segments found: {len(segments)}")
            
            # Display segments
            self._display_segments(segments)
            
            # Validate segments
            validation = self._validate_segments(segments, max_duration)
            
            # Show validation results
            if not validation['valid']:
                print(f"\n❌ Critical validation issues found:")
                for issue in validation['issues']:
                    print(f"  - {issue}")
            
            if validation.get('info'):
                print(f"\nℹ️  Segment length notes:")
                for info in validation['info']:
                    print(f"  - {info}")
            
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
    
    def _validate_segments(self, segments, max_duration):
        """
        Validate segment data - LLM decides length based on content quality and coherence
        
        Args:
            segments: List of segment dicts
            max_duration: Maximum allowed duration (hard limit)
            
        Returns:
            dict: Validation results
        """
        issues = []
        info = []
        
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
            
            # Check maximum duration (hard limit)
            if segment['duration'] > max_duration:
                issues.append(
                    f"Segment {i}: Duration ({segment['duration']:.2f}s) exceeds maximum "
                    f"allowed duration ({max_duration:.0f}s = {max_duration/60:.1f} min)"
                )
            
            # Informational notes on segment length (not errors)
            if segment['duration'] < 30:
                info.append(
                    f"Segment {i}: Short duration ({segment['duration']:.2f}s) - acceptable if content is complete"
                )
            elif segment['duration'] > 240:  # Over 4 minutes
                info.append(
                    f"Segment {i}: Long duration ({segment['duration']:.2f}s = {segment['duration']/60:.1f} min) - LLM determined this is optimal for content coherence"
                )
            
            # Check for overlaps with previous segments
            if i > 1:
                prev_segment = segments[i-2]
                if segment['start_time'] < prev_segment['end_time']:
                    issues.append(f"Segment {i}: Overlaps with Segment {i-1}")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'info': info
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
    
    def test_from_stage2_output(self, stage2_json_path, num_segments=3, 
                               max_duration=300, custom_instructions=None):
        """
        Test using output from Stage 2
        
        Args:
            stage2_json_path: Path to Stage 2 output JSON
            num_segments: Number of segments to identify (default 3)
            max_duration: Maximum segment duration in seconds (default 300s = 5 minutes)
            custom_instructions: Optional custom instructions for segment selection
            
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
                max_duration=max_duration,
                custom_instructions=custom_instructions,
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
    parser.add_argument('--num-segments', type=int, default=3,
                       help='Number of segments to identify (max 5, default: 3)')
    parser.add_argument('--max-duration', type=int, default=300,
                       help='Maximum segment duration in seconds (max 300s = 5 minutes, default: 300)')
    parser.add_argument('--custom-instructions', type=str, default=None,
                       help='Custom instructions for segment selection (e.g., "focus on educational content")')
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
            max_duration=args.max_duration,
            custom_instructions=args.custom_instructions
        )
    elif args.transcript_json:
        tester.test_identify_segments(
            args.transcript_json,
            num_segments=args.num_segments,
            max_duration=args.max_duration,
            custom_instructions=args.custom_instructions,
            save_output=True
        )
    else:
        parser.print_help()
        print("\nExample usage:")
        print("  python tests/test_stage3_segment_identification.py transcript.json")
        print("  python tests/test_stage3_segment_identification.py --from-stage2 test_outputs/stage2/transcript.json")
        print("  python tests/test_stage3_segment_identification.py transcript.json --num-segments 3 --max-duration 300")
        print('  python tests/test_stage3_segment_identification.py transcript.json --custom-instructions "focus on educational moments"')
        print("\nNote: LLM decides optimal segment length based on content quality (max 5 minutes)")
        print("      Default criteria: viral content. Use --custom-instructions to specify different criteria.")


if __name__ == '__main__':
    main()
