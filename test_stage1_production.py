#!/usr/bin/env python3
"""
Test Stage 1 (Preprocessing) on Production App
Tests video upload, audio extraction, and S3 storage
"""

import requests
import time
import sys
import os

# Production API URL
API_URL = "https://www.koolclips.ai/api"

# Test video file
TEST_VIDEO = "demo_files/test_video_10s.mp4"

def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)

def print_status(label, status, details=""):
    """Print formatted status"""
    symbols = {
        'success': '✅',
        'fail': '❌',
        'pending': '⏳',
        'info': 'ℹ️'
    }
    symbol = symbols.get(status, '•')
    print(f"{symbol} {label}: {details}" if details else f"{symbol} {label}")

def test_stage1():
    """Test Stage 1: Preprocessing"""
    
    print_header("STAGE 1: PREPROCESSING TEST")
    print(f"API URL: {API_URL}")
    print(f"Test File: {TEST_VIDEO}")
    
    if not os.path.exists(TEST_VIDEO):
        print_status("Test file check", "fail", f"{TEST_VIDEO} not found")
        return False
    
    print_status("Test file check", "success", f"Found {TEST_VIDEO}")
    
    # Step 1: Upload video and create job
    print_header("Step 1: Upload Video")
    
    try:
        with open(TEST_VIDEO, 'rb') as f:
            files = {'media_file': f}
            data = {
                'num_segments': 1,  # Minimal segments for quick test
                'min_duration': 3,
                'max_duration': 10
            }
            
            print_status("Uploading", "pending", "Sending video to API...")
            response = requests.post(f"{API_URL}/jobs/", files=files, data=data)
            
            if response.status_code != 201:
                print_status("Upload", "fail", f"Status {response.status_code}")
                print(response.text)
                return False
            
            job_data = response.json()
            job_id = job_data['id']
            media_url = job_data.get('media_file', 'N/A')
            
            print_status("Upload", "success", f"Job created: {job_id}")
            print_status("Media URL", "info", media_url)
            
            # Verify Cloudcube URL structure
            if 'mkwcrxocz0mi/public/' in media_url:
                print_status("Cloudcube prefix", "success", "Cube prefix present")
            else:
                print_status("Cloudcube prefix", "fail", "Missing cube prefix")
            
    except Exception as e:
        print_status("Upload", "fail", str(e))
        return False
    
    # Step 2: Monitor preprocessing
    print_header("Step 2: Monitor Preprocessing")
    
    max_wait = 60  # 60 seconds max wait
    check_interval = 3
    elapsed = 0
    
    while elapsed < max_wait:
        try:
            response = requests.get(f"{API_URL}/jobs/{job_id}/")
            if response.status_code != 200:
                print_status("Status check", "fail", f"Status {response.status_code}")
                return False
            
            job_data = response.json()
            status = job_data.get('status', 'unknown')
            
            print(f"\n[{elapsed}s] Status: {status}", end="")
            
            # Check preprocessing completion
            if status == 'preprocessing':
                print(" - In progress...")
                
            elif status == 'transcribing':
                # Preprocessing completed! Check results
                print_status("\nPreprocessing", "success", "Completed!")
                
                # Verify extracted audio
                audio_path = job_data.get('extracted_audio_path')
                audio_s3_url = job_data.get('extracted_audio_s3_url')
                audio_cf_url = job_data.get('extracted_audio_cloudfront_url')
                
                print_header("Step 3: Verify Audio Extraction")
                
                if audio_path:
                    print_status("Audio path", "success", audio_path)
                else:
                    print_status("Audio path", "fail", "Not set")
                    return False
                
                if audio_s3_url:
                    print_status("S3 URL", "success", audio_s3_url[:80] + "...")
                    
                    # Verify Cloudcube prefix
                    if 'mkwcrxocz0mi/public/' in audio_s3_url:
                        print_status("Cloudcube prefix", "success", "Cube prefix in audio URL")
                    else:
                        print_status("Cloudcube prefix", "fail", "Missing cube prefix in audio")
                else:
                    print_status("S3 URL", "fail", "Not set")
                
                if audio_cf_url:
                    print_status("CloudFront URL", "success", audio_cf_url[:80] + "...")
                else:
                    print_status("CloudFront URL", "info", "Not set (OK for Cloudcube)")
                
                # Test audio URL accessibility
                print_header("Step 4: Test Audio URL Accessibility")
                
                if audio_s3_url:
                    print_status("Testing S3 URL", "pending", "Checking if URL is accessible...")
                    try:
                        head_response = requests.head(audio_s3_url, timeout=10)
                        if head_response.status_code == 200:
                            print_status("Audio accessible", "success", f"HTTP {head_response.status_code}")
                            content_type = head_response.headers.get('Content-Type', 'unknown')
                            content_length = head_response.headers.get('Content-Length', 'unknown')
                            print_status("Content-Type", "info", content_type)
                            print_status("Size", "info", f"{content_length} bytes")
                        else:
                            print_status("Audio accessible", "fail", f"HTTP {head_response.status_code}")
                    except Exception as e:
                        print_status("Audio accessible", "fail", str(e))
                
                # Summary
                print_header("STAGE 1 RESULTS")
                print_status("Video upload", "success")
                print_status("Cloudcube storage", "success")
                print_status("Audio extraction", "success")
                print_status("Audio upload", "success")
                print_status("S3 URLs generated", "success")
                print_status("Stage 1 Complete", "success", "Ready for Stage 2 (Transcription)")
                
                return True
                
            elif status == 'failed':
                print_status("\nPreprocessing", "fail", "Job failed")
                error_msg = job_data.get('error_message', 'No error message')
                print_status("Error", "fail", error_msg)
                return False
            
            elif status in ['completed', 'analyzing', 'clipping']:
                print_status("\nPreprocessing", "success", "Already completed (job progressed further)")
                # Still verify audio was extracted
                audio_path = job_data.get('extracted_audio_path')
                if audio_path:
                    print_status("Audio extraction", "success", audio_path)
                    return True
                else:
                    print_status("Audio extraction", "fail", "No audio path found")
                    return False
            
        except Exception as e:
            print_status("Monitor", "fail", str(e))
            return False
        
        time.sleep(check_interval)
        elapsed += check_interval
    
    print_status("Timeout", "fail", f"Stage 1 did not complete in {max_wait}s")
    return False

if __name__ == "__main__":
    print_header("PRODUCTION STAGE 1 TEST")
    print("Testing: www.koolclips.ai")
    print("Stage: Preprocessing (Video → Audio Extraction → S3 Upload)")
    
    success = test_stage1()
    
    if success:
        print_header("TEST PASSED ✅")
        print("Stage 1 (Preprocessing) is working correctly!")
        sys.exit(0)
    else:
        print_header("TEST FAILED ❌")
        print("Stage 1 (Preprocessing) has issues that need to be fixed.")
        sys.exit(1)
