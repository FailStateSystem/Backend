# Quick Test Guide - AI Fallback Filtering

## 🎯 What to Test

Your backend now has **two-layer content protection**:
- **Layer 1:** Pre-ingestion filters (may be unavailable on some servers)
- **Layer 2:** AI verification (always available, acts as fallback)

---

## ✅ Quick Tests (5 minutes)

### Test 1: Normal Submission (Should Work)
```bash
# Use your frontend or curl
curl -X POST https://backend-13ck.onrender.com/api/issues \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "description=Broken streetlight on Main St" \
  -F "category=infrastructure" \
  -F "location_name=Main St" \
  -F "location_lat=40.7128" \
  -F "location_lng=-74.0060" \
  -F "image=@pothole.jpg"

# Expected: 201 Created
# Check logs for: "✅ All pre-ingestion filters passed"
```

---

### Test 2: Check Logs for Filter Availability
```bash
# SSH into your Render server or check Render logs
# Look for these lines:

# If NudeNet unavailable:
"⚠️ Failed to initialize NSFWDetector: ..."
"NSFW detection will be disabled. This is OK for testing."

# If Tesseract unavailable:
"⚠️ Tesseract not available - OCR detection disabled"

# These are EXPECTED and OK - AI will handle these checks
```

---

### Test 3: Monitor Verification Process
```bash
# After submitting an issue, check its status
curl https://backend-13ck.onrender.com/api/issues/YOUR_ISSUE_ID/verification-status \
  -H "Authorization: Bearer YOUR_TOKEN"

# Response:
{
  "issue_id": "abc-123",
  "verification_status": "pending",  # Processing
  "processed_at": null
}

# Wait 5-10 seconds, check again:
{
  "issue_id": "abc-123",
  "verification_status": "verified",  # Success!
  "processed_at": "2026-01-17T12:34:56Z"
}
```

---

### Test 4: Check Database Tables
```sql
-- Check verified issues
SELECT 
    id,
    generated_title,
    ai_confidence_score,
    is_genuine,
    severity,
    created_at
FROM issues_verified
ORDER BY created_at DESC
LIMIT 5;

-- Check rejected issues (if any)
SELECT 
    id,
    rejection_reason,
    ai_reasoning,
    confidence_score,
    created_at
FROM issues_rejected
ORDER BY created_at DESC
LIMIT 5;

-- Check verification status in original issues table
SELECT 
    id,
    description,
    verification_status,
    retry_count,
    processed_at
FROM issues
WHERE verification_status IN ('verified', 'rejected', 'pending')
ORDER BY created_at DESC
LIMIT 10;
```

---

## 🧪 Advanced Tests (Optional)

### Test 5: Duplicate Detection
```bash
# Submit the same image twice with the same user account

# First submission
curl -X POST ... -F "image=@test.jpg"  # Should work

# Second submission (same image)
curl -X POST ... -F "image=@test.jpg"  # Should get 400 error

# Expected response:
{
  "detail": "You have already uploaded this image"
}
```

---

### Test 6: Rate Limit
```bash
# Submit 11 issues within 1 hour with the same account

# Issues 1-10: Should all succeed (201 Created)
# Issue 11: Should fail with rate limit

# Expected response on 11th attempt:
{
  "detail": "Rate limit exceeded. You can submit 10 issues per hour."
}
# Response headers:
# Retry-After: 3540 (seconds until retry allowed)
```

---

### Test 7: AI Fallback - NSFW Detection
**Only test this if NudeNet is unavailable (check logs first)**

```bash
# Submit an image that would be considered inappropriate
# (Use a mildly suggestive image, not extreme content)

# Expected flow:
# 1. 201 Created (pre-ingestion skips NSFW check)
# 2. Image uploaded to Supabase
# 3. AI verification runs
# 4. AI detects NSFW content
# 5. Issue moved to issues_rejected

# Check in database:
SELECT * FROM issues_rejected 
WHERE rejection_reason = 'nsfw_content_detected'
ORDER BY created_at DESC LIMIT 1;

# Verify it's NOT in issues_verified
```

---

### Test 8: AI Fallback - Screenshot Detection
**Only test this if Tesseract is unavailable**

