# Viral Clips - AI-Powered Video Clipping Tool

Automate the creation of short-form viral clips from long-form content like podcasts using AI.

## Overview

This tool uses a 4-stage pipeline with AI and automation:
1. **Preprocess media** - Extract audio from video files (ffmpeg) or validate audio files
2. **Extract transcripts** with word-level timestamps from audio (ElevenLabs)
3. **Analyze content** to identify the most viral, provocative segments (OpenAI/Anthropic)
4. **Create clips** automatically based on identified segments (Shotstack)

### 🎵 **NEW: Audio File Support!**
Upload audio files directly (MP3, WAV, M4A, etc.) for faster processing and smaller file sizes. The tool will automatically create video clips with waveform visualizations. [Learn more](AUDIO_SUPPORT.md)

## Features

- 🎥 **Automated Video Processing**: Upload a video and get viral clips automatically
- 🎵 **Audio File Support**: Upload audio files (MP3, WAV, etc.) with automatic waveform visualization
- 🤖 **AI-Powered Analysis**: Uses GPT-4 or Claude to identify engaging content
- 📝 **Transcript Extraction**: Accurate timestamps for precise clipping
- 🎬 **Professional Clips**: High-quality video clips ready for social media
- 🔄 **Async Processing**: Background job processing with Celery
- 🌐 **REST API**: Full-featured API for integration
- 💻 **CLI Tool**: Command-line interface for direct usage
- 📊 **Admin Interface**: Django admin for monitoring and management

## Architecture

```
Upload (Video/Audio) → Stage 1: Preprocessing → Stage 2: Transcription → Stage 3: Analysis → Stage 4: Clipping
                        (Audio Extract)    (ElevenLabs)        (Claude/GPT)      (Shotstack)
```

### Pipeline Stages

1. **Stage 1 - Preprocessing**: Extract audio from video files using ffmpeg (audio files pass through)
2. **Stage 2 - Transcription**: Convert audio to text with word-level timestamps via ElevenLabs
3. **Stage 3 - Segment Identification**: Use LLM to identify viral segments
4. **Stage 4 - Clip Creation**: Generate video clips via Shotstack API

Each stage can be tested independently. See [Testing Framework](#testing-framework).

## Installation

### Prerequisites

- **Python 3.11 or 3.12** (recommended)
  - ⚠️ **Python 3.13 has SSL issues on macOS** - see [PYTHON_VERSION_FIX.md](PYTHON_VERSION_FIX.md)
- **Redis** (for Celery background tasks)
- **ffmpeg** (required for Stage 1 - audio extraction from video)
  ```bash
  # macOS
  brew install ffmpeg
  
  # Ubuntu/Debian
  sudo apt-get install ffmpeg
  
  # Verify installation
  ffmpeg -version
  ```

### Setup

1. **Clone the repository**
```bash
git clone <repository-url>
cd viral-clips
```

2. **Create and activate virtual environment**
```bash
# Use Python 3.11 or 3.12 (avoid Python 3.13 due to SSL issues)
python3.11 -m venv venv  # or python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your API keys
```

Required API keys:
- `ELEVENLABS_API_KEY` - Get from https://elevenlabs.io
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` - For LLM analysis
  - **Recommended:** Anthropic Claude (better for content analysis)
- `SHOTSTACK_API_KEY` - Get from https://shotstack.io
- `SHOTSTACK_ENV` - Set to `sandbox` or `production` (default: sandbox)

5. **Run migrations**
```bash
python manage.py migrate
```

6. **Create superuser (optional, for admin access)**
```bash
python manage.py createsuperuser
```

7. **Start Redis** (in a separate terminal)
```bash
redis-server
```

8. **Start Celery worker** (in a separate terminal)
```bash
celery -A config worker -l info
```

9. **Start Django development server**
```bash
python manage.py runserver
```

## Usage

### Option 1: REST API

#### Submit a Video for Processing

```bash
# With video file
curl -X POST http://localhost:8000/api/jobs/ \
  -F "media_file=@/path/to/video.mp4" \
  -F "num_segments=5" \
  -F "min_duration=60" \
  -F "max_duration=180"

# With audio file (auto-creates video with waveform)
curl -X POST http://localhost:8000/api/jobs/ \
  -F "media_file=@/path/to/podcast.mp3" \
  -F "num_segments=5"
```

Response:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "file_type": "video",
  "num_segments": 5,
  "created_at": "2024-01-01T12:00:00Z"
}
```

**Job Status Values:**
- `pending` - Job created, waiting to start
- `preprocessing` - Extracting audio from video (Stage 1)
- `transcribing` - Converting audio to text (Stage 2)
- `analyzing` - Identifying viral segments (Stage 3)
- `clipping` - Creating video clips (Stage 4)
- `completed` - All clips ready
- `failed` - Error occurred (check `error_message`)
```

#### Check Job Status

```bash
curl http://localhost:8000/api/jobs/{job_id}/status/
```

Response:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": {
    "total_segments": 5,
    "segments_identified": 5,
    "clips_completed": 5
  },
  "segments": [
    {
      "id": "...",
      "title": "Controversial Take on AI Safety",
      "start_time": 145.2,
      "end_time": 267.8,
      "clip_status": "completed",
      "clip_url": "https://..."
    }
  ]
}
```

#### Get Completed Clips

```bash
curl http://localhost:8000/api/jobs/{job_id}/clips/
```

Response:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_clips": 5,
  "clips": [
    {
      "clip_id": "...",
      "segment_title": "Controversial Take on AI Safety",
      "video_url": "https://...",
      "start_time": 145.2,
      "end_time": 267.8,
      "duration": 122.6,
      "completed_at": "2024-01-01T12:15:00Z"
    }
  ]
}
```

### Option 2: Command Line

#### Process a Video or Audio File

```bash
# Process video
python manage.py process_video /path/to/video.mp4 --segments 5 --wait

