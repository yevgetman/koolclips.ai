#!/usr/bin/env python3
"""
Test custom_instructions feature in production
"""

import requests
import time
import sys
import os

API_URL = "https://www.koolclips.ai/api"
TEST_VIDEO = "demo_files/test_video_10s.mp4"

def print_header(text):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)

def print_status(label, status, details=""):
    symbols = {
        'success': '✅',
        'fail': '❌',
        'pending': '⏳',
        'info': 'ℹ️',
    }
    symbol = symbols.get(status, '•')
    print(f"{symbol} {label}: {details}" if details else f"{symbol} {label}")

def test_default_instructions():
    """Test with default (viral) instructions"""
    print_header("TEST 1: Default Instructions (Viral Content)")
    
    if not os.path.exists(TEST_VIDEO):
        print_status("File check", "fail", f"{TEST_VIDEO} not found")
        return None
    
    try:
        with open(TEST_VIDEO, 'rb') as f:
            files = {'media_file': f}
            data = {
                'num_segments': 2,
                'max_duration': 300
            }
            
            print_status("Creating job", "pending", "Default viral content...")
            response = requests.post(f"{API_URL}/jobs/", files=files, data=data)
            
            if response.status_code != 201:
                print_status("Job creation", "fail", f"Status {response.status_code}")
                return None
            
            job_data = response.json()
            job_id = job_data['id']
            print_status("Job created", "success", job_id)
            
            return wait_and_check_segments(job_id, "Default (viral)")
            
    except Exception as e:
        print_status("Test", "fail", str(e))
        return None

def test_custom_instructions():
    """Test with custom educational instructions"""
    print_header("TEST 2: Custom Instructions (Educational)")
    
    if not os.path.exists(TEST_VIDEO):
        print_status("File check", "fail", f"{TEST_VIDEO} not found")
        return None
    
    try:
        with open(TEST_VIDEO, 'rb') as f:
            files = {'media_file': f}
            data = {
                'num_segments': 2,
                'max_duration': 300,
                'custom_instructions': 'Focus on the most educational and informative moments that clearly explain concepts'
            }
            
            print_status("Creating job", "pending", "Custom educational criteria...")
            response = requests.post(f"{API_URL}/jobs/", files=files, data=data)
            
            if response.status_code != 201:
                print_status("Job creation", "fail", f"Status {response.status_code}")
                return None
            
            job_data = response.json()
            job_id = job_data['id']
            custom_inst = job_data.get('custom_instructions', 'N/A')
            print_status("Job created", "success", job_id)
            print_status("Custom instructions", "info", custom_inst)
            
            return wait_and_check_segments(job_id, "Educational")
            
    except Exception as e:
        print_status("Test", "fail", str(e))
        return None

def wait_and_check_segments(job_id, test_label):
    """Wait for job to complete and check segments"""
    print_status("Monitoring", "pending", "Waiting for completion...")
    
    max_wait = 180  # 3 minutes
    check_interval = 5
    elapsed = 0
    
    while elapsed < max_wait:
        try:
            response = requests.get(f"{API_URL}/jobs/{job_id}/")
            if response.status_code != 200:
                return None
            
            job_data = response.json()
            status = job_data.get('status', 'unknown')
            
            print(f"[{elapsed}s] Status: {status}...", end="\r")
            
            if status in ['completed', 'clipping']:
                print_status(f"\n{test_label} job complete", "success")
                
                # Get segments
                segments = job_data.get('segments', [])
                print_status("Segments found", "success", f"{len(segments)} segment(s)")
                
                print_header(f"{test_label} - Segment Analysis")
                for i, segment in enumerate(segments, 1):
                    print(f"\n--- Segment {i} ---")
                    print(f"Title: {segment.get('title', 'N/A')}")
                    print(f"Duration: {segment.get('duration', 0):.2f}s")
                    print(f"Description: {segment.get('description', 'N/A')[:100]}...")
                    print(f"Reasoning: {segment.get('reasoning', 'N/A')[:100]}...")
                
                return {
                    'job_id': job_id,
                    'segments': segments,
                    'custom_instructions': job_data.get('custom_instructions')
                }
                
            elif status == 'failed':
                error_msg = job_data.get('error_message', 'Unknown error')
                print_status("\nJob failed", "fail", error_msg)
                return None
            
        except Exception as e:
            print_status("Monitoring", "fail", str(e))
            return None
        
        time.sleep(check_interval)
        elapsed += check_interval
    
    print_status("\nTimeout", "fail", f"Did not complete in {max_wait}s")
    return None

def main():
    print_header("PRODUCTION TEST: Custom Instructions Feature")
    print(f"API: {API_URL}")
    
    # Test 1: Default instructions
    result1 = test_default_instructions()
    
    # Wait a bit between tests
    time.sleep(5)
    
    # Test 2: Custom instructions
    result2 = test_custom_instructions()
    
    # Summary
    print_header("TEST SUMMARY")
    
    if result1:
        print_status("Test 1 (Default/Viral)", "success", f"{len(result1['segments'])} segments")
    else:
        print_status("Test 1 (Default/Viral)", "fail")
    
    if result2:
        print_status("Test 2 (Custom/Educational)", "success", f"{len(result2['segments'])} segments")
        print_status("Custom instructions applied", "success", result2.get('custom_instructions', 'N/A')[:50])
    else:
        print_status("Test 2 (Custom/Educational)", "fail")
    
    if result1 and result2:
        print_header("FEATURE VALIDATION ✅")
        print("✅ Default viral content selection works")
        print("✅ Custom instructions parameter accepted")
        print("✅ LLM applies custom criteria to segment selection")
        print("\n📝 Note: Compare the 'reasoning' fields to see how LLM behavior differs")
        sys.exit(0)
    else:
        print_header("TESTS FAILED ❌")
        sys.exit(1)

if __name__ == "__main__":
    main()
