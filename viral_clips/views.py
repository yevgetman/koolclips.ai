from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.conf import settings
import json
import uuid
import io
import os
import logging
from datetime import datetime

from .models import VideoJob, TranscriptSegment, ClippedVideo
from .serializers import (
    VideoJobSerializer, VideoJobCreateSerializer, VideoJobListSerializer,
    TranscriptSegmentSerializer, ClippedVideoSerializer
)
from .services.s3_service import S3Service
from .services.preprocessing_service import PreprocessingService
from .services.elevenlabs_service import ElevenLabsService
from .services.llm_service import LLMService
from .services.shotstack_service import ShotstackService
from .utils import detect_file_type

logger = logging.getLogger(__name__)


class VideoJobViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing video processing jobs
    
    list: Get all video jobs
    retrieve: Get a specific video job with all segments and clips
    create: Upload a video and start processing
    """
    
    queryset = VideoJob.objects.all()
    parser_classes = (MultiPartParser, FormParser)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return VideoJobCreateSerializer
        elif self.action == 'list':
            return VideoJobListSerializer
        return VideoJobSerializer
    
    def create(self, request, *args, **kwargs):
        """Create a new video job and start processing"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = serializer.save()
        
        # Return full job details
        output_serializer = VideoJobSerializer(job)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """Get the current status of a video job"""
        job = self.get_object()
        
        segments_data = []
        for segment in job.segments.all():
            segment_info = {
                'id': str(segment.id),
                'title': segment.title,
                'start_time': segment.start_time,
                'end_time': segment.end_time,
                'clip_status': None,
                'clip_url': None
            }
            
            if hasattr(segment, 'clip'):
                segment_info['clip_status'] = segment.clip.status
                segment_info['clip_url'] = segment.clip.video_url
            
            segments_data.append(segment_info)
        
        return Response({
            'job_id': str(job.id),
            'status': job.status,
            'error_message': job.error_message,
            'progress': {
                'total_segments': job.num_segments,
                'segments_identified': job.segments.count(),
                'clips_completed': job.segments.filter(clip__status='completed').count()
            },
            'segments': segments_data,
            'created_at': job.created_at,
            'completed_at': job.completed_at
        })
    
    @action(detail=True, methods=['get'])
    def clips(self, request, pk=None):
        """Get all completed clips for a job"""
        job = self.get_object()
        
        completed_clips = ClippedVideo.objects.filter(
            segment__video_job=job,
            status='completed'
        ).select_related('segment')
        
        clips_data = []
        for clip in completed_clips:
            clips_data.append({
                'clip_id': str(clip.id),
                'segment_title': clip.segment.title,
                'video_url': clip.video_url,
                'start_time': clip.segment.start_time,
                'end_time': clip.segment.end_time,
                'duration': clip.segment.duration,
                'completed_at': clip.completed_at
            })
        
        return Response({
            'job_id': str(job.id),
            'total_clips': len(clips_data),
            'clips': clips_data
        })


class TranscriptSegmentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing transcript segments
    
    list: Get all segments
    retrieve: Get a specific segment with clip information
    """
    
    queryset = TranscriptSegment.objects.all()
    serializer_class = TranscriptSegmentSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by job_id if provided
        job_id = self.request.query_params.get('job_id', None)
        if job_id is not None:
            queryset = queryset.filter(video_job_id=job_id)
        
        return queryset


class ClippedVideoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing clipped videos
    
    list: Get all clips
    retrieve: Get a specific clip
    """
    
    queryset = ClippedVideo.objects.all()
    serializer_class = ClippedVideoSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by status if provided
        clip_status = self.request.query_params.get('status', None)
        if clip_status is not None:
            queryset = queryset.filter(status=clip_status)
        
        # Filter by job_id if provided
        job_id = self.request.query_params.get('job_id', None)
        if job_id is not None:
            queryset = queryset.filter(segment__video_job_id=job_id)
        
        return queryset