# Process audio (creates video with waveform)
python manage.py process_video /path/to/podcast.mp3 --segments 5 --wait
```

Options:
- `--segments N` - Number of segments to generate (default: 5)
- `--min-duration SECONDS` - Minimum segment duration (default: 60)
- `--max-duration SECONDS` - Maximum segment duration (default: 180)
- `--wait` - Wait for processing to complete and show results

#### Check Job Status

```bash
python manage.py check_job {job_id}
```

## API Reference

### Endpoints

#### Jobs

- `GET /api/jobs/` - List all jobs
- `POST /api/jobs/` - Create a new job
- `GET /api/jobs/{id}/` - Get job details
- `GET /api/jobs/{id}/status/` - Get job status with progress
- `GET /api/jobs/{id}/clips/` - Get completed clips for a job

#### Segments

- `GET /api/segments/` - List all segments
- `GET /api/segments/?job_id={id}` - List segments for a job
- `GET /api/segments/{id}/` - Get segment details

#### Clips

- `GET /api/clips/` - List all clips
- `GET /api/clips/?status=completed` - Filter clips by status
- `GET /api/clips/?job_id={id}` - List clips for a job
- `GET /api/clips/{id}/` - Get clip details

## Configuration

### Environment Variables

```bash
# Django Settings
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# API Keys
ELEVENLABS_API_KEY=your-elevenlabs-api-key
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key

# Shotstack (separate keys for sandbox and production)
SHOTSTACK_SANDBOX_API_KEY=your-shotstack-sandbox-api-key
SHOTSTACK_PRODUCTION_API_KEY=your-shotstack-production-api-key
SHOTSTACK_ENV=sandbox

# LLM Provider (openai or anthropic)
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-opus-20240229

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# File Storage
MEDIA_ROOT=/tmp/viral_clips_media
```

### LLM Models

**Anthropic (Recommended):**
- `claude-3-opus-20240229` ✅ (best for content analysis, higher token limits)
- `claude-3-sonnet-20240229`
- `claude-3-haiku-20240307`

**OpenAI:**
- `gpt-4o` (latest model)
- `gpt-4-turbo`
- `gpt-4`

**Note:** Anthropic Claude is recommended over OpenAI due to:
- Higher token limits (200k vs 30k)
- Better handling of long transcripts
- Fewer content policy restrictions

## Project Structure

```
viral-clips/
├── config/                 # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── celery.py
├── viral_clips/           # Main application
│   ├── models.py          # Database models (VideoJob, TranscriptSegment, ClippedVideo)
│   ├── views.py           # API views
│   ├── serializers.py     # REST serializers
│   ├── tasks.py           # Celery tasks (4-stage pipeline)
│   ├── services/          # External API integrations (4 stages)
│   │   ├── preprocessing_service.py    # Stage 1: Audio extraction
│   │   ├── elevenlabs_service.py       # Stage 2: Transcription
│   │   ├── llm_service.py              # Stage 3: Segment analysis
│   │   └── shotstack_service.py        # Stage 4: Clip creation
│   └── management/        # CLI commands
│       └── commands/
│           ├── process_video.py
│           └── check_job.py
├── tests/                 # Testing framework (modular per stage)
│   ├── test_stage1_preprocessing.py
│   ├── test_stage2_transcription.py
│   ├── test_stage3_segment_identification.py
│   ├── test_stage4_clip_creation.py
│   ├── test_runner.py     # Integrated pipeline testing
│   └── fixtures/          # Sample test data
├── requirements.txt
├── README.md
└── QUICKSTART.md
```

## Development Workflow

1. **Upload**: User uploads video/audio via API or CLI (status: `pending`)
2. **Preprocessing** (Stage 1): Extract audio from video using ffmpeg (status: `preprocessing`)
   - Video files: Audio extracted to temporary file
   - Audio files: Pass through without modification
   - Output: Audio file path stored in `extracted_audio_path`
3. **Transcription** (Stage 2): ElevenLabs extracts transcript with word-level timestamps (status: `transcribing`)
   - Model: `scribe_v2`
   - Processing time: ~2 minutes per minute of audio
4. **Analysis** (Stage 3): LLM analyzes transcript to identify viral segments (status: `analyzing`)
   - Provider: Anthropic Claude or OpenAI
   - Processing time: ~15-30 seconds
5. **Clipping** (Stage 4): Shotstack creates clips based on timestamps (status: `clipping`)
   - Parallel processing for each segment
   - Processing time: ~1-2 minutes per clip
6. **Delivery**: Clips available via API (status: `completed`)

## Models

### VideoJob
- Tracks overall processing status through all 4 stages
- Stores configuration (num_segments, min_duration, max_duration)
- Fields:
  - `status`: Current stage (pending, preprocessing, transcribing, analyzing, clipping, completed, failed)
  - `file_type`: 'video' or 'audio'
  - `extracted_audio_path`: Path to extracted audio (for video files)
  - `transcript_json`: Full transcript with word-level timestamps
- Links to segments and clips

### TranscriptSegment
- Identified viral segment
- Contains title, description, reasoning
- Includes precise timestamps

### ClippedVideo
- Rendered video clip
- Links to source segment
- Stores video URL and status

## Testing Framework

The project includes a comprehensive testing framework for validating each stage independently or the complete pipeline.

### Test Individual Stages

```bash
# Stage 1: Preprocessing (audio extraction)
python tests/test_stage1_preprocessing.py /path/to/video.mp4

