# Frontend Integration Guide - Email Verification

## 🔄 What Changed in the Backend

### Before (Old Flow):
```
User signs up → Gets access token immediately → Can use app
```

### After (New Flow):
```
User signs up → Receives verification email → Verifies email → Can log in
```

---

## 📝 Required Frontend Changes

### 1. Update Signup Flow

#### Old Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

#### New Response:
```json
{
  "message": "Account created successfully. Please check your email to verify your account.",
  "email": "user@example.com",
  "username": "johndoe"
}
```

#### Frontend Code Update:

**Before:**
```typescript
// Old signup handler
const handleSignup = async (email: string, username: string, password: string) => {
  const response = await fetch(`${API_URL}/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, username, password })
  });
  
  const data = await response.json();
  
  // Old: Immediately save token and redirect
  localStorage.setItem('token', data.access_token);
  router.push('/dashboard');
};
```

**After:**
```typescript
// New signup handler
const handleSignup = async (email: string, username: string, password: string) => {
  const response = await fetch(`${API_URL}/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, username, password })
  });
  
  const data = await response.json();
  
  // New: Show verification message, don't redirect yet
  setVerificationEmail(data.email);
  setShowVerificationMessage(true);
  // Stay on page or redirect to verification-pending page
};
```

---

### 2. Add Verification Pending Page/Message

Create a new page or component to show after signup:

```tsx
// components/VerificationPending.tsx or pages/verify-email-pending.tsx

export default function VerificationPending({ email }: { email: string }) {
  return (
    <div className="verification-pending">
      <h1>Check Your Email</h1>
      <p>
        We've sent a verification link to <strong>{email}</strong>
      </p>
      <p>
        Click the link in the email to verify your account and access the system.
      </p>
      
      <div className="info-box">
        <p>📧 Check your spam folder if you don't see the email</p>
        <p>⏱️ The link expires in 24 hours</p>
      </div>
      
      <button onClick={() => handleResendVerification(email)}>
        Resend Verification Email
      </button>
      
      <a href="/login">Back to Login</a>
    </div>
  );
}
```

---

### 3. Update Login Flow

Handle the new email verification error:

```typescript
const handleLogin = async (email: string, password: string) => {
  try {
    const response = await fetch(`${API_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    
    if (!response.ok) {
      const error = await response.json();
      
      // NEW: Handle unverified email
      if (response.status === 403 && error.detail.includes('Email not verified')) {
        setError('Please verify your email before logging in. Check your inbox.');
        setShowResendButton(true);
        setUserEmail(email);
        return;
      }
      
      throw new Error(error.detail || 'Login failed');
    }
    
    const data = await response.json();
    localStorage.setItem('token', data.access_token);
    router.push('/dashboard');
    
  } catch (error) {
    setError(error.message);
  }
};
```

---

### 4. Add Resend Verification Function

```typescript
const handleResendVerification = async (email: string) => {
  try {
    setResending(true);
    
    const response = await fetch(`${API_URL}/auth/resend-verification`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    
    const data = await response.json();
    
    setSuccess('Verification email sent! Check your inbox.');
    
  } catch (error) {
    setError('Failed to resend verification email');
  } finally {
    setResending(false);
  }
};
```

---

### 5. Handle Email Verification Callback

When users click the verification link in their email, they're redirected to your frontend with a query parameter:

```
https://yourdomain.com/login?verified=true
```

Handle this in your login page:

```tsx
// pages/login.tsx or app/login/page.tsx

import { useSearchParams } from 'next/navigation'; // Next.js 13+
// or
import { useRouter } from 'next/router'; // Next.js 12

export default function LoginPage() {
  const searchParams = useSearchParams();
  const verified = searchParams.get('verified');
  
  useEffect(() => {
    if (verified === 'true') {
      setSuccessMessage('✅ Email verified! You can now log in.');
      // Optionally auto-focus the email input
    }
  }, [verified]);
  
  return (
    <div>
      {verified === 'true' && (
        <div className="success-banner">
          ✅ Email verified successfully! Please log in to continue.
        </div>
      )}
      
      {/* Your login form */}
    </div>
  );
}
```

---

### 6. Update API Types (TypeScript)

```typescript
// types/auth.ts

export interface SignupRequest {
  email: string;
  username: string;
  password: string;
}

// OLD
export interface SignupResponse {
  access_token: string;
  token_type: string;
}

// NEW
export interface SignupResponse {
  message: string;
  email: string;
  username: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface ResendVerificationRequest {
  email: string;
}

export interface ResendVerificationResponse {
  message: string;
}
```

---

## 🎨 Example Complete Flow (React/Next.js)

### Signup Page

```tsx
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function SignupPage() {
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [showVerification, setShowVerification] = useState(false);
  const [error, setError] = useState('');
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, username, password }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Signup failed');
      }

      const data = await response.json();
      
      // Show verification message instead of redirecting
      setShowVerification(true);

    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (showVerification) {
    return (
      <div className="verification-screen">
        <h1>Check Your Email</h1>
        <p>We've sent a verification link to <strong>{email}</strong></p>
        <p>Click the link to verify your account and get started.</p>
        
        <div className="tips">
          <p>💡 Check your spam folder if you don't see it</p>
          <p>⏱️ The link expires in 24 hours</p>
        </div>

        <button onClick={() => router.push('/login')}>
          Go to Login
        </button>
      </div>
    );
  }

  return (
    <div className="signup-form">
      <h1>Create Account</h1>
      
      {error && <div className="error">{error}</div>}
      
      <form onSubmit={handleSubmit}>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        
        <input
          type="text"
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
        />
        
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        
        <button type="submit" disabled={loading}>
          {loading ? 'Creating Account...' : 'Sign Up'}
        </button>
      </form>
      
      <p>
        Already have an account? <a href="/login">Log in</a>
      </p>
    </div>
  );
}
```

### Login Page

```tsx
'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showResend, setShowResend] = useState(false);
  const router = useRouter();
  const searchParams = useSearchParams();
  
  const verified = searchParams.get('verified');

  useEffect(() => {
    if (verified === 'true') {
      // Show success message for verified email
      setError(''); // Clear any errors
    }
  }, [verified]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setShowResend(false);

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        const data = await response.json();
        
        // Handle unverified email
        if (response.status === 403) {
          setError('Email not verified. Please check your inbox for the verification link.');
          setShowResend(true);
          throw new Error('Email not verified');
        }
        
        throw new Error(data.detail || 'Login failed');
      }

      const data = await response.json();
      localStorage.setItem('token', data.access_token);
      router.push('/dashboard');

    } catch (err: any) {
      if (!error) { // Only set if not already set
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/resend-verification`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });

      if (response.ok) {
        setError('');
        alert('Verification email sent! Check your inbox.');
      }
    } catch (err) {
      console.error('Failed to resend:', err);
    }
  };

  return (
    <div className="login-form">
      <h1>Log In</h1>
      
      {verified === 'true' && (
        <div className="success-banner">
          ✅ Email verified successfully! You can now log in.
        </div>
      )}
      
      {error && <div className="error">{error}</div>}
      
      {showResend && (
        <button onClick={handleResend} className="resend-btn">
          Resend Verification Email
        </button>
      )}
      
      <form onSubmit={handleLogin}>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        
        <button type="submit" disabled={loading}>
          {loading ? 'Logging in...' : 'Log In'}
        </button>
      </form>
      
      <p>
        Don't have an account? <a href="/signup">Sign up</a>
      </p>
    </div>
  );
}
```

---

## 🎯 Environment Variables

Add to your frontend `.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

Or for production:

```env
NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api
```

---

## ✅ Checklist

Frontend changes needed:

- [ ] Update signup handler to show verification message
- [ ] Create verification pending page/component
- [ ] Update login handler to catch 403 error
- [ ] Add resend verification button/function
- [ ] Handle `?verified=true` query param on login page
- [ ] Update TypeScript types (if using TS)
- [ ] Test complete flow: signup → verify → login
- [ ] Update any auth context/store
- [ ] Remove auto-login after signup
- [ ] Add user feedback messages

---

## 🧪 Testing Checklist

- [ ] Sign up new user → See "check email" message
- [ ] Try to login before verifying → See error + resend button
- [ ] Click resend → Receive new email
- [ ] Click verification link → Redirected to login with success message
- [ ] Login after verification → Successfully enter app
- [ ] Try verification link again → See "already verified" message

---

## 📱 UI/UX Recommendations

### Success Messages
- ✅ "Account created! Check your email to verify."
- ✅ "Email verified successfully! You can now log in."
- ✅ "Verification email sent! Check your inbox."

### Error Messages
- ❌ "Email not verified. Please check your inbox for the verification link."
- ❌ "Invalid or expired verification token. Please request a new one."
- ❌ "Email already registered."

### Loading States
- "Creating account..."
- "Logging in..."
- "Sending verification email..."

### Empty States
- Show email icon when waiting for verification
- Animated envelope or loading indicator
- Clear call-to-action buttons

---

## 🎨 Optional: Verification Status Page

Create a dedicated route for handling verification:

```tsx
// app/verify-email/page.tsx

'use client';

import { useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';

export default function VerifyEmailPage() {
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('');
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get('token');

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setMessage('Invalid verification link');
      return;
    }

    // Call backend verification endpoint
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/verify-email?token=${token}`)
      .then(res => res.json())
      .then(data => {
        setStatus('success');
        setMessage(data.message);
        // Redirect to login after 3 seconds
        setTimeout(() => router.push('/login?verified=true'), 3000);
      })
      .catch(err => {
        setStatus('error');
        setMessage('Verification failed. The link may be expired.');
      });
  }, [token, router]);

  return (
    <div className="verify-page">
      {status === 'loading' && <div>Verifying your email...</div>}
      {status === 'success' && (
        <div className="success">
          <h1>✅ Email Verified!</h1>
          <p>{message}</p>
          <p>Redirecting to login...</p>
        </div>
      )}
      {status === 'error' && (
        <div className="error">
          <h1>❌ Verification Failed</h1>
          <p>{message}</p>
          <button onClick={() => router.push('/login')}>Go to Login</button>
        </div>
      )}
    </div>
  );
}
```

---

## 🔗 Summary

**Minimum required changes:**
1. Update signup response handling
2. Update login error handling
3. Add resend verification function
4. Handle `?verified=true` query parameter

**Recommended additions:**
5. Dedicated verification pending page
6. Verification status page
7. Better error messages and UI feedback

---

Your backend is ready! Now update your frontend with these changes and you'll have a complete email verification flow. 🚀

