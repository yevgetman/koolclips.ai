from celery import shared_task
from django.utils import timezone
from django.core.files.base import File
import logging
import os

from .models import VideoJob, TranscriptSegment, ClippedVideo
from .services import PreprocessingService, ElevenLabsService, LLMService, ShotstackService
from .services.s3_service import S3Service

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
        
        # Step 1: Preprocess media (extract audio if needed)
        job.status = 'preprocessing'
        job.save()
        preprocess_media.delay(job_id)
        
    except VideoJob.DoesNotExist:
        logger.error(f"VideoJob {job_id} not found")
    except Exception as e:
        logger.error(f"Error processing job {job_id}: {str(e)}")
        job = VideoJob.objects.get(id=job_id)
        job.status = 'failed'
        job.error_message = str(e)
        job.save()


@shared_task(bind=True)
def preprocess_media(self, job_id):
    """
    Preprocess media file (extract audio from video if needed)
    Now downloads from S3, processes, and uploads back to S3
    
    Args:
        job_id: UUID of the VideoJob
    """
    temp_input = None
    temp_audio = None
    
    try:
        job = VideoJob.objects.get(id=job_id)
        logger.info(f"Preprocessing media for job {job_id} (file_type: {job.file_type})")
        
        # Check if S3 is configured
        if not S3Service.is_s3_configured():
            # Fallback to local file processing for development
            logger.warning(f"S3 not configured, using local file processing")
            media_path = job.media_file.path
            preprocessing = PreprocessingService()
            result = preprocessing.process_media_file(media_path)
            audio_path = result['audio_path']
            if result['extracted']:
                job.extracted_audio_path = audio_path
                logger.info(f"Audio extracted from video to: {audio_path}")
            job.save()
            transcribe_video.delay(job_id)
            return
        
        # Initialize S3 service
        s3_service = S3Service()
        
        # Download file from S3 to temp directory
        # For Cloudcube, we need to use the storage backend to get the actual S3 key
        if hasattr(job.media_file, 'storage'):
            # Get the actual S3 key from the storage backend
            s3_key = job.media_file.storage._normalize_name(job.media_file.name)
        else:
            s3_key = job.media_file.name
        
        logger.info(f"Downloading media from S3: {s3_key}")
        temp_input = s3_service.download_file(s3_key)
        
        # Preprocess using PreprocessingService
        preprocessing = PreprocessingService()
        
        if job.file_type == 'video':
            # Extract audio from video
            logger.info(f"Extracting audio from video")
            temp_audio = preprocessing.extract_audio_from_video(temp_input, output_format='mp3')
            
            # Upload audio to S3
            audio_s3_key = f"uploads/{job_id}/audio/{os.path.basename(temp_audio)}"
            logger.info(f"Uploading audio to S3: {audio_s3_key}")
            audio_urls = s3_service.upload_file(
                temp_audio,
                audio_s3_key,
                content_type='audio/mpeg'
            )
            
            job.extracted_audio_s3_url = audio_urls['s3_url']
            job.extracted_audio_cloudfront_url = audio_urls['cloudfront_url']
            job.extracted_audio_path = audio_s3_key
            
            logger.info(f"Audio uploaded to S3: {audio_urls['cloudfront_url']}")
        else:
            # Audio file - use original S3 URLs
            job.extracted_audio_s3_url = job.media_file_s3_url
            job.extracted_audio_cloudfront_url = job.media_file_cloudfront_url
            job.extracted_audio_path = job.media_file.name
            logger.info(f"Audio file - using original S3 URLs")
        
        job.save()
        logger.info(f"Preprocessing complete for job {job_id}")
        
        # Move to next step
        transcribe_video.delay(job_id)
        
    except Exception as e:
        logger.error(f"Preprocessing failed for job {job_id}: {str(e)}")
        job = VideoJob.objects.get(id=job_id)
        job.status = 'failed'
        job.error_message = f"Preprocessing failed: {str(e)}"
        job.save()
    finally:
        # Clean up temp files
        if temp_input and os.path.exists(temp_input):
            os.remove(temp_input)
            logger.info(f"Cleaned up temp input file: {temp_input}")
        if temp_audio and os.path.exists(temp_audio):
            os.remove(temp_audio)
            logger.info(f"Cleaned up temp audio file: {temp_audio}")


