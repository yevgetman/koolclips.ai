from django.shortcuts import render
from django.contrib.auth.decorators import login_required


def register_page(request):
    """Render the registration page"""
    return render(request, 'auth/register.html')


def login_page(request):
    """Render the login page"""
    return render(request, 'auth/login.html')


@login_required
def profile_page(request):
    """Render the profile page"""
    return render(request, 'auth/profile.html')


def home_page(request):
    """Render the home page"""
    return render(request, 'home.html')
