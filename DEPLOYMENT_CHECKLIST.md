# 🚀 Deployment Checklist - Penalty System & Email Notifications

## ✅ What's Been Implemented

1. **OpenAI Timeout Fix** - Images downloaded as base64 to prevent timeouts
2. **Progressive Penalty System** - 1st warning → 5th suspension
3. **Email Notifications** - Success and rejection emails
4. **Rejection Tracking** - Frontend can display rejection reasons
5. **Database Schema** - New tables and functions for enforcement

---

## 📋 Deployment Steps

### Step 1: Run SQL Migration ⏳
**File:** `ADD_REJECTION_TRACKING.sql`

1. Open Supabase Dashboard
2. Go to SQL Editor
3. Copy contents of `ADD_REJECTION_TRACKING.sql`
4. Run the script
5. Verify tables and function created:
   ```sql
   -- Check tables exist
   SELECT * FROM user_penalties LIMIT 1;
   SELECT rejection_reason FROM issues LIMIT 1;
   
   -- Check function exists
   SELECT proname FROM pg_proc WHERE proname = 'apply_fake_submission_penalty';
   ```

**Status:** ⏳ **REQUIRED - Run this first!**

---

### Step 2: Deploy Code to Render 🚀

Code is ready to deploy. When you push to git, Render will automatically redeploy.

```bash
git add .
git commit -m "feat: Add penalty system, email notifications, fix OpenAI timeout"
git push origin main
```

**Watch Render logs for:**
- ✅ Build successful
- ✅ `✅ Downloaded and encoded image` (confirms timeout fix)
- ✅ `✅ AI verification successful`
- ✅ `⚠️ Penalty applied` (when testing fake issues)
- ✅ `📧 Sent rejection email` (confirms emails working)

**Status:** ⏳ **Ready when Step 1 complete**

---

### Step 3: Test the System 🧪

#### Test 1: Submit Genuine Issue
**Expected Result:**
- ✅ Issue verified and published
- ✅ +25 points awarded
- ✅ Verification success email received
- ✅ Issue appears on public map

---

#### Test 2: Submit Fake Issue (1st Rejection)
**Expected Result:**
- ❌ Issue rejected by AI
- ⚠️ First warning email received
- 📊 0 points deducted
- 📊 `rejection_count = 1` in database
- ❌ Issue NOT on public map
- ✅ `rejection_reason` visible in `/api/issues/my-issues`

---

#### Test 3: Submit Fake Issue (3rd Rejection)
**Expected Result:**
- ❌ Issue rejected by AI
- ⚠️ Penalty email received: "-10 POINTS"
- 📊 10 points deducted from account
- 📊 `rejection_count = 3` in database
- 📊 Entry in `user_penalties` table

---

#### Test 4: Submit Fake Issue (5th Rejection)
**Expected Result:**
- ❌ Issue rejected by AI
- 🚫 Suspension email received: "ACCOUNT SUSPENDED"
- 📊 50 points deducted
- 📊 `account_status = 'suspended'` in users table
- 🚫 User **cannot submit new issues** (test this!)

---

### Step 4: Verify Email Delivery ✉️

Check your email inbox for:
1. ✅ **Verification Success** email (green, positive tone)
2. ❌ **Rejection Notification** email (red, warning tone with penalties explained)

**Email should include:**
- FailState branding
- Issue details
- Rejection reason (if rejected)
- Penalty details (warning/points/suspension)
- Progressive enforcement policy explained
- Platform guidelines

**If emails not received:**
- Check Render logs for email errors
- Verify `RESEND_API_KEY` is set in Render environment variables
- Check spam folder
- Verify domain is verified in Resend dashboard

---

### Step 5: Monitor Database 📊

Run these queries to verify system is working:

#### Check Penalty Summary
```sql
SELECT * FROM penalty_summary
ORDER BY total_rejections DESC
LIMIT 10;
```

