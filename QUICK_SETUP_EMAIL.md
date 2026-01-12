# Email Verification - Quick Setup (5 Minutes)

## Step 1: Run SQL in Supabase (1 minute)

Go to Supabase → SQL Editor → New Query → Paste & Run:

```sql
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS verification_token TEXT,
ADD COLUMN IF NOT EXISTS verification_token_expires TIMESTAMP WITH TIME ZONE;

CREATE INDEX IF NOT EXISTS idx_users_verification_token ON users(verification_token);
```

## Step 2: Get Your Titan Email Credentials (1 minute)

You'll need:
- Your Titan email address (e.g., noreply@yourdomain.com)
- Your Titan email password

## Step 3: Update .env File (1 minute)

Add these lines to your `.env`:

```env
# Titan Email Configuration
SMTP_HOST=smtp.titan.email
SMTP_PORT=587
SMTP_USER=your-email@yourdomain.com
SMTP_PASSWORD=your-titan-password

# Application URLs
FRONTEND_URL=https://your-frontend-url.com
BACKEND_URL=https://your-backend-url.com
```

## Step 4: Deploy (1 minute)

```bash
fly deploy
```

## Done! ✅

Test it:
1. Sign up a new user
2. Check email for verification link
3. Click link
4. Check email for "Access Granted" welcome message
5. Log in

---

**Full documentation:** `EMAIL_VERIFICATION_SETUP.md`

