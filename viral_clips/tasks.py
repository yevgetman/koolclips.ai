from celery import shared_task
from django.utils import timezone
from django.core.files.base import File
import logging
import os

from .models import VideoJob, TranscriptSegment, ClippedVideo
from .services import ElevenLabsService, LLMService, ShotstackService

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def process_video_job(self, job_id):
    """
    Main task to process a video job through the entire pipeline
    
    Args:
        job_id: UUID of the VideoJob
    """
    try:
        job = VideoJob.objects.get(id=job_id)
        logger.info(f"Starting processing for job {job_id}")
        
        # Step 1: Transcribe video
        job.status = 'transcribing'
        job.save()
        transcribe_video.delay(job_id)
        
    except VideoJob.DoesNotExist:
        logger.error(f"VideoJob {job_id} not found")
    except Exception as e:
        logger.error(f"Error processing job {job_id}: {str(e)}")
        job = VideoJob.objects.get(id=job_id)
        job.status = 'failed'
        job.error_message = str(e)
        job.save()


@shared_task(bind=True)
def transcribe_video(self, job_id):
    """
    Transcribe video using Eleven Labs API
    
    Args:
        job_id: UUID of the VideoJob
    """
    try:
        job = VideoJob.objects.get(id=job_id)
        logger.info(f"Transcribing {job.file_type} for job {job_id}")
        
        # Get media file path
        media_path = job.media_file.path
        
        # Call Eleven Labs service
        elevenlabs = ElevenLabsService()
        transcript_data = elevenlabs.transcribe_video(media_path)
        
        # Save transcript data
        job.transcript_json = transcript_data
        job.save()
        
        logger.info(f"Transcription complete for job {job_id}")
        
        # Move to next step: analyze transcript
        analyze_transcript.delay(job_id)
        
    except Exception as e:
        logger.error(f"Transcription failed for job {job_id}: {str(e)}")
        job = VideoJob.objects.get(id=job_id)
        job.status = 'failed'
        job.error_message = f"Transcription failed: {str(e)}"
        job.save()


@shared_task(bind=True)
def analyze_transcript(self, job_id):
    """
    Analyze transcript using LLM to identify viral segments
    
    Args:
        job_id: UUID of the VideoJob
    """
    try:
        job = VideoJob.objects.get(id=job_id)
        logger.info(f"Analyzing transcript for job {job_id}")
        
        job.status = 'analyzing'
        job.save()
        
        # Call LLM service
        llm = LLMService()
        segments = llm.analyze_transcript(
            job.transcript_json,
            num_segments=job.num_segments,
            min_duration=job.min_duration,
            max_duration=job.max_duration
        )
        
        # Create TranscriptSegment objects
        for i, segment_data in enumerate(segments):
            TranscriptSegment.objects.create(
                video_job=job,
                title=segment_data['title'],
                description=segment_data['description'],
                reasoning=segment_data['reasoning'],
                start_time=segment_data['start_time'],
                end_time=segment_data['end_time'],
                duration=segment_data['duration'],
                segment_order=i
            )
        
        logger.info(f"Analysis complete for job {job_id}, created {len(segments)} segments")
        
        # Move to next step: clip videos
        clip_segments.delay(job_id)
        
    except Exception as e:
        logger.error(f"Analysis failed for job {job_id}: {str(e)}")
        job = VideoJob.objects.get(id=job_id)
        job.status = 'failed'
        job.error_message = f"Analysis failed: {str(e)}"
        job.save()


@shared_task(bind=True)
def clip_segments(self, job_id):
    """
    Create video clips for all segments using Shotstack API
    
    Args:
        job_id: UUID of the VideoJob
    """
    try:
        job = VideoJob.objects.get(id=job_id)
        logger.info(f"Clipping segments for job {job_id}")
        
        job.status = 'clipping'
        job.save()
        
        segments = job.segments.all()
        
        # Create ClippedVideo objects and initiate rendering
        for segment in segments:
            clip = ClippedVideo.objects.create(segment=segment)
            # Process each clip
            process_clip.delay(clip.id)
        
        # Mark job as completed (clips will continue processing asynchronously)
        job.status = 'completed'
        job.completed_at = timezone.now()
        job.save()
        
        logger.info(f"Clip jobs initiated for job {job_id}")
        
    except Exception as e:
        logger.error(f"Clipping failed for job {job_id}: {str(e)}")
        job = VideoJob.objects.get(id=job_id)
        job.status = 'failed'
        job.error_message = f"Clipping failed: {str(e)}"
        job.save()


@shared_task(bind=True, max_retries=3)
def process_clip(self, clip_id):
    """
    Process a single video clip using Shotstack
    
    Args:
        clip_id: UUID of the ClippedVideo
    """
    try:
        clip = ClippedVideo.objects.get(id=clip_id)
        segment = clip.segment
        job = segment.video_job
        
        logger.info(f"Processing clip {clip_id} for segment '{segment.title}'")
        
        clip.status = 'processing'
        clip.save()
        
        # Get media URL (need to make it accessible to Shotstack)
        # For now, we'll use the file path - in production, upload to S3 or similar
        media_url = job.media_file.url
        is_audio = job.is_audio_only()
        
        # Create clip using Shotstack
        shotstack = ShotstackService()
        render_id = shotstack.create_clip(
            media_url=media_url,
            start_time=segment.start_time,
            end_time=segment.end_time,
            is_audio_only=is_audio
        )
        
        clip.shotstack_render_id = render_id
        clip.save()
        
        # Check render status
        check_render_status.delay(clip_id)
        
    except Exception as e:
        logger.error(f"Clip processing failed for {clip_id}: {str(e)}")
        clip = ClippedVideo.objects.get(id=clip_id)
        clip.status = 'failed'
        clip.error_message = str(e)
        clip.save()
        
        # Retry if possible
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=10)
def check_render_status(self, clip_id):
    """
    Check the status of a Shotstack render and update when complete
    
    Args:
        clip_id: UUID of the ClippedVideo
    """
    try:
        clip = ClippedVideo.objects.get(id=clip_id)
        
        if not clip.shotstack_render_id:
            logger.error(f"Clip {clip_id} has no render ID")
            return
        
        shotstack = ShotstackService()
        status = shotstack.get_render_status(clip.shotstack_render_id)
        
        if status['status'] == 'done':
            clip.video_url = status['url']
            clip.status = 'completed'
            clip.completed_at = timezone.now()
            clip.save()
            
            logger.info(f"Clip {clip_id} completed: {clip.video_url}")
            
        elif status['status'] == 'failed':
            clip.status = 'failed'
            clip.error_message = status.get('error', 'Render failed')
            clip.save()
            
            logger.error(f"Clip {clip_id} failed: {clip.error_message}")
            
        else:
            # Still processing, check again later
            logger.info(f"Clip {clip_id} still processing: {status['status']}")
            raise self.retry(countdown=10)
            
    except Exception as e:
        logger.error(f"Error checking render status for {clip_id}: {str(e)}")
        raise self.retry(exc=e, countdown=10)
