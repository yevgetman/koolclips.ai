#!/usr/bin/env python
"""
Test script for authentication endpoints
Run: python test_auth.py
"""

import requests
import json
import sys

BASE_URL = "http://127.0.0.1:8000/api/auth"

def print_response(title, response):
    """Pretty print API response"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"Status Code: {response.status_code}")
    try:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except:
        print(f"Response: {response.text}")
    print()

def test_registration():
    """Test user registration"""
    print("\n🧪 Testing User Registration...")
    
    data = {
        "username": "testuser123",
        "email": "testuser@example.com",
        "password": "TestPass123!@#",
        "password_confirm": "TestPass123!@#",
        "first_name": "Test",
        "last_name": "User"
    }
    
    response = requests.post(f"{BASE_URL}/register/", json=data)
    print_response("Registration Response", response)
    
    if response.status_code == 201:
        tokens = response.json().get('tokens', {})
        return tokens.get('access'), tokens.get('refresh')
    return None, None

def test_login():
    """Test user login"""
    print("\n🧪 Testing User Login...")
    
    data = {
        "username": "testuser123",
        "password": "TestPass123!@#"
    }
    
    response = requests.post(f"{BASE_URL}/login/", json=data)
    print_response("Login Response", response)
    
    if response.status_code == 200:
        tokens = response.json().get('tokens', {})
        return tokens.get('access'), tokens.get('refresh')
    return None, None

def test_profile(access_token):
    """Test getting user profile"""
    print("\n🧪 Testing Get Profile...")
    
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    response = requests.get(f"{BASE_URL}/profile/", headers=headers)
    print_response("Profile Response", response)
    return response.status_code == 200

def test_update_profile(access_token):
    """Test updating user profile"""
    print("\n🧪 Testing Update Profile...")
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    data = {
        "first_name": "Updated",
        "last_name": "Name"
    }
    
    response = requests.patch(f"{BASE_URL}/profile/", json=data, headers=headers)
    print_response("Update Profile Response", response)
    return response.status_code == 200

def test_change_password(access_token):
    """Test changing password"""
    print("\n🧪 Testing Change Password...")
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    data = {
        "old_password": "TestPass123!@#",
        "new_password": "NewTestPass456!@#",
        "new_password_confirm": "NewTestPass456!@#"
    }
    
    response = requests.post(f"{BASE_URL}/change-password/", json=data, headers=headers)
    print_response("Change Password Response", response)
    return response.status_code == 200

def test_refresh_token(refresh_token):
    """Test refreshing access token"""
    print("\n🧪 Testing Refresh Token...")
    
    data = {
        "refresh": refresh_token
    }
    
    response = requests.post(f"{BASE_URL}/refresh/", json=data)
    print_response("Refresh Token Response", response)
    
    if response.status_code == 200:
        return response.json().get('access')
    return None

def main():
    """Run all authentication tests"""
    print("\n" + "="*60)
    print("🚀 Starting Authentication Tests")
    print("="*60)
    
    # Test 1: Registration
    access_token, refresh_token = test_registration()
    
    if not access_token:
        print("❌ Registration failed, trying login instead...")
        # If registration fails (user might exist), try login
        access_token, refresh_token = test_login()
    
    if not access_token:
        print("❌ Authentication tests failed - could not get access token")
        sys.exit(1)
    
    # Test 2: Get Profile
    if test_profile(access_token):
        print("✅ Get Profile - PASSED")
    else:
        print("❌ Get Profile - FAILED")
    
    # Test 3: Update Profile
    if test_update_profile(access_token):
        print("✅ Update Profile - PASSED")
    else:
        print("❌ Update Profile - FAILED")
    
    # Test 4: Change Password
    if test_change_password(access_token):
        print("✅ Change Password - PASSED")
    else:
        print("❌ Change Password - FAILED")
    
    # Test 5: Refresh Token
    new_access_token = test_refresh_token(refresh_token)
    if new_access_token:
        print("✅ Refresh Token - PASSED")
    else:
        print("❌ Refresh Token - FAILED")
    
    print("\n" + "="*60)
    print("✅ All Authentication Tests Completed!")
    print("="*60 + "\n")
    
    # Note about cleanup
    print("📝 Note: Test user 'testuser123' was created during testing.")
    print("   You can delete it via the admin panel or profile page.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error running tests: {str(e)}")
        sys.exit(1)
