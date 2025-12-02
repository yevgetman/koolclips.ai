"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from viral_clips.template_views import register_page, login_page, profile_page, home_page, test_stage1_upload, test_stage1_uppy_upload, test_stage2_transcription, test_stage3_segments, test_stage4_clipping, workflow_page

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include('viral_clips.urls')),
    # UI Pages
    path("", home_page, name='home'),
    path("register/", register_page, name='register'),
    path("login/", login_page, name='login'),
    path("profile/", profile_page, name='profile'),
    # Test Pages
    path("test/stage1/", test_stage1_upload, name='test-stage1'),
    path("test/stage1/uppy/", test_stage1_uppy_upload, name='test-stage1-uppy'),
    path("test/stage2/", test_stage2_transcription, name='test-stage2'),
    path("test/stage3/", test_stage3_segments, name='test-stage3'),
    path("test/stage4/", test_stage4_clipping, name='test-stage4'),
    # Production Workflow
    path("workflow/", workflow_page, name='workflow'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