# Stage 2: Transcription (ElevenLabs)
python tests/test_stage2_transcription.py --from-stage1 test_outputs/stage1/preprocessing_result.json

# Stage 3: Segment Identification (LLM)
python tests/test_stage3_segment_identification.py --from-stage2 test_outputs/stage2/transcript.json

# Stage 4: Clip Creation (Shotstack)
python tests/test_stage4_clip_creation.py --from-stage3 test_outputs/stage3/segments.json
```

### Test Complete Pipeline

```bash
# Run all 4 stages end-to-end
python tests/test_runner.py --input /path/to/video.mp4 --all-stages

# Custom parameters
python tests/test_runner.py --input podcast.mp3 --all-stages \
  --num-segments 3 --min-duration 45 --max-duration 120
```

### Test with Sample Data

```bash
# Test without API calls using fixtures
python tests/test_stage3_segment_identification.py tests/fixtures/sample_transcript.json
```

### Test Features

- ✅ **Independent Stage Testing** - Test each stage in isolation
- ✅ **Chained Testing** - Pass outputs between stages
- ✅ **Sample Fixtures** - Test without hitting external APIs
- ✅ **Validation** - Automatic structure and data validation
- ✅ **Real Services** - Tests use actual production code (not mocks)

See `tests/README.md` for detailed testing documentation.

## Production Considerations

1. **File Storage**: Use S3 or similar for production (not local files)
2. **Video URLs**: Videos need to be publicly accessible for Shotstack
3. **API Keys**: Keep production keys secure and separate
4. **Celery**: Use production broker (RabbitMQ) instead of Redis
5. **Database**: Use PostgreSQL instead of SQLite
6. **Monitoring**: Add logging and error tracking (Sentry)
7. **Rate Limiting**: Implement API rate limiting
8. **Authentication**: Add API authentication/authorization

## Troubleshooting

### Celery worker not processing tasks
```bash
# Check Redis is running
redis-cli ping

# Check Celery worker logs
celery -A config worker -l debug
```

### API key errors
- Verify keys are set in .env file
- Check keys are valid on respective platforms
- Ensure .env file is being loaded

### SSL/Connection errors with Python 3.13
If you see `SSLError(5, '[SYS] unknown error')`:
- Python 3.13.0 has SSL bugs on macOS
- **Solution:** Use Python 3.11 or 3.12 instead
- See detailed fix: [PYTHON_VERSION_FIX.md](PYTHON_VERSION_FIX.md)

### Video upload issues
- Check MEDIA_ROOT directory exists and is writable
- Verify file size limits in Django settings
- Ensure video format is supported

## License

[Your License Here]

## Support

For issues and questions:
- Create an issue on GitHub
- Contact: [your-email]

## Roadmap

- [ ] Support for more video formats
- [ ] Batch processing
- [ ] Custom branding/watermarks
- [ ] Social media auto-posting
- [ ] Advanced analytics
- [ ] Web UI dashboard
