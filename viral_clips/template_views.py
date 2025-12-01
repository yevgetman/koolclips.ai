from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie


@ensure_csrf_cookie
def register_page(request):
    """Render the registration page"""
    # Redirect authenticated users to profile
    if request.user.is_authenticated:
        return redirect('profile')
    return render(request, 'auth/register.html')


@ensure_csrf_cookie
def login_page(request):
    """Render the login page"""
    # Redirect authenticated users to profile
    if request.user.is_authenticated:
        return redirect('profile')
    return render(request, 'auth/login.html')


@login_required
def profile_page(request):
    """Render the profile page"""
    return render(request, 'auth/profile.html')


def home_page(request):
    """Render the home page"""
    return render(request, 'home.html')


@login_required
def test_stage1_upload(request):
    """Test page for Stage 1: Video upload and pre-processing"""
    return render(request, 'test/stage1_upload.html')


@login_required
def test_stage2_transcription(request):
    """Test page for Stage 2: Audio transcription"""
    return render(request, 'test/stage2_transcription.html')


@login_required
def test_stage3_segments(request):
    """Test page for Stage 3: Segment selection"""
    return render(request, 'test/stage3_segments.html')
