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
