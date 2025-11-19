"""
Example script showing how to use the Viral Clips API programmatically
"""

import requests
import time

# Configuration
API_BASE_URL = "http://localhost:8000/api"
VIDEO_FILE_PATH = "/path/to/your/video.mp4"


def create_job(video_path, num_segments=5, min_duration=60, max_duration=180):
    """Create a new video processing job"""
    
    url = f"{API_BASE_URL}/jobs/"
    
    with open(video_path, 'rb') as video_file:
        files = {'video_file': video_file}
        data = {
            'num_segments': num_segments,
            'min_duration': min_duration,
            'max_duration': max_duration
        }
        
        response = requests.post(url, files=files, data=data)
        response.raise_for_status()
        
        return response.json()


def get_job_status(job_id):
    """Get the status of a job"""
    
    url = f"{API_BASE_URL}/jobs/{job_id}/status/"
    response = requests.get(url)
    response.raise_for_status()
    
    return response.json()


def get_completed_clips(job_id):
    """Get all completed clips for a job"""
    
    url = f"{API_BASE_URL}/jobs/{job_id}/clips/"
    response = requests.get(url)
    response.raise_for_status()
    
    return response.json()


def wait_for_completion(job_id, max_wait=600, check_interval=10):
    """Wait for a job to complete"""
    
    elapsed = 0
    
    while elapsed < max_wait:
        status_data = get_job_status(job_id)
        status = status_data['status']
        
        print(f"Status: {status}")
        
        if status == 'completed':
            print("✓ Processing completed!")
            return status_data
        elif status == 'failed':
            error = status_data.get('error_message', 'Unknown error')
            print(f"✗ Processing failed: {error}")
            return status_data
        
        time.sleep(check_interval)
        elapsed += check_interval
    
    print(f"Timeout after {max_wait} seconds")
    return None


def main():
    """Main example workflow"""
    
    print("=" * 60)
    print("Viral Clips - Example API Usage")
    print("=" * 60)
    
    # Step 1: Create a job
    print("\n1. Creating video processing job...")
    job = create_job(VIDEO_FILE_PATH, num_segments=5)
    job_id = job['id']
    print(f"✓ Job created: {job_id}")
    
    # Step 2: Wait for completion
    print("\n2. Waiting for processing to complete...")
    result = wait_for_completion(job_id)
    
    if result and result['status'] == 'completed':
        # Step 3: Get clips
        print("\n3. Retrieving completed clips...")
        clips_data = get_completed_clips(job_id)
        
        print(f"\n✓ Found {clips_data['total_clips']} clips:")
        for i, clip in enumerate(clips_data['clips'], 1):
            print(f"\n{i}. {clip['segment_title']}")
            print(f"   Duration: {clip['duration']:.1f}s")
            print(f"   URL: {clip['video_url']}")
        
        print("\n" + "=" * 60)
        print("Processing complete!")
        print("=" * 60)


if __name__ == '__main__':
    main()
