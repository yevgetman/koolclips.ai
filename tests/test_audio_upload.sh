#!/bin/bash

# Test Audio Upload Script
# This script demonstrates uploading an audio file to the Viral Clips API

echo "======================================================================"
echo "Testing Audio File Upload"
echo "======================================================================"
echo ""

# Check if audio file path provided
if [ -z "$1" ]; then
    echo "Usage: ./test_audio_upload.sh /path/to/audio.mp3"
    echo ""
    echo "Supported formats: mp3, wav, m4a, aac, ogg, flac, and more"
    echo ""
    echo "Example:"
    echo "  ./test_audio_upload.sh test_files/podcast.mp3"
    exit 1
fi

AUDIO_FILE="$1"

# Check if file exists
if [ ! -f "$AUDIO_FILE" ]; then
    echo "❌ Error: File not found: $AUDIO_FILE"
    exit 1
fi

echo "📁 Audio file: $AUDIO_FILE"
echo "📊 File size: $(du -h "$AUDIO_FILE" | cut -f1)"
echo ""
echo "🚀 Uploading to API..."
echo ""

# Upload the file
RESPONSE=$(curl -s -X POST http://127.0.0.1:8000/api/jobs/ \
  -F "media_file=@$AUDIO_FILE" \
  -F "num_segments=3" \
  -F "min_duration=60" \
  -F "max_duration=180")

# Parse response
JOB_ID=$(echo "$RESPONSE" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
FILE_TYPE=$(echo "$RESPONSE" | grep -o '"file_type":"[^"]*"' | cut -d'"' -f4)
STATUS=$(echo "$RESPONSE" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)

if [ -z "$JOB_ID" ]; then
    echo "❌ Upload failed!"
    echo "Response: $RESPONSE"
    exit 1
fi

echo "✅ Upload successful!"
echo ""
echo "Job Details:"
echo "  Job ID: $JOB_ID"
echo "  File Type: $FILE_TYPE"
echo "  Status: $STATUS"
echo ""
echo "======================================================================"
echo "Monitoring Progress..."
echo "======================================================================"
echo ""

# Monitor progress
for i in {1..60}; do
    STATUS_RESPONSE=$(curl -s "http://127.0.0.1:8000/api/jobs/$JOB_ID/status/")
    CURRENT_STATUS=$(echo "$STATUS_RESPONSE" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    SEGMENTS_COUNT=$(echo "$STATUS_RESPONSE" | grep -o '"segments_identified":[0-9]*' | cut -d':' -f2)
    CLIPS_COMPLETED=$(echo "$STATUS_RESPONSE" | grep -o '"clips_completed":[0-9]*' | cut -d':' -f2)
    
    echo "[$i/60] Status: $CURRENT_STATUS | Segments: $SEGMENTS_COUNT | Clips: $CLIPS_COMPLETED"
    
    if [ "$CURRENT_STATUS" = "completed" ]; then
        echo ""
        echo "======================================================================"
        echo "✅ Processing Complete!"
        echo "======================================================================"
        echo ""
        echo "🎬 Fetching clips..."
        echo ""
        
        # Get clips
        CLIPS_RESPONSE=$(curl -s "http://127.0.0.1:8000/api/jobs/$JOB_ID/clips/")
        echo "$CLIPS_RESPONSE" | python3 -m json.tool
        
        echo ""
        echo "======================================================================"
        echo "View results:"
        echo "  http://127.0.0.1:8000/api/jobs/$JOB_ID/"
        echo "======================================================================"
        exit 0
    fi
    
    if [ "$CURRENT_STATUS" = "failed" ]; then
        echo ""
        echo "❌ Processing failed!"
        echo "Check details: http://127.0.0.1:8000/api/jobs/$JOB_ID/"
        exit 1
    fi
    
    sleep 5
done

echo ""
echo "⏱️ Monitoring timeout (5 minutes)"
echo "Job still processing. Check status at:"
echo "  http://127.0.0.1:8000/api/jobs/$JOB_ID/"
