"""
Test script for uploading large files using presigned S3 URLs

This script demonstrates the 2-step upload process:
1. Get a presigned URL from the API
2. Upload file directly to S3
3. Create job after upload completes

Usage:
    python test_large_file_upload.py --file demo_files/diazreport2.mp4 --url http://localhost:8000
    python test_large_file_upload.py --file demo_files/diazreport2.mp4 --url https://koolclips-ed69bc2e07f2.herokuapp.com
"""

import requests
import os
import argparse
import mimetypes
from pathlib import Path


def get_presigned_url(api_base_url, filename, file_size, content_type):
    """
    Step 1: Get presigned URL for direct S3 upload
    """
    url = f"{api_base_url}/api/upload/presigned-url/"
    
    data = {
        'filename': filename,
        'file_size': file_size,
        'content_type': content_type
    }
    
    print(f"\n{'='*70}")
    print(f"STEP 1: Requesting presigned upload URL")
    print(f"{'='*70}")
    print(f"API: {url}")
    print(f"File: {filename}")
    print(f"Size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
    print(f"Type: {content_type}")
    
    response = requests.post(url, json=data, timeout=30)
    
    if response.status_code != 200:
        print(f"\n✗ Failed to get presigned URL: {response.status_code}")
        print(response.text)
        return None
    
    result = response.json()
    
    if not result.get('success'):
        print(f"\n✗ Error: {result.get('error')}")
        return None
    
    print(f"\n✓ Presigned URL obtained!")
    print(f"Job ID: {result['job_id']}")
    print(f"S3 Key: {result['s3_key']}")
    print(f"Expires in: {result['expires_in']} seconds")
    
    return result


def upload_to_s3(presigned_data, file_path):
    """
    Step 2: Upload file directly to S3 using presigned URL
    """
    print(f"\n{'='*70}")
    print(f"STEP 2: Uploading file to S3")
    print(f"{'='*70}")
    print(f"Upload URL: {presigned_data['upload_url'][:80]}...")
    print(f"Starting upload...")
    
    # Prepare the multipart form data
    with open(file_path, 'rb') as f:
        files = {'file': f}
        fields = presigned_data['upload_fields']
        
        # Upload to S3
        response = requests.post(
            presigned_data['upload_url'],
            data=fields,
            files=files,
            timeout=600  # 10 minutes for large files
        )
    
    if response.status_code not in [200, 201, 204]:
        print(f"\n✗ Upload failed: {response.status_code}")
        print(response.text)
        return False
    
    print(f"\n✓ File uploaded successfully to S3!")
    return True


def create_job(api_base_url, presigned_data, num_segments=5):
    """
    Step 3: Create job after S3 upload completes
    """
    url = f"{api_base_url}/api/upload/create-job/"
    
    data = {
        'job_id': presigned_data['job_id'],
        's3_key': presigned_data['s3_key'],
        'file_type': presigned_data['file_type'],
        'num_segments': num_segments,
        'min_duration': 60,
        'max_duration': 300
    }
    
    print(f"\n{'='*70}")
    print(f"STEP 3: Creating processing job")
    print(f"{'='*70}")
    print(f"API: {url}")
    print(f"Job ID: {presigned_data['job_id']}")
    
    response = requests.post(url, json=data, timeout=30)
    
    if response.status_code != 201:
        print(f"\n✗ Failed to create job: {response.status_code}")
        print(response.text)
        return None
    
    result = response.json()
    
    print(f"\n✓ Job created successfully!")
    print(f"Job ID: {result['id']}")
    print(f"Status: {result['status']}")
    print(f"File type: {result['file_type']}")
    
    return result


def monitor_job(api_base_url, job_id, max_wait=600, check_interval=10):
    """
    Monitor job status until it completes or fails
    """
    import time
    
    print(f"\n{'='*70}")
    print(f"MONITORING JOB PROGRESS")
    print(f"{'='*70}")
    print(f"Job ID: {job_id}")
    print(f"Status URL: {api_base_url}/api/jobs/{job_id}/status/")
    
    url = f"{api_base_url}/api/jobs/{job_id}/status/"
    elapsed = 0
    
    while elapsed < max_wait:
        try:
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                status_data = response.json()
                status = status_data.get('status')
                
                print(f"\n[{elapsed}s] Status: {status}")
                
                if status == 'completed':
                    print(f"\n✓ Job completed!")
                    print(f"Total segments: {status_data.get('progress', {}).get('total_segments', 0)}")
                    print(f"Clips completed: {status_data.get('progress', {}).get('clips_completed', 0)}")
                    return status_data
                elif status == 'failed':
                    print(f"\n✗ Job failed: {status_data.get('error_message')}")
                    return status_data
                
                # Show progress
                progress = status_data.get('progress', {})
                if progress:
                    print(f"  Segments identified: {progress.get('segments_identified', 0)}")
                    print(f"  Clips completed: {progress.get('clips_completed', 0)}")
            
            time.sleep(check_interval)
            elapsed += check_interval
            
        except Exception as e:
            print(f"Error checking status: {str(e)}")
            time.sleep(check_interval)
            elapsed += check_interval
    
    print(f"\n⚠ Monitoring timeout after {max_wait}s")
    print(f"Job may still be processing. Check status at: {url}")
    return None


def main():
    parser = argparse.ArgumentParser(description='Test large file upload with presigned URLs')
    parser.add_argument('--file', required=True, help='Path to file to upload')
    parser.add_argument('--url', required=True, help='API base URL (e.g., http://localhost:8000)')
    parser.add_argument('--segments', type=int, default=5, help='Number of segments to create')
    parser.add_argument('--monitor', action='store_true', help='Monitor job progress after upload')
    
    args = parser.parse_args()
    
    # Validate file exists
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"✗ Error: File not found: {args.file}")
        return
    
    # Get file info
    filename = file_path.name
    file_size = file_path.stat().st_size
    content_type, _ = mimetypes.guess_type(str(file_path))
    
    api_base_url = args.url.rstrip('/')
    
    print("\n" + "="*70)
    print("LARGE FILE UPLOAD TEST - PRESIGNED URL METHOD")
    print("="*70)
    print(f"File: {filename}")
    print(f"Size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
    print(f"Type: {content_type}")
    print(f"API: {api_base_url}")
    print("="*70)
    
    # Step 1: Get presigned URL
    presigned_data = get_presigned_url(api_base_url, filename, file_size, content_type)
    if not presigned_data:
        return
    
    # Step 2: Upload to S3
    success = upload_to_s3(presigned_data, str(file_path))
    if not success:
        return
    
    # Step 3: Create job
    job = create_job(api_base_url, presigned_data, args.segments)
    if not job:
        return
    
    print("\n" + "="*70)
    print("✓ UPLOAD COMPLETE!")
    print("="*70)
    print(f"Job ID: {job['id']}")
    print(f"Status URL: {api_base_url}/api/jobs/{job['id']}/status/")
    print(f"Job is now processing in the background...")
    
    # Optionally monitor progress
    if args.monitor:
        monitor_job(api_base_url, job['id'])
    
    print("\n" + "="*70)


if __name__ == '__main__':
    main()
