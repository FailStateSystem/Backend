# Frontend Integration Guide - Pre-Ingestion Filtering System

## 🎯 Overview

The backend now has comprehensive pre-ingestion filtering. While the system works without any frontend changes, implementing these recommendations will significantly improve user experience.

**Backend is backward compatible** ✅ - Existing frontend will work, but users will get generic error messages.

---

## 📋 Required Changes (Minimum)

### **1. Handle New Error Responses**

The backend now returns specific error codes and messages for filtering failures.

#### **New HTTP Status Codes:**

| Status | Meaning | User Action |
|--------|---------|-------------|
| `400` | Content filtered (NSFW, duplicate, garbage, etc.) | Fix and resubmit |
| `429` | Rate limit exceeded | Wait and retry |
| `403` | Shadow banned (rare - fake success usually) | N/A |

#### **Error Response Format:**

```typescript
interface FilterErrorResponse {
  detail: string;  // User-friendly error message
  // For rate limits:
  headers?: {
    'Retry-After': string;  // Seconds until retry allowed
  }
}
```

#### **Implementation:**

**Before:**
```typescript
const handleSubmit = async (data) => {
  try {
    await createIssue(data);
    toast.success('Issue created!');
  } catch (error) {
    toast.error('Failed to create issue');  // Generic
  }
};
```

**After:**
```typescript
const handleSubmit = async (data) => {
  try {
    await createIssue(data);
    toast.success('Issue submitted for verification!');
  } catch (error) {
    if (error.response?.status === 429) {
      // Rate limit
      const retryAfter = error.response.headers['retry-after'];
      const minutes = Math.ceil(retryAfter / 60);
      toast.error(`Rate limit exceeded. Please try again in ${minutes} minutes.`);
    } else if (error.response?.status === 400) {
      // Content filter
      const message = error.response.data.detail;
      if (message.includes('NSFW')) {
        toast.error('Image contains inappropriate content.');
      } else if (message.includes('duplicate')) {
        toast.error('You\'ve already uploaded this image.');
      } else if (message.includes('screenshot')) {
        toast.error('Please upload a photo, not a screenshot.');
      } else if (message.includes('pure black') || message.includes('pure white')) {
        toast.error('Image quality too low. Please upload a clear photo.');
      } else {
        toast.error(message);  // Show backend message
      }
    } else {
      toast.error('Failed to create issue. Please try again.');
    }
  }
};
```

---

## 🚀 Recommended Changes (Better UX)

### **2. Client-Side Pre-Validation** (Optional but Recommended)

Add client-side checks BEFORE upload to catch issues early.

```typescript
// components/IssueForm.tsx

const validateImage = async (file: File): Promise<string | null> => {
  // Check 1: File size
  if (file.size > 10 * 1024 * 1024) {  // 10MB
    return 'Image too large (max 10MB)';
  }
  
  // Check 2: File type
  if (!file.type.startsWith('image/')) {
    return 'Please upload an image file';
  }
  
  // Check 3: Image dimensions (too small)
  const img = await createImageBitmap(file);
  if (img.width < 100 || img.height < 100) {
    return 'Image too small (minimum 100x100 pixels)';
  }
  
  // Check 4: Aspect ratio (optional - flag weird ratios)
  const aspectRatio = img.width / img.height;
  if (aspectRatio > 10 || aspectRatio < 0.1) {
    return 'Unusual image dimensions. Is this a screenshot?';
  }
  
  return null;  // Valid
};

const handleImageSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
  const file = e.target.files?.[0];
  if (!file) return;
  
  const error = await validateImage(file);
  if (error) {
    toast.error(error);
    e.target.value = '';  // Clear input
    return;
  }
  
  // Proceed with image
  setSelectedImage(file);
};
```

---

### **3. Rate Limit Countdown Timer**

Show users when they can submit again after hitting rate limit.

```typescript
// hooks/useRateLimitTimer.ts

import { useState, useEffect } from 'react';

export const useRateLimitTimer = (retryAfter: number | null) => {
  const [timeLeft, setTimeLeft] = useState(retryAfter);
  
  useEffect(() => {
    if (!retryAfter) return;
    
    setTimeLeft(retryAfter);
    
    const interval = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev === null || prev <= 1) {
          clearInterval(interval);
          return null;
        }
        return prev - 1;
      });
    }, 1000);
    
    return () => clearInterval(interval);
  }, [retryAfter]);
  
  return timeLeft;
};

// Usage in component:
const CreateIssueForm = () => {
  const [retryAfter, setRetryAfter] = useState<number | null>(null);
  const timeLeft = useRateLimitTimer(retryAfter);
  
  const handleSubmit = async (data) => {
    try {
      await createIssue(data);
    } catch (error) {
      if (error.response?.status === 429) {
        const seconds = parseInt(error.response.headers['retry-after']);
        setRetryAfter(seconds);
      }
    }
  };
  
  return (
    <form onSubmit={handleSubmit}>
      {/* Form fields */}
      
      <button 
        type="submit" 
        disabled={timeLeft !== null}
      >
        {timeLeft ? `Wait ${Math.ceil(timeLeft / 60)} minutes` : 'Submit Issue'}
      </button>
      
      {timeLeft && (
        <div className="rate-limit-notice">
          ⏱️ Rate limit reached. You can submit again in {formatTime(timeLeft)}
        </div>
      )}
    </form>
  );
};

const formatTime = (seconds: number): string => {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
};
```

