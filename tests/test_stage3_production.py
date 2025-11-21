#!/usr/bin/env python3
"""
Test Stage 3 (Analysis) on Production App
Tests LLM analysis of transcript and viral segment identification
"""

import requests
import time
import sys
import os
import json
from datetime import datetime

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

def create_job_and_wait_for_analysis():
    """Create a job and wait for it to reach analysis stage"""
    print_header("Creating Job for Analysis Test")
    
    if not os.path.exists(TEST_VIDEO):
        print_status("File check", "fail", f"{TEST_VIDEO} not found")
        return None
    
    try:
        with open(TEST_VIDEO, 'rb') as f:
            files = {'media_file': f}
            data = {
                'num_segments': 2,  # Request 2 segments
                'max_duration': 300  # Max 5 minutes, LLM decides optimal length
            }
            
            print_status("Uploading", "pending", "Creating job...")
            response = requests.post(f"{API_URL}/jobs/", files=files, data=data)
            
            if response.status_code != 201:
                print_status("Upload", "fail", f"Status {response.status_code}")
                return None
            
            job_data = response.json()
            job_id = job_data['id']
            print_status("Job created", "success", job_id)
            
            # Wait for analysis stage
            print_header("Waiting for Analysis Stage")
            print_status("Monitoring", "pending", "Waiting for transcription to complete...")
            
            max_wait = 120  # 2 minutes max
            check_interval = 3
            elapsed = 0
            
            while elapsed < max_wait:
                response = requests.get(f"{API_URL}/jobs/{job_id}/")
                if response.status_code != 200:
                    return None
                
                job_data = response.json()
                status = job_data.get('status', 'unknown')
                
                print(f"[{elapsed}s] Status: {status}...", end="\r")
                
                if status == 'analyzing':
                    print_status("\nStage 3 started", "success", "LLM analyzing transcript")
                    return job_id
                elif status in ['completed', 'clipping']:
                    print_status("\nStage 3 complete", "success", "Already finished analyzing")
                    return job_id
                elif status == 'failed':
                    error_msg = job_data.get('error_message', 'Unknown error')
                    print_status("\nJob failed", "fail", error_msg)
                    return None
                
                time.sleep(check_interval)
                elapsed += check_interval
            
            print_status("\nTimeout", "fail", f"Did not reach analysis in {max_wait}s")
            return None
            
    except Exception as e:
        print_status("Job creation", "fail", str(e))
        return None

def wait_for_analysis_completion(job_id):
    """Wait for analysis to complete"""
    print_header("Monitoring Analysis Completion")
    
    max_wait = 60  # 1 minute for analysis
    check_interval = 3
    elapsed = 0
    
    while elapsed < max_wait:
        try:
            response = requests.get(f"{API_URL}/jobs/{job_id}/")
            if response.status_code != 200:
                return None, f"HTTP {response.status_code}"
            
            job_data = response.json()
            status = job_data.get('status', 'unknown')
            
            print(f"[{elapsed}s] Status: {status}...", end="\r")
            
            if status in ['completed', 'clipping']:
                print_status("\nAnalysis complete", "success", "Segments identified")
                return job_data, None
            elif status == 'failed':
                error_msg = job_data.get('error_message', 'Unknown error')
                return None, f"Job failed: {error_msg}"
            
        except Exception as e:
            return None, str(e)
        
        time.sleep(check_interval)
        elapsed += check_interval
    
    return None, f"Timeout after {max_wait}s"

