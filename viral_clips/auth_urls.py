from django.urls import path
from .auth_views import (
    UserRegistrationView, UserLoginView, UserProfileView,
    ChangePasswordView, UserDeleteView, refresh_token_view, logout_view
)

urlpatterns = [
    # Authentication
    path('register/', UserRegistrationView.as_view(), name='user-register'),
    path('login/', UserLoginView.as_view(), name='user-login'),
    path('logout/', logout_view, name='user-logout'),
    path('refresh/', refresh_token_view, name='token-refresh'),
    
    # User Profile Management
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('delete-account/', UserDeleteView.as_view(), name='delete-account'),
]
