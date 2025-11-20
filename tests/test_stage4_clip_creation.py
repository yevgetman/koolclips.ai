"""
Test Stage 4: Clip Creation (Original Media + Timestamps → Video Clip)

Tests the Shotstack service that:
- Accepts original audio or video file
- Accepts timestamps for ONE segment from Stage 3
- Creates a clipped segment from the original file via Shotstack API
- Returns the rendered clip URL/file

Usage:
    python tests/test_stage4_clip_creation.py <original_file> <start_time> <end_time>
    
    Or test with JSON output from Stage 3:
    python tests/test_stage4_clip_creation.py --from-stage3 test_outputs/stage3/segments.json --segment-index 0
    
    Or test a complete pipeline:
    python tests/test_stage4_clip_creation.py --from-stage1 test_outputs/stage1/result.json --from-stage3 test_outputs/stage3/segments.json
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

from viral_clips.services.shotstack_service import ShotstackService
from viral_clips.utils import detect_file_type


class Stage4Tester:
    """Test harness for Stage 4: Clip Creation"""
    
    def __init__(self, output_dir=None):
        self.output_dir = output_dir or './test_outputs/stage4'
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        self.service = ShotstackService()
        
        print(f"Shotstack environment: {self.service.env}")
        print(f"Shotstack stage: {self.service.stage}")
    
    def test_create_clip(self, media_path, start_time, end_time, 
                        wait_for_completion=True, download=False):
        """
        Test creating a clip from a media file
        
        Args:
            media_path: Path to original video or audio file
            start_time: Start time in seconds
            end_time: End time in seconds
            wait_for_completion: Whether to wait for render to complete
            download: Whether to download the completed clip
            
        Returns:
            dict: Test results
        """
        print(f"\n{'='*60}")
        print(f"STAGE 4 TEST: Create Clip")
        print(f"{'='*60}")
        print(f"Media file: {media_path}")
        print(f"Start time: {start_time}s")
        print(f"End time: {end_time}s")
        print(f"Duration: {end_time - start_time}s")
        
        # Check if media_path is a URL or local file
        is_url = media_path.startswith('http://') or media_path.startswith('https://')
        
        if not is_url and not os.path.exists(media_path):
            print(f"\n✗ Error: Media file not found: {media_path}")
            return {
                'success': False,
                'render_id': None,
                'error': 'File not found'
            }
        
        # Detect file type (skip for URLs - assume video unless specified)
        if is_url:
            # For URLs, assume video by default
            file_type = 'video'
            is_audio_only = False
            print(f"Media type: URL (assumed video)")
        else:
            file_type = detect_file_type(media_path)
            is_audio_only = (file_type == 'audio')
            print(f"File type: {file_type}")
            print(f"Audio only: {is_audio_only}")
        
        try:
            # For testing, we need a publicly accessible URL
            # If media_path is already a URL, use it directly
            # Otherwise, ask for a URL
            
            if is_url:
                media_url = media_path
                print(f"\n✓ Using provided URL: {media_url}")
            else:
                print(f"\n⚠ Note: Shotstack requires a publicly accessible URL")
                print(f"For testing, you can:")
                print(f"  1. Upload the file to a cloud storage service")
                print(f"  2. Use a local file server with ngrok")
                print(f"  3. Use the Django media URL (if server is running)")
                
                # Ask for media URL
                media_url = input(f"\nEnter publicly accessible URL for {media_path}: ").strip()
                
                if not media_url:
                    print(f"\n✗ No URL provided. Test cannot proceed.")
                    return {
                        'success': False,
                        'render_id': None,
                        'error': 'No media URL provided'
                    }
            
            # Create clip
            print(f"\nCreating clip via Shotstack...")
            start_request_time = datetime.now()
            
            render_id = self.service.create_clip(
                media_url=media_url,
                start_time=start_time,
                end_time=end_time,
                is_audio_only=is_audio_only
            )
            
            print(f"\n✓ Clip creation initiated!")
            print(f"  Render ID: {render_id}")
            
            # Save render info
            render_info = {
                'render_id': render_id,
                'media_path': media_path,
                'media_url': media_url,
                'start_time': start_time,
                'end_time': end_time,
                'duration': end_time - start_time,
                'file_type': file_type,
                'is_audio_only': is_audio_only,
                'timestamp': datetime.now().isoformat()
            }
            
            output_file = self._save_render_info(render_info)
            print(f"  Render info saved to: {output_file}")
            
            # Wait for completion if requested
            if wait_for_completion:
                print(f"\nWaiting for render to complete...")
                status = self.service.wait_for_render(render_id, max_wait=300, check_interval=10)
                
                end_request_time = datetime.now()
                total_time = (end_request_time - start_request_time).total_seconds()
                
                print(f"\n✓ Render completed!")
                print(f"  Total time: {total_time:.2f} seconds")
                print(f"  Video URL: {status['url']}")
                
                render_info['status'] = status
                render_info['total_time'] = total_time
                
                # Update saved info
                self._save_render_info(render_info)
                
                # Download if requested
                if download and status['url']:
                    download_path = self._download_clip(status['url'], render_id)
                    render_info['download_path'] = download_path
                    self._save_render_info(render_info)
                
                return {
                    'success': True,
                    'render_id': render_id,
                    'status': status,
                    'total_time': total_time,
                    'error': None
                }
            else:
                return {
                    'success': True,
                    'render_id': render_id,
                    'status': 'pending',
                    'error': None
                }
            
        except Exception as e:
            print(f"\n✗ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'render_id': None,
                'error': str(e)
            }
    
    def test_check_render_status(self, render_id):
        """
        Test checking the status of a render
        
        Args:
            render_id: Render ID from create_clip
            
        Returns:
            dict: Status information
        """
        print(f"\n{'='*60}")
        print(f"STAGE 4 TEST: Check Render Status")
        print(f"{'='*60}")
        print(f"Render ID: {render_id}")
        
        try:
            status = self.service.get_render_status(render_id)
            
            print(f"\n✓ Status retrieved!")
            print(f"  Status: {status['status']}")
            print(f"  Progress: {status.get('progress', 0)}%")
            if status.get('url'):
                print(f"  URL: {status['url']}")
            if status.get('error'):
                print(f"  Error: {status['error']}")
            
            return {
                'success': True,
                'status': status,
                'error': None
            }
            
        except Exception as e:
            print(f"\n✗ Error: {str(e)}")
            return {
                'success': False,
                'status': None,
                'error': str(e)
            }
    
    def _download_clip(self, video_url, render_id):
        """Download a clip from Shotstack"""
        print(f"\nDownloading clip...")
        
        download_filename = f"clip_{render_id}.mp4"
        download_path = os.path.join(self.output_dir, download_filename)
        
        self.service.download_clip(video_url, download_path)
        
        file_size = os.path.getsize(download_path)
        print(f"✓ Downloaded: {download_path}")
        print(f"  Size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
        
        return download_path
    
    def _save_render_info(self, render_info):
        """Save render information to JSON file"""
        output_filename = f"render_{render_info['render_id']}.json"
        output_path = os.path.join(self.output_dir, output_filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(render_info, f, indent=2, ensure_ascii=False)
        
        return output_path
    
    def test_from_stage3_output(self, stage3_json_path, stage1_json_path=None,
                                segment_index=0, wait=True, download=False):
        """
        Test using output from Stage 3 (and optionally Stage 1)
        
        Args:
            stage3_json_path: Path to Stage 3 output JSON (segments)
            stage1_json_path: Path to Stage 1 output JSON (original media path)
            segment_index: Which segment to create clip for (0-based)
            wait: Whether to wait for render completion
            download: Whether to download the clip
            
        Returns:
            dict: Test results
        """
        print(f"\n{'='*60}")
        print(f"STAGE 4 TEST: Process Stage 3 Output")
        print(f"{'='*60}")
        print(f"Stage 3 output: {stage3_json_path}")
        if stage1_json_path:
            print(f"Stage 1 output: {stage1_json_path}")
        print(f"Segment index: {segment_index}")
        
        try:
            # Load Stage 3 output
            with open(stage3_json_path, 'r', encoding='utf-8') as f:
                stage3_data = json.load(f)
            
            segments = stage3_data.get('segments')
            if not segments:
                raise ValueError("No segments found in Stage 3 output")
            
            if segment_index >= len(segments):
                raise ValueError(f"Segment index {segment_index} out of range (max: {len(segments)-1})")
            
            segment = segments[segment_index]
            print(f"\nSelected segment: {segment['title']}")
            print(f"  Time: {segment['start_time']:.2f}s - {segment['end_time']:.2f}s")
            print(f"  Duration: {segment['duration']:.2f}s")
            
            # Get media path
            media_path = None
            if stage1_json_path:
                with open(stage1_json_path, 'r') as f:
                    stage1_data = json.load(f)
                media_path = stage1_data.get('original_path')
            
            if not media_path:
                media_path = input("\nEnter path to original media file: ").strip()
            
            if not media_path or not os.path.exists(media_path):
                raise ValueError(f"Media file not found: {media_path}")
            
            print(f"Media file: {media_path}")
            
            # Create clip
            return self.test_create_clip(
                media_path=media_path,
                start_time=segment['start_time'],
                end_time=segment['end_time'],
                wait_for_completion=wait,
                download=download
            )
            
        except Exception as e:
            print(f"\n✗ Error: {str(e)}")
            return {
                'success': False,
                'render_id': None,
                'error': str(e)
            }
    
    def test_create_all_clips(self, stage3_json_path, stage1_json_path,
                             wait=False, download=False):
        """
        Test creating clips for all segments from Stage 3
        
        Args:
            stage3_json_path: Path to Stage 3 output JSON
            stage1_json_path: Path to Stage 1 output JSON
            wait: Whether to wait for each render
            download: Whether to download clips
            
        Returns:
            list: Results for each segment
        """
        print(f"\n{'='*60}")
        print(f"STAGE 4 TEST: Create All Clips")
        print(f"{'='*60}")
        
        try:
            # Load segments
            with open(stage3_json_path, 'r') as f:
                stage3_data = json.load(f)
            segments = stage3_data.get('segments', [])
            
            print(f"Creating clips for {len(segments)} segments...")
            
            results = []
            for i, segment in enumerate(segments):
                print(f"\n{'='*60}")
                print(f"Segment {i+1}/{len(segments)}: {segment['title']}")
                print(f"{'='*60}")
                
                result = self.test_from_stage3_output(
                    stage3_json_path,
                    stage1_json_path,
                    segment_index=i,
                    wait=wait,
                    download=download
                )
                
                results.append({
                    'segment_index': i,
                    'segment_title': segment['title'],
                    'result': result
                })
            
            # Summary
            print(f"\n{'='*60}")
            print(f"SUMMARY")
            print(f"{'='*60}")
            successful = sum(1 for r in results if r['result']['success'])
            print(f"Total segments: {len(segments)}")
            print(f"Successful: {successful}")
            print(f"Failed: {len(segments) - successful}")
            
            return results
            
        except Exception as e:
            print(f"\n✗ Error: {str(e)}")
            return []


def main():
    parser = argparse.ArgumentParser(description='Test Stage 4: Clip Creation')
    parser.add_argument('media_file', nargs='?', help='Original media file')
    parser.add_argument('start_time', nargs='?', type=float, help='Start time in seconds')
    parser.add_argument('end_time', nargs='?', type=float, help='End time in seconds')
    parser.add_argument('--from-stage3', help='Use output JSON from Stage 3')
    parser.add_argument('--from-stage1', help='Use output JSON from Stage 1 (for media path)')
    parser.add_argument('--segment-index', type=int, default=0,
                       help='Which segment to create clip for (default: 0)')
    parser.add_argument('--all-segments', action='store_true',
                       help='Create clips for all segments from Stage 3')
    parser.add_argument('--check-status', help='Check status of a render by ID')
    parser.add_argument('--no-wait', action='store_true',
                       help='Do not wait for render completion')
    parser.add_argument('--download', action='store_true',
                       help='Download completed clips')
    parser.add_argument('--output-dir', default='./test_outputs/stage4',
                       help='Output directory for test results')
    
    args = parser.parse_args()
    
    # Initialize tester
    tester = Stage4Tester(output_dir=args.output_dir)
    
    # Run tests
    if args.check_status:
        tester.test_check_render_status(args.check_status)
    elif args.all_segments and args.from_stage3 and args.from_stage1:
        tester.test_create_all_clips(
            args.from_stage3,
            args.from_stage1,
            wait=not args.no_wait,
            download=args.download
        )
    elif args.from_stage3:
        tester.test_from_stage3_output(
            args.from_stage3,
            args.from_stage1,
            segment_index=args.segment_index,
            wait=not args.no_wait,
            download=args.download
        )
    elif args.media_file and args.start_time is not None and args.end_time is not None:
        tester.test_create_clip(
            args.media_file,
            args.start_time,
            args.end_time,
            wait_for_completion=not args.no_wait,
            download=args.download
        )
    else:
        parser.print_help()
        print("\nExample usage:")
        print("  python tests/test_stage4_clip_creation.py video.mp4 10.5 45.2")
        print("  python tests/test_stage4_clip_creation.py --from-stage3 test_outputs/stage3/segments.json --segment-index 0")
        print("  python tests/test_stage4_clip_creation.py --from-stage3 test_outputs/stage3/segments.json --from-stage1 test_outputs/stage1/result.json")
        print("  python tests/test_stage4_clip_creation.py --check-status <render_id>")


if __name__ == '__main__':
    main()
