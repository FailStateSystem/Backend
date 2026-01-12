# Admin Quick Guide - Processing Pending Issues

## 🚨 When to Use This

Use these commands when:
- ✅ OpenAI credits have been restored
- ✅ OpenAI service is back online after outage
- ✅ You see issues stuck in "pending" status
- ✅ Users report their issues aren't appearing in the feed

---

## 📊 Step 1: Check How Many Issues Are Pending

```bash
curl https://backend-13ck.onrender.com/api/issues/admin/stats \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Example Response:**
```json
{
  "verification_stats": {
    "pending": 23,
    "verified": 156,
    "rejected": 8,
    "failed": 0,
    "total": 187
  },
  "message": "Use POST /api/issues/admin/process-pending to process pending issues"
}
```

**What to look for:**
- `pending: 23` → You have 23 issues waiting for AI verification
- `failed: 0` → Good, no failed verifications

---

## ⚡ Step 2: Trigger Batch Processing

```bash
curl -X POST "https://backend-13ck.onrender.com/api/issues/admin/process-pending?batch_size=50" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Parameters:**
- `batch_size` (optional, default=50, max=200): How many issues to process

**Example Response:**
```json
{
  "message": "Successfully queued 23 issues for verification",
  "pending_count": 23,
  "note": "Processing will happen in background. Check logs or verification status."
}
```

---

## 🔍 Step 3: Monitor Progress

### **Option A: Check Render Logs**

1. Go to https://dashboard.render.com
2. Click on your backend service
3. Click "Logs" tab
4. Look for:

```
INFO: 🔄 Processing issue abc-123
INFO: Sending issue abc-123 to OpenAI for verification
INFO: ✅ Issue abc-123 verified as GENUINE
INFO: ✅ Created verified issue for abc-123
INFO: ✅ Awarded points to user xyz-456
```

### **Option B: Check Stats Again**

Wait 30 seconds, then run Step 1 again. You should see:
- `pending` count decreasing
- `verified` or `rejected` count increasing

---

## 🔄 Complete Workflow Example

### **Scenario: OpenAI Quota Restored**

```bash
# 1. Check current status
curl https://backend-13ck.onrender.com/api/issues/admin/stats \
  -H "Authorization: Bearer $TOKEN"

# Response: pending: 15

# 2. Top up OpenAI credits at https://platform.openai.com/account/billing

# 3. Trigger processing
curl -X POST "https://backend-13ck.onrender.com/api/issues/admin/process-pending?batch_size=50" \
  -H "Authorization: Bearer $TOKEN"

# Response: Successfully queued 15 issues

# 4. Wait 30-60 seconds

# 5. Check stats again
curl https://backend-13ck.onrender.com/api/issues/admin/stats \
  -H "Authorization: Bearer $TOKEN"

# Response: pending: 0, verified: increased by ~15

# ✅ Done! Issues now visible in public feed
```

---

## 🎯 Quick Commands Cheat Sheet

### **Get Stats:**
```bash
curl https://backend-13ck.onrender.com/api/issues/admin/stats \
  -H "Authorization: Bearer $TOKEN"
```

### **Process All Pending (Default 50):**
```bash
curl -X POST https://backend-13ck.onrender.com/api/issues/admin/process-pending \
  -H "Authorization: Bearer $TOKEN"
```

### **Process Custom Batch Size:**
```bash
curl -X POST "https://backend-13ck.onrender.com/api/issues/admin/process-pending?batch_size=100" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 🔑 Getting Your JWT Token

### **Option 1: From Browser (Easiest)**

1. Open your frontend app
2. Log in with admin account
3. Open browser DevTools (F12)
4. Go to Console tab
5. Type: `localStorage.getItem('token')`
6. Copy the token value

### **Option 2: API Login**

```bash
# Login
curl -X POST https://backend-13ck.onrender.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@failstate.in",
    "password": "your-password"
  }'

# Response includes:
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}

