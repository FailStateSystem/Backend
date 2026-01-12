# Titan Email SMTP Configuration

## Quick Setup for Titan Email

### 1. Your Titan Email Credentials

You'll need:
- **Email Address**: Your full Titan email (e.g., `noreply@yourdomain.com`)
- **Password**: Your Titan email password (regular password, not an app password)

### 2. Add to .env File

```env
# Titan Email Configuration
SMTP_HOST=smtp.titan.email
SMTP_PORT=587
SMTP_USER=noreply@yourdomain.com
SMTP_PASSWORD=your_titan_password

# Application URLs
FRONTEND_URL=https://yourdomain.com
BACKEND_URL=https://api.yourdomain.com
```

### 3. Titan SMTP Settings

| Setting | Value |
|---------|-------|
| **SMTP Host** | `smtp.titan.email` |
| **Port (STARTTLS)** | `587` ✅ Recommended |
| **Port (SSL/TLS)** | `465` |
| **Username** | Full email address |
| **Password** | Regular email password |
| **Authentication** | Required |
| **Encryption** | STARTTLS (port 587) or SSL (port 465) |

### 4. Recommended Email Address

Create a dedicated email for sending system emails:
- `noreply@yourdomain.com` ✅ Recommended
- `system@yourdomain.com`
- `notifications@yourdomain.com`

**Why?**
- Professional appearance
- Easier to track sent emails
- Keeps your personal inbox separate
- Better deliverability

### 5. Test Connection

After deploying, test your SMTP connection:

```python
import smtplib

try:
    server = smtplib.SMTP('smtp.titan.email', 587)
    server.starttls()
    server.login('your-email@yourdomain.com', 'your-password')
    print("✅ Titan SMTP connection successful!")
    server.quit()
except Exception as e:
    print(f"❌ Error: {e}")
```

### 6. Common Issues & Solutions

#### Issue: "Authentication failed"
**Solution:**
- Double-check email address (must be full address)
- Verify password is correct
- Ensure Titan account is active

#### Issue: "Connection timed out"
**Solution:**
- Check if port 587 is open
- Try port 465 instead (requires code change)
- Verify firewall isn't blocking SMTP

#### Issue: "Emails going to spam"
**Solution:**
- Set up SPF record: `v=spf1 include:titan.email ~all`
- Set up DKIM (configured in Titan dashboard)
- Set up DMARC record
- Use a "from" address on your domain
- Avoid spam trigger words

### 7. DNS Records (For Better Deliverability)

Add these DNS records in your domain registrar:

**SPF Record:**
```
Type: TXT
Name: @
Value: v=spf1 include:titan.email ~all
```

**DMARC Record:**
```
Type: TXT
Name: _dmarc
Value: v=DMARC1; p=none; rua=mailto:dmarc@yourdomain.com
```

**DKIM:**
Configured automatically by Titan (check your Titan dashboard)

### 8. Port 465 Configuration (If Needed)

If you need to use port 465 instead of 587, you'll need to modify `app/email_service.py`:

```python
# Change this line:
with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
    server.starttls()

# To this:
with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT) as server:
    # No starttls() needed for SSL
```

Then update your .env:
```env
SMTP_PORT=465
```

### 9. Email Sending Limits

**Titan Email Limits:**
- Depends on your Titan plan
- Most plans: 50-100 emails per hour
- Business plans: Higher limits
- Check your Titan dashboard for specific limits

**Monitor your usage:**
- Track sent emails in Titan dashboard
- Implement rate limiting if needed
- Use queuing for bulk emails

### 10. Testing Emails in Development

**Option A: Use your production Titan email**
- Works immediately
- Uses your real email quota
- Emails actually send

**Option B: Use Mailtrap for testing**
```env
SMTP_HOST=smtp.mailtrap.io
SMTP_PORT=587
SMTP_USER=your_mailtrap_username
SMTP_PASSWORD=your_mailtrap_password
```
- Catches all emails (nothing actually sends)
- Unlimited testing
- Preview emails before going live

### 11. Troubleshooting Checklist

- [ ] Email address is the full address (not just username)
- [ ] Password is correct (no extra spaces)
- [ ] Port 587 is being used
- [ ] SMTP_HOST is `smtp.titan.email` exactly
- [ ] Titan account is active and paid
- [ ] Domain is verified in Titan
- [ ] SPF/DKIM/DMARC records are set up
- [ ] Firewall allows outbound SMTP connections
- [ ] Backend can reach smtp.titan.email

### 12. Verification

After setup, sign up a test user and check:

1. ✅ Verification email arrives
2. ✅ Email is not in spam
3. ✅ Links work correctly
4. ✅ Welcome email arrives after verification
5. ✅ Emails have correct "from" address
6. ✅ Email design renders properly

### 13. Production Checklist

Before going live:

- [ ] Use `noreply@yourdomain.com` or similar
- [ ] Set up SPF, DKIM, DMARC records
- [ ] Test email delivery to Gmail, Outlook, Yahoo
- [ ] Check spam scores (use mail-tester.com)
- [ ] Set up email monitoring/logging
- [ ] Configure proper FRONTEND_URL and BACKEND_URL
- [ ] Test the complete signup → verify → welcome flow

---

## Example .env for Production

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_anon_key
SUPABASE_SERVICE_KEY=your_service_key
DATABASE_URL=postgresql://postgres:password@db.your-project.supabase.co:5432/postgres

# JWT
SECRET_KEY=your_generated_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Titan Email
SMTP_HOST=smtp.titan.email
SMTP_PORT=587
SMTP_USER=noreply@yourdomain.com
SMTP_PASSWORD=your_secure_password

# Application
ENVIRONMENT=production
DEBUG=False
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
FRONTEND_URL=https://yourdomain.com
BACKEND_URL=https://api.yourdomain.com
```

---

## Support

- **Titan Support**: https://support.titan.email
- **Titan SMTP Docs**: Check your Titan dashboard → Settings → SMTP
- **DNS Help**: Your domain registrar's documentation

---

✅ **Your Titan Email is ready for FailState!**

