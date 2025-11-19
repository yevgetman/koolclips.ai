# Viral Clips - AI-Powered Video Clipping Tool

Automate the creation of short-form viral clips from long-form content like podcasts using AI.

## Overview

This tool uses a combination of APIs and AI models to:
1. **Extract transcripts** with timestamps from video or audio files (Eleven Labs)
2. **Analyze content** to identify the most viral, provocative segments (OpenAI/Claude)
3. **Create clips** automatically based on identified segments (Shotstack)

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
Video Upload → Eleven Labs → Transcript → LLM Analysis → Viral Segments → Shotstack → Clips
```

## Installation

### Prerequisites

- **Python 3.11 or 3.12** (recommended)
  - ⚠️ **Python 3.13 has SSL issues on macOS** - see [PYTHON_VERSION_FIX.md](PYTHON_VERSION_FIX.md)
- Redis (for Celery)
- ffmpeg (for video processing)

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
- `SHOTSTACK_SANDBOX_API_KEY` - Get from https://shotstack.io (sandbox)
- `SHOTSTACK_PRODUCTION_API_KEY` - Get from https://shotstack.io (production)
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
  "num_segments": 5,
  "created_at": "2024-01-01T12:00:00Z"
}
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
LLM_PROVIDER=openai
LLM_MODEL=gpt-4-turbo-preview

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# File Storage
MEDIA_ROOT=/tmp/viral_clips_media
```

### LLM Models

**OpenAI Options:**
- `gpt-4-turbo-preview` (recommended)
- `gpt-4`
- `gpt-3.5-turbo`

**Anthropic Options:**
- `claude-3-opus-20240229`
- `claude-3-sonnet-20240229`
- `claude-3-haiku-20240307`

## Project Structure

```
viral-clips/
├── config/                 # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── celery.py
├── viral_clips/           # Main application
│   ├── models.py          # Database models
│   ├── views.py           # API views
│   ├── serializers.py     # REST serializers
│   ├── tasks.py           # Celery tasks
│   ├── services/          # External API integrations
│   │   ├── elevenlabs_service.py
│   │   ├── llm_service.py
│   │   └── shotstack_service.py
│   └── management/        # CLI commands
│       └── commands/
│           ├── process_video.py
│           └── check_job.py
├── requirements.txt
└── README.md
```

## Development Workflow

1. **Video Upload**: User uploads a video via API or CLI
2. **Transcription**: Eleven Labs extracts transcript with timestamps
3. **Analysis**: LLM analyzes transcript to identify viral segments
4. **Clipping**: Shotstack creates clips based on timestamps
5. **Delivery**: Clips are available via API or downloadable

## Models

### VideoJob
- Tracks overall processing status
- Stores configuration (num_segments, duration limits)
- Links to transcript and segments

### TranscriptSegment
- Identified viral segment
- Contains title, description, reasoning
- Includes precise timestamps

### ClippedVideo
- Rendered video clip
- Links to source segment
- Stores video URL and status

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
