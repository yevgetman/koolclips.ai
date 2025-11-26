from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from .auth_serializers import (
    UserSerializer, UserRegistrationSerializer, 
    UserUpdateSerializer, ChangePasswordSerializer
)


class UserRegistrationView(generics.CreateAPIView):
    """
    Register a new user account
    
    POST /api/auth/register/
    Body: {
        "username": "johndoe",
        "email": "john@example.com",
        "password": "secure_password123",
        "password_confirm": "secure_password123",
        "first_name": "John",  // optional
        "last_name": "Doe"      // optional
    }
    
    Returns: User details with JWT tokens
    """
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []  # No authentication required for registration
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'success': True,
            'message': 'User registered successfully',
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)


class UserLoginView(APIView):
    """
    Login user and get JWT tokens
    
    POST /api/auth/login/
    Body: {
        "username": "johndoe",
        "password": "secure_password123"
    }
    
    Returns: User details with JWT tokens
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []  # No authentication required for login
    
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response({
                'success': False,
                'error': 'Please provide both username and password'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user = authenticate(username=username, password=password)
        
        if user is None:
            return Response({
                'success': False,
                'error': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'success': True,
            'message': 'Login successful',
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_200_OK)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    Get or update current user profile
    
    GET /api/auth/profile/
    Returns: User details
    
    PUT/PATCH /api/auth/profile/
    Body: {
        "email": "newemail@example.com",
        "first_name": "John",
        "last_name": "Doe"
    }
    
    Returns: Updated user details
    """
    serializer_class = UserUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user
    
    def retrieve(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = UserSerializer(user)
        return Response({
            'success': True,
            'user': serializer.data
        })
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        user = self.get_object()
        serializer = self.get_serializer(user, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            'success': True,
            'message': 'Profile updated successfully',
            'user': UserSerializer(user).data
        })


class ChangePasswordView(APIView):
    """
    Change user password
    
    POST /api/auth/change-password/
    Body: {
        "old_password": "current_password",
        "new_password": "new_secure_password",
        "new_password_confirm": "new_secure_password"
    }
    
    Returns: Success message
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user = request.user
        
        # Check old password
        if not user.check_password(serializer.validated_data['old_password']):
            return Response({
                'success': False,
                'error': 'Old password is incorrect'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Set new password
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        return Response({
            'success': True,
            'message': 'Password changed successfully'
        }, status=status.HTTP_200_OK)


class UserDeleteView(APIView):
    """
    Delete user account
    
    DELETE /api/auth/delete-account/
    Body: {
        "password": "current_password"  // confirmation
    }
    
    Returns: Success message
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def delete(self, request):
        password = request.data.get('password')
        
        if not password:
            return Response({
                'success': False,
                'error': 'Password confirmation required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user = request.user
        
        # Verify password
        if not user.check_password(password):
            return Response({
                'success': False,
                'error': 'Password is incorrect'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Delete user
        username = user.username
        user.delete()
        
        return Response({
            'success': True,
            'message': f'Account {username} has been deleted successfully'
        }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def refresh_token_view(request):
    """
    Refresh JWT access token
    
    POST /api/auth/refresh/
    Body: {
        "refresh": "refresh_token_here"
    }
    
    Returns: New access token
    """
    refresh_token = request.data.get('refresh')
    
    if not refresh_token:
        return Response({
            'success': False,
            'error': 'Refresh token is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        refresh = RefreshToken(refresh_token)
        return Response({
            'success': True,
            'access': str(refresh.access_token)
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'success': False,
            'error': 'Invalid or expired refresh token'
        }, status=status.HTTP_401_UNAUTHORIZED)
