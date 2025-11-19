from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import VideoJobViewSet, TranscriptSegmentViewSet, ClippedVideoViewSet

router = DefaultRouter()
router.register(r'jobs', VideoJobViewSet, basename='videojob')
router.register(r'segments', TranscriptSegmentViewSet, basename='transcriptsegment')
router.register(r'clips', ClippedVideoViewSet, basename='clippedvideo')

urlpatterns = [
    path('', include(router.urls)),
]
