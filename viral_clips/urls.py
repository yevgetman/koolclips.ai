from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    VideoJobViewSet, TranscriptSegmentViewSet, ClippedVideoViewSet,
    get_presigned_upload_url, create_job_from_s3, upload_test_result
)

router = DefaultRouter()
router.register(r'jobs', VideoJobViewSet, basename='videojob')
router.register(r'segments', TranscriptSegmentViewSet, basename='transcriptsegment')
router.register(r'clips', ClippedVideoViewSet, basename='clippedvideo')

urlpatterns = [
    path('', include(router.urls)),
    path('upload/presigned-url/', get_presigned_upload_url, name='presigned-upload-url'),
    path('upload/create-job/', create_job_from_s3, name='create-job-from-s3'),
    path('test-results/upload/', upload_test_result, name='upload-test-result'),
]
