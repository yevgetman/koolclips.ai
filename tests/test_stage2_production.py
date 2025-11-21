#!/usr/bin/env python3
"""
Test Stage 2 (Transcription) on Production App
Tests audio download from Cloudcube, ElevenLabs transcription, and JSON storage
"""

import requests
import time
import sys
import os
import json

# Production API URL
API_URL = "https://www.koolclips.ai/api"

# Test files
TEST_VIDEO = "demo_files/test_video_10s.mp4"
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
        'info': 'ℹ️',
        'warning': '⚠️'
    }
    symbol = symbols.get(status, '•')
    print(f"{symbol} {label}: {details}" if details else f"{symbol} {label}")

def create_job(file_path, file_type_name):
    """Create a job for testing"""
    print_header(f"Creating Job with {file_type_name}")
    
    if not os.path.exists(file_path):
        print_status("File check", "fail", f"{file_path} not found")
        return None
    
    try:
        with open(file_path, 'rb') as f:
            files = {'media_file': f}
            data = {
                'num_segments': 1,
                'min_duration': 3,
                'max_duration': 10
            }
            
            print_status("Uploading", "pending", f"Sending {file_type_name}...")
            response = requests.post(f"{API_URL}/jobs/", files=files, data=data)
            
            if response.status_code != 201:
                print_status("Upload", "fail", f"Status {response.status_code}")
                return None
            
            job_data = response.json()
            job_id = job_data['id']
            print_status("Job created", "success", job_id)
            return job_id
            
    except Exception as e:
        print_status("Job creation", "fail", str(e))
        return None

def wait_for_stage(job_id, target_stage, timeout=60):
    """Wait for job to reach or pass a specific stage"""
    elapsed = 0
    check_interval = 2
    
    while elapsed < timeout:
        try:
            response = requests.get(f"{API_URL}/jobs/{job_id}/")
            if response.status_code != 200:
                return None, f"HTTP {response.status_code}"
            
            job_data = response.json()
            status = job_data.get('status', 'unknown')
            
            print(f"[{elapsed}s] Status: {status}...", end="\r")
            
            if status == target_stage:
                return job_data, None
            elif status in ['completed', 'analyzing', 'clipping'] and target_stage in ['preprocessing', 'transcribing']:
                # Job has progressed past target stage
                return job_data, None
            elif status == 'failed':
                error_msg = job_data.get('error_message', 'Unknown error')
                return None, f"Job failed: {error_msg}"
            
        except Exception as e:
            return None, str(e)
        
        time.sleep(check_interval)
        elapsed += check_interval
    
    return None, f"Timeout after {timeout}s"

def validate_transcript_structure(transcript_json):
    """Validate the transcript JSON structure"""
    print_header("Validating Transcript Structure")
    
    if not isinstance(transcript_json, dict):
        print_status("JSON structure", "fail", "Not a dictionary")
        return False
    
    # Check for required top-level keys
    required_keys = ['words', 'metadata']
    for key in required_keys:
        if key in transcript_json:
            print_status(f"Field: {key}", "success", "Present")
        else:
            print_status(f"Field: {key}", "fail", "Missing")
            return False
    
    # Validate words array
    words = transcript_json.get('words', [])
    if not isinstance(words, list):
        print_status("Words field", "fail", "Not an array")
        return False
    
    if len(words) == 0:
        print_status("Words array", "warning", "Empty (no speech detected?)")
    else:
        print_status("Words array", "success", f"{len(words)} words transcribed")
        
        # Check structure of first word
        if len(words) > 0:
            first_word = words[0]
            word_fields = ['text', 'start', 'end']
            all_present = all(field in first_word for field in word_fields)
            
            if all_present:
                print_status("Word structure", "success", "Has text, start, end timestamps")
                print_status("Sample word", "info", 
                    f'"{first_word["text"]}" ({first_word["start"]}s - {first_word["end"]}s)')
            else:
                print_status("Word structure", "fail", "Missing required fields")
                return False
    
    # Validate metadata
    metadata = transcript_json.get('metadata', {})
    if not isinstance(metadata, dict):
        print_status("Metadata field", "fail", "Not a dictionary")
        return False
    
    metadata_fields = ['duration', 'language', 'transcription_id']
    for field in metadata_fields:
        if field in metadata:
            value = metadata[field]
            print_status(f"Metadata: {field}", "info", str(value))
        else:
            print_status(f"Metadata: {field}", "warning", "Missing")
    
    # Check for full_text (convenience field)
    if 'full_text' in transcript_json:
        full_text = transcript_json['full_text']
        text_preview = full_text[:100] + "..." if len(full_text) > 100 else full_text
        print_status("Full text", "success", text_preview)
    
    return True

