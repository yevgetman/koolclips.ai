# 🔍 Browser Registration Debugging Guide

## 🚀 Latest Changes Deployed (v45)

### What Was Fixed:

1. **CSRF Cookie Settings** - Configured proper cookie settings for production
2. **@ensure_csrf_cookie** - Added decorator to registration/login views to force cookie creation  
3. **Better CSRF Token Detection** - Improved JavaScript to find token from form or cookie
4. **Console Logging** - Added debugging output to browser console
5. **Better Error Messages** - More detailed error reporting

---

## 🧪 Step-by-Step Testing

### Step 1: Clear Everything
1. Open browser
2. Clear cookies for `www.koolclips.ai`
3. Clear cache (Cmd+Shift+Delete or Ctrl+Shift+Delete)
4. Close all tabs for the site

### Step 2: Open DevTools FIRST
1. Open DevTools: **F12** (or Cmd+Option+I on Mac)
2. Go to **Console** tab
3. Keep it open

### Step 3: Visit Registration Page
1. Navigate to: https://www.koolclips.ai/register/
2. **DO NOT FILL FORM YET**
3. Check Console for any errors
4. Check Application/Storage tab → Cookies

### Step 4: Check for CSRF Cookie
**In DevTools → Application → Cookies → https://www.koolclips.ai**

Look for a cookie named: **`csrftoken`**

**✅ If you see it:**
- Value should be a long random string
- Domain should be `.koolclips.ai` or `www.koolclips.ai`
- Path should be `/`
- Secure should be checked (✓)
- HttpOnly should be **unchecked** (important!)

**❌ If you DON'T see it:**
- This is the problem
- Django isn't setting the cookie
- Take a screenshot and share it

### Step 5: Check Network Tab
1. Switch to **Network** tab in DevTools
2. Find the request for `/register/` page load
3. Click on it
4. Go to **Response Headers**
5. Look for: **`Set-Cookie: csrftoken=...`**

**Should see something like:**
```
Set-Cookie: csrftoken=abc123...; Path=/; SameSite=Lax; Secure
```

### Step 6: Fill and Submit Form
1. Fill in the registration form
2. Watch the Console tab
3. You should see: **"CSRF Token: Found"** or **"CSRF Token: Not found"**
4. Click "Create Account"

### Step 7: Check the API Request
**In Network tab:**
1. Find the POST request to `/api/auth/register/`
2. Click on it
3. Check **Request Headers**

**Should include:**
```
X-CSRFToken: [the token value]
Content-Type: application/json
```

### Step 8: Check Response
**Look at the Response:**

**✅ Success (201):**
```json
{
  "success": true,
  "message": "User registered successfully",
  ...
}
```

**❌ Failure (400):**
```json
{
  "detail": "CSRF Failed: CSRF token missing or incorrect."
}
```

---

## 🐛 Common Issues & Solutions

### Issue 1: No csrftoken Cookie

**Symptom:** Cookie not appearing in browser

**Possible Causes:**
- Cookie settings blocking
- Browser privacy mode too strict
- Cookie domain mismatch

**Solutions:**
1. Try in different browser
2. Disable browser extensions
3. Check browser privacy settings
4. Try without VPN/proxy

### Issue 2: CSRF Token Not Found in Console

**Symptom:** Console shows "CSRF Token: Not found"

**What to check:**
```javascript
// Open Console and run:
document.cookie
// Should see: csrftoken=...

document.querySelector('[name=csrfmiddlewaretoken]')
// Should return: <input ...>
```

### Issue 3: Still Getting 400 Error

**Symptom:** Request sends but returns 400

**Debug in Console:**
```javascript
// Check what was sent:
// Look at Console for: "Registration failed: 400 {detail: '...'}"
```

**The error detail will tell you exactly what's wrong**

### Issue 4: Cookie Domain Mismatch

**Check in DevTools → Application → Cookies:**
- Cookie Domain should be `.koolclips.ai` (with dot) or `www.koolclips.ai`
- If it's showing `.herokuapp.com`, that won't work
- If it's showing `localhost`, you're not on the right domain

---

## 📊 What to Look For

### ✅ Working Setup:
```
1. Visit /register/ → Sets csrftoken cookie
2. Console logs: "CSRF Token: Found"  
3. Form submit → Includes X-CSRFToken header
4. Response: 201 Created
5. Redirects to /profile/
```

### ❌ Broken Setup:
```
1. Visit /register/ → No cookie set OR
2. Console logs: "CSRF Token: Not found" OR
3. Form submit → Missing X-CSRFToken header OR
4. Response: 400 Bad Request
5. Error about CSRF
```

---

## 🔧 Manual Testing Commands

### Test 1: Check if page sets cookie
```bash
curl -I https://www.koolclips.ai/register/
# Look for: Set-Cookie: csrftoken=...
```

### Test 2: Test with explicit cookie
```bash
# First, get a cookie
COOKIE=$(curl -c - https://www.koolclips.ai/register/ 2>/dev/null | grep csrftoken | awk '{print $7}')
echo "Token: $COOKIE"

# Then use it
curl -X POST https://www.koolclips.ai/api/auth/register/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $COOKIE" \
  -H "Cookie: csrftoken=$COOKIE" \
  -d '{
    "username": "browsertest",
    "email": "browsertest@example.com",
    "password": "TestPass123!",
    "password_confirm": "TestPass123!"
  }' | jq .
```

---

## 📸 What to Screenshot

If it's still not working, please provide:

1. **Console Tab** - Any errors or logs
2. **Network Tab** - The `/api/auth/register/` request
   - Headers (both request and response)
   - Response body
3. **Application Tab** - Cookies section
4. **The error message** shown on the page

---

## 🎯 Expected Behavior After v45

1. Visit `/register/` → Django sets csrftoken cookie
2. Page loads with `{% csrf_token %}` in form
3. JavaScript finds token (from input OR cookie)
4. Console logs: "CSRF Token: Found"
5. Form submits with `X-CSRFToken` header
6. Server validates token against cookie
7. Returns 201 + JWT tokens
8. Redirects to profile

---

## 🚨 If Still Failing

### Quick Checklist:
- [ ] Hard refresh: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)
- [ ] Clear all koolclips.ai cookies
- [ ] Disable browser extensions
- [ ] Try incognito/private window
- [ ] Try different browser (Chrome vs Firefox)
- [ ] Check console for "CSRF Token: Found" or "Not found"
- [ ] Check Network tab for X-CSRFToken header
- [ ] Look at actual error message in response

### Report These:
1. Browser and version
2. Any console errors
3. Screenshot of Network request headers
4. Screenshot of Cookies in DevTools
5. The exact error message shown

---

## 📞 Version Info

**Current Version:** v45  
**Deployed:** November 25, 2025, 6:59 PM CST  

**Changes in v45:**
- Added CSRF_COOKIE_SECURE = True (production)
- Added CSRF_COOKIE_HTTPONLY = False (so JS can read)
- Added CSRF_COOKIE_SAMESITE = 'Lax'
- Added @ensure_csrf_cookie decorator to views
- Improved JavaScript token detection
- Added console.log debugging

**Test URL:** https://www.koolclips.ai/register/
