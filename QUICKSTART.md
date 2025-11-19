# Quick Start Guide

Get up and running with Viral Clips in 5 minutes.

## Prerequisites

- **Python 3.11 or 3.12** (recommended)
  - ⚠️ Python 3.13 has SSL issues - see [PYTHON_VERSION_FIX.md](PYTHON_VERSION_FIX.md)
- Redis installed
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
2. **OpenAI** (or Anthropic) - https://platform.openai.com/api-keys
3. **Shotstack** - https://dashboard.shotstack.io/api-keys
   - Get both sandbox and production keys
   - Sandbox is free for testing

## 3. Configure Environment

Copy and edit the environment file:

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```bash
ELEVENLABS_API_KEY=your-key-here
OPENAI_API_KEY=your-key-here

# Shotstack (use sandbox for testing)
SHOTSTACK_SANDBOX_API_KEY=your-sandbox-key-here
SHOTSTACK_PRODUCTION_API_KEY=your-production-key-here
SHOTSTACK_ENV=sandbox

# Choose your LLM provider
LLM_PROVIDER=openai
LLM_MODEL=gpt-4-turbo-preview
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
  -F "video_file=@/path/to/video.mp4" \
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
        files={'video_file': f},
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

## Processing Flow

1. **Upload** → Video is saved and job created
2. **Transcribe** → Eleven Labs extracts transcript (~1-2 min)
3. **Analyze** → LLM identifies viral segments (~30 sec)
4. **Clip** → Shotstack creates videos (~2-5 min per clip)
5. **Complete** → Clips available via API

## Expected Timeline

For a 1-hour podcast:
- Transcription: 1-2 minutes
- Analysis: 30 seconds
- Clipping (5 segments): 10-15 minutes total
- **Total: ~12-18 minutes**

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

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Explore the [API Reference](README.md#api-reference)
- Check [example_api_usage.py](example_api_usage.py) for programmatic usage
- Customize segment detection in `viral_clips/services/llm_service.py`

## Support

Issues? Questions?
- Check logs in terminal running Celery
- Review Django admin at http://localhost:8000/admin/
- Check job status via API

---

**Ready to create viral clips! 🚀**