---

### **4. Better Error Messages with Icons**

Make filtering errors more user-friendly.

```tsx
// components/FilterErrorMessage.tsx

interface FilterErrorProps {
  error: string;
}

export const FilterErrorMessage: React.FC<FilterErrorProps> = ({ error }) => {
  const getErrorConfig = (error: string) => {
    if (error.includes('NSFW')) {
      return {
        icon: '🚫',
        title: 'Inappropriate Content',
        message: 'Your image contains content that violates our community guidelines.',
        action: 'Please upload a different photo of the actual civic issue.'
      };
    } else if (error.includes('duplicate')) {
      return {
        icon: '🔄',
        title: 'Duplicate Image',
        message: 'You\'ve already reported this issue.',
        action: 'Check your previous submissions or upload a different photo.'
      };
    } else if (error.includes('screenshot') || error.includes('text')) {
      return {
        icon: '📱',
        title: 'Screenshot Detected',
        message: 'Please upload a photo of the actual issue, not a screenshot.',
        action: 'Take a new photo with your camera.'
      };
    } else if (error.includes('black') || error.includes('white') || error.includes('blurry')) {
      return {
        icon: '🌫️',
        title: 'Image Quality Too Low',
        message: 'Your image is too dark, bright, or blurry to process.',
        action: 'Please take a clearer photo with better lighting.'
      };
    } else if (error.includes('Rate limit')) {
      return {
        icon: '⏱️',
        title: 'Slow Down',
        message: error,
        action: 'Please wait before submitting more issues.'
      };
    } else {
      return {
        icon: '❌',
        title: 'Submission Failed',
        message: error,
        action: 'Please try again or contact support.'
      };
    }
  };
  
  const config = getErrorConfig(error);
  
  return (
    <div className="filter-error-card">
      <div className="error-icon">{config.icon}</div>
      <h3>{config.title}</h3>
      <p className="error-message">{config.message}</p>
      <p className="error-action">{config.action}</p>
    </div>
  );
};
```

---

### **5. Trust Score Display** (Optional)

Show users their reputation/trust score.

```tsx
// components/UserTrustBadge.tsx

interface TrustBadgeProps {
  trustScore: number;
}

export const UserTrustBadge: React.FC<TrustBadgeProps> = ({ trustScore }) => {
  const getTrustLevel = (score: number) => {
    if (score >= 80) return { label: 'Excellent', color: 'green', icon: '⭐' };
    if (score >= 50) return { label: 'Good', color: 'blue', icon: '👍' };
    if (score >= 30) return { label: 'Fair', color: 'yellow', icon: '⚠️' };
    return { label: 'Low', color: 'red', icon: '🔻' };
  };
  
  const level = getTrustLevel(trustScore);
  
  return (
    <div className={`trust-badge trust-${level.color}`}>
      <span className="trust-icon">{level.icon}</span>
      <span className="trust-label">Trust: {level.label}</span>
      <span className="trust-score">{trustScore}/100</span>
    </div>
  );
};

// Add to user profile API response
interface UserProfile {
  // ... existing fields
  trust_score: number;  // NEW
}

// Display in header/profile
const UserHeader = () => {
  const { user } = useAuth();
  
  return (
    <div className="user-header">
      <Avatar src={user.avatar} />
      <span>{user.username}</span>
      <UserTrustBadge trustScore={user.trust_score} />
    </div>
  );
};
```

---

### **6. Rate Limit Progress Indicator**

Show users how close they are to hitting limits.

```tsx
// components/RateLimitProgress.tsx

interface RateLimitProgressProps {
  current: number;
  limit: number;
  period: 'hour' | 'day';
}

export const RateLimitProgress: React.FC<RateLimitProgressProps> = ({
  current,
  limit,
  period
}) => {
  const percentage = (current / limit) * 100;
  const remaining = limit - current;
  
  const getColor = () => {
    if (percentage >= 90) return 'red';
    if (percentage >= 70) return 'yellow';
    return 'green';
  };
  
  return (
    <div className="rate-limit-progress">
      <div className="progress-label">
        {remaining} issue{remaining !== 1 ? 's' : ''} remaining this {period}
      </div>
      <div className="progress-bar">
        <div 
          className={`progress-fill progress-${getColor()}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <div className="progress-text">
        {current} / {limit}
      </div>
    </div>
  );
};

