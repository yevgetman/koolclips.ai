#!/usr/bin/env python
"""
Integrated Test Runner

Run multiple stages in sequence or all stages end-to-end.

Usage:
    # Run complete pipeline
    python tests/test_runner.py --input video.mp4 --all-stages
    
    # Run stages 1-3 only
    python tests/test_runner.py --input video.mp4 --stages 1 2 3
    
    # Continue from Stage 2 with existing audio
    python tests/test_runner.py --audio audio.mp3 --stages 2 3 4
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

from test_stage1_preprocessing import Stage1Tester
from test_stage2_transcription import Stage2Tester
from test_stage3_segment_identification import Stage3Tester
from test_stage4_clip_creation import Stage4Tester


class IntegratedTestRunner:
    """Run integrated tests across multiple stages"""
    
    def __init__(self, output_base_dir='./test_outputs'):
        self.output_base_dir = output_base_dir
        Path(output_base_dir).mkdir(parents=True, exist_ok=True)
        
        # Create timestamped run directory
        self.run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.run_dir = os.path.join(output_base_dir, f'run_{self.run_id}')
        Path(self.run_dir).mkdir(parents=True, exist_ok=True)
        
        print(f"Test run ID: {self.run_id}")
        print(f"Output directory: {self.run_dir}")
    
    def run_complete_pipeline(self, input_file, num_segments=3, 
                             max_duration=300, create_clips=False):
        """
        Run all 4 stages in sequence
        
        Args:
            input_file: Input video or audio file
            num_segments: Number of segments to identify (default: 3)
            max_duration: Maximum segment duration in seconds (default: 300s = 5 minutes)
            create_clips: Whether to actually create clips in Stage 4
            
        Returns:
            dict: Results from all stages
        """
        print(f"\n{'='*70}")
        print(f"INTEGRATED TEST: Complete Pipeline")
        print(f"{'='*70}")
        print(f"Input: {input_file}")
        print(f"Run ID: {self.run_id}")
        
        results = {
            'run_id': self.run_id,
            'input_file': input_file,
            'timestamp': datetime.now().isoformat(),
            'stages': {}
        }
        
        # Stage 1: Preprocessing
        print(f"\n{'*'*70}")
        print("STAGE 1: PREPROCESSING")
        print(f"{'*'*70}")
        
        stage1_dir = os.path.join(self.run_dir, 'stage1')
        stage1_tester = Stage1Tester(output_dir=stage1_dir)
        stage1_result = stage1_tester.test_process_media_file(input_file)
        results['stages']['stage1'] = stage1_result
        
        if not stage1_result['success']:
            print("\n✗ Stage 1 failed. Stopping pipeline.")
            return results
        
        audio_path = stage1_result['result']['audio_path']
        original_path = stage1_result['result']['original_path']
        
        # Stage 2: Transcription
        print(f"\n{'*'*70}")
        print("STAGE 2: TRANSCRIPTION")
        print(f"{'*'*70}")
        
        stage2_dir = os.path.join(self.run_dir, 'stage2')
        stage2_tester = Stage2Tester(output_dir=stage2_dir)
        stage2_result = stage2_tester.test_transcribe_audio(audio_path, save_output=True)
        results['stages']['stage2'] = {
            'success': stage2_result['success'],
            'processing_time': stage2_result.get('processing_time'),
            'error': stage2_result.get('error')
        }
        
        if not stage2_result['success']:
            print("\n✗ Stage 2 failed. Stopping pipeline.")
            return results
        
        transcript = stage2_result['transcript']
        
        # Stage 3: Segment Identification
        print(f"\n{'*'*70}")
        print("STAGE 3: SEGMENT IDENTIFICATION")
        print(f"{'*'*70}")
        
        stage3_dir = os.path.join(self.run_dir, 'stage3')
        stage3_tester = Stage3Tester(output_dir=stage3_dir)
        stage3_result = stage3_tester.test_identify_segments(
            transcript,
            num_segments=num_segments,
            max_duration=max_duration,
            save_output=True
        )
        results['stages']['stage3'] = {
            'success': stage3_result['success'],
            'num_segments': len(stage3_result.get('segments', [])),
            'processing_time': stage3_result.get('processing_time'),
            'validation': stage3_result.get('validation'),
            'error': stage3_result.get('error')
        }
        
        if not stage3_result['success']:
            print("\n✗ Stage 3 failed. Stopping pipeline.")
            return results
        
        segments = stage3_result['segments']
        
        # Stage 4: Clip Creation (optional)
        if create_clips:
            print(f"\n{'*'*70}")
            print("STAGE 4: CLIP CREATION")
            print(f"{'*'*70}")
            
            stage4_dir = os.path.join(self.run_dir, 'stage4')
            stage4_tester = Stage4Tester(output_dir=stage4_dir)
            
            # For demo, only create clip for first segment
            print("\n⚠ Creating clip for first segment only (for demo)")
            segment = segments[0]
            
            # Note: This will prompt for media URL
            stage4_result = stage4_tester.test_create_clip(
                media_path=original_path,
                start_time=segment['start_time'],
                end_time=segment['end_time'],
                wait_for_completion=True,
                download=False
            )
            
            results['stages']['stage4'] = {
                'success': stage4_result['success'],
                'render_id': stage4_result.get('render_id'),
                'error': stage4_result.get('error')
            }
        else:
            print(f"\n{'*'*70}")
            print("STAGE 4: SKIPPED (use --create-clips to enable)")
            print(f"{'*'*70}")
            results['stages']['stage4'] = {'skipped': True}
        
        # Save summary
        self._save_run_summary(results)
        
        # Print summary
        self._print_summary(results)
        
        return results
    
    def _save_run_summary(self, results):
        """Save run summary to JSON"""
        summary_path = os.path.join(self.run_dir, 'run_summary.json')
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n✓ Run summary saved to: {summary_path}")
    
    def _print_summary(self, results):
        """Print test run summary"""
        print(f"\n{'='*70}")
        print("TEST RUN SUMMARY")
        print(f"{'='*70}")
        print(f"Run ID: {results['run_id']}")
        print(f"Input: {results['input_file']}")
        print(f"Timestamp: {results['timestamp']}")
        print(f"\nStage Results:")
        
        for stage_name, stage_result in results['stages'].items():
            if stage_result.get('skipped'):
                print(f"  {stage_name.upper()}: SKIPPED")
            elif stage_result.get('success'):
                print(f"  {stage_name.upper()}: ✓ SUCCESS")
                if 'processing_time' in stage_result:
                    print(f"    Time: {stage_result['processing_time']:.2f}s")
                if 'num_segments' in stage_result:
                    print(f"    Segments: {stage_result['num_segments']}")
            else:
                print(f"  {stage_name.upper()}: ✗ FAILED")
                if 'error' in stage_result:
                    print(f"    Error: {stage_result['error']}")


def main():
    parser = argparse.ArgumentParser(description='Integrated Test Runner')
    parser.add_argument('--input', help='Input video or audio file')
    parser.add_argument('--audio', help='Input audio file (skip Stage 1)')
    parser.add_argument('--all-stages', action='store_true',
                       help='Run all stages')
    parser.add_argument('--stages', nargs='+', type=int,
                       help='Specific stages to run (e.g., 1 2 3)')
    parser.add_argument('--num-segments', type=int, default=3,
                       help='Number of segments to identify (default: 3)')
    parser.add_argument('--max-duration', type=int, default=300,
                       help='Maximum segment duration in seconds (default: 300s = 5 minutes)')
    parser.add_argument('--create-clips', action='store_true',
                       help='Actually create clips in Stage 4 (requires media URL)')
    parser.add_argument('--output-dir', default='./test_outputs',
                       help='Base output directory')
    
    args = parser.parse_args()
    
    # Initialize runner
    runner = IntegratedTestRunner(output_base_dir=args.output_dir)
    
    # Validate inputs
    if args.all_stages and not args.input:
        print("Error: --input required when using --all-stages")
        return
    
    # Run complete pipeline
    if args.all_stages or args.input:
        input_file = args.input
        runner.run_complete_pipeline(
            input_file,
            num_segments=args.num_segments,
            max_duration=args.max_duration,
            create_clips=args.create_clips
        )
    else:
        parser.print_help()
        print("\nExample usage:")
        print("  python tests/test_runner.py --input video.mp4 --all-stages")
        print("  python tests/test_runner.py --input video.mp4 --all-stages --create-clips")
        print("  python tests/test_runner.py --input podcast.mp3 --num-segments 3 --max-duration 300")
        print("\nNote: LLM decides optimal segment length (max 5 minutes)")


if __name__ == '__main__':
    main()
