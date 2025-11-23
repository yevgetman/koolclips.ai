#!/bin/bash

# Deployment script for Viral Clips Authentication System
# Usage: ./deploy.sh

set -e  # Exit on error

echo ""
echo "🚀 =============================================="
echo "   Viral Clips - Production Deployment"
echo "   =============================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if Heroku CLI is installed
if ! command -v heroku &> /dev/null; then
    echo -e "${RED}❌ Heroku CLI not found. Please install it first:${NC}"
    echo "   brew tap heroku/brew && brew install heroku"
    exit 1
fi

# Check if git is initialized
if [ ! -d .git ]; then
    echo -e "${RED}❌ Not a git repository. Please initialize git first.${NC}"
    exit 1
fi

# Step 1: Pre-deployment checks
echo -e "${BLUE}📋 Step 1: Pre-deployment checks${NC}"
echo "   Checking git status..."
git status --short

echo ""
read -p "   Do you want to commit all changes? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}   📦 Committing changes...${NC}"
    git add .
    git commit -m "Deploy authentication system with JWT and modern UI

- Implemented JWT authentication with djangorestframework-simplejwt
- Created 7 API endpoints for user management
- Built modern UI with Tailwind CSS and Alpine.js
- Added registration, login, and profile pages
- Configured JWT tokens (1hr access, 7-day refresh)
- Added comprehensive documentation and tests" || echo "   ℹ️  No changes to commit"
else
    echo -e "${YELLOW}   ⏩ Skipping commit${NC}"
fi

# Step 2: Push to Heroku
echo ""
echo -e "${BLUE}📤 Step 2: Deploying to Heroku${NC}"
echo "   Available Heroku apps:"
heroku apps --all 2>/dev/null || echo "   No apps found or not logged in"

echo ""
read -p "   Enter your Heroku app name (or press Enter to skip): " APP_NAME
echo ""

if [ -z "$APP_NAME" ]; then
    echo -e "${YELLOW}   ⏩ Skipping Heroku deployment${NC}"
    echo -e "${YELLOW}   Run manually: git push heroku master${NC}"
else
    echo -e "${YELLOW}   🔄 Setting Heroku remote...${NC}"
    heroku git:remote -a $APP_NAME 2>/dev/null || echo "   Remote already exists"
    
    echo -e "${YELLOW}   ☁️  Pushing to Heroku...${NC}"
    git push heroku master || git push heroku main:master
    
    # Step 3: Run migrations
    echo ""
    echo -e "${BLUE}🔄 Step 3: Running migrations${NC}"
    heroku run python manage.py migrate -a $APP_NAME
    
    # Step 4: Collect static files
    echo ""
    echo -e "${BLUE}📁 Step 4: Collecting static files${NC}"
    heroku run python manage.py collectstatic --noinput -a $APP_NAME
    
    # Step 5: Restart dynos
    echo ""
    echo -e "${BLUE}♻️  Step 5: Restarting application${NC}"
    heroku restart -a $APP_NAME
    
    # Step 6: Check status
    echo ""
    echo -e "${BLUE}📊 Step 6: Checking application status${NC}"
    heroku ps -a $APP_NAME
    
    # Step 7: Show logs
    echo ""
    echo -e "${BLUE}📝 Recent logs:${NC}"
    heroku logs --tail --num 20 -a $APP_NAME
    
    # Success message
    echo ""
    echo -e "${GREEN}✅ =============================================="
    echo "   Deployment Complete!"
    echo "   ==============================================${NC}"
    echo ""
    echo -e "${GREEN}🌐 Your app: https://$APP_NAME.herokuapp.com${NC}"
    echo ""
    echo -e "${YELLOW}📋 Next Steps:${NC}"
    echo "   1. Test home page: https://$APP_NAME.herokuapp.com/"
    echo "   2. Test registration: https://$APP_NAME.herokuapp.com/register/"
    echo "   3. Test login: https://$APP_NAME.herokuapp.com/login/"
    echo "   4. Monitor logs: heroku logs --tail -a $APP_NAME"
    echo ""
    echo -e "${YELLOW}🧪 Run API tests:${NC}"
    echo "   export API_URL=https://$APP_NAME.herokuapp.com"
    echo '   curl -X POST $API_URL/api/auth/register/ -H "Content-Type: application/json" -d {...}'
    echo ""
    
    # Ask to open browser
    read -p "   Open app in browser? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        heroku open -a $APP_NAME
    fi
fi

echo ""
echo -e "${GREEN}🎉 All done!${NC}"
echo ""
