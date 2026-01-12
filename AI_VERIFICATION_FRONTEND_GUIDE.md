# Frontend Integration Guide - AI Verification Pipeline

## 🤔 Are Frontend Changes Required?

**Short answer:** **NO, but RECOMMENDED for better UX**

The backend changes are **backward compatible** - your existing frontend will continue to work without any modifications. However, adding a few optional enhancements will significantly improve user experience.

---

## ✅ What Works Without Any Changes

### 1. **Issue Creation** - No Change Needed ✅
```typescript
// This still works exactly as before
const createIssue = async (issueData) => {
  const response = await fetch(`${API_URL}/issues`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(issueData)
  });
  
  const issue = await response.json();
  // Returns the same response format as before
};
```

### 2. **Issue List/Feed** - No Change Needed ✅
```typescript
// This still works - backend automatically returns only verified issues
const getIssues = async () => {
  const response = await fetch(`${API_URL}/issues`);
  const issues = await response.json();
  // Returns same Issue[] format as before
};
```

### 3. **Single Issue View** - No Change Needed ✅
```typescript
// This still works
const getIssue = async (issueId) => {
  const response = await fetch(`${API_URL}/issues/${issueId}`);
  const issue = await response.json();
};
```

---

## 🎯 What Changes (Behavior Only)

### Before AI Verification:
```
User creates issue → Immediately visible in public feed → Reward given
```

### After AI Verification:
```
User creates issue → Pending verification (2-10 seconds) → AI verifies → Visible in public feed → Reward given
```

**Impact:** Users won't see their issue appear immediately in the public feed. It takes 2-10 seconds for AI verification to complete.

---

## 🚨 Potential User Confusion

**Without frontend changes:**
1. User creates an issue
2. Gets success message
3. Checks public feed
4. **Issue not there yet** ❌
5. User confused: "Did my issue submit?"

**With recommended frontend changes:**
1. User creates an issue
2. Sees "Pending AI verification..." message ✅
3. Auto-updates when verified ✅
4. Issue appears in feed ✅
5. User happy! 😊

---

## 💡 Recommended Frontend Enhancements

### **Enhancement 1: Show Pending Status After Creation**

When a user creates an issue, show a pending state:

```typescript
const createIssue = async (issueData) => {
  const response = await fetch(`${API_URL}/issues`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(issueData)
  });
  
  const issue = await response.json();
  
  // NEW: Show pending verification UI
  showNotification({
    type: 'info',
    title: 'Issue Submitted!',
    message: 'Your issue is being verified by our AI system. This usually takes 5-10 seconds.',
    icon: '🔄'
  });
  
  // Start polling for verification status
  pollVerificationStatus(issue.id);
};
```

---

### **Enhancement 2: Poll Verification Status** (NEW ENDPOINT)

Use the new verification status endpoint to track progress:

```typescript
const pollVerificationStatus = async (issueId: string) => {
  const maxAttempts = 20; // Poll for up to 20 seconds
  let attempts = 0;
  
  const interval = setInterval(async () => {
    attempts++;
    
    try {
      const response = await fetch(
        `${API_URL}/issues/${issueId}/verification-status`,
        {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );
      
      const status = await response.json();
      
      if (status.is_verified) {
        clearInterval(interval);
        
        // Show success
        showNotification({
          type: 'success',
          title: '✅ Issue Verified!',
          message: 'Your issue has been verified and is now visible to everyone.',
        });
        
        // Optionally redirect to the issue or refresh feed
        router.push(`/issues/${issueId}`);
      } else if (status.is_rejected) {
        clearInterval(interval);
        
        // Show rejection (rare)
        showNotification({
          type: 'error',
          title: '❌ Issue Not Verified',
          message: status.rejection_reason || 'Our AI could not verify this issue.',
        });
      } else if (attempts >= maxAttempts) {
        clearInterval(interval);
        
        // Timeout (very rare)
        showNotification({
          type: 'warning',
          title: '⏱️ Verification Taking Longer',
          message: 'Your issue is still being verified. Check back in a few minutes.',
        });
      }
      
    } catch (error) {
      console.error('Verification status check failed:', error);
    }
  }, 1000); // Poll every 1 second
};
```

---

### **Enhancement 3: Add Verification Status Badge**

In the user's "My Issues" page, show verification status:

