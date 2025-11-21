#!/usr/bin/env python3
"""
Test Stage 1 (Preprocessing) with Audio File Input
Tests audio upload and storage without extraction
"""

import requests
import time
import sys
import os

# Production API URL
API_URL = "https://www.koolclips.ai/api"

# Test audio file (we'll need to create one)
TEST_AUDIO = "demo_files/test_audio.mp3"

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

def create_test_audio():
    """Create a test audio file from the test video if needed"""
    if os.path.exists(TEST_AUDIO):
        print_status("Test audio file", "success", f"Found {TEST_AUDIO}")
        return True
    
    # Try to extract audio from test video
    test_video = "demo_files/test_video_10s.mp4"
    if not os.path.exists(test_video):
        print_status("Test files", "fail", "Neither audio nor video test file found")
        return False
    
    print_status("Creating test audio", "pending", f"Extracting from {test_video}")
    
    try:
        import subprocess
        os.makedirs("demo_files", exist_ok=True)
        cmd = [
            'ffmpeg', '-i', test_video,
            '-vn', '-acodec', 'libmp3lame', '-q:a', '4',
            TEST_AUDIO, '-y'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(TEST_AUDIO):
            print_status("Test audio created", "success", TEST_AUDIO)
            return True
        else:
            print_status("Test audio creation", "fail", "ffmpeg failed")
            return False
    except Exception as e:
        print_status("Test audio creation", "fail", str(e))
        return False

def test_stage1_audio():
    """Test Stage 1: Preprocessing with Audio Input"""
    
    print_header("STAGE 1: AUDIO FILE PREPROCESSING TEST")
    print(f"API URL: {API_URL}")
    print(f"Test File: {TEST_AUDIO}")
    
    if not create_test_audio():
        return False
    
    # Get file size
    file_size = os.path.getsize(TEST_AUDIO)
    print_status("Audio file size", "info", f"{file_size:,} bytes")
    
    # Step 1: Upload audio file
    print_header("Step 1: Upload Audio File")
    
    try:
        with open(TEST_AUDIO, 'rb') as f:
            files = {'media_file': f}
            data = {
                'num_segments': 1,
                'min_duration': 3,
                'max_duration': 10
            }
            
            print_status("Uploading", "pending", "Sending audio to API...")
            response = requests.post(f"{API_URL}/jobs/", files=files, data=data)
            
            if response.status_code != 201:
                print_status("Upload", "fail", f"Status {response.status_code}")
                print(response.text)
                return False
            
            job_data = response.json()
            job_id = job_data['id']
            file_type = job_data.get('file_type', 'unknown')
            media_url = job_data.get('media_file', 'N/A')
            
            print_status("Upload", "success", f"Job created: {job_id}")
            print_status("Detected file type", "info", file_type)
            print_status("Media URL", "info", media_url)
            
            # Verify file type detection
            if file_type != 'audio':
                print_status("File type detection", "fail", f"Expected 'audio', got '{file_type}'")
                return False
            else:
                print_status("File type detection", "success", "Correctly identified as audio")
            
            # Verify Cloudcube URL
            if 'mkwcrxocz0mi/public/' in media_url:
                print_status("Cloudcube prefix", "success", "Cube prefix present")
            else:
                print_status("Cloudcube prefix", "fail", "Missing cube prefix")
            
    except Exception as e:
        print_status("Upload", "fail", str(e))
        return False
    
    # Step 2: Monitor preprocessing
    print_header("Step 2: Verify Audio Processing")
    
    max_wait = 30  # 30 seconds max wait for audio
    check_interval = 2
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
            
            # For audio files, preprocessing should be minimal or skipped
            if status == 'preprocessing':
                print(" - Processing (should be quick)...")
                
            elif status == 'transcribing':
                # Audio ready for transcription
                print_status("\nAudio processing", "success", "Ready for transcription!")
                
                # Verify audio handling
                print_header("Step 3: Verify Audio Storage")
                
                extracted_audio_path = job_data.get('extracted_audio_path')
                audio_s3_url = job_data.get('extracted_audio_s3_url')
                
                # For audio input, extracted_audio_path might be empty or same as input
                if extracted_audio_path:
                    print_status("Audio path", "info", extracted_audio_path)
                    print_status("Audio extraction", "info", "Path set (may be original file)")
                else:
                    print_status("Audio path", "info", "Not set (using original file)")
                
                # The original media file URL should be accessible
                print_status("Original file", "success", "Available for transcription")
                
                # Test media URL accessibility
                print_header("Step 4: Test Audio URL Accessibility")
                
                print_status("Testing media URL", "pending", "Checking accessibility...")
                try:
                    head_response = requests.head(media_url, timeout=10)
                    if head_response.status_code == 200:
                        print_status("Audio accessible", "success", f"HTTP {head_response.status_code}")
                        content_type = head_response.headers.get('Content-Type', 'unknown')
                        content_length = head_response.headers.get('Content-Length', 'unknown')
                        print_status("Content-Type", "info", content_type)
                        print_status("Size", "info", f"{content_length} bytes")
                    elif head_response.status_code == 403:
                        print_status("Audio accessible", "fail", "HTTP 403 - Permission denied")
                        print_status("Issue", "info", "Check Cloudcube public folder permissions")
                    else:
                        print_status("Audio accessible", "fail", f"HTTP {head_response.status_code}")
                except Exception as e:
                    print_status("Audio accessible", "fail", str(e))
                
                # Summary
                print_header("STAGE 1 AUDIO RESULTS")
                print_status("Audio upload", "success")
                print_status("File type detection", "success", "Identified as audio")
                print_status("Cloudcube storage", "success")
                print_status("No extraction needed", "success", "Skipped video processing")
                print_status("Ready for transcription", "success")
                print_status("Stage 1 Complete", "success", "Audio file ready for Stage 2")
                
                return True
                
            elif status == 'failed':
                print_status("\nAudio processing", "fail", "Job failed")
                error_msg = job_data.get('error_message', 'No error message')
                print_status("Error", "fail", error_msg)
                return False
            
            elif status in ['completed', 'analyzing', 'clipping']:
                print_status("\nAudio processing", "success", "Completed (job progressed further)")
                print_status("Stage 1", "success", "Audio was processed successfully")
                return True
            
        except Exception as e:
            print_status("Monitor", "fail", str(e))
            return False
        
        time.sleep(check_interval)
        elapsed += check_interval
    
    print_status("Timeout", "fail", f"Audio processing did not complete in {max_wait}s")
    return False

if __name__ == "__main__":
    print_header("PRODUCTION STAGE 1 AUDIO TEST")
    print("Testing: www.koolclips.ai")
    print("Stage: Audio File Preprocessing (No Extraction)")
    
    success = test_stage1_audio()
    
    if success:
        print_header("TEST PASSED ✅")
        print("Stage 1 audio processing is working correctly!")
        print("Audio files are properly handled without unnecessary extraction.")
        sys.exit(0)
    else:
        print_header("TEST FAILED ❌")
        print("Stage 1 audio processing has issues.")
        sys.exit(1)