@shared_task(bind=True)
def transcribe_video(self, job_id):
    """
    Transcribe audio using Eleven Labs API
    
    Args:
        job_id: UUID of the VideoJob
    """
    try:
        job = VideoJob.objects.get(id=job_id)
        logger.info(f"Transcribing {job.file_type} for job {job_id}")
        
        job.status = 'transcribing'
        job.save()
        
        # Get audio file - download from S3 if needed
        temp_audio_file = None
        
        if job.extracted_audio_cloudfront_url:
            # Download from CloudFront URL
            logger.info(f"Downloading audio from CloudFront: {job.extracted_audio_cloudfront_url}")
            s3_service = S3Service()
            audio_path = s3_service.download_from_url(job.extracted_audio_cloudfront_url)
            temp_audio_file = audio_path
            logger.info(f"Downloaded audio to: {audio_path}")
        elif job.extracted_audio_s3_url:
            # Download from S3 URL
            logger.info(f"Downloading audio from S3: {job.extracted_audio_s3_url}")
            s3_service = S3Service()
            audio_path = s3_service.download_from_url(job.extracted_audio_s3_url)
            temp_audio_file = audio_path
            logger.info(f"Downloaded audio to: {audio_path}")
        elif job.extracted_audio_path:
            # S3 configured - download using S3 key
            if S3Service.is_s3_configured():
                s3_service = S3Service()
                # Get actual S3 key with cube prefix if using Cloudcube
                if hasattr(job.media_file, 'storage'):
                    s3_key = job.media_file.storage._normalize_name(job.extracted_audio_path)
                else:
                    s3_key = job.extracted_audio_path
                audio_path = s3_service.download_file(s3_key)
                temp_audio_file = audio_path
                logger.info(f"Downloaded audio from S3 to: {audio_path}")
            else:
                audio_path = job.extracted_audio_path
                logger.info(f"Using local audio file: {audio_path}")
        else:
            # Fallback to original media file
            if S3Service.is_s3_configured() and job.media_file.name:
                s3_service = S3Service()
                if hasattr(job.media_file, 'storage'):
                    s3_key = job.media_file.storage._normalize_name(job.media_file.name)
                else:
                    s3_key = job.media_file.name
                audio_path = s3_service.download_file(s3_key)
                temp_audio_file = audio_path
                logger.info(f"Downloaded media from S3 to: {audio_path}")
            else:
                audio_path = job.media_file.path
                logger.info(f"Using local media file: {audio_path}")
        
        try:
            # Call Eleven Labs service
            elevenlabs = ElevenLabsService()
            transcript_data = elevenlabs.transcribe_video(audio_path)
            
            # Save transcript data
            job.transcript_json = transcript_data
            job.save()
            
            logger.info(f"Transcription complete for job {job_id}")
            
            # Move to next step: analyze transcript
            analyze_transcript.delay(job_id)
        finally:
            # Clean up temp audio file
            if temp_audio_file and os.path.exists(temp_audio_file):
                os.remove(temp_audio_file)
                logger.info(f"Cleaned up temp audio file: {temp_audio_file}")
        
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
        
        # Get media CloudFront URL for Shotstack
        media_url = job.get_media_cloudfront_url()
        if not media_url:
            # Fallback to S3 URL or local URL
            if job.media_file_s3_url:
                media_url = job.media_file_s3_url
            else:
                media_url = job.media_file.url
        
        logger.info(f"Using media URL for Shotstack: {media_url}")
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
            shotstack_url = status['url']
            clip.shotstack_render_url = shotstack_url
            logger.info(f"Shotstack render complete: {shotstack_url}")
            
            # Download from Shotstack and upload to S3 if configured
            if S3Service.is_s3_configured():
                try:
                    s3_service = S3Service()
                    segment = clip.segment
                    job = segment.video_job
                    
                    # Download from Shotstack to temp file
                    import requests
                    import tempfile
                    
                    response = requests.get(shotstack_url, stream=True)
                    response.raise_for_status()
                    
                    fd, temp_clip = tempfile.mkstemp(suffix='.mp4')
                    os.close(fd)
                    
                    with open(temp_clip, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    logger.info(f"Downloaded clip from Shotstack to: {temp_clip}")
                    
                    # Upload to S3 output bucket
                    clip_s3_key = f"clips/{job.id}/{segment.id}/clip.mp4"
                    clip_urls = s3_service.upload_file(
                        temp_clip,
                        clip_s3_key,
                        bucket=s3_service.output_bucket,
                        content_type='video/mp4'
                    )
                    
                    clip.video_s3_url = clip_urls['s3_url']
                    clip.video_cloudfront_url = clip_urls['cloudfront_url']
                    clip.video_url = clip_urls['cloudfront_url']  # Use CloudFront URL for public access
                    
                    # Clean up temp file
                    os.remove(temp_clip)
                    
                    logger.info(f"Clip uploaded to S3: {clip.video_cloudfront_url}")
                except Exception as upload_err:
                    logger.error(f"Failed to upload clip to S3: {str(upload_err)}")
                    # Fallback to Shotstack URL
                    clip.video_url = shotstack_url
            else:
                # S3 not configured, use Shotstack URL directly
                clip.video_url = shotstack_url
            
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
