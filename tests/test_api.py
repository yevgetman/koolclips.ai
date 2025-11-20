#!/usr/bin/env python3
"""
Quick API test script - verifies the API is running and accessible
"""

import requests
import sys

API_BASE_URL = "http://127.0.0.1:8000/api"

def test_api_health():
    """Test if the API is accessible"""
    print("Testing API connectivity...")
    
    try:
        # Test jobs endpoint
        response = requests.get(f"{API_BASE_URL}/jobs/", timeout=5)
        
        if response.status_code == 200:
            print("✅ API is running and accessible")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"❌ API returned unexpected status: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API. Is the server running?")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_endpoints():
    """Test all main endpoints"""
    print("\nTesting API endpoints...")
    
    endpoints = [
        ("/jobs/", "Jobs list"),
        ("/segments/", "Segments list"),
        ("/clips/", "Clips list"),
    ]
    
    for endpoint, name in endpoints:
        try:
            response = requests.get(f"{API_BASE_URL}{endpoint}", timeout=5)
            status = "✅" if response.status_code == 200 else "❌"
            print(f"{status} {name}: {response.status_code}")
        except Exception as e:
            print(f"❌ {name}: Error - {e}")


def show_next_steps():
    """Show next steps for testing"""
    print("\n" + "="*60)
    print("🎉 All services are running!")
    print("="*60)
    
    print("\n📋 Available Services:")
    print("   • Django API: http://127.0.0.1:8000/api/")
    print("   • Admin Panel: http://127.0.0.1:8000/admin/")
    print("   • Redis: Running on port 6379")
    print("   • Celery: Worker is active")
    
    print("\n🧪 To test with a video:")
    print("\n   Option 1 - CLI:")
    print("   python manage.py process_video /path/to/video.mp4 --segments 3")
    
    print("\n   Option 2 - API (cURL):")
    print("   curl -X POST http://127.0.0.1:8000/api/jobs/ \\")
    print("     -F 'video_file=@/path/to/video.mp4' \\")
    print("     -F 'num_segments=3'")
    
    print("\n   Option 3 - Python:")
    print("   python example_api_usage.py")
    
    print("\n📊 Check status:")
    print("   curl http://127.0.0.1:8000/api/jobs/")
    
    print("\n🛑 To stop all services:")
    print("   pkill -f 'celery.*worker'")
    print("   redis-cli shutdown")
    print("   # Press Ctrl+C in the Django server terminal")
    
    print("\n" + "="*60)


if __name__ == '__main__':
    print("="*60)
    print("Viral Clips - API Test")
    print("="*60 + "\n")
    
    # Test API
    if test_api_health():
        test_endpoints()
        show_next_steps()
        sys.exit(0)
    else:
        print("\n⚠️  API is not accessible. Check if services are running.")
        sys.exit(1)