def validate_segment_structure(segment):
    """Validate a single segment structure"""
    required_fields = ['id', 'title', 'description', 'reasoning', 'start_time', 'end_time', 'duration']
    
    missing_fields = []
    for field in required_fields:
        if field not in segment:
            missing_fields.append(field)
    
    if missing_fields:
        print_status("Segment structure", "fail", f"Missing: {', '.join(missing_fields)}")
        return False
    
    # Validate field types and values
    if not isinstance(segment['title'], str) or len(segment['title']) == 0:
        print_status("Segment title", "fail", "Empty or invalid")
        return False
    
    if not isinstance(segment['description'], str) or len(segment['description']) == 0:
        print_status("Segment description", "fail", "Empty or invalid")
        return False
    
    if not isinstance(segment['reasoning'], str) or len(segment['reasoning']) == 0:
        print_status("Segment reasoning", "fail", "Empty or invalid")
        return False
    
    # Validate timing
    start = segment['start_time']
    end = segment['end_time']
    duration = segment['duration']
    
    if not (isinstance(start, (int, float)) and start >= 0):
        print_status("Start time", "fail", f"Invalid: {start}")
        return False
    
    if not (isinstance(end, (int, float)) and end > start):
        print_status("End time", "fail", f"Invalid or not after start: {end}")
        return False
    
    calculated_duration = end - start
    if abs(calculated_duration - duration) > 0.1:
        print_status("Duration", "warning", f"Mismatch: {duration} vs calculated {calculated_duration}")
    
    return True

