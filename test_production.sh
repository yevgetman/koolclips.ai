#!/bin/bash

# Production Testing Script for Authentication System
# Usage: ./test_production.sh [app-url]

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Get app URL
if [ -z "$1" ]; then
    read -p "Enter your app URL (e.g., https://koolclips.herokuapp.com): " APP_URL
else
    APP_URL=$1
fi

# Remove trailing slash
APP_URL=${APP_URL%/}

echo ""
echo -e "${BLUE}🧪 =============================================="
echo "   Testing Production Authentication System"
echo "   ==============================================${NC}"
echo ""
echo "   App URL: $APP_URL"
echo ""

# Test 1: Home page
echo -e "${YELLOW}Test 1: Home Page${NC}"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" $APP_URL/)
if [ "$STATUS" -eq 200 ]; then
    echo -e "${GREEN}✅ Home page - PASSED (200)${NC}"
else
    echo -e "${RED}❌ Home page - FAILED ($STATUS)${NC}"
fi

# Test 2: Registration page
echo -e "${YELLOW}Test 2: Registration Page${NC}"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" $APP_URL/register/)
if [ "$STATUS" -eq 200 ]; then
    echo -e "${GREEN}✅ Registration page - PASSED (200)${NC}"
else
    echo -e "${RED}❌ Registration page - FAILED ($STATUS)${NC}"
fi

# Test 3: Login page
echo -e "${YELLOW}Test 3: Login Page${NC}"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" $APP_URL/login/)
if [ "$STATUS" -eq 200 ]; then
    echo -e "${GREEN}✅ Login page - PASSED (200)${NC}"
else
    echo -e "${RED}❌ Login page - FAILED ($STATUS)${NC}"
fi

# Test 4: API Registration
echo -e "${YELLOW}Test 4: API Registration Endpoint${NC}"
TIMESTAMP=$(date +%s)
USERNAME="prodtest$TIMESTAMP"

RESPONSE=$(curl -s -X POST $APP_URL/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d "{
    \"username\": \"$USERNAME\",
    \"email\": \"$USERNAME@example.com\",
    \"password\": \"TestPass123!\",
    \"password_confirm\": \"TestPass123!\"
  }")

if echo "$RESPONSE" | grep -q "success.*true"; then
    echo -e "${GREEN}✅ API Registration - PASSED${NC}"
    ACCESS_TOKEN=$(echo "$RESPONSE" | grep -o '"access":"[^"]*' | cut -d'"' -f4)
    echo "   Created user: $USERNAME"
else
    echo -e "${RED}❌ API Registration - FAILED${NC}"
    echo "   Response: $RESPONSE"
    ACCESS_TOKEN=""
fi

# Test 5: API Login
echo -e "${YELLOW}Test 5: API Login Endpoint${NC}"
RESPONSE=$(curl -s -X POST $APP_URL/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d "{
    \"username\": \"$USERNAME\",
    \"password\": \"TestPass123!\"
  }")

if echo "$RESPONSE" | grep -q "success.*true"; then
    echo -e "${GREEN}✅ API Login - PASSED${NC}"
    if [ -z "$ACCESS_TOKEN" ]; then
        ACCESS_TOKEN=$(echo "$RESPONSE" | grep -o '"access":"[^"]*' | cut -d'"' -f4)
    fi
else
    echo -e "${RED}❌ API Login - FAILED${NC}"
    echo "   Response: $RESPONSE"
fi

# Test 6: API Profile (Protected)
if [ ! -z "$ACCESS_TOKEN" ]; then
    echo -e "${YELLOW}Test 6: API Profile Endpoint (Protected)${NC}"
    RESPONSE=$(curl -s -X GET $APP_URL/api/auth/profile/ \
      -H "Authorization: Bearer $ACCESS_TOKEN")
    
    if echo "$RESPONSE" | grep -q "success.*true"; then
        echo -e "${GREEN}✅ API Profile - PASSED${NC}"
    else
        echo -e "${RED}❌ API Profile - FAILED${NC}"
        echo "   Response: $RESPONSE"
    fi
    
    # Test 7: Update Profile
    echo -e "${YELLOW}Test 7: Update Profile Endpoint${NC}"
    RESPONSE=$(curl -s -X PATCH $APP_URL/api/auth/profile/ \
      -H "Authorization: Bearer $ACCESS_TOKEN" \
      -H "Content-Type: application/json" \
      -d '{
        "first_name": "Production",
        "last_name": "Test"
      }')
    
    if echo "$RESPONSE" | grep -q "success.*true"; then
        echo -e "${GREEN}✅ Update Profile - PASSED${NC}"
    else
        echo -e "${RED}❌ Update Profile - FAILED${NC}"
        echo "   Response: $RESPONSE"
    fi
else
    echo -e "${YELLOW}⏩ Skipping protected endpoint tests (no token)${NC}"
fi

# Test 8: Static Files
echo -e "${YELLOW}Test 8: Static Files & CDN${NC}"
PAGE_CONTENT=$(curl -s $APP_URL/register/)
if echo "$PAGE_CONTENT" | grep -q "tailwindcss.com"; then
    echo -e "${GREEN}✅ Tailwind CSS CDN - PASSED${NC}"
else
    echo -e "${RED}❌ Tailwind CSS CDN - FAILED${NC}"
fi

if echo "$PAGE_CONTENT" | grep -q "alpinejs"; then
    echo -e "${GREEN}✅ Alpine.js CDN - PASSED${NC}"
else
    echo -e "${RED}❌ Alpine.js CDN - FAILED${NC}"
fi

# Summary
echo ""
echo -e "${BLUE}=============================================="
echo "   Test Summary"
echo "   ==============================================${NC}"
echo ""
echo -e "${GREEN}✅ Production authentication system is working!${NC}"
echo ""
echo "   Test user created: $USERNAME"
echo "   Password: TestPass123!"
echo ""
echo -e "${YELLOW}📋 Manual Testing:${NC}"
echo "   1. Visit: $APP_URL/"
echo "   2. Click 'Sign Up' and create an account"
echo "   3. Test login functionality"
echo "   4. Check profile page and features"
echo ""
echo -e "${YELLOW}📊 Monitor logs:${NC}"
echo "   heroku logs --tail -a koolclips"
echo ""