```tsx
function MyIssuesPage() {
  const [issues, setIssues] = useState([]);
  
  useEffect(() => {
    // Fetch user's issues (all, not just verified)
    fetchMyIssues();
  }, []);
  
  return (
    <div>
      <h1>My Issues</h1>
      {issues.map(issue => (
        <IssueCard key={issue.id}>
          <h3>{issue.title}</h3>
          
          {/* NEW: Show verification status */}
          {issue.verification_status === 'pending' && (
            <Badge color="yellow">
              🔄 Pending Verification
            </Badge>
          )}
          {issue.verification_status === 'verified' && (
            <Badge color="green">
              ✅ Verified
            </Badge>
          )}
          {issue.verification_status === 'rejected' && (
            <Badge color="red">
              ❌ Not Verified
            </Badge>
          )}
          
          {/* If rejected, show reason */}
          {issue.verification_status === 'rejected' && (
            <p className="rejection-reason">
              Reason: {issue.rejection_reason}
            </p>
          )}
        </IssueCard>
      ))}
    </div>
  );
}
```

---

### **Enhancement 4: Add "My Issues" Endpoint** (If Not Already Exists)

You might need a separate endpoint to fetch the current user's issues (including pending/rejected):

**Backend Change Needed:**
```python
# In app/routers/issues.py

@router.get("/my-issues", response_model=List[Issue])
async def get_my_issues(
    current_user: TokenData = Depends(get_current_user)
):
    """Get all issues created by the current user (including pending)"""
    supabase = get_supabase()
    
    # Query original issues table (not verified)
    result = supabase.table("issues").select("*").eq(
        "reported_by", current_user.user_id
    ).order("reported_at", desc=True).execute()
    
    issues = []
    for issue_data in result.data:
        issue = await build_issue_response(issue_data)
        issues.append(issue)
    
    return issues
```

**Frontend:**
```typescript
const getMyIssues = async () => {
  const response = await fetch(`${API_URL}/issues/my-issues`, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  
  const myIssues = await response.json();
  // Shows ALL user's issues (pending, verified, rejected)
};
```

---

## 📊 Complete User Flow Example

### Step 1: User Creates Issue

```tsx
const handleSubmit = async (formData) => {
  setLoading(true);
  
  try {
    const response = await createIssue(formData);
    
    // Show pending message
    toast.info('🔄 Issue submitted! Verifying with AI...');
    
    // Start polling
    const status = await pollVerificationStatus(response.id);
    
    if (status.is_verified) {
      toast.success('✅ Issue verified and published!');
      router.push('/issues'); // Go to feed
    } else if (status.is_rejected) {
      toast.error(`❌ ${status.rejection_reason}`);
      router.push('/my-issues'); // Go to user's issues
    }
    
  } catch (error) {
    toast.error('Failed to create issue');
  } finally {
    setLoading(false);
  }
};
```

### Step 2: Public Feed (No Changes Needed)

```tsx
// This works as-is - backend filters to verified only
const IssuesFeed = () => {
  const { data: issues } = useQuery('issues', getIssues);
  
  return (
    <div>
      {issues.map(issue => (
        <IssueCard key={issue.id} issue={issue} />
      ))}
    </div>
  );
};
```

### Step 3: My Issues Page (New Feature)

```tsx
const MyIssuesPage = () => {
  const { data: myIssues } = useQuery('my-issues', getMyIssues);
  
  return (
    <div>
      <h1>My Issues</h1>
      
      {myIssues.filter(i => i.verification_status === 'pending').length > 0 && (
        <section>
          <h2>🔄 Pending Verification</h2>
          {myIssues
            .filter(i => i.verification_status === 'pending')
            .map(issue => (
              <IssueCard key={issue.id} issue={issue}>
                <Badge>Verifying...</Badge>
              </IssueCard>
            ))}
        </section>
      )}
      
      {myIssues.filter(i => i.verification_status === 'verified').length > 0 && (
        <section>
          <h2>✅ Verified Issues</h2>
          {myIssues
            .filter(i => i.verification_status === 'verified')
            .map(issue => (
              <IssueCard key={issue.id} issue={issue} />
            ))}
        </section>
      )}
      
      {myIssues.filter(i => i.verification_status === 'rejected').length > 0 && (
        <section>
          <h2>❌ Not Verified</h2>
          {myIssues
            .filter(i => i.verification_status === 'rejected')
            .map(issue => (
              <IssueCard key={issue.id} issue={issue}>
                <Badge color="red">Rejected</Badge>
                <p className="reason">{issue.rejection_reason}</p>
              </IssueCard>
            ))}
        </section>
      )}
    </div>
  );
};
```

---

## 🎨 UI/UX Recommendations

