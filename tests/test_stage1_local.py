"""
Comprehensive Stage 1 Preprocessing Tests - LOCAL

Tests all demo files through the preprocessing service locally.
Results are saved to test_outputs/stage1/

Usage:
    python test_stage1_local.py
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from viral_clips.services.preprocessing_service import PreprocessingService
from viral_clips.utils import detect_file_type


class ComprehensiveStage1LocalTester:
    """Comprehensive test harness for Stage 1 preprocessing - LOCAL"""
    
    def __init__(self, output_dir='./test_outputs/stage1'):
        self.output_dir = output_dir
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        self.service = PreprocessingService(output_dir=self.output_dir)
        self.results = []
        
    def test_file(self, file_path):
        """Test preprocessing a single file"""
        filename = os.path.basename(file_path)
        print(f"\n{'='*70}")
        print(f"Testing: {filename}")
        print(f"{'='*70}")
        
        test_result = {
            'filename': filename,
            'file_path': file_path,
            'timestamp': datetime.now().isoformat(),
            'success': False,
            'error': None,
            'file_type': None,
            'preprocessing_result': None,
            'media_info': None
        }
        
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            file_size = os.path.getsize(file_path)
            print(f"Input file size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
            
            # Detect file type
            file_type = detect_file_type(file_path)
            test_result['file_type'] = file_type
            print(f"Detected file type: {file_type}")
            
            if file_type == 'unknown':
                raise ValueError("Unsupported file type")
            
            # Get media info
            print("\nRetrieving media information...")
            media_info = self.service.get_media_info(file_path)
            test_result['media_info'] = media_info
            print(f"  Duration: {media_info['duration']:.2f}s ({media_info['duration']/60:.2f} min)")
            print(f"  Format: {media_info['format']}")
            print(f"  Has audio: {media_info['has_audio']}")
            print(f"  Has video: {media_info['has_video']}")
            
            # Process the file
            print("\nProcessing media file...")
            result = self.service.process_media_file(file_path)
            test_result['preprocessing_result'] = result
            
            print(f"\n✓ Processing successful!")
            print(f"\nResults:")
            print(f"  Audio path: {result['audio_path']}")
            print(f"  File type: {result['file_type']}")
            print(f"  Audio extracted: {result['extracted']}")
            
            # Verify output file exists
            if result['extracted']:
                if not os.path.exists(result['audio_path']):
                    raise RuntimeError("Output audio file does not exist!")
                
                output_size = os.path.getsize(result['audio_path'])
                print(f"  Output audio size: {output_size:,} bytes ({output_size / 1024 / 1024:.2f} MB)")
            else:
                print(f"  (Audio file passed through without extraction)")
            
            test_result['success'] = True
            print(f"\n✓ Test PASSED for {filename}")
            
        except Exception as e:
            print(f"\n✗ Test FAILED: {str(e)}")
            test_result['error'] = str(e)
            test_result['success'] = False
        
        self.results.append(test_result)
        return test_result
    
    def run_all_tests(self, demo_files_dir='./demo_files'):
        """Run tests on all media files in demo_files directory"""
        print("\n" + "="*70)
        print("STAGE 1 PREPROCESSING - LOCAL COMPREHENSIVE TEST")
        print("="*70)
        print(f"Output directory: {self.output_dir}")
        print(f"Demo files directory: {demo_files_dir}")
        
        # Get all media files
        media_extensions = {'.mp4', '.mp3', '.mov', '.avi', '.wav', '.m4a'}
        demo_path = Path(demo_files_dir)
        
        if not demo_path.exists():
            print(f"\n✗ Error: Demo files directory not found: {demo_files_dir}")
            return
        
        media_files = [
            f for f in demo_path.iterdir()
            if f.is_file() and f.suffix.lower() in media_extensions
        ]
        
        if not media_files:
            print(f"\n✗ Error: No media files found in {demo_files_dir}")
            return
        
        print(f"\nFound {len(media_files)} media files to test:")
        for f in media_files:
            size_mb = f.stat().st_size / 1024 / 1024
            print(f"  - {f.name} ({size_mb:.2f} MB)")
        
        # Test each file
        for media_file in sorted(media_files):
            self.test_file(str(media_file))
        
        # Generate summary report
        self.generate_report()
    
    def generate_report(self):
        """Generate comprehensive test report"""
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"\nTotal tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success rate: {(passed_tests/total_tests*100):.1f}%")
        
        if failed_tests > 0:
            print(f"\nFailed tests:")
            for result in self.results:
                if not result['success']:
                    print(f"  ✗ {result['filename']}: {result['error']}")
        
        # Save detailed report to JSON
        report_file = os.path.join(self.output_dir, 'test_report_local.json')
        report_data = {
            'test_info': {
                'test_type': 'stage1_preprocessing_local',
                'timestamp': datetime.now().isoformat(),
                'environment': 'local',
                'output_dir': self.output_dir
            },
            'summary': {
                'total_tests': total_tests,
                'passed': passed_tests,
                'failed': failed_tests,
                'success_rate': f"{(passed_tests/total_tests*100):.1f}%"
            },
            'test_results': self.results
        }
        
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        print(f"\n✓ Detailed report saved to: {report_file}")
        
        print("\n" + "="*70)
        if failed_tests == 0:
            print("✓ ALL TESTS PASSED!")
        else:
            print(f"⚠ {failed_tests} TEST(S) FAILED")
        print("="*70 + "\n")


def main():
    """Main test execution"""
    tester = ComprehensiveStage1LocalTester(output_dir='./test_outputs/stage1')
    tester.run_all_tests(demo_files_dir='./demo_files')


if __name__ == '__main__':
    main()