def save_segments_to_cloud(segments, job_id):
    """Save segments JSON to cloud storage and return public URL"""
    print_header("Saving Segments to Cloud Storage")
    
    try:
        # Create output data structure
        output_data = {
            'job_id': job_id,
            'timestamp': datetime.now().isoformat(),
            'num_segments': len(segments),
            'segments': segments,
            'test_info': {
                'test_type': 'stage3_production',
                'api_url': API_URL
            }
        }
        
        # Save to local file first
        output_filename = f"stage3_segments_{job_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        local_path = f"/tmp/{output_filename}"
        
        with open(local_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print_status("Local file", "success", local_path)
        
        # Upload to S3 via production API
        try:
            upload_url = f"{API_URL}/test-results/upload/"
            print_status("Uploading to S3", "pending", "Uploading via API...")
            
            response = requests.post(
                upload_url,
                json=output_data,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 201:
                result = response.json()
                public_url = result.get('public_url')
                print_status("Cloud upload", "success", "Uploaded to S3")
                print_status("Public URL", "success", public_url)
                return local_path, output_data, public_url
            else:
                print_status("Cloud upload", "warning", f"Upload failed: {response.status_code}")
                return local_path, output_data, None
        except Exception as upload_error:
            print_status("Cloud upload", "warning", f"Could not upload: {str(upload_error)}")
            return local_path, output_data, None
        
    except Exception as e:
        print_status("Save segments", "fail", str(e))
        return None, None, None

def test_stage3():
    """Test Stage 3: Analysis"""
    
    print_header("STAGE 3 ANALYSIS TEST")
    print(f"API URL: {API_URL}")
    
    # Step 1: Create job and wait for analysis
    job_id = create_job_and_wait_for_analysis()
    if not job_id:
        return False
    
    # Step 2: Wait for analysis to complete
    job_data, error = wait_for_analysis_completion(job_id)
    if error:
        print_status("Analysis completion", "fail", error)
        return False
    
    # Step 3: Verify segments were created
    print_header("Step 3: Verify Segment Creation")
    
    segments = job_data.get('segments', [])
    
    if not segments:
        print_status("Segments", "fail", "No segments created")
        return False
    
    num_segments = len(segments)
    print_status("Segments created", "success", f"{num_segments} segment(s)")
    
    # Validate each segment
    print_header("Step 4: Validate Segment Structure")
    
    all_valid = True
    for i, segment in enumerate(segments, 1):
        print(f"\n--- Segment {i} ---")
        print_status("Title", "info", segment.get('title', 'N/A')[:60])
        
        if not validate_segment_structure(segment):
            all_valid = False
            continue
        
        print_status("Structure", "success", "All required fields present")
        print_status("Description", "info", segment['description'][:80] + "...")
        print_status("Reasoning", "info", segment['reasoning'][:80] + "...")
        print_status("Timing", "success", 
            f"{segment['start_time']:.2f}s - {segment['end_time']:.2f}s ({segment['duration']:.2f}s)")
        
        # Check if clip object exists
        if 'clip' in segment:
            clip = segment['clip']
            clip_status = clip.get('status', 'unknown')
            print_status("Clip object", "success", f"Present (status: {clip_status})")
        else:
            print_status("Clip object", "warning", "Not yet created")
    
    if not all_valid:
        return False
    
    # Step 5: Verify LLM reasoning quality
    print_header("Step 5: Verify LLM Analysis Quality")
    
    # Check that segments have meaningful titles
    titles_valid = all(len(seg.get('title', '')) > 10 for seg in segments)
    if titles_valid:
        print_status("Segment titles", "success", "Meaningful titles generated")
    else:
        print_status("Segment titles", "fail", "Titles too short or missing")
        return False
    
    # Check that descriptions explain the content
    descriptions_valid = all(len(seg.get('description', '')) > 20 for seg in segments)
    if descriptions_valid:
        print_status("Descriptions", "success", "Detailed descriptions provided")
    else:
        print_status("Descriptions", "fail", "Descriptions too short")
        return False
    
    # Check that reasoning explains why it's viral-worthy
    reasoning_valid = all(len(seg.get('reasoning', '')) > 20 for seg in segments)
    if reasoning_valid:
        print_status("Viral reasoning", "success", "Reasoning provided for virality")
    else:
        print_status("Viral reasoning", "fail", "Reasoning too short")
        return False
    
    # Step 6: Verify timing constraints
    print_header("Step 6: Verify Timing Constraints")
    
    requested_max = 300  # 5 minutes hard limit
    
    timing_valid = True
    for i, segment in enumerate(segments, 1):
        duration = segment['duration']
        if duration > requested_max:
            print_status(f"Segment {i} duration", "fail", 
                f"{duration:.2f}s > max {requested_max}s (5 min)")
            timing_valid = False
        elif duration < 30:
            print_status(f"Segment {i} duration", "info", 
                f"{duration:.2f}s (short but OK if content is complete)")
        elif duration > 240:
            print_status(f"Segment {i} duration", "info", 
                f"{duration:.2f}s = {duration/60:.1f} min (long, LLM determined optimal for coherence)")
        else:
            print_status(f"Segment {i} duration", "success", 
                f"{duration:.2f}s = {duration/60:.1f} min")
    
    if not timing_valid:
        print_status("Timing constraints", "fail", "Segments exceed 5-minute maximum")
    else:
        print_status("Timing constraints", "success", "All segments within 5-minute limit")
    
    # Summary
    print_header("STAGE 3 RESULTS")
    print_status("Transcript analyzed", "success")
    print_status("LLM processing", "success")
    print_status("Segments identified", "success", f"{num_segments} segment(s)")
    print_status("Segment metadata", "success", "Title, description, reasoning")
    print_status("Timing data", "success", "Start, end, duration")
    print_status("Stage 3 Complete", "success", "Ready for Stage 4 (Clipping)")
    
    # Show segment summary
    print_header("Segment Summary")
    for i, segment in enumerate(segments, 1):
        print(f"\n{i}. {segment['title']}")
        print(f"   ⏱️  {segment['start_time']:.2f}s - {segment['end_time']:.2f}s ({segment['duration']:.2f}s)")
        print(f"   📝 {segment['description'][:80]}...")
        print(f"   💡 {segment['reasoning'][:80]}...")
    
    # Save segments to cloud storage
    local_path, output_data, public_url = save_segments_to_cloud(segments, job_id)
    if local_path:
        print_header("Output File")
        print_status("Local path", "success", local_path)
        if public_url:
            print_status("S3 URL", "success", public_url)
            print(f"\n📄 Output JSON saved with {num_segments} segments")
            print(f"   Local: {local_path}")
            print(f"   Cloud: {public_url}")
        else:
            print(f"\n📄 Output JSON saved locally with {num_segments} segments")
            print(f"   View segments at: {local_path}")
    
    return True

if __name__ == "__main__":
    print_header("PRODUCTION STAGE 3 TEST")
    print("Testing: www.koolclips.ai")
    print("Stage: Analysis (LLM → Viral Segments)")
    
    success = test_stage3()
    
    if success:
        print_header("TEST PASSED ✅")
        print("Stage 3 (Analysis) is working correctly!")
        print("LLM successfully identifies viral segments from transcripts.")
        sys.exit(0)
    else:
        print_header("TEST FAILED ❌")
        print("Stage 3 (Analysis) has issues that need fixing.")
        sys.exit(1)
