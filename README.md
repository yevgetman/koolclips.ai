# Viral Clips - AI-Powered Video Clipping Tool

🚀 **Live Production App:** [www.koolclips.ai](https://www.koolclips.ai/api/)

Automate the creation of short-form viral clips from long-form content like podcasts using AI.

**Status:** ✅ Fully operational in production with complete cloud storage integration

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
                        (FFmpeg + S3)      (ElevenLabs)        (Claude/GPT)      (Shotstack + S3)
                             ↓                     ↓                    ↓                  ↓
                       Cloudcube Storage    Download from S3    LLM Analysis     Public CDN URLs
```

### Cloud Infrastructure

**Production Deployment:**
- **Platform:** Heroku (www.koolclips.ai)
- **Storage:** Cloudcube (AWS S3)
- **Database:** Heroku Postgres
- **Cache:** Heroku Redis
- **Workers:** Celery on Heroku dynos
- **CDN:** Public S3 URLs with automatic cube prefixing

### Pipeline Stages

1. **Stage 1 - Preprocessing**: Extract audio from video files using ffmpeg, upload to cloud storage
   - Video: Extract audio → Upload to S3
   - Audio: Upload directly to S3 (no extraction)
   - Output: Public S3 URLs with Cloudcube prefixing

2. **Stage 2 - Transcription**: Download from S3, convert audio to text with timestamps via ElevenLabs
   - Downloads audio from cloud storage
   - Generates transcript JSON with word-level timestamps
   - Stores structured data in database

3. **Stage 3 - Segment Identification**: Use LLM to identify viral segments
   - Analyzes transcript for viral potential
   - Generates engaging titles, descriptions, reasoning
   - Creates segments with precise timing

4. **Stage 4 - Clip Creation**: Generate video clips via Shotstack, deliver via CDN
   - Renders clips using Shotstack API
   - Downloads and uploads to S3
   - Generates public CDN URLs

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
│   ├── settings.py         # Auto-detects Cloudcube, configures S3
│   ├── urls.py
│   ├── wsgi.py
│   ├── asgi.py
│   └── celery.py           # Redis SSL configuration
├── viral_clips/           # Main application
│   ├── models.py          # Database models with S3 URL fields
│   ├── views.py           # API views
│   ├── serializers.py     # REST serializers with S3 integration
│   ├── tasks.py           # Celery tasks (4-stage pipeline with S3)
│   ├── storage_backends.py # Custom Cloudcube storage backend
│   ├── services/          # External API integrations
│   │   ├── s3_service.py              # S3 upload/download utility
│   │   ├── cloudcube_adapter.py       # Cloudcube prefix handling
│   │   ├── preprocessing_service.py   # Stage 1: Audio extraction
│   │   ├── elevenlabs_service.py      # Stage 2: Transcription
│   │   ├── llm_service.py             # Stage 3: Segment analysis
│   │   └── shotstack_service.py       # Stage 4: Clip creation
│   ├── migrations/        # Database migrations
│   └── management/        # CLI commands
│       └── commands/
├── tests/                 # Local development tests
├── test_stage1_production.py          # Production Stage 1 test
├── test_stage1_audio_production.py    # Production audio test
├── test_stage2_production.py          # Production Stage 2 test  
├── test_stage3_production.py          # Production Stage 3 test
├── test_stage4_production.py          # Production Stage 4 test
├── Procfile               # Heroku process definitions
├── runtime.txt            # Python version for Heroku
├── requirements.txt       # Python dependencies
├── README.md
└── docs/                  # Documentation (gitignored)
    ├── HEROKU_DEPLOYMENT.md
    ├── CLOUDCUBE_QUICKSTART.md
    ├── AWS_SETUP_GUIDE.md
    └── STORAGE_RECOMMENDATION.md
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

The project includes comprehensive testing for both local development and production environments.

### Production Testing (Live API)

Test the complete production pipeline at www.koolclips.ai:

```bash
# Test Stage 1: Video Preprocessing
python3 test_stage1_production.py

# Test Stage 1: Audio Preprocessing  
python3 test_stage1_audio_production.py

# Test Stage 2: Transcription (both video and audio)
python3 test_stage2_production.py

# Test Stage 3: LLM Analysis
python3 test_stage3_production.py

# Test Stage 4: Shotstack Rendering & CDN Delivery
python3 test_stage4_production.py
```

**Production Test Features:**
- ✅ Tests against live www.koolclips.ai API
- ✅ Validates complete workflow from upload to public URL
- ✅ Verifies Cloudcube storage integration
- ✅ Tests ElevenLabs, LLM, and Shotstack APIs
- ✅ Confirms public CDN URL accessibility
- ✅ Provides downloadable clip URLs for inspection

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

## Production Deployment

### Current Production Setup

**Live URL:** [www.koolclips.ai](https://www.koolclips.ai/api/)

**Infrastructure:**
- ✅ **Heroku Platform**: Web and worker dynos
- ✅ **Cloudcube Storage**: AWS S3 with automatic prefixing
- ✅ **Heroku Postgres**: Production database
- ✅ **Heroku Redis**: Celery broker with SSL
- ✅ **Custom Domain**: www.koolclips.ai configured
- ✅ **Gunicorn**: WSGI server with 180s timeout for uploads
- ✅ **Celery Workers**: Background job processing

**Cost:** ~$27/month
- Heroku Eco Dynos: $7/month (web + worker)
- Heroku Postgres Mini: $5/month
- Heroku Redis Mini: $3/month
- Cloudcube Practice: $5/month
- Heroku SSL: Included

### Cloud Storage Integration

**Cloudcube (Production):**
- Automatic cube prefix: `mkwcrxocz0mi/public/`
- Public files in `/public/` folder
- Direct S3 URLs: `https://cloud-cube.s3.us-east-1.amazonaws.com/...`
- Auto-configured via `CLOUDCUBE_URL` environment variable

**AWS S3 + CloudFront (Alternative):**
- Standalone AWS setup supported
- CloudFront CDN for faster delivery
- Separate input/output buckets
- See `/docs/AWS_SETUP_GUIDE.md` for configuration

### Heroku Deployment

```bash
# Deploy to Heroku
git push heroku master

# Scale dynos
heroku ps:scale web=1 worker=1

# View logs
heroku logs --tail

# Run migrations
heroku run python manage.py migrate

# Set environment variables
heroku config:set ELEVENLABS_API_KEY=your-key
heroku config:set ANTHROPIC_API_KEY=your-key
heroku config:set SHOTSTACK_API_KEY=your-key
```

See `/docs/HEROKU_DEPLOYMENT.md` for complete deployment guide.

### Production Monitoring

1. **File Storage**: ✅ Cloudcube (S3) with public URLs
2. **Video URLs**: ✅ Publicly accessible for Shotstack
3. **API Keys**: ✅ Secured via Heroku config vars
4. **Celery**: ✅ Production-ready with Redis SSL
5. **Database**: ✅ Heroku Postgres with connection pooling
6. **Monitoring**: Available via Heroku metrics
7. **Rate Limiting**: Django REST framework throttling
8. **Authentication**: DRF token authentication supported

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

## Recent Updates

### ✅ Completed (v1.0 - Production Ready)

- ✅ **Production Deployment**: Fully deployed on Heroku at www.koolclips.ai
- ✅ **Cloud Storage**: Cloudcube integration for persistent file storage
- ✅ **Custom Domain**: www.koolclips.ai configured with SSL
- ✅ **Complete Testing**: Production test suite for all 4 stages
- ✅ **Public CDN**: Automatic public URL generation for clips
- ✅ **Error Handling**: Robust error handling and logging
- ✅ **Gunicorn Config**: Optimized for video uploads (180s timeout)
- ✅ **Worker Scaling**: Celery workers for background processing

## Roadmap

### Next (v1.1)
- [ ] Web UI dashboard for job monitoring
- [ ] Webhook notifications for job completion
- [ ] API authentication/authorization
- [ ] Rate limiting per user

### Future (v2.0)
- [ ] Batch processing for multiple videos
- [ ] Custom branding/watermarks
- [ ] Social media auto-posting (Twitter, TikTok, YouTube)
- [ ] Advanced analytics (view counts, engagement)
- [ ] Support for more video formats
- [ ] Multi-language support
