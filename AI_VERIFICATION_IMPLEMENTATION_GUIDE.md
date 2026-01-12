# AI Verification Pipeline - Implementation Guide

## 🎯 Status: **CORE IMPLEMENTED** - Integration Steps Remaining

---

## ✅ What's Already Done

### 1. **Database Schema** ✅
- File: `CREATE_AI_VERIFICATION_TABLES.sql`
- Tables created:
  - `issues_verified` - Public, rewardable issues
  - `issues_rejected` - Never public
  - `verification_audit_log` - Monitoring
- Fields added to `issues`:
  - `verification_status` (pending/verified/rejected/failed)
  - `processed_at`

### 2. **AI Service** ✅
- File: `app/ai_verification.py`
- Features:
  - OpenAI GPT-4o integration with vision
  - Conservative verification logic
  - Strict JSON output
  - Retry logic
  - Fallback when AI unavailable

### 3. **Background Worker** ✅
- File: `app/verification_worker.py`
- Features:
  - Async processing
  - Idempotency (no double processing)
  - Audit logging
  - Automatic routing (verified/rejected)
  - Post-verification hooks (rewards, emails)
  - Error handling & retries

### 4. **Configuration** ✅
- Added to `app/config.py`:
  - `OPENAI_API_KEY`
  - `OPENAI_MODEL` (default: gpt-4o)
  - `AI_VERIFICATION_ENABLED`
  - `AI_MAX_RETRIES`
  - `AI_TIMEOUT_SECONDS`

### 5. **Dependencies** ✅
- Added to `requirements.txt`:
  - `openai==1.12.0`
  - `httpx==0.26.0`

---

## 🔧 Integration Steps (TODO)

### Step 1: Run Database Migration

```bash
# In Supabase SQL Editor, run:
CREATE_AI_VERIFICATION_TABLES.sql
```

**Verify:**
```sql
SELECT * FROM issues_verified LIMIT 1;
SELECT * FROM issues_rejected LIMIT 1;
SELECT * FROM verification_audit_log LIMIT 1;
```

---

### Step 2: Add OpenAI API Key

**Render Dashboard → Environment:**
```env
OPENAI_API_KEY=sk-your-openai-api-key
AI_VERIFICATION_ENABLED=true
```

**Get API Key:**
- Go to https://platform.openai.com/api-keys
- Create new key
- Copy and add to Render

---

### Step 3: Update Issues Router

**File: `app/routers/issues.py`**

**A. Import the worker:**
```python
from app.verification_worker import verify_issue_async
import asyncio
```

**B. Update CREATE endpoint (after line where issue is created):**

```python
# After: issue = result.data[0]
# Add this:

# Trigger async verification (fire and forget)
asyncio.create_task(verify_issue_async(issue["id"]))

logger.info(f"Issue {issue['id']} created - queued for verification")
```

**C. Update GET endpoints to query `issues_verified`:**

Change all issue GET endpoints from:
```python
# OLD
result = supabase.table("issues").select("*")...
```

To:
```python
# NEW
result = supabase.table("issues_verified").select("*")...
```

**Affected endpoints:**
- `GET /api/issues` - List all issues
- `GET /api/issues/{issue_id}` - Get single issue
- `GET /api/issues` with filters (status, category, etc.)

**D. Add new endpoint to check verification status:**

```python
@router.get("/{issue_id}/verification-status")
async def get_verification_status(
    issue_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Check verification status of an issue"""
    supabase = get_supabase()
    
    # Check original issue
    result = supabase.table("issues").select(
        "verification_status, processed_at"
    ).eq("id", issue_id).execute()
    
    if not result.data:
        raise HTTPException(404, "Issue not found")
    
    status = result.data[0]
    
    # Check if verified
    verified = supabase.table("issues_verified").select("id").eq(
        "original_issue_id", issue_id
    ).execute()
    
    # Check if rejected
    rejected = supabase.table("issues_rejected").select(
        "rejection_reason"
    ).eq("original_issue_id", issue_id).execute()
    
    return {
        "status": status["verification_status"],
        "processed_at": status.get("processed_at"),
        "is_verified": bool(verified.data),
        "is_rejected": bool(rejected.data),
        "rejection_reason": rejected.data[0]["rejection_reason"] if rejected.data else None
    }
```

---

### Step 4: Start Background Worker

**File: `app/main.py`**

**Add at the top:**
```python
from contextlib import asynccontextmanager
import asyncio
from app.verification_worker import process_verification_queue
```

**Replace app initialization:**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background verification worker
    worker_task = asyncio.create_task(process_verification_queue())
    logger.info("🚀 Background verification worker started")
    
    yield
    
    # Shutdown
    worker_task.cancel()
    logger.info("🛑 Background verification worker stopped")

