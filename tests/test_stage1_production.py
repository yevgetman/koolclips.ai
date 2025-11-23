"""
Comprehensive Stage 1 Preprocessing Tests - PRODUCTION

Tests all demo files through the production API and Celery tasks.
Files are uploaded to cloud storage and processed through the full pipeline.

Usage:
    # Test against local development server
    python test_stage1_production.py --local
    
    # Test against production server
    python test_stage1_production.py --url https://your-app.herokuapp.com
    
    # Test specific files only
    python test_stage1_production.py --files test_video_10s.mp4 test_audio.mp3
"""

import sys
import os
import json
import time
import argparse
import requests
from pathlib import Path
from datetime import datetime


class ComprehensiveStage1ProductionTester:
    """Comprehensive test harness for Stage 1 preprocessing - PRODUCTION"""
    
    def __init__(self, api_base_url, output_dir='./test_outputs/stage1'):
        self.api_base_url = api_base_url.rstrip('/')
        self.output_dir = output_dir
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        self.results = []
        
    def upload_file(self, file_path):
        """Upload a file to the API and trigger preprocessing"""
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
            'job_id': None,
            'upload_time': None,
            'preprocessing_status': None,
            'preprocessing_result': None
        }
        
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            file_size = os.path.getsize(file_path)
            print(f"File size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
            
            # Upload file
            print(f"\nUploading to {self.api_base_url}...")
            url = f"{self.api_base_url}/api/jobs/"
            
            start_time = time.time()
            with open(file_path, 'rb') as f:
                files = {'media_file': (filename, f)}
                data = {
                    'num_segments': 3,  # Just for testing preprocessing
                    'min_duration': 60,
                    'max_duration': 120
                }
                
                response = requests.post(url, files=files, data=data, timeout=300)
            
            upload_time = time.time() - start_time
            test_result['upload_time'] = f"{upload_time:.2f}s"
            
            if response.status_code != 201:
                raise Exception(f"Upload failed: {response.status_code} - {response.text}")
            
            job_data = response.json()
            job_id = job_data['id']
            test_result['job_id'] = job_id
            
            print(f"✓ Upload successful! Job ID: {job_id}")
            print(f"  Upload time: {upload_time:.2f}s")
            print(f"  Initial status: {job_data.get('status', 'unknown')}")
            
            # Monitor preprocessing status
            print(f"\nMonitoring preprocessing status...")
            preprocessing_result = self.wait_for_preprocessing(job_id)
            test_result['preprocessing_result'] = preprocessing_result
            
            if preprocessing_result['success']:
                test_result['success'] = True
                test_result['preprocessing_status'] = preprocessing_result['final_status']
                print(f"\n✓ Test PASSED for {filename}")
            else:
                test_result['error'] = preprocessing_result.get('error', 'Unknown error')
                test_result['preprocessing_status'] = preprocessing_result.get('final_status', 'unknown')
                print(f"\n✗ Test FAILED for {filename}: {test_result['error']}")
            
        except Exception as e:
            print(f"\n✗ Test FAILED: {str(e)}")
            test_result['error'] = str(e)
            test_result['success'] = False
        
        self.results.append(test_result)
        return test_result
    
    def wait_for_preprocessing(self, job_id, max_wait=600, check_interval=5):
        """Wait for preprocessing stage to complete"""
        elapsed = 0
        
        while elapsed < max_wait:
            try:
                # Get job status
                url = f"{self.api_base_url}/api/jobs/{job_id}/status/"
                response = requests.get(url, timeout=30)
                
                if response.status_code != 200:
                    print(f"  Warning: Status check failed: {response.status_code}")
                    time.sleep(check_interval)
                    elapsed += check_interval
                    continue
                
                status_data = response.json()
                status = status_data.get('status', 'unknown')
                
                print(f"  Status: {status} (elapsed: {elapsed}s)")
                
                # Check if preprocessing is complete
                if status == 'transcribing':
                    # Preprocessing completed, moved to transcription
                    print(f"  ✓ Preprocessing completed! Job moved to transcription.")
                    return {
                        'success': True,
                        'final_status': status,
                        'elapsed_time': elapsed,
                        'status_data': status_data
                    }
                elif status == 'failed':
                    error_msg = status_data.get('error_message', 'Unknown error')
                    print(f"  ✗ Job failed: {error_msg}")
                    return {
                        'success': False,
                        'final_status': status,
                        'error': error_msg,
                        'elapsed_time': elapsed
                    }
                elif status in ['completed', 'analyzing', 'clipping']:
                    # Job progressed past preprocessing
                    print(f"  ✓ Job progressed past preprocessing (current: {status})")
                    return {
                        'success': True,
                        'final_status': status,
                        'elapsed_time': elapsed,
                        'status_data': status_data
                    }
                
                # Still in preprocessing or pending
                time.sleep(check_interval)
                elapsed += check_interval
                
            except Exception as e:
                print(f"  Error checking status: {str(e)}")
                time.sleep(check_interval)
                elapsed += check_interval
        
        # Timeout
        print(f"  ⚠ Timeout after {max_wait}s")
        return {
            'success': False,
            'final_status': 'timeout',
            'error': f'Preprocessing did not complete within {max_wait}s',
            'elapsed_time': elapsed
        }
    
    def run_all_tests(self, demo_files_dir='./demo_files', specific_files=None):
        """Run tests on all media files in demo_files directory"""
        print("\n" + "="*70)
        print("STAGE 1 PREPROCESSING - PRODUCTION COMPREHENSIVE TEST")
        print("="*70)
        print(f"API Base URL: {self.api_base_url}")
        print(f"Demo files directory: {demo_files_dir}")
        
        # Get all media files
        media_extensions = {'.mp4', '.mp3', '.mov', '.avi', '.wav', '.m4a'}
        demo_path = Path(demo_files_dir)
        
        if not demo_path.exists():
            print(f"\n✗ Error: Demo files directory not found: {demo_files_dir}")
            return
        
        if specific_files:
            media_files = [demo_path / f for f in specific_files if (demo_path / f).exists()]
            print(f"\nTesting specific files: {specific_files}")
        else:
            media_files = [
                f for f in demo_path.iterdir()
                if f.is_file() and f.suffix.lower() in media_extensions
            ]
        
        if not media_files:
            print(f"\n✗ Error: No media files found")
            return
        
        print(f"\nFound {len(media_files)} media files to test:")
        for f in media_files:
            size_mb = f.stat().st_size / 1024 / 1024
            print(f"  - {f.name} ({size_mb:.2f} MB)")
        
        # Test each file
        for media_file in sorted(media_files):
            self.upload_file(str(media_file))
            # Small delay between uploads to avoid overwhelming the server
            time.sleep(2)
        
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
        
        if passed_tests > 0:
            print(f"\nSuccessful uploads:")
            for result in self.results:
                if result['success']:
                    print(f"  ✓ {result['filename']}")
                    print(f"    Job ID: {result['job_id']}")
                    print(f"    Upload time: {result['upload_time']}")
                    if result.get('preprocessing_result'):
                        elapsed = result['preprocessing_result'].get('elapsed_time', 'N/A')
                        print(f"    Preprocessing time: {elapsed}s")
        
        if failed_tests > 0:
            print(f"\nFailed tests:")
            for result in self.results:
                if not result['success']:
                    print(f"  ✗ {result['filename']}: {result['error']}")
        
        # Save detailed report to JSON
        report_file = os.path.join(self.output_dir, 'test_report_production.json')
        report_data = {
            'test_info': {
                'test_type': 'stage1_preprocessing_production',
                'timestamp': datetime.now().isoformat(),
                'environment': 'production',
                'api_base_url': self.api_base_url,
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
        
        # Try to upload report to cloud storage if API is available
        try:
            print(f"\nUploading test report to cloud storage...")
            url = f"{self.api_base_url}/api/test-results/upload/"
            response = requests.post(url, json=report_data, timeout=30)
            
            if response.status_code == 201:
                upload_result = response.json()
                print(f"✓ Report uploaded to: {upload_result.get('public_url', 'N/A')}")
            else:
                print(f"⚠ Report upload failed: {response.status_code}")
        except Exception as e:
            print(f"⚠ Could not upload report to cloud: {str(e)}")
        
        print("\n" + "="*70)
        if failed_tests == 0:
            print("✓ ALL TESTS PASSED!")
        else:
            print(f"⚠ {failed_tests} TEST(S) FAILED")
        print("="*70 + "\n")


def main():
    """Main test execution"""
    parser = argparse.ArgumentParser(description='Test Stage 1: Preprocessing (Production)')
    parser.add_argument('--local', action='store_true', help='Test against local development server')
    parser.add_argument('--url', help='API base URL (e.g., https://your-app.herokuapp.com)')
    parser.add_argument('--files', nargs='+', help='Specific files to test (optional)')
    parser.add_argument('--demo-dir', default='./demo_files', help='Demo files directory')
    
    args = parser.parse_args()
    
    # Determine API URL
    if args.local:
        api_url = 'http://localhost:8000'
    elif args.url:
        api_url = args.url
    else:
        print("Error: Must specify either --local or --url")
        parser.print_help()
        sys.exit(1)
    
    tester = ComprehensiveStage1ProductionTester(
        api_base_url=api_url,
        output_dir='./test_outputs/stage1'
    )
    
    tester.run_all_tests(
        demo_files_dir=args.demo_dir,
        specific_files=args.files
    )


if __name__ == '__main__':
    main()
