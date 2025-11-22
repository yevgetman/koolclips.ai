#!/usr/bin/env python3
"""Quick test of custom_instructions in production"""
import requests
import time

API_URL = "https://www.koolclips.ai/api"
TEST_VIDEO = "demo_files/test_video_10s.mp4"

print("Testing custom_instructions in production...")

# Create job with custom instructions
with open(TEST_VIDEO, 'rb') as f:
    files = {'media_file': f}
    data = {
        'num_segments': 1,
        'max_duration': 300,
        'custom_instructions': 'Select the most meaningful and impactful moment that clearly communicates the main message'
    }
    
    print("\n📤 Creating job with custom instructions...")
    response = requests.post(f"{API_URL}/jobs/", files=files, data=data)
    
    if response.status_code == 201:
        job = response.json()
        print(f"✅ Job created: {job['id']}")
        print(f"   Custom instructions: {job.get('custom_instructions', 'NOT FOUND')[:60]}...")
        print(f"   Status: {job['status']}")
        
        # Wait for completion
        print("\n⏳ Waiting for job to complete (up to 2 minutes)...")
        for i in range(24):  # 2 minutes
            time.sleep(5)
            check_response = requests.get(f"{API_URL}/jobs/{job['id']}/")
            if check_response.status_code == 200:
                updated_job = check_response.json()
                status = updated_job['status']
                print(f"   [{i*5}s] Status: {status}")
                
                if status in ['completed', 'clipping']:
                    print("\n✅ Job completed!")
                    print(f"   Segments: {len(updated_job.get('segments', []))}")
                    
                    if updated_job.get('segments'):
                        seg = updated_job['segments'][0]
                        print(f"\n📋 First Segment:")
                        print(f"   Title: {seg.get('title')}")
                        print(f"   Reasoning: {seg.get('reasoning', '')[:100]}...")
                    
                    print("\n🎉 FEATURE WORKING: Custom instructions applied successfully!")
                    break
                    
                elif status == 'failed':
                    print(f"\n❌ Job failed: {updated_job.get('error_message')}")
                    break
    else:
        print(f"❌ Failed to create job: {response.status_code}")
        print(response.text)
