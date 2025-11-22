from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, parser_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from django.conf import settings
import json
import uuid
from datetime import datetime

from .models import VideoJob, TranscriptSegment, ClippedVideo
from .serializers import (
    VideoJobSerializer, VideoJobCreateSerializer, VideoJobListSerializer,
    TranscriptSegmentSerializer, ClippedVideoSerializer
)
from .services.s3_service import S3Service
from .utils import detect_file_type


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
        
        # Validate file size (2GB limit)
        max_size = 2 * 1024 * 1024 * 1024  # 2GB
        if file_size > max_size:
            return Response({
                'success': False,
                'error': f'File too large. Maximum size is 2GB. File size: {file_size / 1024 / 1024 / 1024:.2f}GB'
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
        
        return Response({
            'success': True,
            'upload_url': presigned_data['url'],
            'upload_fields': presigned_data['fields'],
            's3_key': presigned_data['s3_key'],
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
        
        # Generate S3 URLs
        job.media_file_s3_url = s3_service.get_public_url_from_key(s3_key)
        job.media_file_cloudfront_url = job.media_file_s3_url
        
        # Store the S3 key so we can access it later
        # We'll use a custom field to store just the key path
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
