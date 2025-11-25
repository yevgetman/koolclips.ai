# 🌐 Production URLs - Quick Reference

## Live Application

**Production URL:** https://koolclips-ed69bc2e07f2.herokuapp.com

---

## 📱 Web Pages

| Page | URL | Status |
|------|-----|--------|
| **Home** | https://koolclips-ed69bc2e07f2.herokuapp.com/ | ✅ Live |
| **Sign Up** | https://koolclips-ed69bc2e07f2.herokuapp.com/register/ | ✅ Live |
| **Sign In** | https://koolclips-ed69bc2e07f2.herokuapp.com/login/ | ✅ Live |
| **Profile** | https://koolclips-ed69bc2e07f2.herokuapp.com/profile/ | ✅ Live |
| **Admin** | https://koolclips-ed69bc2e07f2.herokuapp.com/admin/ | ✅ Live |

---

## 🔌 API Endpoints

**Base:** `https://koolclips-ed69bc2e07f2.herokuapp.com/api/`

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register/` | Create new account |
| POST | `/api/auth/login/` | Login and get tokens |
| POST | `/api/auth/refresh/` | Refresh access token |
| GET | `/api/auth/profile/` | Get user profile 🔒 |
| PATCH | `/api/auth/profile/` | Update profile 🔒 |
| POST | `/api/auth/change-password/` | Change password 🔒 |
| DELETE | `/api/auth/delete-account/` | Delete account 🔒 |

🔒 = Requires authentication (Bearer token)

### Video Processing

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/jobs/` | List all jobs |
| POST | `/api/jobs/` | Create new job |
| GET | `/api/jobs/{id}/` | Get job details |
| GET | `/api/segments/` | List segments |
| GET | `/api/clips/` | List clips |

---

## 🧪 Quick Test Commands

### Test Registration
```bash
curl -X POST https://koolclips-ed69bc2e07f2.herokuapp.com/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "SecurePass123!",
    "password_confirm": "SecurePass123!"
  }'
```

### Test Login
```bash
curl -X POST https://koolclips-ed69bc2e07f2.herokuapp.com/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "SecurePass123!"
  }'
```

### Test Profile (with token)
```bash
curl -X GET https://koolclips-ed69bc2e07f2.herokuapp.com/api/auth/profile/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## 📊 Monitoring

### View Logs
```bash
heroku logs --tail -a koolclips
```

### Check Status
```bash
heroku ps -a koolclips
```

### View Config
```bash
heroku config -a koolclips
```

---

## 🎯 Getting Started

1. **Visit:** https://koolclips-ed69bc2e07f2.herokuapp.com/
2. **Sign Up:** Click "Sign Up" button
3. **Create Account:** Fill in the form
4. **Explore:** Check out your profile dashboard

---

## 🔧 Management

- **Heroku Dashboard:** https://dashboard.heroku.com/apps/koolclips
- **Git Repository:** Connected to your local repo
- **Database:** PostgreSQL (Heroku Postgres)
- **Cache:** Redis (Heroku Redis)

---

**Status:** ✅ All systems operational  
**Last Updated:** November 23, 2025  
**Version:** v42