app = FastAPI(
    title="FailState Backend API",
    description="Backend API for civic issue reporting with AI verification",
    version="2.0.0",
    lifespan=lifespan  # Add this
)
```

---

### Step 5: Update Rewards Integration

**File: `app/verification_worker.py`**

**In `trigger_post_verification_hooks` method:**

Already implemented! It calls:
```python
self.supabase.rpc("award_points", {
    "user_id": user_id,
    "points": 25,
    "reason": "verified_issue_reported"
}).execute()
```

**Make sure this function exists in your database:**

```sql
-- If not already exists, create it:
CREATE OR REPLACE FUNCTION award_points(user_id UUID, points INTEGER, reason TEXT)
RETURNS VOID AS $$
BEGIN
    -- Update user_rewards
    UPDATE user_rewards
    SET total_points = total_points + points,
        updated_at = NOW()
    WHERE user_rewards.user_id = award_points.user_id;
    
    -- Log to rewards_history
    INSERT INTO rewards_history (user_id, points, reason, timestamp)
    VALUES (user_id, points, reason, NOW());
END;
$$ LANGUAGE plpgsql;
```

---

### Step 6: Update Frontend (if needed)

**A. Issue Submission Response:**
- Frontend gets same response as before
- Issue is created immediately
- Verification happens in background
- Frontend can poll `/api/issues/{id}/verification-status`

**B. Issue Feed:**
- No change needed!
- Backend now returns `issues_verified` automatically
- Only verified issues appear in feed

**C. Optional: Show pending status:**

Add a "pending verification" indicator:
```typescript
if (issue.verification_status === 'pending') {
  return <Badge>Pending Verification</Badge>
}
```

---

## 🧪 Testing Checklist

### Test 1: Create Issue
```bash
curl -X POST https://your-backend.com/api/issues \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Pothole on Main St",
    "description": "Large pothole causing damage",
    "category": "infrastructure",
    "image_url": "https://example.com/image.jpg",
    "location": {
      "name": "Main St",
      "coordinates": {"lat": 40.7128, "lng": -74.0060}
    }
  }'
```

**Expected:**
- Issue created
- Returns 201 with issue data
- `verification_status`: "pending"

### Test 2: Check Logs
```bash
# In Render logs, you should see:
INFO: Issue abc123 created - queued for verification
INFO: 🔄 Processing issue abc123
INFO: AI raw response: {...}
INFO: ✅ Issue abc123 verified as GENUINE
INFO: ✅ Created verified issue for abc123
INFO: ✅ Awarded points to user xyz
```

### Test 3: Check Database
```sql
-- Original issue
SELECT id, verification_status, processed_at FROM issues WHERE id = 'abc123';
-- Should show: verified, with timestamp

-- Verified issue
SELECT * FROM issues_verified WHERE original_issue_id = 'abc123';
-- Should have enriched data from AI

-- Audit log
SELECT * FROM verification_audit_log WHERE issue_id = 'abc123';
-- Should show processing steps
```

### Test 4: Public Feed
```bash
curl https://your-backend.com/api/issues

# Should only return verified issues
# Should NOT return pending/rejected issues
```

---

## 🚨 Important Notes

### Breaking Changes: NONE ✅
- Existing APIs still work
- `POST /api/issues` - same request/response
- `GET /api/issues` - same response format (just different data source)
- No frontend changes required

### Data Flow

```
User Submit
    ↓
issues (quarantine)
    ↓
Background Worker
    ↓
AI Verification
    ↓
   / \
  /   \
Genuine  Fake
  ↓      ↓
verified rejected
  ↓
Rewards + Email
```

### Monitoring

**Check pending count:**
```sql
SELECT COUNT(*) FROM issues WHERE verification_status = 'pending';
```

**Check verification success rate:**
```sql
SELECT 
    verification_status,
    COUNT(*) as count
FROM issues
GROUP BY verification_status;
```

**Check AI audit logs:**
```sql
SELECT status, COUNT(*) 
FROM verification_audit_log 
GROUP BY status 
ORDER BY COUNT(*) DESC;
```

---

## 📊 Environment Variables Summary

```env
# Required
OPENAI_API_KEY=sk-xxxxx

# Optional (with defaults)
OPENAI_MODEL=gpt-4o
AI_VERIFICATION_ENABLED=true
AI_MAX_RETRIES=3
AI_TIMEOUT_SECONDS=30
```

---

## 🎯 Deployment Checklist

- [ ] Run `CREATE_AI_VERIFICATION_TABLES.sql` in Supabase
- [ ] Add `OPENAI_API_KEY` to Render environment
- [ ] Update `app/routers/issues.py` (integrate verification trigger)
- [ ] Update `app/main.py` (start background worker)
- [ ] Create `award_points` function in database (if not exists)
- [ ] Push changes to Git
- [ ] Verify deployment successful
- [ ] Test issue creation
- [ ] Check logs for verification processing
- [ ] Verify issues appear in public feed after verification

---

## 🔗 File Reference

| File | Purpose |
|------|---------|
| `CREATE_AI_VERIFICATION_TABLES.sql` | Database schema |
| `app/ai_verification.py` | OpenAI integration |
| `app/verification_worker.py` | Background processor |
| `app/config.py` | Configuration (updated) |
| `requirements.txt` | Dependencies (updated) |
| `app/routers/issues.py` | **NEEDS UPDATING** |
| `app/main.py` | **NEEDS UPDATING** |

---

## 💡 Next Steps

1. **Review this guide**
2. **Run the SQL migration**
3. **Add OpenAI API key**
4. **I can update the remaining files** (`issues.py` and `main.py`) if you approve
5. **Deploy and test**

Would you like me to complete the integration by updating `issues.py` and `main.py`? 🚀

