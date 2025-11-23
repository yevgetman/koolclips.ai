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
import sys
import time
from pathlib import Path
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor


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


class ProgressTracker:
    """Track upload progress with visual feedback"""
    
    def __init__(self, total_size):
        self.total_size = total_size
        self.bytes_uploaded = 0
        self.start_time = time.time()
        self.last_print_time = time.time()
        
    def update(self, bytes_uploaded):
        """Update progress and print if enough time has passed"""
        self.bytes_uploaded = bytes_uploaded
        
        current_time = time.time()
        # Update display every 0.3 seconds
        if current_time - self.last_print_time >= 0.3:
            self._print_progress()
            self.last_print_time = current_time
    
    def _print_progress(self):
        """Print upload progress bar"""
        if self.total_size == 0:
            return
        
        percent = (self.bytes_uploaded / self.total_size) * 100
        elapsed = time.time() - self.start_time
        
        # Calculate speed and ETA
        if elapsed > 0 and self.bytes_uploaded > 0:
            speed_mbps = (self.bytes_uploaded / elapsed) / (1024 * 1024)
            remaining_bytes = self.total_size - self.bytes_uploaded
            eta_seconds = remaining_bytes / (self.bytes_uploaded / elapsed)
        else:
            speed_mbps = 0
            eta_seconds = 0
        
        # Create progress bar
        bar_width = 40
        filled = int(bar_width * self.bytes_uploaded / self.total_size)
        bar = '█' * filled + '░' * (bar_width - filled)
        
        # Format sizes
        uploaded_mb = self.bytes_uploaded / (1024 * 1024)
        total_mb = self.total_size / (1024 * 1024)
        
        # Print progress (overwrite same line)
        sys.stdout.write(f'\r  [{bar}] {percent:.1f}% | {uploaded_mb:.1f}/{total_mb:.1f} MB | {speed_mbps:.2f} MB/s | ETA: {eta_seconds:.0f}s ')
        sys.stdout.flush()
    
    def finish(self):
        """Print final progress"""
        self._print_progress()
        print()  # New line after progress bar


def upload_to_s3(presigned_data, file_path):
    """
    Step 2: Upload file directly to S3 using presigned URL with progress tracking
    """
    print(f"\n{'='*70}")
    print(f"STEP 2: Uploading file to S3")
    print(f"{'='*70}")
    print(f"Upload URL: {presigned_data['upload_url'][:80]}...")
    
    file_size = os.path.getsize(file_path)
    print(f"File size: {file_size / (1024 * 1024):.2f} MB")
    print(f"\nUploading (this may take several minutes for large files)...")
    
    # Create progress tracker
    progress = ProgressTracker(file_size)
    
    def progress_callback(monitor):
        """Callback for upload progress"""
        progress.update(monitor.bytes_read)
    
    try:
        # Prepare multipart form data with streaming and progress tracking
        with open(file_path, 'rb') as f:
            # Prepare fields for S3 upload
            fields = presigned_data['upload_fields'].copy()
            fields['file'] = ('file', f)
            
            # Create multipart encoder with progress monitoring
            encoder = MultipartEncoder(fields=fields)
            monitor = MultipartEncoderMonitor(encoder, progress_callback)
            
            # Upload to S3 with streaming
            start_time = time.time()
            response = requests.post(
                presigned_data['upload_url'],
                data=monitor,
                headers={'Content-Type': monitor.content_type},
                timeout=1800  # 30 minutes for very large files
            )
            elapsed = time.time() - start_time
        
        # Finish progress display
        progress.finish()
        
        if response.status_code not in [200, 201, 204]:
            print(f"\n✗ Upload failed: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False
        
        print(f"\n✓ File uploaded successfully to S3!")
        print(f"  Total time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
        if elapsed > 0:
            print(f"  Average speed: {(file_size / elapsed) / (1024 * 1024):.2f} MB/s")
        return True
        
    except requests.exceptions.Timeout:
        print(f"\n\n✗ Upload timed out after 30 minutes")
        return False
    except ImportError:
        print(f"\n\n✗ Missing required library. Install with: pip install requests-toolbelt")
        return False
    except Exception as e:
        print(f"\n\n✗ Upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


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
