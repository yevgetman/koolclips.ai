"""
Quick test for Shotstack API integration

This test verifies that the Shotstack service can successfully create a render job.
Note: Requires a publicly accessible media URL
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from viral_clips.services.shotstack_service import ShotstackService


def test_shotstack_basic():
    """Test basic Shotstack API connection and render creation"""
    
    print("\n" + "="*60)
    print("SHOTSTACK API TEST")
    print("="*60)
    
    # Initialize service
    service = ShotstackService()
    print(f"✓ Service initialized")
    print(f"  Environment: {service.env}")
    print(f"  Stage: {service.stage}")
    print(f"  API Key configured: {service.api_key[:8]}...{service.api_key[-4:]}" if service.api_key else "  API Key: NOT SET")
    
    # Test with a public demo video
    # Using Shotstack's own demo video
    demo_video_url = "https://shotstack-assets.s3.amazonaws.com/footage/beach-overhead.mp4"
    
    print(f"\nTest Parameters:")
    print(f"  Video URL: {demo_video_url}")
    print(f"  Start time: 2.0 seconds")
    print(f"  End time: 7.0 seconds")
    print(f"  Duration: 5.0 seconds")
    
    try:
        # Create a 5-second clip starting at 2 seconds
        print(f"\n📤 Creating render job...")
        render_id = service.create_clip(
            media_url=demo_video_url,
            start_time=2.0,
            end_time=7.0,
            is_audio_only=False,
            output_format='mp4'
        )
        
        print(f"\n✓ Render job created successfully!")
        print(f"  Render ID: {render_id}")
        
        # Check initial status
        print(f"\n🔍 Checking render status...")
        status = service.get_render_status(render_id)
        
        print(f"\n✓ Status retrieved!")
        print(f"  Status: {status['status']}")
        print(f"  Progress: {status.get('progress', 0)}%")
        if status.get('url'):
            print(f"  URL: {status['url']}")
        
        return {
            'success': True,
            'render_id': render_id,
            'status': status
        }
        
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }


if __name__ == '__main__':
    result = test_shotstack_basic()
    
    if result['success']:
        print(f"\n{'='*60}")
        print("TEST PASSED ✓")
        print(f"{'='*60}")
        print(f"\nRender ID: {result['render_id']}")
        print(f"You can check the status with:")
        print(f"  python tests/test_stage4_clip_creation.py --check-status {result['render_id']}")
    else:
        print(f"\n{'='*60}")
        print("TEST FAILED ✗")
        print(f"{'='*60}")
        sys.exit(1)
