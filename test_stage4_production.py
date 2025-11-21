#!/usr/bin/env python3
"""
Test Stage 4 (Clipping/Rendering) on Production App
Tests Shotstack rendering, download, and Cloudcube upload
"""

import requests
import time
import sys
import os

# Production API URL
API_URL = "https://www.koolclips.ai/api"

# Test files
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
        'info': 'ℹ️',
        'warning': '⚠️'
    }
    symbol = symbols.get(status, '•')
    print(f"{symbol} {label}: {details}" if details else f"{symbol} {label}")

def print_url_box(url):
    """Print URL in a nice box"""
    print("\n" + "╔" + "═" * 70 + "╗")
    print("║" + " " * 70 + "║")
    print("║" + "  🎬 PUBLIC CLIP URL (Click to view):".ljust(70) + "║")
    print("║" + " " * 70 + "║")
    
    # Split URL if too long
    if len(url) > 66:
        chunks = [url[i:i+66] for i in range(0, len(url), 66)]
        for chunk in chunks:
            print("║  " + chunk.ljust(68) + "║")
    else:
        print("║  " + url.ljust(68) + "║")
    
    print("║" + " " * 70 + "║")
    print("╚" + "═" * 70 + "╝")

def create_job_and_wait():
    """Create a job and return job_id"""
    print_header("Creating Job for Complete Pipeline Test")
    
    if not os.path.exists(TEST_VIDEO):
        print_status("File check", "fail", f"{TEST_VIDEO} not found")
        return None
    
    try:
        with open(TEST_VIDEO, 'rb') as f:
            files = {'media_file': f}
            data = {
                'num_segments': 1,  # Single segment for faster testing
                'min_duration': 5,
                'max_duration': 10
            }
            
            print_status("Uploading", "pending", "Creating job...")
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

def wait_for_job_completion(job_id):
    """Wait for entire job to complete"""
    print_header("Monitoring Complete Pipeline")
    print_status("Info", "info", "This may take 30-60 seconds...")
    
    max_wait = 180  # 3 minutes max
    check_interval = 5
    elapsed = 0
    
    last_status = None
    
    while elapsed < max_wait:
        try:
            response = requests.get(f"{API_URL}/jobs/{job_id}/")
            if response.status_code != 200:
                return None, f"HTTP {response.status_code}"
            
            job_data = response.json()
            status = job_data.get('status', 'unknown')
            
            # Print status changes
            if status != last_status:
                if status == 'preprocessing':
                    print_status(f"\n[{elapsed}s] Stage 1", "pending", "Extracting audio...")
                elif status == 'transcribing':
                    print_status(f"[{elapsed}s] Stage 2", "pending", "Transcribing with ElevenLabs...")
                elif status == 'analyzing':
                    print_status(f"[{elapsed}s] Stage 3", "pending", "Analyzing with LLM...")
                elif status == 'clipping':
                    print_status(f"[{elapsed}s] Stage 4", "pending", "Rendering clips with Shotstack...")
                elif status == 'completed':
                    print_status(f"\n[{elapsed}s] Complete", "success", "All stages finished!")
                last_status = status
            else:
                print(f"[{elapsed}s] {status}...", end="\r")
            
            if status == 'completed':
                return job_data, None
            elif status == 'failed':
                error_msg = job_data.get('error_message', 'Unknown error')
                return None, f"Job failed: {error_msg}"
            
        except Exception as e:
            return None, str(e)
        
        time.sleep(check_interval)
        elapsed += check_interval
    
    # Check if any clips are ready even if job isn't fully complete
    try:
        response = requests.get(f"{API_URL}/jobs/{job_id}/")
        if response.status_code == 200:
            job_data = response.json()
            segments = job_data.get('segments', [])
            if segments and any(seg.get('clip', {}).get('status') == 'completed' for seg in segments):
                print_status("\nPartial success", "warning", "Some clips completed but job still processing")
                return job_data, None
    except:
        pass
    
    return None, f"Timeout after {max_wait}s"

def validate_clip(clip_data):
    """Validate clip structure and URLs"""
    required_fields = ['id', 'status', 'public_url']
    
    missing_fields = []
    for field in required_fields:
        if field not in clip_data or not clip_data[field]:
            missing_fields.append(field)
    
    if missing_fields:
        print_status("Clip structure", "fail", f"Missing: {', '.join(missing_fields)}")
        return False
    
    # Check clip status
    clip_status = clip_data.get('status')
    if clip_status != 'completed':
        print_status("Clip status", "warning", f"Status: {clip_status}")
        if clip_status == 'failed':
            error = clip_data.get('error_message', 'No error message')
            print_status("Error", "fail", error)
            return False
        return False
    
    print_status("Clip status", "success", "Completed")
    
    # Validate URLs
    public_url = clip_data.get('public_url')
    video_s3_url = clip_data.get('video_s3_url')
    
    if public_url:
        print_status("Public URL", "success", "Generated")
        
        # Check for Cloudcube prefix
        if 'mkwcrxocz0mi/public/' in public_url:
            print_status("Cloudcube storage", "success", "Proper cube prefix")
        else:
            print_status("Cloudcube storage", "warning", "Unexpected URL format")
    else:
        print_status("Public URL", "fail", "Not generated")
        return False
    
    if video_s3_url:
        print_status("S3 URL", "success", "Present")
    
    return True

