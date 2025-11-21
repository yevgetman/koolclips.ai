from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, parser_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from django.conf import settings
import json
from datetime import datetime

from .models import VideoJob, TranscriptSegment, ClippedVideo
from .serializers import (
    VideoJobSerializer, VideoJobCreateSerializer, VideoJobListSerializer,
    TranscriptSegmentSerializer, ClippedVideoSerializer
)
from .services.s3_service import S3Service


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