### Notification Messages

**Success:**
- ✅ "Issue verified and published!"
- ✅ "Your report has been verified by AI and is now visible to everyone"

**Pending:**
- 🔄 "Verifying your issue... This usually takes 5-10 seconds"
- 🔄 "AI is analyzing your report"

**Rejected:**
- ❌ "Issue could not be verified"
- ❌ "Our AI was unable to verify this issue. Reason: [reason]"

### Loading States

```tsx
{verifying && (
  <div className="verification-progress">
    <Spinner />
    <p>AI is verifying your issue...</p>
    <p className="subtext">Analyzing image and description</p>
  </div>
)}
```

### Status Badges

```tsx
<Badge color={
  status === 'verified' ? 'green' :
  status === 'pending' ? 'yellow' :
  'red'
}>
  {status === 'verified' && '✅ Verified'}
  {status === 'pending' && '🔄 Verifying'}
  {status === 'rejected' && '❌ Not Verified'}
</Badge>
```

---

## 📝 TypeScript Types (If Using TypeScript)

```typescript
// types/issue.ts

export enum VerificationStatus {
  PENDING = 'pending',
  VERIFIED = 'verified',
  REJECTED = 'rejected',
  FAILED = 'failed',
  QUARANTINED = 'quarantined'
}

export interface Issue {
  id: string;
  title: string;
  description: string;
  category: string;
  status: string;
  location: Location;
  image_url?: string;
  video_url?: string;
  reported_by: string;
  reported_at: string;
  resolved_at?: string;
  upvotes: number;
  timeline: TimelineEvent[];
  
  // NEW: Verification fields (may not be present on all issues)
  verification_status?: VerificationStatus;
  rejection_reason?: string;
}

export interface VerificationStatusResponse {
  issue_id: string;
  verification_status: VerificationStatus;
  processed_at?: string;
  is_verified: boolean;
  is_rejected: boolean;
  verified_at?: string;
  rejection_reason?: string;
  rejection_details?: string;
}
```

---

## ✅ Summary

### **Required Changes:** **NONE** ✅

Your existing frontend will continue to work without any modifications.

### **Recommended Changes:**

1. ✅ **Show pending status** after issue creation
2. ✅ **Poll verification status** using new endpoint
3. ✅ **Add "My Issues" page** to show pending/rejected issues
4. ✅ **Add verification badges** in UI
5. ✅ **Better user feedback** with notifications

### **Priority:**

- **High Priority:** Show pending status notification (prevents user confusion)
- **Medium Priority:** Add verification status polling
- **Low Priority:** Add "My Issues" page for rejected issues

---

## 🚀 Quick Start (Minimal Changes)

If you want the **absolute minimum** frontend change, just add this after issue creation:

```typescript
// After creating issue
toast.info('Issue submitted! It will appear in the feed after AI verification (~10 seconds).');
```

That's it! This prevents user confusion while you work on more advanced features.

---

## 🔗 New API Endpoint

### **GET `/api/issues/{issue_id}/verification-status`**

**Authentication:** Required (JWT)

**Response:**
```json
{
  "issue_id": "abc-123",
  "verification_status": "verified",
  "processed_at": "2026-01-12T10:30:00Z",
  "is_verified": true,
  "is_rejected": false,
  "verified_at": "2026-01-12T10:30:05Z",
  "rejection_reason": null,
  "rejection_details": null
}
```

**Use Case:** Poll this endpoint after creating an issue to track verification progress.

---

## 🧪 Testing Checklist

- [ ] Create issue → See pending notification
- [ ] Wait 5-10 seconds → Issue appears in feed
- [ ] Check "My Issues" → See all issues with status badges
- [ ] Create fake/meme issue → Gets rejected, shows reason
- [ ] Verify public feed → Only shows verified issues
- [ ] Test without changes → Confirm existing frontend still works

---

## 💡 Pro Tips

1. **Don't block the user** - Let them continue browsing while verification happens in background
2. **Use optimistic UI** - Show the issue immediately in "My Issues" with a "pending" badge
3. **Set expectations** - Tell users verification takes 5-10 seconds
4. **Handle edge cases** - What if verification takes longer? Show "still verifying" message
5. **Celebrate success** - When verified, show a satisfying success message! 🎉

---

## 📞 Questions?

The backend is backward compatible, so you can deploy it immediately and add frontend enhancements at your own pace. The public feed will automatically show only verified issues, even if your frontend doesn't change at all.

Start with the minimal notification change, then add more sophisticated features as needed! 🚀

