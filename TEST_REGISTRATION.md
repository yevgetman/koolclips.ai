# ✅ Test Registration - Quick Guide

## 🎯 What Was Fixed

**Issue:** 400 error when registering from browser  
**Solution:** Added CSRF token handling  
**Status:** ✅ Fixed and deployed (v43)

---

## 🧪 Test Now

### Step 1: Open Registration Page
```
https://koolclips-ed69bc2e07f2.herokuapp.com/register/
```

### Step 2: Open Browser DevTools
- Press **F12** (or Cmd+Option+I on Mac)
- Go to **Network** tab
- Keep it open while testing

### Step 3: Fill Out Form
Try creating a test account:
- **Username:** yourname123
- **Email:** yourname@example.com
- **Password:** TestPass123!
- **Confirm Password:** TestPass123!

### Step 4: Submit & Check
Click **"Create Account"**

**What to Look For:**

✅ **Success Indicators:**
- Request shows `Status: 201` in Network tab
- Request headers include `X-CSRFToken`
- Response has `"success": true`
- Redirects to profile page
- Toast notification: "Account created successfully!"

❌ **If Still Failing:**
- Status: 400 → Check CSRF token in headers
- Status: 400 → Clear browser cache and try again
- Network error → Check console for errors

---

## 🔍 Debugging

### Check Request Headers
In Network tab, click on the `/api/auth/register/` request:
- Should see `X-CSRFToken: [long token]`
- Should see `Content-Type: application/json`

### Check Request Payload
```json
{
  "username": "yourname123",
  "email": "yourname@example.com",
  "password": "TestPass123!",
  "password_confirm": "TestPass123!"
}
```

### Expected Response (Success)
```json
{
  "success": true,
  "message": "User registered successfully",
  "user": {
    "id": 35,
    "username": "yourname123",
    "email": "yourname@example.com",
    ...
  },
  "tokens": {
    "access": "eyJ...",
    "refresh": "eyJ..."
  }
}
```

---

## 📊 Test Other Features

Once registered, test these:

### ✅ Login
1. Logout or open incognito window
2. Go to: https://koolclips-ed69bc2e07f2.herokuapp.com/login/
3. Enter credentials
4. Should redirect to profile

### ✅ Profile Update
1. Go to profile page
2. Click "Edit Profile"
3. Change first/last name
4. Click "Save Changes"
5. Should update without errors

### ✅ Change Password
1. Scroll to "Change Password" section
2. Enter current password
3. Enter new password (twice)
4. Click "Change Password"
5. Should show success message

---

## 🚨 Common Issues

### Issue 1: Still Getting 400
**Solution:** Hard refresh the page
- Windows/Linux: `Ctrl + Shift + R`
- Mac: `Cmd + Shift + R`

### Issue 2: CSRF Token Not Found
**Solution:** Make sure you're visiting the page (not just hitting API)
- Visit the `/register/` page first
- Django will set the CSRF cookie
- Then submit the form

### Issue 3: "Network Error"
**Solution:** Check browser console (F12 → Console tab)
- Look for JavaScript errors
- Check if fetch is blocked by CORS

---

## ✅ Success Checklist

- [ ] Visited registration page
- [ ] Form loads without errors
- [ ] DevTools Network tab open
- [ ] Filled in all fields
- [ ] Password meets requirements (8+ chars)
- [ ] Clicked "Create Account"
- [ ] Saw request in Network tab
- [ ] Request has CSRF token in headers
- [ ] Got 201 response code
- [ ] Redirected to profile page
- [ ] Can see user data on profile

---

## 📞 If It Still Doesn't Work

### Check Heroku Logs
```bash
heroku logs --tail -a koolclips | grep "POST /api/auth/register"
```

### Look for:
- Status code (should be 201, not 400)
- Error messages
- Stack traces

### Share This Info:
- Browser used (Chrome, Firefox, Safari, etc.)
- Request payload from Network tab
- Response body from Network tab
- Console errors (if any)
- Heroku log excerpt

---

## 🎉 Expected Result

**When working correctly:**

1. Fill form → Click submit
2. Loading spinner appears
3. Request sent with CSRF token
4. Server responds 201 Created
5. Tokens stored in localStorage
6. Green toast: "Account created successfully!"
7. Redirect to `/profile/` page
8. Profile shows your username and email

---

**Try it now!**  
👉 https://koolclips-ed69bc2e07f2.herokuapp.com/register/