// Add to create issue page
const CreateIssuePage = () => {
  const { rateLimits } = useUserRateLimits();  // Fetch from API
  
  return (
    <div>
      <RateLimitProgress 
        current={rateLimits.hourly_count}
        limit={rateLimits.hourly_limit}
        period="hour"
      />
      <IssueForm />
    </div>
  );
};

// Add API endpoint to get rate limit status
// GET /api/users/me/rate-limits
// Response:
// {
//   "hourly_count": 3,
//   "hourly_limit": 10,
//   "daily_count": 8,
//   "daily_limit": 50
// }
```

---

### **7. Image Quality Pre-Check** (Advanced)

Use client-side image analysis to warn users before upload.

```typescript
// utils/imageQuality.ts

export const checkImageQuality = async (file: File): Promise<{
  valid: boolean;
  warnings: string[];
}> => {
  const warnings: string[] = [];
  
  // Create image
  const img = await createImageBitmap(file);
  
  // Check 1: Too small
  if (img.width < 200 || img.height < 200) {
    warnings.push('Image resolution is low. Consider taking a higher quality photo.');
  }
  
  // Check 2: Weird aspect ratio (possible screenshot)
  const aspectRatio = img.width / img.height;
  if (aspectRatio > 3 || aspectRatio < 0.33) {
    warnings.push('Unusual image dimensions. Screenshots may be rejected.');
  }
  
  // Check 3: Canvas analysis for pure colors
  const canvas = document.createElement('canvas');
  canvas.width = img.width;
  canvas.height = img.height;
  const ctx = canvas.getContext('2d')!;
  ctx.drawImage(img, 0, 0);
  
  const imageData = ctx.getImageData(0, 0, img.width, img.height);
  const pixels = imageData.data;
  
  // Sample pixels to check for pure black/white
  let blackCount = 0;
  let whiteCount = 0;
  const sampleSize = 100;
  
  for (let i = 0; i < sampleSize; i++) {
    const idx = Math.floor(Math.random() * (pixels.length / 4)) * 4;
    const r = pixels[idx];
    const g = pixels[idx + 1];
    const b = pixels[idx + 2];
    
    if (r < 10 && g < 10 && b < 10) blackCount++;
    if (r > 245 && g > 245 && b > 245) whiteCount++;
  }
  
  if (blackCount > sampleSize * 0.8) {
    warnings.push('Image appears to be mostly black. May be rejected.');
  }
  if (whiteCount > sampleSize * 0.8) {
    warnings.push('Image appears to be mostly white. May be rejected.');
  }
  
  return {
    valid: warnings.length === 0,
    warnings
  };
};

// Usage:
const handleImageSelect = async (file: File) => {
  const { valid, warnings } = await checkImageQuality(file);
  
  if (!valid) {
    setImageWarnings(warnings);
    // Show warnings but still allow upload
  }
  
  setSelectedImage(file);
};
```

---

### **8. Better Loading States**

Show what's happening during filtering.

```tsx
// components/IssueSubmitButton.tsx

type SubmitState = 'idle' | 'validating' | 'uploading' | 'verifying' | 'success' | 'error';

export const IssueSubmitButton = () => {
  const [state, setState] = useState<SubmitState>('idle');
  
  const handleSubmit = async () => {
    setState('validating');
    // Client-side checks
    
    setState('uploading');
    // Submit to backend (which runs server-side filtering)
    
    setState('verifying');
    // Backend AI verification
    
    setState('success');
  };
  
  const getButtonContent = () => {
    switch (state) {
      case 'validating':
        return (
          <>
            <Spinner />
            Checking image quality...
          </>
        );
      case 'uploading':
        return (
          <>
            <Spinner />
            Running security checks...
          </>
        );
      case 'verifying':
        return (
          <>
            <Spinner />
            Verifying with AI...
          </>
        );
      case 'success':
        return (
          <>
            ✅ Submitted!
          </>
        );
      default:
        return 'Submit Issue';
    }
  };
  
  return (
    <button 
      onClick={handleSubmit}
      disabled={state !== 'idle'}
      className={`submit-btn submit-${state}`}
    >
      {getButtonContent()}
    </button>
  );
};
```

---

## 📊 API Changes Needed (Backend)

To support frontend features, add these endpoints:

### **1. Get User Rate Limit Status**
```typescript
GET /api/users/me/rate-limits

