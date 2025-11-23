# User Authentication System Setup

This document describes the user authentication system that has been implemented for the Viral Clips application.

## Overview

A complete JWT-based authentication system with modern UI components has been added to the application.

## Features Implemented

### Backend (Django REST Framework + JWT)

1. **Authentication Endpoints** (`/api/auth/`)
   - `POST /api/auth/register/` - Create new user account
   - `POST /api/auth/login/` - Login and get JWT tokens
   - `POST /api/auth/refresh/` - Refresh access token
   - `GET /api/auth/profile/` - Get current user profile
   - `PATCH /api/auth/profile/` - Update user profile
   - `POST /api/auth/change-password/` - Change password
   - `DELETE /api/auth/delete-account/` - Delete user account

2. **JWT Authentication**
   - Access token lifetime: 1 hour
   - Refresh token lifetime: 7 days
   - Bearer token authentication for API requests

3. **Security Features**
   - Password validation (Django's built-in validators)
   - CSRF protection
   - Session-based and JWT-based authentication

### Frontend (Modern UI with Tailwind CSS)

1. **Page Routes**
   - `/` - Home page with hero section
   - `/register/` - User registration page
   - `/login/` - User login page
   - `/profile/` - User profile dashboard (requires authentication)

2. **UI Components**
   - Responsive design with Tailwind CSS
   - Alpine.js for reactive components
   - Toast notifications for user feedback
   - Form validation
   - Loading states

3. **Features**
   - Registration form with validation
   - Login form with remember me option
   - Profile management (edit personal info)
   - Password change functionality
   - Account deletion with confirmation
   - Client-side token management (localStorage)

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run Migrations

```bash
python manage.py migrate
```

### 3. Create a Superuser (Optional)

```bash
python manage.py createsuperuser
```

### 4. Start the Development Server

```bash
python manage.py runserver
```

### 5. Access the Application

- Home: http://localhost:8000/
- Registration: http://localhost:8000/register/
- Login: http://localhost:8000/login/
- Profile: http://localhost:8000/profile/ (requires login)
- API Docs: http://localhost:8000/api/

## API Usage Examples

### Register a New User

```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "johndoe",
    "email": "john@example.com",
    "password": "SecurePass123!",
    "password_confirm": "SecurePass123!",
    "first_name": "John",
    "last_name": "Doe"
  }'
```

### Login

```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "johndoe",
    "password": "SecurePass123!"
  }'
```

Response:
```json
{
  "success": true,
  "message": "Login successful",
  "user": {
    "id": 1,
    "username": "johndoe",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "date_joined": "2024-11-23T22:42:00Z"
  },
  "tokens": {
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "access": "eyJ0eXAiOiJKV1QiLCJhbGc..."
  }
}
```

### Get Profile (Protected Endpoint)

```bash
curl -X GET http://localhost:8000/api/auth/profile/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Update Profile

```bash
curl -X PATCH http://localhost:8000/api/auth/profile/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Jane",
    "email": "jane@example.com"
  }'
```

### Change Password

```bash
curl -X POST http://localhost:8000/api/auth/change-password/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "old_password": "SecurePass123!",
    "new_password": "NewSecurePass456!",
    "new_password_confirm": "NewSecurePass456!"
  }'
```

### Delete Account

```bash
curl -X DELETE http://localhost:8000/api/auth/delete-account/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "password": "SecurePass123!"
  }'
```

## Frontend Integration

### Storing Tokens

After successful login or registration, tokens are stored in localStorage:

```javascript
localStorage.setItem('access_token', data.tokens.access);
localStorage.setItem('refresh_token', data.tokens.refresh);
```

### Making Authenticated Requests

Use the helper function to include auth headers:

```javascript
const response = await fetch('/api/auth/profile/', {
  headers: getAuthHeaders()  // Includes Bearer token
});
```

### Logout

```javascript
function handleLogout() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  window.location.href = '/login/';
}
```

## File Structure

```
viral_clips/
├── auth_serializers.py    # Serializers for user auth operations
├── auth_views.py          # API views for authentication
├── auth_urls.py           # URL routing for auth endpoints
└── template_views.py      # Views for rendering HTML templates

templates/
├── base.html              # Base template with Tailwind CSS
├── home.html              # Landing page
└── auth/
    ├── register.html      # Registration page
    ├── login.html         # Login page
    └── profile.html       # User profile dashboard

config/
├── settings.py           # Updated with JWT and auth settings
└── urls.py              # Main URL configuration
```

## Security Notes

1. **Token Storage**: Tokens are stored in localStorage (consider HttpOnly cookies for production)
2. **HTTPS**: Use HTTPS in production to secure token transmission
3. **CSRF**: CSRF protection is enabled for session-based views
4. **Password Validation**: Django's password validators are active
5. **Token Expiry**: Access tokens expire after 1 hour, refresh tokens after 7 days

## Next Steps

1. **Email Verification**: Add email verification for new registrations
2. **Password Reset**: Implement forgot password functionality
3. **Social Auth**: Add OAuth integration (Google, GitHub, etc.)
4. **Rate Limiting**: Add rate limiting to prevent abuse
5. **2FA**: Implement two-factor authentication
6. **User Roles**: Add user roles and permissions system

## Troubleshooting

### Token Expired Error

If you get a 401 error, your access token may have expired. Use the refresh token:

```javascript
const response = await fetch('/api/auth/refresh/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ refresh: localStorage.getItem('refresh_token') })
});
```

### CORS Issues

If testing from a different domain, ensure CORS is properly configured in settings.py.

### Static Files Not Loading

Run `python manage.py collectstatic` to gather static files.

## Support

For issues or questions, refer to:
- Django REST Framework docs: https://www.django-rest-framework.org/
- djangorestframework-simplejwt: https://django-rest-framework-simplejwt.readthedocs.io/
- Tailwind CSS: https://tailwindcss.com/docs
- Alpine.js: https://alpinejs.dev/
