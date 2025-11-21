#!/usr/bin/env python3
"""
Test Stage 1 against production Heroku app
Tests job creation and initial preprocessing
"""

import requests
import time
import sys
import os

# Production API Configuration
API_BASE_URL = "https://koolclips-ed69bc2e07f2.herokuapp.com/api"
VIDEO_FILE_PATH = "/Users/yev/Sites/viral-clips/demo_files/diazreport2.mp4"


def test_api_health():
    """Test if the API is accessible"""
    print(f"\n{'='*60}")
    print("TESTING: API Health Check")
    print(f"{'='*60}")
    
    try:
        # Try to access the API root
        response = requests.get(f"{API_BASE_URL}/", timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✓ API is accessible")
            return True
        else:
            print(f"✗ API returned unexpected status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ Error accessing API: {str(e)}")
        return False


def create_job(video_path, num_segments=3, max_duration=300):
    """Create a new video processing job (Stage 1)"""
    print(f"\n{'='*60}")
    print("STAGE 1 TEST: Create Job")
    print(f"{'='*60}")
    print(f"API URL: {API_BASE_URL}/jobs/")
    print(f"Video: {video_path}")
    print(f"Segments: {num_segments}")
    print(f"Max duration: {max_duration}s ({max_duration/60:.1f} min)")
    print(f"Note: LLM decides optimal segment length based on content")
    
    try:
        # Check if video file exists
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        file_size = os.path.getsize(video_path)
        print(f"File size: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
        
        url = f"{API_BASE_URL}/jobs/"
        
        print("\nUploading video...")
        with open(video_path, 'rb') as video_file:
            files = {'video_file': video_file}
            data = {
                'num_segments': num_segments,
                'max_duration': max_duration
            }
            
            response = requests.post(url, files=files, data=data, timeout=120)
            
            print(f"Response Status: {response.status_code}")
            
            if response.status_code == 201:
                job_data = response.json()
                print(f"\n✓ Job created successfully!")
                print(f"\nJob Details:")
                print(f"  ID: {job_data['id']}")
                print(f"  Status: {job_data['status']}")
                print(f"  Created: {job_data['created_at']}")
                print(f"  Video URL: {job_data.get('video_url', 'N/A')}")
                
                return {
                    'success': True,
                    'job_data': job_data,
                    'error': None
                }
            else:
                error_msg = f"Status {response.status_code}: {response.text}"
                print(f"\n✗ Failed to create job: {error_msg}")
                return {
                    'success': False,
                    'job_data': None,
                    'error': error_msg
                }
                
    except Exception as e:
        print(f"\n✗ Error creating job: {str(e)}")
        return {
            'success': False,
            'job_data': None,
            'error': str(e)
        }


def get_job_status(job_id):
    """Get the current status of a job"""
    url = f"{API_BASE_URL}/jobs/{job_id}/status/"
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            return {
                'success': True,
                'data': response.json(),
                'error': None
            }
        else:
            return {
                'success': False,
                'data': None,
                'error': f"Status {response.status_code}: {response.text}"
            }
            
    except Exception as e:
        return {
            'success': False,
            'data': None,
            'error': str(e)
        }


def monitor_job(job_id, max_wait=60, check_interval=5):
    """Monitor job status for a limited time"""
    print(f"\n{'='*60}")
    print("MONITORING: Job Status")
    print(f"{'='*60}")
    print(f"Job ID: {job_id}")
    print(f"Max wait time: {max_wait}s")
    
    elapsed = 0
    
    while elapsed < max_wait:
        result = get_job_status(job_id)
        
        if result['success']:
            status_data = result['data']
            status = status_data['status']
            
            print(f"\n[{elapsed}s] Status: {status}")
            
            if 'current_stage' in status_data:
                print(f"  Current stage: {status_data['current_stage']}")
            
            if 'error_message' in status_data and status_data['error_message']:
                print(f"  Error: {status_data['error_message']}")
            
            if status in ['completed', 'failed']:
                print(f"\n✓ Job reached terminal state: {status}")
                return result
        else:
            print(f"\n✗ Error checking status: {result['error']}")
        
        time.sleep(check_interval)
        elapsed += check_interval
    
    print(f"\n⏱ Monitoring stopped after {max_wait}s")
    print("Note: Job may still be processing in the background")
    
    return get_job_status(job_id)


def main():
    print("=" * 60)
    print("STAGE 1 PRODUCTION TEST")
    print("Testing Heroku App: koolclips")
    print("=" * 60)
    
    # Step 1: Health check
    if not test_api_health():
        print("\n✗ API health check failed. Aborting test.")
        sys.exit(1)
    
    # Step 2: Create job (Stage 1)
    result = create_job(VIDEO_FILE_PATH, num_segments=3)
    
    if not result['success']:
        print("\n✗ Stage 1 test failed - could not create job")
        sys.exit(1)
    
    job_id = result['job_data']['id']
    
    # Step 3: Monitor job briefly
    print("\n" + "=" * 60)
    print("Monitoring job for 60 seconds...")
    print("=" * 60)
    
    final_result = monitor_job(job_id, max_wait=60)
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"✓ API Health: PASSED")
    print(f"✓ Job Creation: PASSED")
    print(f"  Job ID: {job_id}")
    
    if final_result['success']:
        status = final_result['data']['status']
        print(f"  Final Status: {status}")
        
        if status == 'completed':
            print("\n🎉 Stage 1 completed successfully!")
        elif status == 'failed':
            error = final_result['data'].get('error_message', 'Unknown')
            print(f"\n⚠️  Job failed: {error}")
        else:
            print(f"\n⏳ Job still processing (status: {status})")
            print(f"\nTo check job status later, run:")
            print(f"  curl {API_BASE_URL}/jobs/{job_id}/status/")
    
    print("=" * 60)


if __name__ == '__main__':
    main()