```bash
# Submit a screenshot of a phone/computer
# (e.g., screenshot of a tweet, Instagram post, etc.)

# Expected flow:
# 1. 201 Created (pre-ingestion skips OCR check)
# 2. Image uploaded to Supabase
# 3. AI verification runs
# 4. AI detects screenshot
# 5. Issue moved to issues_rejected

# Check in database:
SELECT * FROM issues_rejected 
WHERE rejection_reason = 'screenshot_or_meme_detected'
ORDER BY created_at DESC LIMIT 1;
```

---

## 📊 Monitoring Queries

### Query 1: Rejection Breakdown
```sql
SELECT 
    rejection_reason,
    COUNT(*) as count,
    ROUND(AVG(confidence_score), 2) as avg_confidence
FROM issues_rejected
GROUP BY rejection_reason
ORDER BY count DESC;
```

**Expected output:**
```
rejection_reason                | count | avg_confidence
--------------------------------|-------|---------------
not_genuine_civic_issue         | 5     | 0.85
screenshot_or_meme_detected     | 2     | 0.90
nsfw_content_detected           | 1     | 0.95
```

---

### Query 2: Filter Stats (Last 24 Hours)
```sql
SELECT 
    filter_name,
    action,
    COUNT(*) as count
FROM filtering_audit_logs
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY filter_name, action
ORDER BY count DESC;
```

**Expected output:**
```
filter_name    | action  | count
---------------|---------|------
nsfw           | pass    | 25
duplicate      | pass    | 25
ocr            | pass    | 23
garbage        | pass    | 25
exif           | pass    | 25
duplicate      | block   | 2
```

---

### Query 3: AI Fallback Effectiveness
```sql
-- How many issues did AI catch that filters missed?
SELECT 
    DATE(created_at) as date,
    COUNT(*) as ai_caught_violations
FROM issues_rejected
WHERE rejection_reason IN ('nsfw_content_detected', 'screenshot_or_meme_detected')
AND created_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

---

## 🚨 What to Look For

### ✅ Good Signs
- Most submissions reach `issues_verified` table
- Rejection rate < 5%
- AI confidence scores > 0.7
- Logs show filters running smoothly
- No NSFW content in public issues

### ⚠️ Warning Signs
- Rejection rate > 10% (filters too strict)
- Many issues stuck in "pending" (AI quota exhausted)
- High retry counts (AI service issues)
- Users complaining about false rejections

### 🚨 Critical Issues
- NSFW content appearing publicly (Layer 2 failed)
- Backend crashes on filter initialization
- All submissions failing (filters too strict)

---

## 📝 Testing Checklist

Use this checklist to track your testing progress:

- [ ] Normal submission works (pothole photo)
- [ ] Check logs for filter availability warnings
- [ ] Monitor verification status endpoint
- [ ] Verify issues appear in `issues_verified`
- [ ] Check reward points awarded
- [ ] Test duplicate submission (should block)
- [ ] Test rate limit (11 submissions)
- [ ] Monitor `filtering_audit_logs` table
- [ ] Monitor `abuse_logs` table
- [ ] Check rejection breakdown query
- [ ] (Optional) Test AI NSFW fallback
- [ ] (Optional) Test AI screenshot fallback
- [ ] Verify no NSFW content publicly visible

---

## 🎯 Success Criteria

Your system is working correctly if:

1. ✅ Normal civic issues get verified and published
2. ✅ Inappropriate content gets rejected (by either layer)
3. ✅ No NSFW content appears publicly
4. ✅ Duplicate submissions blocked
5. ✅ Rate limits enforced
6. ✅ Trust scores updating correctly
7. ✅ AI fallback catches violations when Layer 1 unavailable

---

## 💡 Tips

1. **Don't test NSFW on production** - Use staging/dev environment
2. **Start with normal submissions** - Ensure basic flow works
3. **Check logs frequently** - They tell you what's happening
4. **Use SQL queries** - Fastest way to verify data
5. **Be patient with AI** - Verification takes 5-10 seconds

---

## 📞 Need Help?

- Check `AI_FALLBACK_DEPLOYMENT_COMPLETE.md` for detailed documentation
- Check `TROUBLESHOOTING.md` if something's not working
- Review Render logs for error messages
- Query database tables for verification status

---

**Ready to test? Start with Test 1-4 above!** 🚀

