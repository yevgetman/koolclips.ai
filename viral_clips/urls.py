from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    VideoJobViewSet, TranscriptSegmentViewSet, ClippedVideoViewSet,
    get_presigned_upload_url, create_job_from_s3, upload_test_result,
    initiate_multipart_upload, get_multipart_upload_urls,
    complete_multipart_upload, abort_multipart_upload, proxy_upload_chunk,
    bulk_cleanup_cloudcube, cleanup_all_clips, extract_audio_from_video,
    transcribe_audio, analyze_segments, create_clip, get_clip_status,
    process_workflow, get_workflow_status
)

router = DefaultRouter()
router.register(r'jobs', VideoJobViewSet, basename='videojob')
router.register(r'segments', TranscriptSegmentViewSet, basename='transcriptsegment')
router.register(r'clips', ClippedVideoViewSet, basename='clippedvideo')

urlpatterns = [
    path('', include(router.urls)),
    # Authentication endpoints
    path('auth/', include('viral_clips.auth_urls')),
    # Single-part upload (for smaller files)
    path('upload/presigned-url/', get_presigned_upload_url, name='presigned-upload-url'),
    # Multipart upload (for large files)
    path('upload/multipart/initiate/', initiate_multipart_upload, name='initiate-multipart-upload'),
    path('upload/multipart/urls/', get_multipart_upload_urls, name='get-multipart-upload-urls'),
    path('upload/multipart/complete/', complete_multipart_upload, name='complete-multipart-upload'),
    path('upload/multipart/abort/', abort_multipart_upload, name='abort-multipart-upload'),
    path('upload/proxy-chunk/', proxy_upload_chunk, name='proxy-upload-chunk'),
    # Create job after upload
    path('upload/create-job/', create_job_from_s3, name='create-job-from-s3'),
    # Audio extraction (Stage 1 preprocessing)
    path('upload/extract-audio/', extract_audio_from_video, name='extract-audio-from-video'),
    # Transcription (Stage 2)
    path('transcribe/', transcribe_audio, name='transcribe-audio'),
    # Segment analysis (Stage 3)
    path('analyze-segments/', analyze_segments, name='analyze-segments'),
    # Clip creation (Stage 4)
    path('create-clip/', create_clip, name='create-clip'),
    path('clip-status/<str:render_id>/', get_clip_status, name='get-clip-status'),
    # Production workflow (combines Stages 2-4)
    path('process-workflow/', process_workflow, name='process-workflow'),
    path('workflow-status/<str:workflow_id>/', get_workflow_status, name='get-workflow-status'),
    # Cleanup utilities
    path('cleanup/bulk/', bulk_cleanup_cloudcube, name='bulk-cleanup-cloudcube'),
    path('cleanup/clips/', cleanup_all_clips, name='cleanup-all-clips'),
    # Test utilities
    path('test-results/upload/', upload_test_result, name='upload-test-result'),
]