def test_clip_accessibility(url):
    """Test if the clip URL is accessible"""
    print_header("Testing Clip Accessibility")
    
    try:
        print_status("Testing URL", "pending", "Sending HEAD request...")
        response = requests.head(url, timeout=10, allow_redirects=True)
        
        if response.status_code == 200:
            print_status("HTTP Status", "success", f"{response.status_code} OK")
            
            # Get headers
            content_type = response.headers.get('Content-Type', 'unknown')
            content_length = response.headers.get('Content-Length', 'unknown')
            
            print_status("Content-Type", "info", content_type)
            
            if content_length != 'unknown':
                size_mb = int(content_length) / (1024 * 1024)
                print_status("File Size", "info", f"{size_mb:.2f} MB ({content_length} bytes)")
            else:
                print_status("File Size", "info", "Unknown")
            
            # Verify it's a video
            if 'video' in content_type.lower():
                print_status("File Type", "success", "Video file confirmed")
            else:
                print_status("File Type", "warning", f"Unexpected type: {content_type}")
            
            return True
        else:
            print_status("HTTP Status", "fail", f"{response.status_code}")
            return False
            
    except Exception as e:
        print_status("Accessibility test", "fail", str(e))
        return False

def test_stage4():
    """Test Stage 4: Clipping/Rendering"""
    
    print_header("STAGE 4 CLIPPING/RENDERING TEST")
    print(f"API URL: {API_URL}")
    
    # Step 1: Create job
    job_id = create_job_and_wait()
    if not job_id:
        return False
    
    # Step 2: Wait for complete pipeline
    job_data, error = wait_for_job_completion(job_id)
    if error:
        print_status("Pipeline completion", "fail", error)
        return False
    
    # Step 3: Verify clips were created
    print_header("Step 3: Verify Clip Generation")
    
    segments = job_data.get('segments', [])
    
    if not segments:
        print_status("Segments", "fail", "No segments found")
        return False
    
    print_status("Segments", "success", f"{len(segments)} segment(s)")
    
    # Check each clip
    completed_clips = []
    for i, segment in enumerate(segments, 1):
        print(f"\n--- Segment {i}: {segment.get('title', 'Unknown')} ---")
        
        clip = segment.get('clip')
        if not clip:
            print_status("Clip", "fail", "No clip object")
            continue
        
        if validate_clip(clip):
            completed_clips.append(clip)
            print_status("Validation", "success", "Clip ready")
        else:
            print_status("Validation", "fail", "Clip not ready or invalid")
    
    if not completed_clips:
        print_status("Completed clips", "fail", "No clips completed successfully")
        return False
    
    print_header(f"Step 4: Test Clip Accessibility ({len(completed_clips)} clip(s))")
    
    accessible_clips = []
    for i, clip in enumerate(completed_clips, 1):
        print(f"\n--- Clip {i} ---")
        public_url = clip.get('public_url')
        
        if test_clip_accessibility(public_url):
            accessible_clips.append(clip)
    
    if not accessible_clips:
        print_status("Accessibility", "fail", "No clips are accessible")
        return False
    
    # Summary
    print_header("STAGE 4 RESULTS")
    print_status("Shotstack rendering", "success")
    print_status("Clip download", "success")
    print_status("Cloudcube upload", "success")
    print_status("Public URLs generated", "success")
    print_status("Clips accessible", "success", f"{len(accessible_clips)}/{len(completed_clips)}")
    print_status("Stage 4 Complete", "success", "End-to-end pipeline working!")
    
    # Display public URLs
    print_header("PUBLIC CLIP URLs")
    
    for i, clip in enumerate(accessible_clips, 1):
        segment_title = None
        for seg in segments:
            if seg.get('clip', {}).get('id') == clip.get('id'):
                segment_title = seg.get('title')
                break
        
        print(f"\n📹 Clip {i}: {segment_title or 'Unknown'}")
        print_url_box(clip.get('public_url'))
        
        print("\nℹ️  Clip Details:")
        print(f"   - Video S3 URL: {clip.get('video_s3_url', 'N/A')[:80]}...")
        print(f"   - Clip ID: {clip.get('id')}")
        print(f"   - Created: {clip.get('created_at', 'N/A')}")
        print(f"   - Completed: {clip.get('completed_at', 'N/A')}")
    
    return True

if __name__ == "__main__":
    print_header("PRODUCTION STAGE 4 TEST")
    print("Testing: www.koolclips.ai")
    print("Stage: Clipping/Rendering (Shotstack → Cloudcube)")
    print("\n⚠️  This test takes 30-60 seconds to complete")
    
    success = test_stage4()
    
    if success:
        print_header("TEST PASSED ✅")
        print("Stage 4 (Clipping/Rendering) is working correctly!")
        print("Complete end-to-end pipeline operational.")
        print("\n👆 Use the public URL(s) above to view your clips!")
        sys.exit(0)
    else:
        print_header("TEST FAILED ❌")
        print("Stage 4 (Clipping/Rendering) has issues.")
        sys.exit(1)
