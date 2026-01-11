# Storage Migration: AWS S3 → Supabase Storage

## What Changed?

Your FailState backend has been **migrated from AWS S3 to Supabase Storage** for handling image and video uploads.

## Why This Change?

✅ **Simplified Setup**: No need for AWS account or credentials  
✅ **Cost Effective**: Included in Supabase free tier (1GB storage)  
✅ **Integrated Solution**: Everything in one place (database + storage)  
✅ **Better for Development**: Easier to set up and manage  
✅ **Built-in Features**: Image transformation, CDN, and more

## What Was Removed

### 1. Environment Variables (ENV_TEMPLATE.txt)
**Removed:**
```env
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_S3_BUCKET=your-bucket-name
AWS_REGION=us-east-1
```

**Replaced with:**
```env
# No additional config needed!
# Uses existing SUPABASE_URL and SUPABASE_SERVICE_KEY
```

### 2. Configuration (app/config.py)
**Removed AWS-related settings:**
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_S3_BUCKET`
- `AWS_REGION`

### 3. Dependencies (requirements.txt)
**Removed:**
- `boto3==1.34.22` (AWS SDK)

## What Was Added

### 1. Storage Service (`app/storage.py`)
New comprehensive storage service with:
- ✅ Image upload with validation (max 5MB)
- ✅ Video upload with validation (max 50MB)
- ✅ Automatic image optimization and resizing
- ✅ File type validation (JPEG, PNG, WebP, GIF, MP4, WebM, MOV)
- ✅ Unique filename generation to prevent conflicts
- ✅ File deletion functionality
- ✅ Thumbnail URL generation

### 2. Upload Endpoints (`app/routers/uploads.py`)
New API endpoints:
- `POST /api/uploads/image` - Upload images
- `POST /api/uploads/video` - Upload videos
- `DELETE /api/uploads/file` - Delete files
- `GET /api/uploads/health` - Storage health check

### 3. Documentation (`SUPABASE_STORAGE_SETUP.md`)
Complete guide covering:
- How to create storage buckets in Supabase
- Setting up bucket policies
- Using upload endpoints
- Frontend integration examples
- Image optimization tips
- Troubleshooting

### 4. Updated Documentation
- `SUPABASE_SETUP.md` - Added storage setup step
- `QUICK_START.md` - Added upload endpoints and storage reference
- `ENV_TEMPLATE.txt` - Simplified storage configuration

## How to Use the New System

### Step 1: Create Storage Buckets
Go to Supabase Dashboard → Storage → Create two buckets:
1. `issue-images` (Public)
2. `issue-videos` (Public)

**👉 See `SUPABASE_STORAGE_SETUP.md` for detailed instructions**

### Step 2: Upload Files
```bash
# Upload an image
curl -X POST http://localhost:8000/api/uploads/image \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/path/to/image.jpg"

# Response:
{
  "url": "https://xxxxx.supabase.co/storage/v1/object/public/issue-images/123456_abc_photo.jpg",
  "path": "123456_abc_photo.jpg",
  "bucket": "issue-images"
}
```

### Step 3: Use in Your App
```javascript
// Upload image
const formData = new FormData();
formData.append('file', imageFile);

const uploadResponse = await fetch('/api/uploads/image', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` },
  body: formData
});

const { url } = await uploadResponse.json();

// Create issue with image
await fetch('/api/issues', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    title: "Pothole",
    description: "Large pothole",
    category: "infrastructure",
    image_url: url,  // ← Use uploaded image URL
    location: { /* ... */ }
  })
});
```

## Features of New Storage System

### 🖼️ Automatic Image Optimization
- Resizes images larger than 1920px
- Compresses with 85% quality
- Converts RGBA to RGB for JPEG compatibility
- Reduces file sizes automatically

### 🔒 File Validation
- Checks file types (only allowed formats)
- Enforces size limits (5MB images, 50MB videos)
- Generates unique filenames to prevent conflicts
- Validates extensions match content types

### 🌐 CDN & Transformations
```
Original: https://xxx.supabase.co/.../photo.jpg
Thumbnail: https://xxx.supabase.co/.../photo.jpg?width=200&height=200
```

### 🎯 Two Storage Buckets
- `issue-images` - For photos/screenshots
- `issue-videos` - For video evidence

## Migration Checklist

If you're migrating from AWS S3:

- [ ] Remove AWS credentials from your `.env` file
- [ ] Create `issue-images` bucket in Supabase
- [ ] Create `issue-videos` bucket in Supabase
- [ ] Update frontend to use new upload endpoints
- [ ] Test image upload flow
- [ ] Test video upload flow
- [ ] (Optional) Migrate existing S3 files to Supabase

## Comparison: Before vs After

### Before (AWS S3)
```
❌ Requires AWS account
❌ Need to configure IAM permissions
❌ Separate credentials (AWS_ACCESS_KEY, AWS_SECRET_KEY)
❌ boto3 dependency (extra library)
❌ More complex setup
❌ Potential AWS costs
```

### After (Supabase Storage)
```
✅ Uses existing Supabase account
✅ Integrated with your database
✅ Uses existing Supabase credentials
✅ Built into supabase-py (already installed)
✅ Simple setup (just create buckets)
✅ Included in free tier
```

## Breaking Changes

⚠️ **None!** This was a pre-implementation change.

The AWS configuration was present but **not actually used anywhere** in the codebase. No existing functionality was broken.

## Need Help?

- **Storage Setup**: See `SUPABASE_STORAGE_SETUP.md`
- **API Reference**: http://localhost:8000/docs
- **Database Setup**: See `SUPABASE_SETUP.md`
- **Quick Start**: See `QUICK_START.md`

## Summary

You now have a **fully integrated storage solution** that:
- 📦 Stores all data in Supabase (database + files)
- 🚀 Works out of the box with existing credentials
- 💰 Costs nothing (free tier)
- 🔧 Requires minimal setup (just create buckets)
- ✨ Includes automatic image optimization
- 🌍 Has built-in CDN for fast delivery

**No AWS account needed! Everything runs on Supabase! 🎉**