Response:
{
  "hourly_count": 3,
  "hourly_limit": 10,
  "daily_count": 8,
  "daily_limit": 50,
  "trust_score": 85
}
```

### **2. Get User Trust Score**
```typescript
GET /api/users/me

Response:
{
  // ... existing fields
  "trust_score": 85,
  "is_shadow_banned": false  // Always false in response (hidden)
}
```

### **3. Get User Violation History** (Optional)
```typescript
GET /api/users/me/violations

Response:
{
  "violations": [
    {
      "type": "rate_limit",
      "severity": "low",
      "timestamp": "2026-01-16T10:30:00Z",
      "details": "Hourly limit exceeded"
    }
  ],
  "total_count": 1,
  "trust_score": 97
}
```

---

## 🎨 UI/UX Recommendations

### **Error Message Guidelines:**

| Filter | User-Friendly Message | Icon |
|--------|----------------------|------|
| NSFW | "Image contains inappropriate content" | 🚫 |
| Duplicate | "You've already uploaded this image" | 🔄 |
| Screenshot | "Please upload a photo, not a screenshot" | 📱 |
| Garbage | "Image quality too low - take a clearer photo" | 🌫️ |
| Rate Limit | "Slow down! Wait X minutes" | ⏱️ |

### **Trust Score Colors:**

| Score | Level | Color | Icon |
|-------|-------|-------|------|
| 80-100 | Excellent | Green | ⭐ |
| 50-79 | Good | Blue | 👍 |
| 30-49 | Fair | Yellow | ⚠️ |
| 0-29 | Low | Red | 🔻 |

---

## 📱 Mobile Considerations

### **Camera vs Screenshots:**
```typescript
// Encourage camera usage over gallery
<input 
  type="file" 
  accept="image/*" 
  capture="environment"  // Prefer camera
/>

// Or use separate buttons
<button onClick={openCamera}>
  📷 Take Photo
</button>
<button onClick={openGallery}>
  🖼️ Choose from Gallery
</button>
```

### **Haptic Feedback:**
```typescript
// On error
if ('vibrate' in navigator) {
  navigator.vibrate(200);  // Error vibration
}

// On success
if ('vibrate' in navigator) {
  navigator.vibrate([100, 50, 100]);  // Success pattern
}
```

---

## ✅ Implementation Checklist

### **Minimum (Required):**
- [ ] Handle 429 rate limit errors with Retry-After
- [ ] Handle 400 content filter errors with specific messages
- [ ] Show user-friendly error messages

### **Recommended:**
- [ ] Client-side image validation
- [ ] Rate limit countdown timer
- [ ] Better error messages with icons
- [ ] Trust score display in profile
- [ ] Rate limit progress indicator
- [ ] Image quality pre-check warnings
- [ ] Better loading states

### **Advanced (Optional):**
- [ ] Violation history page
- [ ] Appeal system for false positives
- [ ] Image editing tools (crop, rotate, enhance)
- [ ] Duplicate detection warning before upload
- [ ] Community guidelines link in errors

---

## 🧪 Testing Checklist

- [ ] Submit normal issue (should work)
- [ ] Submit same image twice (should show duplicate error)
- [ ] Submit 11 issues in 1 hour (should show rate limit with countdown)
- [ ] Submit screenshot (should show screenshot error)
- [ ] Submit pure black image (should show quality error)
- [ ] Check trust score display
- [ ] Verify error messages are user-friendly
- [ ] Test on mobile (camera vs gallery)

---

## 📞 Support

If users report false positives:
1. Check their trust score
2. Review violation history
3. Manually increase trust score if needed
4. Consider adjusting filter thresholds

---

## 🎯 Expected User Experience

### **Good Actor:**
```
Submit photo → ✅ Pass all filters → Upload → AI verify → Published
Trust score: Increases over time
Rate limits: Generous
```

### **Accidental Violation:**
```
Submit screenshot → ❌ Blocked with helpful message
"Please upload a photo, not a screenshot. Take a new photo."
Trust score: Slightly decreased
Rate limits: Unchanged
```

### **Repeated Abuser:**
```
Multiple NSFW attempts → ❌ Blocked each time
Trust score: Drops rapidly → Shadow banned at < 20
Rate limits: Severely restricted
Eventually: All submissions fake-accepted but discarded
```

---

## 🚀 Summary

**Minimum Changes:** Handle new error codes and messages (30 minutes)

**Recommended Changes:** Add all UX improvements (4-6 hours)

**Result:** Much better user experience with clear feedback on why submissions fail and how to fix them.

---

**Frontend changes are optional but highly recommended for better UX!** 🎨