@api_view(['POST'])
@parser_classes([JSONParser])
def get_presigned_upload_url(request):
    """
    Get a presigned S3 URL for direct file upload
    
    POST /api/upload/presigned-url/
    Body: {
        "filename": "video.mp4",
        "content_type": "video/mp4",
        "file_size": 1234567890  # in bytes
    }
    
    Returns: {
        "upload_url": "https://...",
        "upload_fields": {...},
        "s3_key": "uploads/...",
        "job_id": "uuid"
    }
    """
    try:
        # Validate S3 is configured
        if not S3Service.is_s3_configured():
            return Response({
                'success': False,
                'error': 'S3 storage not configured. Cannot upload files.'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Get request data
        filename = request.data.get('filename')
        content_type = request.data.get('content_type')
        file_size = request.data.get('file_size', 0)
        
        if not filename:
            return Response({
                'success': False,
                'error': 'filename is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate file type
        file_type = detect_file_type(filename)
        if file_type == 'unknown':
            return Response({
                'success': False,
                'error': 'Unsupported file type. Please upload a video or audio file.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate file size (5GB limit - sufficient for most use cases)
        max_size = 5 * 1024 * 1024 * 1024  # 5GB
        if file_size > max_size:
            return Response({
                'success': False,
                'error': f'File too large. Maximum size is 5GB. File size: {file_size / 1024 / 1024 / 1024:.2f}GB'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Generate S3 key
        s3_key = f"uploads/direct/{job_id}/{filename}"
        
        # Generate presigned upload URL
        s3_service = S3Service()
        presigned_data = s3_service.generate_presigned_upload_url(
            s3_key=s3_key,
            content_type=content_type,
            expiration=3600,  # 1 hour
            public=True
        )
        
        # Build CloudFront URL if available
        cloudfront_url = None
        if s3_service.cloudfront_domain:
            cloudfront_url = f"https://{s3_service.cloudfront_domain}/{s3_key}"
        
        return Response({
            'success': True,
            'upload_url': presigned_data['url'],
            'upload_fields': presigned_data['fields'],
            's3_key': presigned_data['s3_key'],
            'cloudfront_url': cloudfront_url,
            'job_id': job_id,
            'file_type': file_type,
            'expires_in': 3600  # seconds
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@parser_classes([JSONParser])
def initiate_multipart_upload(request):
    """
    Initiate a multipart upload for large files
    
    POST /api/upload/multipart/initiate/
    Body: {
        "filename": "large_video.mp4",
        "content_type": "video/mp4",
        "file_size": 5000000000,  # in bytes
        "part_size": 10485760  # optional, default 100MB
    }
    
    Returns: {
        "upload_id": "...",
        "s3_key": "...",
        "job_id": "...",
        "file_type": "video",
        "num_parts": 50,
        "part_size": 10485760
    }
    """
    try:
        # Validate S3 is configured
        if not S3Service.is_s3_configured():
            return Response({
                'success': False,
                'error': 'S3 storage not configured'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Get request data
        filename = request.data.get('filename')
        content_type = request.data.get('content_type')
        file_size = request.data.get('file_size', 0)
        part_size = request.data.get('part_size', 200 * 1024 * 1024)  # Default 200MB per part (faster uploads)
        
        if not filename:
            return Response({
                'success': False,
                'error': 'filename is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate file type
        file_type = detect_file_type(filename)
        if file_type == 'unknown':
            return Response({
                'success': False,
                'error': 'Unsupported file type. Please upload a video or audio file.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate file size (5GB limit)
        max_size = 5 * 1024 * 1024 * 1024  # 5GB
        if file_size > max_size:
            return Response({
                'success': False,
                'error': f'File too large. Maximum size is 5GB. File size: {file_size / 1024 / 1024 / 1024:.2f}GB'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Calculate number of parts
        num_parts = (file_size + part_size - 1) // part_size  # Ceiling division
        
        # Validate part size (min 5MB for S3)
        if part_size < 5 * 1024 * 1024:
            return Response({
                'success': False,
                'error': 'Part size must be at least 5MB'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Generate S3 key
        s3_key = f"uploads/direct/{job_id}/{filename}"
        
        # Initialize multipart upload
        s3_service = S3Service()
        multipart_data = s3_service.initiate_multipart_upload(
            s3_key=s3_key,
            content_type=content_type,
            public=True
        )
        
        return Response({
            'success': True,
            'upload_id': multipart_data['upload_id'],
            's3_key': multipart_data['s3_key'],
            'job_id': job_id,
            'file_type': file_type,
            'num_parts': num_parts,
            'part_size': part_size
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@parser_classes([JSONParser])
def get_multipart_upload_urls(request):
    """
    Get presigned URLs for uploading parts
    
    POST /api/upload/multipart/urls/
    Body: {
        "upload_id": "...",
        "s3_key": "...",
        "part_numbers": [1, 2, 3, ...]  # list of part numbers to get URLs for
    }
    
    Returns: {
        "urls": [
            {"part_number": 1, "url": "https://..."},
            {"part_number": 2, "url": "https://..."},
            ...
        ]
    }
    """
    try:
        # Validate S3 is configured
        if not S3Service.is_s3_configured():
            return Response({
                'success': False,
                'error': 'S3 storage not configured'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Get request data
        upload_id = request.data.get('upload_id')
        s3_key = request.data.get('s3_key')
        part_numbers = request.data.get('part_numbers', [])
        
        if not all([upload_id, s3_key, part_numbers]):
            return Response({
                'success': False,
                'error': 'upload_id, s3_key, and part_numbers are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate presigned URLs for requested parts only
        s3_service = S3Service()
        
        urls = []
        for part_number in part_numbers:
            url = s3_service.s3_client.generate_presigned_url(
                'upload_part',
                Params={
                    'Bucket': s3_service.input_bucket,
                    'Key': s3_key,
                    'UploadId': upload_id,
                    'PartNumber': part_number
                },
                ExpiresIn=3600
            )
            urls.append({
                'part_number': part_number,
                'url': url
            })
        
        return Response({
            'success': True,
            'urls': urls
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@parser_classes([JSONParser])
def complete_multipart_upload(request):
    """
    Complete a multipart upload after all parts are uploaded
    
    POST /api/upload/multipart/complete/
    Body: {
        "upload_id": "...",
        "s3_key": "...",
        "parts": [
            {"PartNumber": 1, "ETag": "..."},
            {"PartNumber": 2, "ETag": "..."},
            ...
        ]
    }
    
    Returns: {
        "success": true,
        "location": "https://..."
    }
    """
    try:
        # Validate S3 is configured
        if not S3Service.is_s3_configured():
            return Response({
                'success': False,
                'error': 'S3 storage not configured'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Get request data
        upload_id = request.data.get('upload_id')
        s3_key = request.data.get('s3_key')
        parts = request.data.get('parts', [])
        
        if not all([upload_id, s3_key, parts]):
            return Response({
                'success': False,
                'error': 'upload_id, s3_key, and parts are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Sanitize parts - S3 only accepts PartNumber and ETag
        sanitized_parts = []
        for part in parts:
            sanitized_parts.append({
                'PartNumber': part.get('PartNumber'),
                'ETag': part.get('ETag')
            })
        
        # Complete multipart upload
        s3_service = S3Service()
        result = s3_service.complete_multipart_upload(
            s3_key=s3_key,
            upload_id=upload_id,
            parts=sanitized_parts
        )
        
        # Get the public URL for the uploaded file
        public_url = s3_service.get_public_url_from_key(s3_key)
        
        return Response({
            'success': True,
            'location': result.get('Location', ''),
            'public_url': public_url,
            's3_key': s3_key,
            'etag': result.get('ETag', '')
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@parser_classes([JSONParser])
def abort_multipart_upload(request):
    """
    Abort a multipart upload and clean up
    
    POST /api/upload/multipart/abort/
    Body: {
        "upload_id": "...",
        "s3_key": "..."
    }
    
    Returns: {
        "success": true
    }
    """
    try:
        # Validate S3 is configured
        if not S3Service.is_s3_configured():
            return Response({
                'success': False,
                'error': 'S3 storage not configured'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Get request data
        upload_id = request.data.get('upload_id')
        s3_key = request.data.get('s3_key')
        
        if not all([upload_id, s3_key]):
            return Response({
                'success': False,
                'error': 'upload_id and s3_key are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Abort multipart upload
        s3_service = S3Service()
        s3_service.abort_multipart_upload(
            s3_key=s3_key,
            upload_id=upload_id
        )
        
        return Response({
            'success': True
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@parser_classes([JSONParser])
def import_from_url(request):
    """
    Import video from external URL (YouTube, Google Drive, Dropbox, etc.)
    
    POST /api/upload/import-url/
    Body: {
        "url": "https://youtube.com/watch?v=..."
    }
    
    Returns: {
        "success": true,
        "job_id": "uuid",
        "status": "importing",
        "source": "youtube"
    }
    """
    from django.core.cache import cache
    
    try:
        # Validate S3 is configured
        if not S3Service.is_s3_configured():
            return Response({
                'success': False,
                'error': 'S3 storage not configured. Cannot import files.'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Get URL from request
        url = request.data.get('url')
        if not url:
            return Response({
                'success': False,
                'error': 'url is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate URL
        from .services.url_import_service import URLImportService
        service = URLImportService()
        validation = service.validate_url(url)
        
        if not validation['valid']:
            return Response({
                'success': False,
                'error': validation['error']
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Set initial status in cache
        cache_key = f"url_import_progress_{job_id}"
        cache.set(cache_key, {
            'status': 'queued',
            'stage': 'queued',
            'percent': 0,
            'message': 'Import queued...'
        }, timeout=3600)
        
        # Queue the import task
        from .tasks import import_video_from_url
        task = import_video_from_url.delay(job_id, url)
        
        return Response({
            'success': True,
            'job_id': job_id,
            'task_id': str(task.id),
            'status': 'importing',
            'source': validation['source']
        }, status=status.HTTP_202_ACCEPTED)
        
    except Exception as e:
        logger.exception(f"Error initiating URL import: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_import_status(request, job_id):
    """
    Get the status of a URL import
    
    GET /api/upload/import-status/<job_id>/
    
    Returns: {
        "status": "importing|completed|failed",
        "stage": "downloading|uploading|complete",
        "percent": 50,
        "message": "Downloading video...",
        "job_id": "uuid" (if completed),
        "public_url": "https://..." (if completed),
        "error": "..." (if failed)
    }
    """
    from django.core.cache import cache
    
    try:
        cache_key = f"url_import_progress_{job_id}"
        status_data = cache.get(cache_key)
        
        if status_data:
            return Response(status_data, status=status.HTTP_200_OK)
        
        # Check if job exists in database
        try:
            job = VideoJob.objects.get(id=job_id)
            return Response({
                'status': 'completed',
                'stage': 'complete',
                'percent': 100,
                'job_id': str(job.id),
                'public_url': job.media_file_cloudfront_url or job.media_file_s3_url
            }, status=status.HTTP_200_OK)
        except VideoJob.DoesNotExist:
            return Response({
                'status': 'not_found',
                'error': 'Import not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.exception(f"Error getting import status: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@parser_classes([MultiPartParser])
def proxy_upload_chunk(request):
    """
    Proxy upload chunk to S3 (server-side upload to avoid CORS issues)
    
    POST /api/upload/proxy-chunk/
    Headers: multipart/form-data
    Fields:
        - chunk: File chunk
        - upload_id: Upload ID
        - s3_key: S3 key
        - part_number: Part number
    
    Returns: {
        "success": true,
        "part_number": 1,
        "etag": "..."
    }
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Validate S3 is configured
        if not S3Service.is_s3_configured():
            logger.error("S3 not configured")
            return Response({
                'success': False,
                'error': 'S3 storage not configured'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Get parameters
        chunk = request.FILES.get('chunk')
        upload_id = request.data.get('upload_id')
        s3_key = request.data.get('s3_key')
        part_number_str = request.data.get('part_number')
        
        logger.info(f"Proxy upload - chunk: {chunk is not None}, upload_id: {upload_id}, s3_key: {s3_key}, part_number: {part_number_str}")
        
        if not chunk:
            return Response({
                'success': False,
                'error': 'Missing chunk file'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        if not upload_id or not s3_key or not part_number_str:
            return Response({
                'success': False,
                'error': f'Missing required parameters: upload_id={bool(upload_id)}, s3_key={bool(s3_key)}, part_number={bool(part_number_str)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            part_number = int(part_number_str)
        except (ValueError, TypeError) as e:
            return Response({
                'success': False,
                'error': f'Invalid part_number: {part_number_str}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Upload part to S3
        s3_service = S3Service()
        
        # Read chunk data
        chunk_data = chunk.read()
        chunk_size = len(chunk_data)
        logger.info(f"Read chunk data: {chunk_size} bytes for part {part_number}")
        
        # Upload part using boto3 directly
        import boto3
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        
        logger.info(f"Uploading part {part_number} to S3: bucket={s3_service.input_bucket}, key={s3_key}")
        
        response = s3_client.upload_part(
            Bucket=s3_service.input_bucket,
            Key=s3_key,
            PartNumber=part_number,
            UploadId=upload_id,
            Body=chunk_data
        )
        
        etag = response['ETag']
        logger.info(f"Part {part_number} uploaded successfully: ETag={etag}")
        
        return Response({
            'success': True,
            'part_number': part_number,
            'etag': etag
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.exception(f"Error in proxy_upload_chunk: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@parser_classes([JSONParser])
def create_job_from_s3(request):
    """
    Create a job after file has been uploaded to S3 via presigned URL
    
    POST /api/upload/create-job/
    Body: {
        "job_id": "uuid",
        "s3_key": "uploads/direct/...",
        "file_type": "video",
        "num_segments": 5,
        "min_duration": 60,
        "max_duration": 300,
        "custom_instructions": "optional"
    }
    
    Returns: VideoJob details
    """
    try:
        # Validate S3 is configured
        if not S3Service.is_s3_configured():
            return Response({
                'success': False,
                'error': 'S3 storage not configured'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Get request data
        job_id = request.data.get('job_id')
        s3_key = request.data.get('s3_key')
        file_type = request.data.get('file_type')
        num_segments = request.data.get('num_segments', 5)
        min_duration = request.data.get('min_duration', 60)
        max_duration = request.data.get('max_duration', 300)
        custom_instructions = request.data.get('custom_instructions', '')
        
        if not all([job_id, s3_key, file_type]):
            return Response({
                'success': False,
                'error': 'job_id, s3_key, and file_type are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify file exists in S3
        s3_service = S3Service()
        if not s3_service.file_exists(s3_key):
            return Response({
                'success': False,
                'error': 'File not found in S3. Upload may have failed.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Create job
        job = VideoJob.objects.create(
            id=job_id,
            file_type=file_type,
            num_segments=num_segments,
            min_duration=min_duration,
            max_duration=max_duration,
            custom_instructions=custom_instructions or None
        )
        
        # Generate S3 URLs from the full prefixed key
        job.media_file_s3_url = s3_service.get_public_url_from_key(s3_key)
        job.media_file_cloudfront_url = job.media_file_s3_url
        
        # Store the S3 key directly
        job.media_file.name = s3_key
        job.save()
        
        # Trigger processing pipeline
        from .tasks import process_video_job
        process_video_job.delay(str(job.id))
        
        # Return job details
        serializer = VideoJobSerializer(job)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@parser_classes([JSONParser])
def upload_test_result(request):
    """
    Upload test result JSON to cloud storage
    
    POST /api/test-results/upload/
    Body: JSON data to upload
    
    Returns: S3 URL of uploaded file
    """
    try:
        # Get JSON data from request
        data = request.data
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        test_type = data.get('test_info', {}).get('test_type', 'test')
        job_id = data.get('job_id', 'unknown')
        filename = f"test_results/{test_type}_{job_id}_{timestamp}.json"
        
        # Convert to JSON string
        json_content = json.dumps(data, indent=2, ensure_ascii=False)
        json_bytes = json_content.encode('utf-8')
        
        # Upload to S3
        s3_service = S3Service()
        s3_url = s3_service.upload_file_content(
            json_bytes,
            filename,
            content_type='application/json'
        )
        
        # Get CloudFront URL if available
        if settings.AWS_CLOUDFRONT_DOMAIN_INPUT:
            cloudfront_url = f"https://{settings.AWS_CLOUDFRONT_DOMAIN_INPUT}/{filename}"
        else:
            cloudfront_url = s3_url
        
        return Response({
            'success': True,
            'message': 'Test results uploaded successfully',
            's3_url': s3_url,
            'cloudfront_url': cloudfront_url,
            'public_url': cloudfront_url,
            'filename': filename
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@parser_classes([JSONParser])
def bulk_cleanup_cloudcube(request):
    """
    Bulk cleanup of Cloudcube filesystem
    
    Deletes all files except final clips created within the retention period.
    This endpoint should be called periodically (daily via CRON or manually)
    to clean up temporary files and old clips.
    
    POST /api/cleanup/bulk/
    Body: {
        "retention_days": 5,  # Optional, default 5 days
        "dry_run": false      # Optional, default false (set true to preview without deleting)
    }
    
    Returns: {
        "success": true,
        "message": "...",
        "deleted_count": 150,
        "deleted_size_mb": 1234.56,
        "retained_count": 25,
        "total_files_scanned": 175,
        "dry_run": false,
        "deleted_files_sample": ["file1.mp4", "file2.mp3", ...]  # First 100 files
    }
    """
    try:
        # Validate S3 is configured
        if not S3Service.is_s3_configured():
            return Response({
                'success': False,
                'error': 'S3 storage not configured. Cannot perform cleanup.'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Get request parameters
        retention_days = request.data.get('retention_days', 5)
        dry_run = request.data.get('dry_run', False)
        
        # Validate retention_days
        if not isinstance(retention_days, int) or retention_days < 0:
            return Response({
                'success': False,
                'error': 'retention_days must be a non-negative integer'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Perform bulk cleanup
        s3_service = S3Service()
        result = s3_service.bulk_cleanup_cloudcube(
            retention_days=retention_days,
            dry_run=dry_run
        )
        
        # Format response
        deleted_size_mb = result['deleted_size'] / (1024 * 1024)
        
        message = (
            f"{'DRY RUN: Would delete' if dry_run else 'Deleted'} "
            f"{result['deleted_count']} files ({deleted_size_mb:.2f} MB), "
            f"retained {result['retained_count']} recent clips"
        )
        
        return Response({
            'success': True,
            'message': message,
            'deleted_count': result['deleted_count'],
            'deleted_size_mb': round(deleted_size_mb, 2),
            'retained_count': result['retained_count'],
            'total_files_scanned': result['total_files_scanned'],
            'dry_run': result['dry_run'],
            'deleted_files_sample': result['deleted_files'],
            'retention_days': retention_days
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Bulk cleanup failed: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@parser_classes([JSONParser])
def cleanup_all_clips(request):
    """
    Delete ALL clips from Cloudcube (regardless of age)
    
    ⚠️ WARNING: This endpoint deletes ALL user-created clips!
    Use with extreme caution. This is meant for complete storage cleanup.
    
    Combined with bulk cleanup, this will delete everything in Cloudcube:
    1. Run bulk cleanup → deletes temp files and old clips
    2. Run this endpoint → deletes all remaining clips
    
    POST /api/cleanup/clips/
    Body: {
        "dry_run": false,  # Optional, default false (set true to preview without deleting)
        "confirm": true    # Required, must be true to execute (safety check)
    }
    
    Returns: {
        "success": true,
        "message": "...",
        "deleted_count": 13,
        "deleted_size_mb": 156.78,
        "dry_run": false,
        "deleted_files_sample": ["clip1.mp4", "clip2.mp4", ...]
    }
    """
    try:
        # Validate S3 is configured
        if not S3Service.is_s3_configured():
            return Response({
                'success': False,
                'error': 'S3 storage not configured. Cannot perform cleanup.'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Get request parameters
        dry_run = request.data.get('dry_run', False)
        confirm = request.data.get('confirm', False)
        
        # Safety check: require explicit confirmation
        if not dry_run and not confirm:
            return Response({
                'success': False,
                'error': 'This operation will delete ALL clips. Set "confirm": true to proceed.',
                'warning': '⚠️ WARNING: This will permanently delete all user-created clips!'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Perform clips cleanup
        s3_service = S3Service()
        result = s3_service.cleanup_all_clips(dry_run=dry_run)
        
        # Format response
        deleted_size_mb = result['deleted_size'] / (1024 * 1024)
        
        message = (
            f"{'DRY RUN: Would delete' if dry_run else 'Deleted'} "
            f"{result['deleted_count']} clips ({deleted_size_mb:.2f} MB)"
        )
        
        return Response({
            'success': True,
            'message': message,
            'deleted_count': result['deleted_count'],
            'deleted_size_mb': round(deleted_size_mb, 2),
            'dry_run': result['dry_run'],
            'deleted_files_sample': result['deleted_files'],
            'warning': '⚠️ All clips have been deleted!' if not dry_run and result['deleted_count'] > 0 else None
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Clips cleanup failed: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@parser_classes([JSONParser])
def extract_audio_from_video(request):
    """
    Extract audio from an uploaded video file (Stage 1 preprocessing)
    
    This endpoint downloads a video from S3, extracts the audio using ffmpeg,
    uploads the extracted audio back to S3, and returns both URLs.
    
    POST /api/upload/extract-audio/
    Body: {
        "s3_key": "uploads/direct/uuid/video.mp4",
        "job_id": "uuid"  # Optional, for organizing files
    }
    
    Returns: {
        "success": true,
        "original_video_url": "https://...",
        "extracted_audio_url": "https://...",
        "audio_s3_key": "uploads/uuid/audio/video.mp3",
        "file_type": "video",
        "extraction_time": 12.5
    }
    """
    import time
    start_time = time.time()
    temp_video = None
    temp_audio = None
    
    try:
        # Validate S3 is configured
        if not S3Service.is_s3_configured():
            return Response({
                'success': False,
                'error': 'S3 storage not configured. Cannot extract audio.'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Get request data
        s3_key = request.data.get('s3_key')
        job_id = request.data.get('job_id', str(uuid.uuid4()))
        
        if not s3_key:
            return Response({
                'success': False,
                'error': 's3_key is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Detect file type from s3_key
        file_type = detect_file_type(s3_key)
        
        if file_type == 'audio':
            # Audio file - no extraction needed, just return the original URL
            s3_service = S3Service()
            original_url = s3_service.get_public_url_from_key(s3_key)
            
            return Response({
                'success': True,
                'original_url': original_url,
                'extracted_audio_url': original_url,  # Same as original for audio
                'audio_s3_key': s3_key,
                'file_type': 'audio',
                'extraction_needed': False,
                'extraction_time': round(time.time() - start_time, 2)
            }, status=status.HTTP_200_OK)
        
        if file_type != 'video':
            return Response({
                'success': False,
                'error': f'Unsupported file type. Expected video or audio file.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Initialize services
        s3_service = S3Service()
        
        # Verify file exists in S3
        if not s3_service.file_exists(s3_key):
            return Response({
                'success': False,
                'error': 'Video file not found in S3'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get original video URL
        original_video_url = s3_service.get_public_url_from_key(s3_key)
        
        # Download video from S3
        logger.info(f"Downloading video from S3: {s3_key}")
        temp_video = s3_service.download_file(s3_key)
        logger.info(f"Downloaded to: {temp_video}")
        
        # Extract audio using PreprocessingService
        logger.info(f"Extracting audio from video")
        preprocessing = PreprocessingService()
        temp_audio = preprocessing.extract_audio_from_video(temp_video, output_format='mp3')
        logger.info(f"Audio extracted to: {temp_audio}")
        
        # Upload extracted audio to S3
        audio_filename = os.path.basename(temp_audio)
        audio_s3_key = f"uploads/{job_id}/audio/{audio_filename}"
        
        logger.info(f"Uploading audio to S3: {audio_s3_key}")
        audio_urls = s3_service.upload_file(
            temp_audio,
            audio_s3_key,
            content_type='audio/mpeg'
        )
        
        extraction_time = round(time.time() - start_time, 2)
        logger.info(f"Audio extraction complete in {extraction_time}s: {audio_urls['cloudfront_url']}")
        
        return Response({
            'success': True,
            'original_video_url': original_video_url,
            'extracted_audio_url': audio_urls['cloudfront_url'],
            'audio_s3_url': audio_urls['s3_url'],
            'audio_s3_key': audio_s3_key,
            'file_type': 'video',
            'extraction_needed': True,
            'extraction_time': extraction_time
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Audio extraction failed: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    finally:
        # Clean up temp files
        if temp_video and os.path.exists(temp_video):
            try:
                os.remove(temp_video)
                logger.info(f"Cleaned up temp video: {temp_video}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp video: {e}")
        
        if temp_audio and os.path.exists(temp_audio):
            try:
                os.remove(temp_audio)
                logger.info(f"Cleaned up temp audio: {temp_audio}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp audio: {e}")


@api_view(['POST'])
@parser_classes([JSONParser])
def transcribe_audio(request):
    """
    Transcribe an audio file using ElevenLabs API (Stage 2)
    
    Downloads audio from a URL, transcribes it using ElevenLabs,
    uploads the transcript JSON to S3, and returns the public URL.
    
    POST /api/transcribe/
    Body: {
        "audio_url": "https://cloudfront.net/.../audio.mp3",
        "job_id": "uuid"  # Optional
    }
    
    Returns: {
        "success": true,
        "job_id": "uuid",
        "audio_url": "https://...",
        "transcript_url": "https://cloudfront.net/.../transcript.json",
        "transcript_text": "Full transcript text...",
        "duration": 120.5,
        "language": "en",
        "word_count": 500,
        "processing_time": 15.3
    }
    """
    import time
    import tempfile
    import requests
    
    start_time = time.time()
    temp_audio = None
    
    try:
        # Get request data
        audio_url = request.data.get('audio_url')
        job_id = request.data.get('job_id') or str(uuid.uuid4())
        
        if not audio_url:
            return Response({
                'success': False,
                'error': 'audio_url is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate URL format
        if not audio_url.startswith(('http://', 'https://')):
            return Response({
                'success': False,
                'error': 'Invalid URL format. Must start with http:// or https://'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"Starting transcription for job {job_id}: {audio_url}")
        
        # Download audio file from URL
        logger.info(f"Downloading audio from: {audio_url}")
        try:
            response = requests.get(audio_url, stream=True, timeout=120)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            return Response({
                'success': False,
                'error': f'Failed to download audio file: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Determine file extension from URL or content type
        content_type = response.headers.get('Content-Type', '')
        if 'audio/mpeg' in content_type or audio_url.endswith('.mp3'):
            ext = '.mp3'
        elif 'audio/wav' in content_type or audio_url.endswith('.wav'):
            ext = '.wav'
        elif 'audio/mp4' in content_type or audio_url.endswith('.m4a'):
            ext = '.m4a'
        else:
            ext = '.mp3'  # Default to mp3
        
        # Save to temp file
        fd, temp_audio = tempfile.mkstemp(suffix=ext)
        os.close(fd)
        
        with open(temp_audio, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"Audio downloaded to: {temp_audio}")
        
        # Transcribe using ElevenLabs
        logger.info(f"Sending to ElevenLabs for transcription...")
        elevenlabs = ElevenLabsService()
        transcript_data = elevenlabs.transcribe_video(temp_audio)
        
        logger.info(f"Transcription complete, uploading to S3...")
        
        # Prepare transcript JSON
        transcript_json = {
            'job_id': job_id,
            'audio_url': audio_url,
            'transcript': transcript_data,
            'created_at': datetime.now().isoformat()
        }
        
        # Upload transcript to S3
        if S3Service.is_s3_configured():
            s3_service = S3Service()
            
            # Generate S3 key for transcript
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            transcript_s3_key = f"transcripts/{job_id}/transcript_{timestamp}.json"
            
            # Convert to JSON bytes
            json_content = json.dumps(transcript_json, indent=2, ensure_ascii=False)
            json_bytes = json_content.encode('utf-8')
            
            # Upload to S3
            transcript_url = s3_service.upload_file_content(
                json_bytes,
                transcript_s3_key,
                content_type='application/json'
            )
            
            # Get CloudFront URL
            if s3_service.cloudfront_domain:
                transcript_url = f"https://{s3_service.cloudfront_domain}/{transcript_s3_key}"
            
            logger.info(f"Transcript uploaded to: {transcript_url}")
        else:
            transcript_url = None
            logger.warning("S3 not configured, transcript not saved to cloud storage")
        
        # Calculate processing time
        processing_time = round(time.time() - start_time, 2)
        
        # Extract metadata
        full_text = transcript_data.get('full_text', '')
        word_count = len(transcript_data.get('words', []))
        duration = transcript_data.get('metadata', {}).get('duration', 0)
        language = transcript_data.get('metadata', {}).get('language', 'unknown')
        
        logger.info(f"Transcription complete for job {job_id} in {processing_time}s")
        
        return Response({
            'success': True,
            'job_id': job_id,
            'audio_url': audio_url,
            'transcript_url': transcript_url,
            'transcript_text': full_text,
            'duration': duration,
            'language': language,
            'word_count': word_count,
            'processing_time': processing_time
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Transcription failed: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    finally:
        # Clean up temp file
        if temp_audio and os.path.exists(temp_audio):
            try:
                os.remove(temp_audio)
                logger.info(f"Cleaned up temp audio: {temp_audio}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp audio: {e}")


@api_view(['POST'])
@parser_classes([JSONParser])
def analyze_segments(request):
    """
    Analyze transcript and select viral segments using LLM (Stage 3)
    
    Downloads transcript JSON from URL, sends to LLM for analysis,
    uploads the segments JSON to S3, and returns the public URL.
    
    POST /api/analyze-segments/
    Body: {
        "transcript_url": "https://cloudfront.net/.../transcript.json",
        "provider": "anthropic",  # or "openai"
        "model": "claude-sonnet-4-5-20250929",  # optional, defaults based on provider
        "num_segments": 3,
        "max_duration": 300,  # seconds
        "custom_instructions": null  # optional
    }
    
    Returns: {
        "success": true,
        "segments_url": "https://cloudfront.net/.../segments.json",
        "segments": [...],
        "provider": "anthropic",
        "model": "claude-3-opus-20240229",
        "processing_time": 15.3
    }
    """
    import time
    import requests
    
    start_time = time.time()
    
    try:
        # Get request data
        transcript_url = request.data.get('transcript_url')
        provider = request.data.get('provider', 'anthropic')
        model = request.data.get('model')  # Optional, LLMService will use default if not provided
        num_segments = request.data.get('num_segments', 3)
        max_duration = request.data.get('max_duration', 300)
        custom_instructions = request.data.get('custom_instructions')
        
        if not transcript_url:
            return Response({
                'success': False,
                'error': 'transcript_url is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate provider
        if provider not in ['openai', 'anthropic']:
            return Response({
                'success': False,
                'error': 'provider must be "openai" or "anthropic"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"Starting segment analysis with {provider}: {transcript_url}")
        
        # Download transcript JSON from URL
        logger.info(f"Downloading transcript from: {transcript_url}")
        try:
            response = requests.get(transcript_url, timeout=60)
            response.raise_for_status()
            transcript_json = response.json()
        except requests.exceptions.RequestException as e:
            return Response({
                'success': False,
                'error': f'Failed to download transcript: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        except json.JSONDecodeError as e:
            return Response({
                'success': False,
                'error': f'Invalid JSON in transcript file: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Extract transcript data (handle both direct format and wrapped format from Stage 2)
        if 'transcript' in transcript_json:
            transcript_data = transcript_json['transcript']
        else:
            transcript_data = transcript_json
        
        logger.info(f"Transcript loaded, sending to {provider} ({model or 'default'}) for analysis...")
        
        # Initialize LLM service with specified provider and model
        llm = LLMService(provider=provider, model=model)
        
        # Analyze transcript
        segments = llm.analyze_transcript(
            transcript_data,
            num_segments=num_segments,
            max_duration=max_duration,
            custom_instructions=custom_instructions
        )
        
        logger.info(f"LLM returned {len(segments)} segments")
        
        # Prepare output JSON
        job_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        output_data = {
            'timestamp': datetime.now().isoformat(),
            'job_id': job_id,
            'source_transcript_url': transcript_url,
            'llm_provider': llm.provider,
            'llm_model': llm.model,
            'num_segments': len(segments),
            'max_duration': max_duration,
            'custom_instructions': custom_instructions,
            'segments': segments
        }
        
        # Upload to S3
        segments_url = None
        if S3Service.is_s3_configured():
            s3_service = S3Service()
            
            # Generate S3 key
            segments_s3_key = f"segments/{job_id}/segments_{timestamp}.json"
            
            # Convert to JSON bytes
            json_content = json.dumps(output_data, indent=2, ensure_ascii=False)
            json_bytes = json_content.encode('utf-8')
            
            # Upload to S3
            s3_service.upload_file_content(
                json_bytes,
                segments_s3_key,
                content_type='application/json'
            )
            
            # Get CloudFront URL
            if s3_service.cloudfront_domain:
                segments_url = f"https://{s3_service.cloudfront_domain}/{segments_s3_key}"
            else:
                segments_url = s3_service.get_public_url_from_key(segments_s3_key)
            
            logger.info(f"Segments uploaded to: {segments_url}")
        else:
            logger.warning("S3 not configured, segments not saved to cloud storage")
        
        # Calculate processing time
        processing_time = round(time.time() - start_time, 2)
        
        logger.info(f"Segment analysis complete in {processing_time}s")
        
        return Response({
            'success': True,
            'job_id': job_id,
            'segments_url': segments_url,
            'segments': segments,
            'provider': llm.provider,
            'model': llm.model,
            'processing_time': processing_time
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Segment analysis failed: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@parser_classes([JSONParser])
def create_clip(request):
    """
    Start video clip creation using Shotstack API (Stage 4)
    
    Initiates clip creation and returns render_id for polling status.
    Use /api/clip-status/ to check render progress.
    
    POST /api/create-clip/
    Body: {
        "video_url": "https://cloudfront.net/.../video.mp4",
        "start_time": 120.5,
        "end_time": 180.3,
        "segment_title": "Optional segment title"
    }
    
    Returns: {
        "success": true,
        "render_id": "abc123",
        "status": "queued",
        "duration": 59.8
    }
    """
    try:
        # Get request data
        video_url = request.data.get('video_url')
        segment_start = request.data.get('start_time')
        segment_end = request.data.get('end_time')
        segment_title = request.data.get('segment_title', 'Untitled Segment')
        
        if not video_url:
            return Response({
                'success': False,
                'error': 'video_url is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if segment_start is None or segment_end is None:
            return Response({
                'success': False,
                'error': 'start_time and end_time are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Convert to float
        segment_start = float(segment_start)
        segment_end = float(segment_end)
        duration = segment_end - segment_start
        
        if duration <= 0:
            return Response({
                'success': False,
                'error': 'end_time must be greater than start_time'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"Creating clip: {segment_start}s - {segment_end}s ({duration}s) from {video_url}")
        
        # Initialize Shotstack service
        shotstack = ShotstackService()
        
        # Create clip - sends to Shotstack (returns immediately with render_id)
        logger.info("Sending to Shotstack for rendering...")
        render_id = shotstack.create_clip(
            media_url=video_url,
            start_time=segment_start,
            end_time=segment_end,
            is_audio_only=False  # Assuming video for this test
        )
        
        logger.info(f"Shotstack render initiated: {render_id}")
        
        return Response({
            'success': True,
            'render_id': render_id,
            'status': 'queued',
            'segment_title': segment_title,
            'start_time': segment_start,
            'end_time': segment_end,
            'duration': duration
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Clip creation failed: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_clip_status(request, render_id):
    """
    Check status of a Shotstack render and return result when complete (Stage 4)
    
    GET /api/clip-status/<render_id>/
    
    Returns: {
        "success": true,
        "status": "done",  // queued, rendering, done, failed
        "progress": 100,
        "clip_url": "https://cloudfront.net/.../clip.mp4"  // only when done
    }
    """
    import tempfile
    import requests as http_requests
    
    temp_clip = None
    
    try:
        # Initialize Shotstack service
        shotstack = ShotstackService()
        
        # Get render status
        render_status = shotstack.get_render_status(render_id)
        
        response_data = {
            'success': True,
            'status': render_status['status'],
            'progress': render_status.get('progress', 0)
        }
        
        # If done, download and upload to S3
        if render_status['status'] == 'done':
            shotstack_url = render_status['url']
            logger.info(f"Shotstack render complete: {shotstack_url}")
            
            clip_url = shotstack_url  # Default to Shotstack URL
            
            if S3Service.is_s3_configured():
                try:
                    s3_service = S3Service()
                    
                    # Download from Shotstack to temp file
                    logger.info("Downloading clip from Shotstack...")
                    dl_response = http_requests.get(shotstack_url, stream=True)
                    dl_response.raise_for_status()
                    
                    fd, temp_clip = tempfile.mkstemp(suffix='.mp4')
                    os.close(fd)
                    
                    with open(temp_clip, 'wb') as f:
                        for chunk in dl_response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    logger.info(f"Downloaded clip to temp file: {temp_clip}")
                    
                    # Upload to S3
                    job_id = str(uuid.uuid4())
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    clip_s3_key = f"clips/{job_id}/clip_{timestamp}.mp4"
                    
                    s3_service.upload_file(temp_clip, clip_s3_key)
                    
                    # Get CloudFront URL
                    if s3_service.cloudfront_domain:
                        clip_url = f"https://{s3_service.cloudfront_domain}/{clip_s3_key}"
                    else:
                        clip_url = s3_service.get_public_url_from_key(clip_s3_key)
                    
                    logger.info(f"Clip uploaded to S3: {clip_url}")
                    
                except Exception as upload_err:
                    logger.error(f"Failed to upload clip to S3: {str(upload_err)}")
                    clip_url = shotstack_url
            
            response_data['clip_url'] = clip_url
            response_data['shotstack_url'] = shotstack_url
        
        elif render_status['status'] == 'failed':
            response_data['error'] = render_status.get('error', 'Render failed')
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Failed to get clip status: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    finally:
        # Clean up temp file
        if temp_clip and os.path.exists(temp_clip):
            try:
                os.remove(temp_clip)
                logger.info(f"Cleaned up temp clip: {temp_clip}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp clip: {e}")


# In-memory workflow storage (for production, use Redis or database)
_workflow_storage = {}


@api_view(['POST'])
@parser_classes([JSONParser])
def process_workflow(request):
    """
    Start the full clip creation workflow (Stages 2-4)
    
    POST /api/process-workflow/
    Body: {
        "video_url": "https://cloudfront.net/.../video.mp4",
        "audio_url": "https://cloudfront.net/.../audio.mp3",
        "provider": "anthropic",
        "model": "claude-sonnet-4-5-20250929",
        "num_segments": 3,
        "max_duration": 300,
        "custom_instructions": null
    }
    """
    import threading
    
    try:
        video_url = request.data.get('video_url')
        audio_url = request.data.get('audio_url')
        provider = request.data.get('provider', 'anthropic')
        model = request.data.get('model')
        num_segments = request.data.get('num_segments', 3)
        max_duration = request.data.get('max_duration', 300)
        custom_instructions = request.data.get('custom_instructions')
        
        if not audio_url:
            return Response({
                'success': False,
                'error': 'audio_url is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create workflow ID
        workflow_id = str(uuid.uuid4())
        
        # Initialize workflow state
        _workflow_storage[workflow_id] = {
            'status': 'processing',
            'stage': 2,
            'stage_detail': 'Starting transcription...',
            'progress': 5,
            'video_url': video_url,
            'audio_url': audio_url,
            'provider': provider,
            'model': model,
            'num_segments': num_segments,
            'max_duration': max_duration,
            'custom_instructions': custom_instructions,
            'transcript_url': None,
            'segments_url': None,
            'segments': [],
            'clips': [],
            'error': None
        }
        
        # Start processing in background thread
        thread = threading.Thread(
            target=_run_workflow,
            args=(workflow_id,)
        )
        thread.daemon = True
        thread.start()
        
        return Response({
            'success': True,
            'workflow_id': workflow_id,
            'status': 'processing'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Failed to start workflow: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _run_workflow(workflow_id):
    """
    Background function to run the full workflow
    """
    import time
    import tempfile
    import requests as http_requests
    
    workflow = _workflow_storage.get(workflow_id)
    if not workflow:
        return
    
    try:
        # ============ STAGE 2: TRANSCRIPTION ============
        workflow['stage'] = 2
        workflow['stage_detail'] = 'Downloading audio file...'
        workflow['progress'] = 10
        
        logger.info(f"Workflow {workflow_id}: Starting transcription")
        
        # Download audio file from URL (same as test page)
        audio_url = workflow['audio_url']
        logger.info(f"Workflow {workflow_id}: Downloading audio from: {audio_url}")
        
        dl_response = http_requests.get(audio_url, stream=True, timeout=120)
        dl_response.raise_for_status()
        
        # Determine file extension
        content_type = dl_response.headers.get('Content-Type', '')
        if 'audio/mpeg' in content_type or audio_url.endswith('.mp3'):
            ext = '.mp3'
        elif 'audio/wav' in content_type or audio_url.endswith('.wav'):
            ext = '.wav'
        else:
            ext = '.mp3'
        
        # Save to temp file
        fd, temp_audio = tempfile.mkstemp(suffix=ext)
        os.close(fd)
        
        with open(temp_audio, 'wb') as f:
            for chunk in dl_response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"Workflow {workflow_id}: Audio downloaded to: {temp_audio}")
        
        workflow['stage_detail'] = 'Transcribing with ElevenLabs...'
        workflow['progress'] = 15
        
        # Transcribe using ElevenLabs (same as test page)
        elevenlabs = ElevenLabsService()
        transcript_data = elevenlabs.transcribe_video(temp_audio)
        
        # Clean up temp audio file
        if os.path.exists(temp_audio):
            os.remove(temp_audio)
        
        workflow['stage_detail'] = 'Saving transcript...'
        workflow['progress'] = 25
        
        # Prepare transcript JSON (same format as test page)
        transcript_result = {
            'workflow_id': workflow_id,
            'audio_url': audio_url,
            'transcript': transcript_data,
            'created_at': time.strftime('%Y-%m-%dT%H:%M:%S')
        }
        
        # Save transcript to S3
        if S3Service.is_s3_configured():
            s3_service = S3Service()
            transcript_key = f"transcripts/{workflow_id}/transcript.json"
            
            # Convert to JSON bytes and upload
            json_content = json.dumps(transcript_result, indent=2, ensure_ascii=False)
            json_bytes = json_content.encode('utf-8')
            
            s3_service.upload_file_content(
                json_bytes,
                transcript_key,
                content_type='application/json'
            )
            
            if s3_service.cloudfront_domain:
                workflow['transcript_url'] = f"https://{s3_service.cloudfront_domain}/{transcript_key}"
            else:
                workflow['transcript_url'] = s3_service.get_public_url_from_key(transcript_key)
        
        # Store transcript data for Stage 3
        workflow['transcript_data'] = transcript_result
        
        logger.info(f"Workflow {workflow_id}: Transcription complete")
        
        # ============ STAGE 3: SEGMENT SELECTION ============
        workflow['stage'] = 3
        workflow['stage_detail'] = f"Analyzing with {workflow['provider']}..."
        workflow['progress'] = 35
        
        logger.info(f"Workflow {workflow_id}: Starting segment analysis")
        
        llm = LLMService(provider=workflow['provider'], model=workflow['model'])
        
        # Extract transcript data (same as test page - handle wrapped format)
        if 'transcript' in transcript_result:
            transcript_for_llm = transcript_result['transcript']
        else:
            transcript_for_llm = transcript_result
        
        segments = llm.analyze_transcript(
            transcript_data=transcript_for_llm,
            num_segments=workflow['num_segments'],
            max_duration=workflow['max_duration'] or 300,
            custom_instructions=workflow['custom_instructions']
        )
        
        workflow['segments'] = segments
        workflow['stage_detail'] = 'Saving segments...'
        workflow['progress'] = 50
        
        # Save segments to S3
        if S3Service.is_s3_configured():
            s3_service = S3Service()
            segments_key = f"segments/{workflow_id}/segments.json"
            
            segments_data = {
                'workflow_id': workflow_id,
                'num_segments': len(segments),
                'provider': workflow['provider'],
                'model': llm.model,
                'segments': segments
            }
            
            fd, temp_segments = tempfile.mkstemp(suffix='.json')
            os.close(fd)
            
            with open(temp_segments, 'w') as f:
                json.dump(segments_data, f, indent=2)
            
            s3_service.upload_file(temp_segments, segments_key)
            os.remove(temp_segments)
            
            if s3_service.cloudfront_domain:
                workflow['segments_url'] = f"https://{s3_service.cloudfront_domain}/{segments_key}"
            else:
                workflow['segments_url'] = s3_service.get_public_url_from_key(segments_key)
        
        logger.info(f"Workflow {workflow_id}: Segment analysis complete, found {len(segments)} segments")
        
        # ============ STAGE 4: CLIP CREATION ============
        workflow['stage'] = 4
        workflow['stage_detail'] = f'Creating {len(segments)} clips...'
        workflow['progress'] = 55
        
        # Use video URL if available, otherwise audio URL
        media_url = workflow['video_url'] or workflow['audio_url']
        is_audio_only = workflow['video_url'] is None
        
        logger.info(f"Workflow {workflow_id}: Starting clip creation for {len(segments)} segments")
        
        shotstack = ShotstackService()
        clips = []
        
        for i, segment in enumerate(segments):
            workflow['stage_detail'] = f'Creating clip {i + 1} of {len(segments)}...'
            base_progress = 55 + (i / len(segments)) * 35
            workflow['progress'] = int(base_progress)
            
            # Add 3 seconds padding to start and end
            start_time = max(0, segment['start_time'] - 3)
            end_time = segment['end_time'] + 3
            
            logger.info(f"Workflow {workflow_id}: Creating clip {i + 1}: {start_time}s - {end_time}s (with 3s padding)")
            
            try:
                # Start render
                render_id = shotstack.create_clip(
                    media_url=media_url,
                    start_time=start_time,
                    end_time=end_time,
                    is_audio_only=is_audio_only
                )
                
                # Wait for render to complete
                workflow['stage_detail'] = f'Rendering clip {i + 1} of {len(segments)}...'
                render_status = shotstack.wait_for_render(render_id, max_wait=300, check_interval=5)
                
                shotstack_url = render_status['url']
                clip_url = shotstack_url
                
                # Upload to S3
                if S3Service.is_s3_configured():
                    try:
                        s3_service = S3Service()
                        
                        dl_response = http_requests.get(shotstack_url, stream=True)
                        dl_response.raise_for_status()
                        
                        fd, temp_clip = tempfile.mkstemp(suffix='.mp4')
                        os.close(fd)
                        
                        with open(temp_clip, 'wb') as f:
                            for chunk in dl_response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        
                        clip_s3_key = f"clips/{workflow_id}/clip_{i + 1}.mp4"
                        s3_service.upload_file(temp_clip, clip_s3_key)
                        os.remove(temp_clip)
                        
                        if s3_service.cloudfront_domain:
                            clip_url = f"https://{s3_service.cloudfront_domain}/{clip_s3_key}"
                        else:
                            clip_url = s3_service.get_public_url_from_key(clip_s3_key)
                        
                        logger.info(f"Workflow {workflow_id}: Clip {i + 1} uploaded to S3: {clip_url}")
                        
                    except Exception as upload_err:
                        logger.error(f"Failed to upload clip to S3: {str(upload_err)}")
                        clip_url = shotstack_url
                
                clips.append({
                    'title': segment.get('title', f'Clip {i + 1}'),
                    'description': segment.get('description', ''),
                    'url': clip_url,
                    'start_time': segment['start_time'],
                    'end_time': segment['end_time'],
                    'duration': segment['end_time'] - segment['start_time'],
                    'render_id': render_id
                })
                
            except Exception as clip_err:
                logger.error(f"Workflow {workflow_id}: Failed to create clip {i + 1}: {str(clip_err)}")
                # Continue with remaining clips
        
        workflow['clips'] = clips
        workflow['progress'] = 100
        workflow['status'] = 'complete'
        workflow['stage_detail'] = 'Complete!'
        
        logger.info(f"Workflow {workflow_id}: Complete! Created {len(clips)} clips")
        
    except Exception as e:
        logger.error(f"Workflow {workflow_id} failed: {str(e)}")
        workflow['status'] = 'failed'
        workflow['error'] = str(e)


@api_view(['GET'])
def get_workflow_status(request, workflow_id):
    """
    Get the status of a workflow
    
    GET /api/workflow-status/<workflow_id>/
    """
    try:
        workflow = _workflow_storage.get(workflow_id)
        
        if not workflow:
            return Response({
                'success': False,
                'error': 'Workflow not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        response_data = {
            'success': True,
            'status': workflow['status'],
            'stage': workflow['stage'],
            'stage_detail': workflow['stage_detail'],
            'progress': workflow['progress']
        }
        
        if workflow['status'] == 'complete':
            response_data['clips'] = workflow['clips']
            response_data['transcript_url'] = workflow['transcript_url']
            response_data['segments_url'] = workflow['segments_url']
            response_data['provider'] = workflow['provider']
            response_data['model'] = workflow['model']
        
        if workflow['status'] == 'failed':
            response_data['error'] = workflow['error']
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Failed to get workflow status: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
