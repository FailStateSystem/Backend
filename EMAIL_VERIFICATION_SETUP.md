# Email Verification Setup Guide

## Overview

FailState now includes a complete email verification flow:

1. **User signs up** → Account created (unverified)
2. **Verification email sent** → User receives email with verification link
3. **User clicks link** → Email verified
4. **Welcome email sent** → User receives the custom "Access Granted" email
5. **User can log in** → Full access to the platform

---

## 🚀 Quick Setup

### Step 1: Update Database Schema

Run this SQL in your Supabase SQL Editor:

```sql
-- Add email verification fields
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS verification_token TEXT,
ADD COLUMN IF NOT EXISTS verification_token_expires TIMESTAMP WITH TIME ZONE;

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_verification_token ON users(verification_token);
```

Or use the provided file: `ADD_EMAIL_VERIFICATION.sql`

### Step 2: Configure SMTP (Email Sending)

Add these to your `.env` file:

```env
# Titan Email Configuration
SMTP_HOST=smtp.titan.email
SMTP_PORT=587
SMTP_USER=your-email@yourdomain.com
SMTP_PASSWORD=your-titan-email-password

# Application URLs
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000
```

**Titan Email Settings:**
- Host: `smtp.titan.email`
- Port: `587` (STARTTLS) or `465` (SSL/TLS)
- Username: Your full Titan email address
- Password: Your Titan email password (not an app password)

**Note:** If using port 465, you may need to modify the email service to use `SMTP_SSL` instead of `SMTP` with `starttls()`.

### Step 3: Rebuild and Deploy

```bash
# Rebuild Docker container
fly deploy

# Or if running locally
docker-compose down
docker-compose up --build -d
```

---

## 📧 Email Flow

### 1. Signup (POST /api/auth/signup)

**Request:**
```json
{
  "email": "user@example.com",
  "username": "johndoe",
  "password": "securepassword123"
}
```

**Response:**
```json
{
  "message": "Account created successfully. Please check your email to verify your account.",
  "email": "user@example.com",
  "username": "johndoe"
}
```

**What happens:**
- User account created (email_verified = false)
- Verification token generated (expires in 24 hours)
- **Verification email sent** with link

### 2. User Clicks Verification Link

**Link format:**
```
http://localhost:8000/api/auth/verify-email?token=abc123xyz...
```

**What happens:**
- Token validated
- User marked as verified (email_verified = true)
- Token cleared from database
- **Welcome email sent** with your custom "Access Granted" message
- User redirected to frontend login page

**Response:**
```json
{
  "message": "Email verified successfully! Welcome to FailState. Check your email for next steps.",
  "redirect_url": "http://localhost:3000/login?verified=true"
}
```

### 3. Login (POST /api/auth/login)

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**If email not verified:**
```json
{
  "detail": "Email not verified. Please check your email for the verification link."
}
```

**If email verified:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 4. Resend Verification (POST /api/auth/resend-verification)

If user didn't receive the email:

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response:**
```json
{
  "message": "Verification email sent. Please check your inbox."
}
```

---

## 📨 Email Templates

### Verification Email

**Subject:** `Verify Your Email — FailState System`

**Content:**
- Dark themed, matches your FailState aesthetic
- Clear "VERIFY EMAIL" button
- Fallback link for manual copy-paste
- 24-hour expiration notice

### Welcome Email (After Verification)

**Subject:** `Access Granted — The System Has Logged You`

**Content:**
- Your custom "Access Granted" message
- Full manifesto text
- "ENTER SYSTEM" button linking to login
- Dark themed with glassmorphism design

---

## 🔧 API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/auth/signup` | POST | No | Create account & send verification |
| `/api/auth/verify-email` | GET | No | Verify email via token |
| `/api/auth/resend-verification` | POST | No | Resend verification email |
| `/api/auth/login` | POST | No | Login (requires verified email) |

---

## 🧪 Testing

### Test the Flow Locally

1. **Sign up a new user:**
```bash
curl -X POST http://localhost:8000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "username": "testuser",
    "password": "password123"
  }'
```

2. **Check your email** for the verification link

3. **Click the link** or visit it manually:
```
http://localhost:8000/api/auth/verify-email?token=YOUR_TOKEN
```

4. **Check your email again** for the welcome message

5. **Log in:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123"
  }'
