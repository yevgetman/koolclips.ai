# 🚀 Quick Start Guide - User Authentication

## ⚡ 3-Step Setup

### 1️⃣ Install Dependencies
```bash
pip install -r requirements.txt
```

### 2️⃣ Run Migrations
```bash
python manage.py migrate
```

### 3️⃣ Start Server
```bash
python manage.py runserver
```

**🎉 Done! Open http://localhost:8000/**

---

## 📱 Try It Out

### Via Web Interface

1. **Visit** http://localhost:8000/
2. **Click** "Sign Up" button
3. **Create** your account
4. **Explore** your profile dashboard

### Via API

```bash
# Register
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "demo",
    "email": "demo@example.com",
    "password": "DemoPass123!",
    "password_confirm": "DemoPass123!"
  }'

# Login
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "demo",
    "password": "DemoPass123!"
  }'
```

---

## 🧪 Run Tests

```bash
python test_auth.py
```

---

## 📚 Full Documentation

- **AUTH_SETUP.md** - Complete setup guide
- **AUTHENTICATION_SUMMARY.md** - Technical details
- **USER_AUTH_README.md** - User guide

---

## 🎨 What You Get

### 🌐 Web Pages
- `/` - Landing page
- `/register/` - Sign up
- `/login/` - Sign in
- `/profile/` - Dashboard

### 🔌 API Endpoints
- `POST /api/auth/register/`
- `POST /api/auth/login/`
- `GET /api/auth/profile/`
- `PATCH /api/auth/profile/`
- `POST /api/auth/change-password/`
- `DELETE /api/auth/delete-account/`
- `POST /api/auth/refresh/`

### ✨ Features
- ✅ JWT authentication
- ✅ Modern Tailwind UI
- ✅ Profile management
- ✅ Password change
- ✅ Account deletion
- ✅ Responsive design

---

## 🎯 Quick Links

| Action | URL |
|--------|-----|
| Home | http://localhost:8000/ |
| Sign Up | http://localhost:8000/register/ |
| Sign In | http://localhost:8000/login/ |
| Profile | http://localhost:8000/profile/ |
| API Docs | http://localhost:8000/api/ |
| Admin | http://localhost:8000/admin/ |

---

**Questions? Check the detailed docs or the test script!**
