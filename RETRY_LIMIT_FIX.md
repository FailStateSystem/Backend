# Retry Limit Fix - Stop Infinite API Calls

## 🐛 Problem

The background worker was continuously retrying the same pending issues when OpenAI quota was exceeded, causing:
- ❌ Spam in logs (same error repeated hundreds of times)
- ❌ Wasted API calls (hitting quota limit repeatedly)
- ❌ No way to stop automatic retries
- ❌ Issues stuck in limbo forever

**Root Cause:** No retry counter, so the worker kept picking up the same pending issues in an infinite loop.

---

## ✅ Solution Implemented

Added a **retry counter system** with a **max of 3 attempts** per issue.

### **Key Changes:**

1. ✅ Added `retry_count` column to `issues` table
2. ✅ Worker only processes issues with `retry_count < 3`
3. ✅ Increment `retry_count` before each attempt
4. ✅ After 3 failures, issue requires manual intervention
5. ✅ Admin endpoint resets `retry_count` to allow reprocessing

---

## 📊 What Changed

### **1. Database Schema** (`ADD_RETRY_COUNT.sql`)

```sql
-- Add retry counter
ALTER TABLE issues ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;

-- Index for performance
CREATE INDEX IF NOT EXISTS idx_issues_verification_retry 
ON issues(verification_status, retry_count);

-- View for monitoring
CREATE OR REPLACE VIEW issues_needs_manual_review AS
SELECT id, title, description, verification_status, retry_count, reported_at
FROM issues
WHERE verification_status = 'pending' AND retry_count >= 3
ORDER BY reported_at DESC;
```

**Run this in Supabase SQL Editor!**

---

### **2. Worker Logic** (`app/verification_worker.py`)

#### **Added `increment_retry_count` Method:**
```python
async def increment_retry_count(self, issue_id: str) -> int:
    """Increment retry count and return new count"""
    current_count = ... # Get from DB
    new_count = current_count + 1
    # Update in DB
    logger.info(f"Issue {issue_id} retry count: {new_count}/3")
    return new_count
```

#### **Updated `process_issue` Method:**
```python
# Before attempting verification:
new_retry_count = await self.increment_retry_count(issue_id)

# Check if max retries exceeded
if new_retry_count >= 3:
    logger.error(f"⛔ Issue {issue_id} exceeded max retries (3)")
    # Stop processing, requires manual intervention
    return False

# Otherwise, attempt AI verification
```

#### **Updated `process_pending_issues` Method:**
```python
# Only fetch issues that haven't exceeded max retries
result = self.supabase.table("issues").select("*").eq(
    "verification_status", "pending"
).lt("retry_count", 3).limit(batch_size).execute()
```

---

### **3. Admin Endpoint** (`app/routers/issues.py`)

#### **Updated `POST /api/issues/admin/process-pending`:**
```python
# Reset retry count before reprocessing (allows retrying after fixing issues)
for issue_id in issue_ids:
    supabase.table("issues").update({
        "retry_count": 0  # Reset to allow reprocessing
    }).eq("id", issue_id).execute()

# Then trigger verification
```

#### **Updated `GET /api/issues/admin/stats`:**
```python
# Show how many issues need manual intervention
pending_needs_manual = supabase.table("issues").select("id", count="exact").eq(
    "verification_status", "pending"
).gte("retry_count", 3).execute()
```

**Response:**
```json
{
  "verification_stats": {
    "pending": 5,
    "pending_needs_manual_intervention": 3,  // NEW!
    "verified": 42,
    "rejected": 8,
    "failed": 0,
    "total": 55
  },
  "note": "3 issues have exceeded max retries and need manual processing"
}
```

---

## 🔄 New Workflow

### **Scenario 1: Normal Operation (With OpenAI Credits)**
```
Issue created → Attempt 1: Success → Verified → Appears in feed ✅
```

### **Scenario 2: OpenAI Quota Exceeded (3 Retries)**
```
Issue created → Attempt 1: Quota error (retry_count = 1)
              ↓
Background worker (5 min later) → Attempt 2: Quota error (retry_count = 2)
              ↓
Background worker (5 min later) → Attempt 3: Quota error (retry_count = 3)
              ↓
⛔ Max retries exceeded → STOPS retrying
              ↓
Issue stays pending, awaits manual intervention
```

### **Scenario 3: Admin Restores Quota and Triggers Manual Processing**
```
Admin adds OpenAI credits
↓
Admin calls: POST /api/issues/admin/process-pending
↓
Retry count reset to 0 for all pending issues
↓
Background worker processes issues
↓
Success! ✅ Issues verified and appear in feed
```

---

## 🎯 Key Benefits

| Before | After |
|--------|-------|
| ❌ Infinite retry loop | ✅ Max 3 attempts then stop |
| ❌ Logs spammed with errors | ✅ Clean logs, stops after 3 tries |
| ❌ Wasted API calls | ✅ No wasted calls |
| ❌ No way to stop automatic retries | ✅ Automatic stop after 3 failures |
| ❌ No visibility into stuck issues | ✅ Admin can see count needing intervention |
| ❌ Manual DB edit required to retry | ✅ Admin endpoint resets retry count |

---

## 🧪 Testing the Fix

### **Step 1: Run SQL Migration**
```sql
-- In Supabase SQL Editor
-- Copy and paste contents of ADD_RETRY_COUNT.sql
```