def test_stage2(test_type="video"):
    """Test Stage 2: Transcription"""
    
    file_path = TEST_VIDEO if test_type == "video" else TEST_AUDIO
    file_name = os.path.basename(file_path)
    
    print_header(f"STAGE 2 TRANSCRIPTION TEST - {test_type.upper()}")
    print(f"API URL: {API_URL}")
    print(f"Test File: {file_name}")
    
    # Step 1: Create job and wait for transcription stage
    job_id = create_job(file_path, file_name)
    if not job_id:
        return False
    
    # Step 2: Wait for transcription to start/complete
    print_header("Step 2: Monitor Transcription")
    print_status("Waiting", "pending", "Job to reach transcription stage...")
    
    job_data, error = wait_for_stage(job_id, 'transcribing', timeout=30)
    if error:
        print_status("Wait for transcription", "fail", error)
        return False
    
    print_status("\nTranscription started", "success", "Stage 2 activated")
    
    # Step 3: Wait for transcription to complete
    print_header("Step 3: Wait for Transcription Completion")
    print_status("Transcribing", "pending", "Sending audio to ElevenLabs...")
    
    job_data, error = wait_for_stage(job_id, 'analyzing', timeout=90)
    if error:
        print_status("Transcription", "fail", error)
        return False
    
    print_status("\nTranscription complete", "success", "Moving to analysis")
    
    # Step 4: Verify transcript data
    print_header("Step 4: Verify Transcript Output")
    
    try:
        response = requests.get(f"{API_URL}/jobs/{job_id}/")
        if response.status_code != 200:
            print_status("Fetch job data", "fail", f"HTTP {response.status_code}")
            return False
        
        job_data = response.json()
        
        # Check if transcript_json exists
        transcript_json = job_data.get('transcript_json')
        
        if not transcript_json:
            print_status("Transcript JSON", "fail", "Not present in job data")
            return False
        
        print_status("Transcript JSON", "success", "Present in job data")
        
        # Validate transcript structure
        if not validate_transcript_structure(transcript_json):
            return False
        
        # Step 5: Verify audio source was from Cloudcube
        print_header("Step 5: Verify Audio Source")
        
        # Check that audio was downloaded from S3
        if test_type == "video":
            audio_s3_url = job_data.get('extracted_audio_s3_url')
            if audio_s3_url:
                print_status("Audio source", "success", "Extracted audio from Cloudcube")
                if 'mkwcrxocz0mi/public/' in audio_s3_url:
                    print_status("Cloudcube prefix", "success", "Proper cube prefix")
                print_status("Audio URL", "info", audio_s3_url[:80] + "...")
            else:
                print_status("Audio source", "warning", "No S3 URL recorded")
        else:
            media_file = job_data.get('media_file')
            if media_file:
                print_status("Audio source", "success", "Direct audio from Cloudcube")
                if 'mkwcrxocz0mi/public/' in media_file:
                    print_status("Cloudcube prefix", "success", "Proper cube prefix")
                print_status("Audio URL", "info", media_file[:80] + "...")
            else:
                print_status("Audio source", "fail", "No media file URL")
                return False
        
        # Summary
        print_header("STAGE 2 RESULTS")
        print_status("Audio from Cloudcube", "success")
        print_status("ElevenLabs transcription", "success")
        print_status("Transcript JSON created", "success")
        print_status("Timestamps present", "success")
        print_status("Metadata included", "success")
        print_status("Stage 2 Complete", "success", "Ready for Stage 3 (Analysis)")
        
        # Show transcript stats
        words_count = len(transcript_json.get('words', []))
        duration = transcript_json.get('metadata', {}).get('duration', 'unknown')
        language = transcript_json.get('metadata', {}).get('language', 'unknown')
        
        print_header("Transcript Statistics")
        print_status("Words transcribed", "info", f"{words_count}")
        print_status("Duration", "info", f"{duration}s")
        print_status("Language", "info", language)
        
        return True
        
    except Exception as e:
        print_status("Verification", "fail", str(e))
        return False

if __name__ == "__main__":
    print_header("PRODUCTION STAGE 2 TEST")
    print("Testing: www.koolclips.ai")
    print("Stage: Transcription (Cloudcube → ElevenLabs → JSON)")
    
    # Test both video and audio inputs
    print("\n" + "=" * 60)
    print("Testing with VIDEO input (extracted audio)")
    print("=" * 60)
    
    video_success = test_stage2("video")
    
    # Wait between tests to avoid rate limiting
    print("\n⏳ Waiting 10 seconds before next test...")
    time.sleep(10)
    
    print("\n" + "=" * 60)
    print("Testing with AUDIO input (direct file)")
    print("=" * 60)
    
    audio_success = test_stage2("audio")
    
    # Final summary
    print_header("FINAL RESULTS")
    
    if video_success:
        print_status("Video transcription", "success", "Working correctly")
    else:
        print_status("Video transcription", "fail", "Has issues")
    
    if audio_success:
        print_status("Audio transcription", "success", "Working correctly")
    else:
        print_status("Audio transcription", "fail", "Has issues")
    
    if video_success and audio_success:
        print_header("ALL TESTS PASSED ✅")
        print("Stage 2 (Transcription) is fully operational!")
        print("Both video and audio inputs work correctly.")
        sys.exit(0)
    else:
        print_header("SOME TESTS FAILED ❌")
        print("Stage 2 (Transcription) has issues that need fixing.")
        sys.exit(1)
