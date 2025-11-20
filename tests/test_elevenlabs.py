#!/usr/bin/env python3
"""
Test script for ElevenLabs service integration
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from viral_clips.services import ElevenLabsService


def test_service_initialization():
    """Test 1: Service initialization and API key configuration"""
    print("\n" + "="*60)
    print("TEST 1: Service Initialization")
    print("="*60)
    
    try:
        service = ElevenLabsService()
        print("✅ Service initialized successfully")
        print(f"   API Key configured: {service.api_key[:8]}..." if service.api_key else "No API key")
        print(f"   Client created: {service.client is not None}")
        return service
    except ValueError as e:
        print(f"❌ Service initialization failed: {e}")
        print("\n💡 Make sure ELEVENLABS_API_KEY is set in your .env file")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None


def test_transcription_with_demo_file(service):
    """Test 2: Transcribe a demo file"""
    print("\n" + "="*60)
    print("TEST 2: Transcription with Demo File")
    print("="*60)
    
    # Check for demo files
    demo_files = [
        'demo_files/diazreport1.mp3',
        'demo_files/diazreport2.mp4'
    ]
    
    test_file = None
    for file in demo_files:
        if os.path.exists(file):
            test_file = file
            break
    
    if not test_file:
        print("⚠️  No demo files found. Skipping transcription test.")
        print("   Place a test audio/video file in demo_files/ to test transcription")
        return False
    
    print(f"📁 Using test file: {test_file}")
    file_size = os.path.getsize(test_file) / 1024 / 1024  # MB
    print(f"   File size: {file_size:.2f} MB")
    
    # Check if file is too large (>10MB for quick test)
    if file_size > 10:
        print(f"⚠️  File is large ({file_size:.2f} MB). This may take a while and use API credits.")
        response = input("   Continue? (y/n): ")
        if response.lower() != 'y':
            print("   Test skipped by user")
            return False
    
    try:
        print("\n🔄 Starting transcription...")
        print("   (This will use ElevenLabs API credits)")
        
        result = service.transcribe_video(test_file)
        
        print("\n✅ Transcription successful!")
        print("\n📊 Results:")
        print(f"   Full text preview: {result['full_text'][:200]}...")
        print(f"   Total words: {len(result['words'])}")
        print(f"   Duration: {result['metadata']['duration']:.2f} seconds")
        print(f"   Language: {result['metadata']['language']}")
        print(f"   Confidence: {result['metadata']['language_probability']:.2%}")
        
        if result['words']:
            print(f"\n   First word: {result['words'][0]}")
            print(f"   Last word: {result['words'][-1]}")
        
        if result['metadata'].get('transcription_id'):
            print(f"   Transaction ID: {result['metadata']['transcription_id']}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Transcription failed: {e}")
        print("\n🔍 Possible issues:")
        print("   • Invalid or expired API key")
        print("   • Insufficient credits in ElevenLabs account")
        print("   • Network connectivity issues")
        print("   • File format not supported")
        return False


def test_response_format(service):
    """Test 3: Validate response format handling"""
    print("\n" + "="*60)
    print("TEST 3: Response Format Validation")
    print("="*60)
    
    # Create a mock response to test parsing
    mock_response = {
        'text': 'This is a test transcript',
        'language_code': 'en',
        'language_probability': 0.95,
        'words': [
            {'text': 'This', 'start': 0.0, 'end': 0.3},
            {'text': 'is', 'start': 0.4, 'end': 0.5},
            {'text': 'a', 'start': 0.6, 'end': 0.7},
            {'text': 'test', 'start': 0.8, 'end': 1.2},
        ],
        'transcription_id': 'test123'
    }
    
    try:
        formatted = service._format_transcript(mock_response)
        
        # Validate structure
        assert 'full_text' in formatted, "Missing 'full_text' key"
        assert 'words' in formatted, "Missing 'words' key"
        assert 'metadata' in formatted, "Missing 'metadata' key"
        
        # Validate content
        assert formatted['full_text'] == mock_response['text'], "Text mismatch"
        assert len(formatted['words']) == len(mock_response['words']), "Word count mismatch"
        assert formatted['metadata']['language'] == 'en', "Language mismatch"
        
        # Test duration calculation
        duration = service.get_transcript_duration(formatted)
        assert duration == 1.2, f"Duration mismatch: expected 1.2, got {duration}"
        
        print("✅ Response format validation passed")
        print(f"   Structure: {list(formatted.keys())}")
        print(f"   Duration calculation: {duration}s")
        return True
        
    except AssertionError as e:
        print(f"❌ Format validation failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "🧪 " + "="*58)
    print("   ElevenLabs Service Integration Test Suite")
    print("="*60)
    
    # Test 1: Initialization
    service = test_service_initialization()
    if not service:
        print("\n❌ Cannot proceed without valid service initialization")
        sys.exit(1)
    
    # Test 3: Response format (doesn't require API call)
    format_ok = test_response_format(service)
    
    # Test 2: Actual transcription (requires API key and credits)
    print("\n" + "⚠️ " + "="*58)
    print("   The next test will make a real API call to ElevenLabs")
    print("   This will use API credits from your account")
    print("="*60)
    
    response = input("\nProceed with live transcription test? (y/n): ")
    if response.lower() == 'y':
        transcription_ok = test_transcription_with_demo_file(service)
    else:
        print("\n⏭️  Live transcription test skipped")
        transcription_ok = None
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"✅ Service Initialization: PASSED")
    print(f"{'✅' if format_ok else '❌'} Response Format: {'PASSED' if format_ok else 'FAILED'}")
    if transcription_ok is not None:
        print(f"{'✅' if transcription_ok else '❌'} Live Transcription: {'PASSED' if transcription_ok else 'FAILED'}")
    else:
        print(f"⏭️  Live Transcription: SKIPPED")
    
    print("\n" + "="*60)
    
    if format_ok and (transcription_ok is None or transcription_ok):
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed. Check output above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