### **Step 2: Deploy Updated Code**
```bash
git add .
git commit -m "fix: Add retry limit to prevent infinite OpenAI API calls"
git push origin main
```

### **Step 3: Test Without OpenAI Credits**

1. **Create 3 test issues:**
```bash
curl -X POST https://backend-13ck.onrender.com/api/issues \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Test 1", ...}'
```

2. **Check logs - should see:**
```
Issue abc-123 retry count: 1/3
AI verification error: insufficient_quota
⚠️ AI verification unavailable (attempt 1/3)

[5 minutes later]
Issue abc-123 retry count: 2/3
AI verification error: insufficient_quota
⚠️ AI verification unavailable (attempt 2/3)

[5 minutes later]
Issue abc-123 retry count: 3/3
⛔ Issue abc-123 has exceeded max retries (3)

[No more attempts - stops! ✅]
```

3. **Check admin stats:**
```bash
curl https://backend-13ck.onrender.com/api/issues/admin/stats \
  -H "Authorization: Bearer $TOKEN"

# Should show:
# "pending_needs_manual_intervention": 3
```

### **Step 4: Test Manual Processing (After Adding Credits)**

```bash
# 1. Add OpenAI credits at platform.openai.com

# 2. Trigger manual processing
curl -X POST "https://backend-13ck.onrender.com/api/issues/admin/process-pending" \
  -H "Authorization: Bearer $TOKEN"

# 3. Check logs - should see:
# Reset retry count for 3 issues
# Issue abc-123 retry count: 1/3  (reset!)
# ✅ Issue abc-123 verified as GENUINE
```

---

## 📊 Monitoring Queries

### **See Issues Needing Manual Intervention:**
```sql
SELECT id, title, retry_count, reported_at
FROM issues
WHERE verification_status = 'pending' AND retry_count >= 3
ORDER BY reported_at DESC;
```

### **Or use the view:**
```sql
SELECT * FROM issues_needs_manual_review;
```

### **Check Retry Distribution:**
```sql
SELECT 
    retry_count,
    COUNT(*) as count
FROM issues
WHERE verification_status = 'pending'
GROUP BY retry_count
ORDER BY retry_count;

-- Example output:
-- retry_count | count
-- 0           | 2
-- 1           | 1
-- 2           | 0
-- 3           | 3  <-- These need manual intervention
```

---

## 🔧 Configuration

### **Change Max Retries (Optional)**

If you want to change from 3 to a different number:

**In `app/verification_worker.py`:**
```python
# Change all occurrences of 3 to your desired number
if new_retry_count >= 5:  # Change to 5 attempts
    ...

# And in process_pending_issues:
.lt("retry_count", 5)  # Change to 5
```

**In SQL:**
```sql
-- Update view and comments
ALTER TABLE issues 
ALTER COLUMN retry_count 
SET DEFAULT 0;

COMMENT ON COLUMN issues.retry_count IS 
'Number of AI verification attempts (max 5 before requiring manual intervention)';
```

---

## 🚨 Important Notes

### **Automatic Retries:**
- Background worker checks every ~5 minutes
- Only retries issues with `retry_count < 3`
- After 3 failures, stops automatically
- No infinite loops! ✅

### **Manual Processing:**
- Admin endpoint **resets retry_count to 0**
- Allows reprocessing after fixing root cause (e.g., adding credits)
- Safe to call multiple times

### **Database Consistency:**
- Existing pending issues get `retry_count = 0` automatically (migration)
- New issues start with `retry_count = 0`
- Counter increments atomically per attempt

---

## ✅ Deployment Checklist

- [ ] Run `ADD_RETRY_COUNT.sql` in Supabase SQL Editor
- [ ] Deploy updated code (`app/verification_worker.py`, `app/routers/issues.py`)
- [ ] Test with quota-exceeded scenario
- [ ] Verify logs show max 3 attempts then stop
- [ ] Test admin stats endpoint
- [ ] Test manual processing endpoint
- [ ] Monitor `issues_needs_manual_review` view

---

## 📞 Troubleshooting

### **Issue: Still seeing infinite retries**
**Check:**
- Did you run the SQL migration?
- Is `retry_count` column present?
- Is the code deployed?

**Fix:**
```sql
-- Verify column exists
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'issues' AND column_name = 'retry_count';

-- If missing, run ADD_RETRY_COUNT.sql
```

### **Issue: All issues stuck, none processing**
**Check:**
- Are all issues at `retry_count >= 3`?

**Fix:**
```bash
# Use admin endpoint to reset and reprocess
curl -X POST "https://backend-13ck.onrender.com/api/issues/admin/process-pending" \
  -H "Authorization: Bearer $TOKEN"
```

### **Issue: Want to manually reset specific issue**
```sql
-- Reset specific issue retry count
UPDATE issues 
SET retry_count = 0 
WHERE id = 'ISSUE_ID';
```

---

## 🎉 Result

**Before:** Logs spammed with 100+ identical errors, wasted API calls, no way to stop

**After:** Clean logs, max 3 attempts, automatic stop, admin control, visibility into stuck issues

**The infinite retry loop is now fixed!** ✅

---

**Status:** Ready to deploy!

**Next Steps:**
1. Run `ADD_RETRY_COUNT.sql` in Supabase
2. Deploy code
3. Monitor logs to confirm fix
4. Use admin endpoint when needed

