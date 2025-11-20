# Viral Clips Testing Framework

Modular testing framework for the 4-stage viral clips pipeline.

## Quick Start

### 1. Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt

# Install ffmpeg (required for Stage 1)
brew install ffmpeg  # macOS
```

### 2. Configure API Keys

Create/update `.env` file:
```env
ELEVENLABS_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
SHOTSTACK_API_KEY=your_key_here
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-opus-20240229
```

**Note:** Anthropic Claude is recommended for better content analysis and higher token limits.

### 3. Run Tests

```bash
# Test individual stage
python tests/test_stage1_preprocessing.py video.mp4

# Test complete pipeline
python tests/test_runner.py --input video.mp4 --all-stages

# Test with sample fixtures (no API calls)
python tests/test_stage3_segment_identification.py tests/fixtures/sample_transcript.json
```

## The 4 Stages

### Stage 1: Preprocessing
- **Input:** Video or audio file
- **Output:** Audio file (mp3)
- **Test:** `test_stage1_preprocessing.py`

### Stage 2: Transcription
- **Input:** Audio file
- **Output:** Transcript JSON with timestamps
- **Test:** `test_stage2_transcription.py`
- **API:** ElevenLabs

### Stage 3: Segment Identification
- **Input:** Transcript JSON, parameters (num_segments, duration)
- **Output:** Viral segments with titles and timestamps
- **Test:** `test_stage3_segment_identification.py`
- **API:** OpenAI or Anthropic

### Stage 4: Clip Creation
- **Input:** Original media file, timestamps
- **Output:** Video clip
- **Test:** `test_stage4_clip_creation.py`
- **API:** Shotstack

## Test Files

```
tests/
├── __init__.py                             # Package init
├── README.md                               # This file
├── test_stage1_preprocessing.py            # Stage 1 tests
├── test_stage2_transcription.py            # Stage 2 tests
├── test_stage3_segment_identification.py   # Stage 3 tests
├── test_stage4_clip_creation.py            # Stage 4 tests
├── test_runner.py                          # Integrated testing
└── fixtures/                               # Sample data
    ├── README.md
    ├── sample_transcript.json
    └── sample_segments.json
```

## Common Commands

### Individual Stage Testing

```bash
# Stage 1: Preprocessing
python tests/test_stage1_preprocessing.py video.mp4
python tests/test_stage1_preprocessing.py --test-video video.mp4 --output-format wav
python tests/test_stage1_preprocessing.py --test-info media.mp4

# Stage 2: Transcription
python tests/test_stage2_transcription.py audio.mp3
python tests/test_stage2_transcription.py --from-stage1 test_outputs/stage1/preprocessing_result.json

# Stage 3: Segment Identification
python tests/test_stage3_segment_identification.py transcript.json
python tests/test_stage3_segment_identification.py --from-stage2 test_outputs/stage2/transcript.json
python tests/test_stage3_segment_identification.py transcript.json --num-segments 3 --max-duration 120

# Stage 4: Clip Creation
python tests/test_stage4_clip_creation.py video.mp4 10.5 45.2
python tests/test_stage4_clip_creation.py --from-stage3 test_outputs/stage3/segments.json --segment-index 0
python tests/test_stage4_clip_creation.py --check-status <render_id>
```

### Integrated Testing

```bash
# Complete pipeline
python tests/test_runner.py --input video.mp4 --all-stages

# With clip creation
python tests/test_runner.py --input video.mp4 --all-stages --create-clips

# Custom parameters
python tests/test_runner.py --input podcast.mp3 --all-stages \
  --num-segments 3 --min-duration 45 --max-duration 120
```

### Testing with Fixtures

```bash
# Test Stage 3 without API calls
python tests/test_stage3_segment_identification.py tests/fixtures/sample_transcript.json

# Test Stage 4 setup
python tests/test_stage4_clip_creation.py --from-stage3 tests/fixtures/sample_segments.json
```

## Output Structure

Each test run creates organized output:

```
test_outputs/
├── stage1/              # Individual stage outputs
├── stage2/
├── stage3/
├── stage4/
└── run_20241120_090000/ # Integrated test run
    ├── run_summary.json
    ├── stage1/
    ├── stage2/
    ├── stage3/
    └── stage4/
```

## Key Features

✅ **Independent Testing** - Test each stage separately  
✅ **Pipeline Testing** - Run all stages together  
✅ **Sample Fixtures** - Test without API calls  
✅ **Detailed Output** - JSON files for each stage  
✅ **Validation** - Automatic checks for data integrity  
✅ **Flexible Parameters** - Customize segments, durations, formats  

## Troubleshooting

### Common Issues

**"ffmpeg is not installed"**
```bash
brew install ffmpeg
```

**"API key not configured"**
- Check `.env` file exists
- Verify keys are correct
- Restart Django server

**"Media file must be publicly accessible" (Stage 4)**
- Upload to cloud storage, or
- Use ngrok for local testing

### Get Help

```bash
# Show help for any test
python tests/test_stage1_preprocessing.py --help
python tests/test_runner.py --help
```

## Documentation

📚 **Comprehensive Guide:** See [`doc/TESTING_FRAMEWORK.md`](../doc/TESTING_FRAMEWORK.md)

Topics covered:
- Detailed command reference
- Expected inputs/outputs for each stage
- API configuration
- Advanced usage
- Best practices
- CI/CD integration

## Example Workflow

```bash
# 1. Process video to audio
python tests/test_stage1_preprocessing.py podcast_episode.mp4

# 2. Transcribe audio
python tests/test_stage2_transcription.py \
  --from-stage1 test_outputs/stage1/preprocessing_result.json

# 3. Identify viral segments
python tests/test_stage3_segment_identification.py \
  --from-stage2 test_outputs/stage2/podcast_episode_transcript.json \
  --num-segments 3

# 4. Create clip for best segment
python tests/test_stage4_clip_creation.py \
  --from-stage3 test_outputs/stage3/viral_segments_*.json \
  --from-stage1 test_outputs/stage1/preprocessing_result.json \
  --segment-index 0
```

Or run all at once:

```bash
python tests/test_runner.py --input podcast_episode.mp4 --all-stages
```

## Development Tips

1. **Use fixtures during development** to avoid API costs
2. **Save successful outputs** as new fixtures
3. **Test incrementally** - verify each stage before moving forward
4. **Monitor API usage** - track costs with test runs

## Next Steps

1. ✅ Install dependencies and ffmpeg
2. ✅ Configure API keys in `.env`
3. ✅ Run Stage 1 test with a video file
4. ✅ Try the complete pipeline
5. ✅ Read full documentation in `doc/TESTING_FRAMEWORK.md`

---

**Questions or Issues?**  
Check the [full documentation](../doc/TESTING_FRAMEWORK.md) or review the service implementations in `viral_clips/services/`.