#### Check Recent Rejections
```sql
SELECT 
    i.id,
    i.description,
    i.rejection_reason,
    i.rejection_count,
    i.processed_at,
    u.email,
    u.username
FROM issues i
JOIN users u ON i.reported_by = u.id
WHERE i.verification_status = 'rejected'
ORDER BY i.processed_at DESC
LIMIT 10;
```

#### Check Penalties Applied
```sql
SELECT 
    up.id,
    u.email,
    u.username,
    up.penalty_type,
    up.points_deducted,
    up.rejection_count_at_time,
    up.created_at
FROM user_penalties up
JOIN users u ON up.user_id = u.id
ORDER BY up.created_at DESC
LIMIT 10;
```

---

## 🎯 Success Criteria

System is working correctly when:

- [✅] Genuine issues get verified and published
- [✅] Fake issues get rejected
- [✅] Rejection reason visible in API response
- [✅] 1st & 2nd rejections send warning emails
- [✅] 3rd rejection deducts 10 points
- [✅] 5th rejection suspends account
- [✅] Emails are delivered successfully
- [✅] No OpenAI timeout errors in logs
- [✅] Database tables properly populated

---

## 🚨 Troubleshooting

### Issue: OpenAI still timing out
**Solution:** Check Render logs for "Downloaded and encoded image" message. If not appearing, the image download might be failing. Check Supabase storage URL is accessible.

### Issue: Emails not sending
**Solution:**
1. Check `RESEND_API_KEY` is set in Render
2. Check domain is verified in Resend dashboard
3. Check Render logs for email errors
4. Try sending a test email manually

### Issue: Penalties not being applied
**Solution:**
1. Verify `ADD_REJECTION_TRACKING.sql` was run successfully
2. Check `apply_fake_submission_penalty()` function exists in database
3. Check Render logs for "Penalty applied" messages
4. Verify `user_penalties` table exists

### Issue: Rejection reason not showing in API
**Solution:**
1. Verify `rejection_reason` column exists in `issues` table
2. Redeploy backend to pick up model changes
3. Check API response includes the field

---

## 📝 Quick Reference

### Progressive Enforcement Policy
| Rejection # | Penalty | Points | Status |
|-------------|---------|--------|--------|
| 1st | First Warning | 0 | Active |
| 2nd | Second Warning | 0 | Active |
| 3rd | Points Deduction | -10 | Active |
| 4th | Severe Penalty | -25 | Active |
| 5th+ | Account Suspended | -50 | Suspended |

### Rejection Reasons
- `nsfw_content_detected` - NSFW/inappropriate content
- `screenshot_or_meme_detected` - Screenshot or meme (not real photo)
- `not_genuine_civic_issue` - Not a real civic infrastructure problem

### API Endpoints
- `GET /api/issues/my-issues` - Returns all user's issues including rejected ones with `rejection_reason`
- `GET /api/issues/{id}/verification-status` - Check verification status

---

## ✅ Final Checklist

Before marking as complete, verify:

- [ ] `ADD_REJECTION_TRACKING.sql` executed in Supabase
- [ ] Code deployed to Render successfully
- [ ] No errors in Render logs
- [ ] Genuine issue can be submitted and verified
- [ ] Fake issue gets rejected (test 1st, 3rd, 5th rejection)
- [ ] Rejection reason shows in API response
- [ ] Success email received for verified issue
- [ ] Rejection email received for fake issue
- [ ] Points deducted correctly for 3rd+ rejection
- [ ] Account suspended after 5th rejection
- [ ] Database tables populated correctly
- [ ] Frontend displays rejection reasons (if implemented)

---

**Status:** ⏳ **READY TO DEPLOY**

**Next Action:** Run `ADD_REJECTION_TRACKING.sql` in Supabase SQL Editor

---

**Last Updated:** January 18, 2026  
**See Also:** `PENALTY_SYSTEM_IMPLEMENTATION.md` for detailed documentation