```

### Test Without SMTP (Development)

If SMTP is not configured:
- Emails won't actually send
- Verification tokens are still generated
- Check server logs for the verification link
- You can manually call the verify endpoint

---

## 🔒 Security Features

✅ **Token Expiration**: Verification links expire after 24 hours  
✅ **One-time Use**: Tokens are cleared after verification  
✅ **Secure Tokens**: Uses `secrets.token_urlsafe(32)` (cryptographically secure)  
✅ **No Email Enumeration**: Resend endpoint doesn't reveal if email exists  
✅ **Password Hashing**: bcrypt with salt  
✅ **Login Protection**: Cannot log in without verified email

---

## 🌐 Production Configuration

### Update URLs in .env

```env
# Production URLs
FRONTEND_URL=https://failstate.app
BACKEND_URL=https://api.failstate.app

# Titan Email (Your Current Setup)
SMTP_HOST=smtp.titan.email
SMTP_PORT=587
SMTP_USER=noreply@failstate.app
SMTP_PASSWORD=your_titan_password
```

### Recommended SMTP Services

**Currently Using:**
- **Titan Email** - Professional email hosting, reliable delivery

**Other Options:**
- **SendGrid** - 100 emails/day free
- **Mailgun** - 5,000 emails/month free
- **AWS SES** - 62,000 emails/month free (if on EC2)
- **Postmark** - 100 emails/month free
- **Gmail** - Easy setup, 500 emails/day (requires App Password)

---

## 📊 Database Schema

### New Columns in `users` Table

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| `email_verified` | BOOLEAN | FALSE | Whether email is verified |
| `verification_token` | TEXT | NULL | Token for email verification |
| `verification_token_expires` | TIMESTAMP | NULL | When token expires |

---

## 🐛 Troubleshooting

### Emails Not Sending

**Check logs:**
```bash
# Look for email service logs
docker logs <container_name> | grep "email"
```

**Common issues:**
- ❌ SMTP credentials incorrect
- ❌ Wrong email/password for Titan
- ❌ Firewall blocking port 587
- ❌ Domain not verified (if using custom domain)

**Test Titan SMTP connection:**
```python
import smtplib
server = smtplib.SMTP('smtp.titan.email', 587)
server.starttls()
server.login('your-email@yourdomain.com', 'your-password')
print("Titan SMTP works!")
server.quit()
```

**Titan Email Specific:**
- Use your full email address as SMTP_USER
- Use your regular email password (not an app password)
- Port 587 with STARTTLS (recommended) or Port 465 with SSL
- Ensure your Titan account is active and in good standing

### Verification Link Not Working

- Check token hasn't expired (24 hours)
- Verify `BACKEND_URL` is correct in .env
- Check database for `verification_token` value
- Look at server logs for errors

### User Can't Log In

- Verify `email_verified` is TRUE in database
- Check if verification email was sent
- Try resending verification email
- Check spam folder

---

## 🎨 Customizing Emails

### Edit Email Templates

Templates are in `app/email_service.py`:

1. **Verification Email**: `send_verification_email()` function
2. **Welcome Email**: `send_welcome_email()` function

### Change Email Styling

Modify the inline CSS in the HTML templates. Current theme:
- Background: `#07090d` (dark)
- Text: `#c9ccd6` (light gray)
- Accent: `#78a0ff` (blue glow)
- Glassmorphism panels with backdrop blur

---

## 📈 Monitoring

### Check Verification Status

```sql
-- See all unverified users
SELECT username, email, created_at, email_verified
FROM users
WHERE email_verified = FALSE
ORDER BY created_at DESC;

-- See expired tokens
SELECT username, email, verification_token_expires
FROM users
WHERE email_verified = FALSE
AND verification_token_expires < NOW();
```

### Email Metrics

Monitor in your logs:
- Verification emails sent
- Welcome emails sent
- Failed email attempts
- Verification completion rate

---

## ✅ Checklist

Before going to production:

- [ ] Database schema updated with verification columns
- [ ] SMTP credentials configured in `.env`
- [ ] `FRONTEND_URL` and `BACKEND_URL` set correctly
- [ ] Tested signup → verification → welcome flow
- [ ] Tested resend verification
- [ ] Tested login with unverified email (should fail)
- [ ] Tested login with verified email (should work)
- [ ] Email templates reviewed and customized
- [ ] Production SMTP service configured
- [ ] Monitoring/logging set up

---

## 🎉 You're Done!

Your FailState backend now has:
- ✅ Email verification on signup
- ✅ Custom verification emails
- ✅ Custom "Access Granted" welcome emails
- ✅ Secure token-based verification
- ✅ 24-hour token expiration
- ✅ Resend verification capability
- ✅ Login protection (verified emails only)

**The system has logged you.** 🔒

