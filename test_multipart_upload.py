"""
Test script for multipart upload of large files (up to 5GB)

This script uses S3 multipart upload with client-side chunking to upload
very large files without hitting timeout limits.

Usage:
    python test_multipart_upload.py --file demo_files/diazreport2.mp4 --url https://koolclips-ed69bc2e07f2.herokuapp.com
"""

import requests
import os
import argparse
import mimetypes
import sys
import time
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


class MultipartUploader:
    """Handle multipart uploads with progress tracking"""
    
    def __init__(self, api_base_url, file_path, part_size=200*1024*1024):
        """
        Args:
            api_base_url: Base URL of the API
            file_path: Path to file to upload
            part_size: Size of each part in bytes (default 200MB for faster uploads)
        """
        self.api_base_url = api_base_url.rstrip('/')
        self.file_path = file_path
        self.file_size = os.path.getsize(file_path)
        self.part_size = part_size
        self.num_parts = (self.file_size + part_size - 1) // part_size
        self.filename = os.path.basename(file_path)
        self.content_type, _ = mimetypes.guess_type(file_path)
        
        # Progress tracking
        self.bytes_uploaded = 0
        self.start_time = None
        self.last_print_time = 0
        
        # Upload state
        self.upload_id = None
        self.s3_key = None
        self.job_id = None
        self.file_type = None
        self.uploaded_parts = []
        
        # Thread safety
        self.progress_lock = threading.Lock()
        self.parts_lock = threading.Lock()
    
    def print_progress(self, force=False):
        """Print upload progress"""
        current_time = time.time()
        
        # Update every 0.5 seconds unless forced
        if not force and current_time - self.last_print_time < 0.5:
            return
        
        self.last_print_time = current_time
        
        percent = (self.bytes_uploaded / self.file_size) * 100
        elapsed = current_time - self.start_time
        
        # Calculate speed and ETA
        if elapsed > 0 and self.bytes_uploaded > 0:
            speed_mbps = (self.bytes_uploaded / elapsed) / (1024 * 1024)
            remaining_bytes = self.file_size - self.bytes_uploaded
            eta_seconds = remaining_bytes / (self.bytes_uploaded / elapsed)
        else:
            speed_mbps = 0
            eta_seconds = 0
        
        # Create progress bar
        bar_width = 40
        filled = int(bar_width * self.bytes_uploaded / self.file_size)
        bar = '█' * filled + '░' * (bar_width - filled)
        
        # Format sizes
        uploaded_mb = self.bytes_uploaded / (1024 * 1024)
        total_mb = self.file_size / (1024 * 1024)
        
        # Print progress (overwrite same line)
        sys.stdout.write(f'\r  [{bar}] {percent:.1f}% | {uploaded_mb:.1f}/{total_mb:.1f} MB | {speed_mbps:.2f} MB/s | ETA: {eta_seconds:.0f}s ')
        sys.stdout.flush()
    
    def initiate_upload(self):
        """Step 1: Initiate multipart upload"""
        print(f"\n{'='*70}")
        print(f"STEP 1: Initiating Multipart Upload")
        print(f"{'='*70}")
        print(f"File: {self.filename}")
        print(f"Size: {self.file_size:,} bytes ({self.file_size / 1024 / 1024:.2f} MB)")
        print(f"Parts: {self.num_parts} x {self.part_size / 1024 / 1024:.0f}MB")
        
        url = f"{self.api_base_url}/api/upload/multipart/initiate/"
        
        data = {
            'filename': self.filename,
            'file_size': self.file_size,
            'content_type': self.content_type,
            'part_size': self.part_size
        }
        
        response = requests.post(url, json=data, timeout=30)
        
        if response.status_code != 200:
            print(f"\n✗ Failed to initiate upload: {response.status_code}")
            print(response.text)
            return False
        
        result = response.json()
        
        if not result.get('success'):
            print(f"\n✗ Error: {result.get('error')}")
            return False
        
        self.upload_id = result['upload_id']
        self.s3_key = result['s3_key']
        self.job_id = result['job_id']
        self.file_type = result['file_type']
        
        print(f"\n✓ Upload initiated!")
        print(f"Upload ID: {self.upload_id}")
        print(f"Job ID: {self.job_id}")
        print(f"S3 Key: {self.s3_key}")
        
        return True
    
    def upload_parts(self, max_workers=10):
        """Step 2: Upload file parts in parallel"""
        print(f"\n{'='*70}")
        print(f"STEP 2: Uploading Parts (Parallel)")
        print(f"{'='*70}")
        print(f"Total parts: {self.num_parts}")
        print(f"Parallel workers: {max_workers}\n")
        
        self.start_time = time.time()
        self.bytes_uploaded = 0
        
        # Get all presigned URLs upfront
        print(f"Generating presigned URLs for all {self.num_parts} parts...")
        all_part_numbers = list(range(1, self.num_parts + 1))
        urls = self.get_part_urls(all_part_numbers)
        
        if not urls:
            print(f"\n✗ Failed to get presigned URLs")
            return False
        
        print(f"✓ Got {len(urls)} presigned URLs, starting parallel upload...\n")
        
        # Upload parts in parallel using ThreadPoolExecutor
        failed_parts = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all upload tasks
            future_to_part = {}
            for url_data in urls:
                part_number = url_data['part_number']
                presigned_url = url_data['url']
                future = executor.submit(self.upload_single_part, part_number, presigned_url)
                future_to_part[future] = part_number
            
            # Process completed uploads
            for future in as_completed(future_to_part):
                part_number = future_to_part[future]
                try:
                    success = future.result()
                    if not success:
                        failed_parts.append(part_number)
                except Exception as e:
                    print(f"\n✗ Exception uploading part {part_number}: {str(e)}")
                    failed_parts.append(part_number)
        
        # Final progress print
        self.print_progress(force=True)
        print()  # New line after progress bar
        
        if failed_parts:
            print(f"\n✗ Failed to upload {len(failed_parts)} parts: {failed_parts}")
            return False
        
        elapsed = time.time() - self.start_time
        print(f"\n✓ All parts uploaded successfully!")
        print(f"  Total time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
        print(f"  Average speed: {(self.file_size / elapsed) / (1024 * 1024):.2f} MB/s")
        
        return True
    
    def get_part_urls(self, part_numbers):
        """Get presigned URLs for specific parts"""
        url = f"{self.api_base_url}/api/upload/multipart/urls/"
        
        data = {
            'upload_id': self.upload_id,
            's3_key': self.s3_key,
            'part_numbers': part_numbers
        }
        
        try:
            response = requests.post(url, json=data, timeout=30)
            
            if response.status_code != 200:
                return None
            
            result = response.json()
            if not result.get('success'):
                return None
            
            return result['urls']
            
        except Exception as e:
            print(f"\n✗ Error getting part URLs: {str(e)}")
            return None
    
    def upload_single_part(self, part_number, presigned_url):
        """Upload a single part (thread-safe)"""
        # Calculate byte range for this part
        start_byte = (part_number - 1) * self.part_size
        end_byte = min(start_byte + self.part_size, self.file_size)
        part_data_size = end_byte - start_byte
        
        try:
            with open(self.file_path, 'rb') as f:
                f.seek(start_byte)
                part_data = f.read(part_data_size)
            
            # Upload part
            response = requests.put(
                presigned_url,
                data=part_data,
                timeout=300  # 5 minutes per part
            )
            
            if response.status_code not in [200, 201, 204]:
                return False
            
            # Extract ETag from response
            etag = response.headers.get('ETag', '').strip('"')
            
            # Store part info for completion (thread-safe)
            with self.parts_lock:
                self.uploaded_parts.append({
                    'PartNumber': part_number,
                    'ETag': etag
                })
            
            # Update progress (thread-safe)
            with self.progress_lock:
                self.bytes_uploaded += part_data_size
                self.print_progress()
            
            return True
            
        except Exception as e:
            print(f"\n✗ Error uploading part {part_number}: {str(e)}")
            return False
    
    def complete_upload(self):
        """Step 3: Complete multipart upload"""
        print(f"\n{'='*70}")
        print(f"STEP 3: Completing Upload")
        print(f"{'='*70}")
        
        url = f"{self.api_base_url}/api/upload/multipart/complete/"
        
        # Sort parts by part number
        self.uploaded_parts.sort(key=lambda x: x['PartNumber'])
        
        data = {
            'upload_id': self.upload_id,
            's3_key': self.s3_key,
            'parts': self.uploaded_parts
        }
        
        response = requests.post(url, json=data, timeout=60)
        
        if response.status_code != 200:
            print(f"\n✗ Failed to complete upload: {response.status_code}")
            print(response.text)
            return False
        
        result = response.json()
        
        if not result.get('success'):
            print(f"\n✗ Error: {result.get('error')}")
            return False
        
        print(f"✓ Upload completed on S3!")
        print(f"Location: {result.get('location', 'N/A')}")
        
        return True
    
    def create_job(self, num_segments=5):
        """Step 4: Create processing job"""
        print(f"\n{'='*70}")
        print(f"STEP 4: Creating Processing Job")
        print(f"{'='*70}")
        
        url = f"{self.api_base_url}/api/upload/create-job/"
        
        data = {
            'job_id': self.job_id,
            's3_key': self.s3_key,
            'file_type': self.file_type,
            'num_segments': num_segments,
            'min_duration': 60,
            'max_duration': 300
        }
        
        response = requests.post(url, json=data, timeout=30)
        
        if response.status_code != 201:
            print(f"\n✗ Failed to create job: {response.status_code}")
            print(response.text)
            return False
        
        result = response.json()
        
        print(f"✓ Job created successfully!")
        print(f"Job ID: {result['id']}")
        print(f"Status: {result['status']}")
        
        return True
    
    def abort_upload(self):
        """Abort the upload if something goes wrong"""
        if not self.upload_id or not self.s3_key:
            return
        
        print(f"\nAborting upload...")
        
        url = f"{self.api_base_url}/api/upload/multipart/abort/"
        
        data = {
            'upload_id': self.upload_id,
            's3_key': self.s3_key
        }
        
        try:
            requests.post(url, json=data, timeout=30)
            print(f"✓ Upload aborted and cleaned up")
        except:
            pass


def main():
    parser = argparse.ArgumentParser(description='Test multipart upload for large files')
    parser.add_argument('--file', required=True, help='Path to file to upload')
    parser.add_argument('--url', required=True, help='API base URL')
    parser.add_argument('--segments', type=int, default=5, help='Number of segments')
    parser.add_argument('--part-size', type=int, default=200, help='Part size in MB (default: 200, optimized for speed)')
    parser.add_argument('--workers', type=int, default=3, help='Number of parallel upload workers (default: 3, use 1 for large files)')
    
    args = parser.parse_args()
    
    # Validate file exists
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"✗ Error: File not found: {args.file}")
        return
    
    api_base_url = args.url.rstrip('/')
    part_size = args.part_size * 1024 * 1024  # Convert MB to bytes
    
    print("\n" + "="*70)
    print("MULTIPART UPLOAD TEST - FOR LARGE FILES UP TO 5GB")
    print("="*70)
    print("OPTIMIZATIONS ENABLED:")
    print("  • S3 Transfer Acceleration (2-5x faster)")
    print("  • Large part size (200MB default)")
    print("  • Parallel uploads (reduce with --workers 1 if errors occur)")
    print("="*70)
    
    # Create uploader
    uploader = MultipartUploader(api_base_url, str(file_path), part_size)
    
    try:
        # Step 1: Initiate
        if not uploader.initiate_upload():
            return
        
        # Step 2: Upload parts in parallel
        if not uploader.upload_parts(max_workers=args.workers):
            uploader.abort_upload()
            return
        
        # Step 3: Complete
        if not uploader.complete_upload():
            uploader.abort_upload()
            return
        
        # Step 4: Create job
        if not uploader.create_job(args.segments):
            return
        
        print("\n" + "="*70)
        print("✓ MULTIPART UPLOAD COMPLETE!")
        print("="*70)
        print(f"Job ID: {uploader.job_id}")
        print(f"Status URL: {api_base_url}/api/jobs/{uploader.job_id}/status/")
        print(f"Job is now processing in the background...")
        print("="*70 + "\n")
        
    except KeyboardInterrupt:
        print("\n\nUpload interrupted by user")
        uploader.abort_upload()
    except Exception as e:
        print(f"\n\n✗ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        uploader.abort_upload()


if __name__ == '__main__':
    main()
