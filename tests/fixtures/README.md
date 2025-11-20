# Test Fixtures

This directory contains sample data for testing the viral clips pipeline without requiring actual API calls or media files.

## Files

### sample_transcript.json
Sample transcript output from Stage 2 (ElevenLabs transcription). Contains:
- Full transcript text
- Word-level timestamps
- Metadata (duration, language, etc.)

Use this to test Stage 3 (segment identification) without calling the ElevenLabs API.

### sample_segments.json
Sample segments output from Stage 3 (LLM analysis). Contains:
- 3 viral segments with titles, descriptions, and timestamps
- Reasoning for each segment selection
- LLM metadata

Use this to test Stage 4 (clip creation) without calling the LLM API.

## Usage

### Test Stage 3 with sample transcript:
```bash
python tests/test_stage3_segment_identification.py tests/fixtures/sample_transcript.json
```

### Test Stage 4 with sample segments:
```bash
python tests/test_stage4_clip_creation.py --from-stage3 tests/fixtures/sample_segments.json
```

## Creating Your Own Fixtures

After running actual tests, you can use the generated output files as fixtures for faster iteration:

1. Run Stage 2 with a real audio file
2. Copy the generated transcript JSON to `fixtures/my_transcript.json`
3. Use it for Stage 3 testing without re-transcribing

This saves time and API costs during development.
