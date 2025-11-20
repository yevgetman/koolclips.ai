# Quick Start Guide

Get up and running with Viral Clips in 5 minutes.

## Prerequisites

- **Python 3.11 or 3.12** (recommended)
  - ⚠️ Python 3.13 has SSL issues - see [PYTHON_VERSION_FIX.md](PYTHON_VERSION_FIX.md)
- **Redis** installed and running
- **ffmpeg** installed (required for video processing)
  ```bash
  # macOS
  brew install ffmpeg
  
  # Ubuntu/Debian
  sudo apt-get install ffmpeg
  ```
- API keys (see below)

## 1. Install Dependencies

```bash
# Use Python 3.11 or 3.12 (avoid Python 3.13)
python3.11 -m venv venv  # or python3.12

# Activate virtual environment
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

## 2. Get API Keys

You'll need these API keys:

1. **Eleven Labs** - https://elevenlabs.io/app/settings/api-keys
2. **Anthropic** (recommended) or OpenAI
   - Anthropic: https://console.anthropic.com/settings/keys
   - OpenAI: https://platform.openai.com/api-keys
3. **Shotstack** - https://dashboard.shotstack.io/api-keys
   - Sandbox is free for testing

**Recommended:** Use Anthropic Claude for better content analysis and higher token limits.

## 3. Configure Environment

Copy and edit the environment file:

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```bash
ELEVENLABS_API_KEY=your-key-here

# LLM Provider (Anthropic recommended)
ANTHROPIC_API_KEY=your-key-here
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-opus-20240229

# Or use OpenAI
# OPENAI_API_KEY=your-key-here
# LLM_PROVIDER=openai
# LLM_MODEL=gpt-4o

# Shotstack (use sandbox for testing)
SHOTSTACK_API_KEY=your-sandbox-key-here
SHOTSTACK_ENV=sandbox
```

## 4. Set Up Database

```bash
python manage.py migrate
```

## 5. Start Services

### Option A: Manual (3 terminals)

**Terminal 1 - Redis:**
```bash
redis-server
```

**Terminal 2 - Celery Worker:**
```bash
celery -A config worker -l info
```

**Terminal 3 - Django Server:**
```bash
python manage.py runserver
```

### Option B: Script (easier)

```bash
./start_services.sh
```

## 6. Test the API

### Using cURL

```bash
curl -X POST http://localhost:8000/api/jobs/ \
  -F "media_file=@/path/to/video.mp4" \
  -F "num_segments=3"
```

You'll get a response with a `job_id`. Use it to check status:

```bash
curl http://localhost:8000/api/jobs/{job_id}/status/
```

### Using CLI

```bash
python manage.py process_video /path/to/video.mp4 --segments 3 --wait
```

### Using Python

```python
import requests

# Upload video
with open('/path/to/video.mp4', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/jobs/',
        files={'media_file': f},
        data={'num_segments': 3}
    )
    job_id = response.json()['id']

# Check status
status = requests.get(
    f'http://localhost:8000/api/jobs/{job_id}/status/'
).json()

print(f"Status: {status['status']}")
```

## 7. Access Admin Panel

Create a superuser:

```bash
python manage.py createsuperuser
```

Then visit: http://localhost:8000/admin/

## Processing Flow (4 Stages)

1. **Upload** → Video/audio saved, job created (status: `pending`)
2. **Preprocessing** (Stage 1) → Extract audio from video (status: `preprocessing`)
   - Video: Audio extracted using ffmpeg (~10-30 sec)
   - Audio: Passes through unchanged
3. **Transcription** (Stage 2) → ElevenLabs extracts transcript (status: `transcribing`)
   - Processing time: ~2 min per minute of audio
4. **Analysis** (Stage 3) → LLM identifies viral segments (status: `analyzing`)
   - Processing time: ~15-30 seconds
5. **Clipping** (Stage 4) → Shotstack creates videos (status: `clipping`)
   - Processing time: ~1-2 min per clip (parallel)
6. **Complete** → Clips available via API (status: `completed`)

## Expected Timeline

For a 1-hour video podcast:
- Preprocessing: 20-30 seconds (audio extraction)
- Transcription: 2 minutes
- Analysis: 30 seconds
- Clipping (5 segments): 10-15 minutes total
- **Total: ~13-18 minutes**

For a 1-hour audio podcast:
- Preprocessing: < 1 second (passthrough)
- Transcription: 2 minutes
- Analysis: 30 seconds
- Clipping (5 segments): 10-15 minutes total
- **Total: ~13-18 minutes**

## Troubleshooting

### "Module not found" errors
```bash
# Make sure virtual environment is activated
source venv/bin/activate
pip install -r requirements.txt
```

### SSL Errors (Python 3.13)
```bash
# Check Python version
python --version

# If 3.13.x, recreate with 3.11 or 3.12
rm -rf venv
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate

# See detailed guide: PYTHON_VERSION_FIX.md
```

### "Connection refused" errors
```bash
# Make sure Redis is running
redis-cli ping
# Should return: PONG

# Check Celery is running
ps aux | grep celery
```

### "API key invalid" errors
- Double-check keys in `.env` file
- Verify keys work on respective platforms
- Make sure no extra spaces or quotes

### Jobs stuck in "pending"
```bash
# Check Celery worker logs
celery -A config worker -l debug

# Check if tasks are queued
celery -A config inspect active
```

## Testing the Pipeline

Test individual stages or the complete pipeline:

```bash
# Test Stage 1 (preprocessing)
python tests/test_stage1_preprocessing.py demo_files/video.mp4

# Test complete pipeline
python tests/test_runner.py --input demo_files/video.mp4 --all-stages
```

See [Testing Framework](README.md#testing-framework) for details.

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Explore the [Testing Framework](README.md#testing-framework)
- Check [API Reference](README.md#api-reference)
- Review [example_api_usage.py](example_api_usage.py) for programmatic usage
- Customize segment detection in `viral_clips/services/llm_service.py`

## Support

Issues? Questions?
- Check logs in terminal running Celery
- Review Django admin at http://localhost:8000/admin/
- Check job status via API

---

**Ready to create viral clips! 🚀**