# Use the access_token value
```

---

## 🚨 Common Issues

### **Issue: "No pending issues to process"**

**Meaning:** All issues are already verified or rejected.

**Action:** Nothing to do! ✅

---

### **Issue: "Quota error" still appearing in logs**

**Possible Causes:**
1. OpenAI credits not yet reflected
2. Using wrong API key
3. Billing issue

**Actions:**
1. Check https://platform.openai.com/account/usage
2. Verify credits are available
3. Check API key is correct in Render environment variables

---

### **Issue: Issues still not appearing in feed after processing**

**Possible Causes:**
1. Issues were verified but rejected (low quality, fake, etc.)
2. Processing still in progress
3. OpenAI still failing

**Actions:**
1. Check stats - are they moving from pending to rejected?
2. Check Render logs for rejection reasons
3. Look for specific issue in audit log

---

## 📊 Database Queries (Advanced)

If you need to check the database directly in Supabase:

### **See Pending Issues:**
```sql
SELECT id, title, description, verification_status, reported_at
FROM issues
WHERE verification_status = 'pending'
ORDER BY reported_at DESC
LIMIT 20;
```

### **See Recent Verifications:**
```sql
SELECT 
    i.id,
    i.title,
    i.verification_status,
    i.reported_at,
    i.processed_at,
    EXTRACT(EPOCH FROM (i.processed_at - i.reported_at)) as processing_seconds
FROM issues i
WHERE i.processed_at IS NOT NULL
ORDER BY i.processed_at DESC
LIMIT 20;
```

### **See Rejection Reasons:**
```sql
SELECT 
    ir.original_issue_id,
    ir.rejection_reason,
    ir.ai_reasoning,
    ir.created_at
FROM issues_rejected ir
ORDER BY ir.created_at DESC
LIMIT 10;
```

### **Verification Success Rate:**
```sql
SELECT 
    verification_status,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 2) as percentage
FROM issues
WHERE verification_status IN ('verified', 'rejected')
GROUP BY verification_status;
```

---

## 💡 Best Practices

### **1. Regular Monitoring**
Check stats once a day:
```bash
# Save this as a bookmark or alias
curl https://backend-13ck.onrender.com/api/issues/admin/stats \
  -H "Authorization: Bearer $TOKEN"
```

### **2. Batch Processing**
- Don't process more than 100 at once (API rate limits)
- If you have 200 pending, run twice with `batch_size=100`

### **3. Off-Peak Processing**
- Process during low traffic hours
- Reduces server load
- Faster processing

### **4. Monitor OpenAI Usage**
- Set up billing alerts: https://platform.openai.com/account/billing/limits
- Track spending: https://platform.openai.com/account/usage
- Each verification costs ~$0.01-0.03 (GPT-4o with image)

---

## 📞 Emergency Contacts

### **If Processing Fails:**

1. **Check Render Logs:**
   - https://dashboard.render.com → Your Service → Logs

2. **Check OpenAI Status:**
   - https://status.openai.com

3. **Check Supabase Status:**
   - https://status.supabase.com

4. **Manual Override (Last Resort):**
   - In Supabase SQL Editor, manually move issue to verified:
   ```sql
   -- Only use if absolutely necessary!
   UPDATE issues 
   SET verification_status = 'verified', processed_at = NOW()
   WHERE id = 'ISSUE_ID';
   
   -- Then manually create verified issue entry
   INSERT INTO issues_verified (
       original_issue_id, 
       is_genuine, 
       ai_confidence_score,
       severity,
       generated_title,
       generated_description,
       public_impact,
       tags,
       ai_reasoning,
       image_url,
       location_name,
       location_lat,
       location_lng,
       reported_by
   )
   SELECT 
       id,
       true,
       0.5,
       'moderate',
       title,
       description,
       'Manually verified issue',
       ARRAY['manual-review'],
       'Manually verified by admin',
       image_url,
       location_name,
       location_lat,
       location_lng,
       reported_by
   FROM issues
   WHERE id = 'ISSUE_ID';
   ```

---

## ✅ Success Checklist

After running batch processing:

- [ ] Pending count decreased to 0
- [ ] Verified count increased
- [ ] No errors in Render logs
- [ ] Issues appear in public feed (frontend)
- [ ] Users received rewards
- [ ] OpenAI usage dashboard shows API calls

---

**Keep this guide handy!** Bookmark this page for quick reference when you need to process pending issues. 🚀

