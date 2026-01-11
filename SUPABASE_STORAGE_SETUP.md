# Supabase Storage Setup Guide

This guide explains how to set up Supabase Storage for handling image and video uploads in FailState.

## Why Supabase Storage Instead of AWS S3?

Supabase Storage provides:
- ✅ **Integrated Solution**: All in one place with your database
- ✅ **No Extra Costs**: Included in Supabase free tier (1GB storage)
- ✅ **No AWS Account Needed**: Simpler setup
- ✅ **Built-in CDN**: Fast content delivery worldwide
- ✅ **Row Level Security**: Fine-grained access control
- ✅ **Image Transformation**: Automatic resizing and optimization

## Step 1: Create Storage Buckets in Supabase

1. Go to your Supabase Dashboard: https://app.supabase.com
2. Navigate to **Storage** (bucket icon in left sidebar)
3. Click **New bucket**

### Create Issue Images Bucket

- **Name**: `issue-images`
- **Public bucket**: ✅ (Enable this so images can be viewed publicly)
- **File size limit**: 5MB (or your preference)
- **Allowed MIME types**: `image/jpeg, image/png, image/webp, image/gif`

Click **Create bucket**

### Create Issue Videos Bucket

- **Name**: `issue-videos`
- **Public bucket**: ✅ (Enable this so videos can be viewed)
- **File size limit**: 50MB (or your preference)
- **Allowed MIME types**: `video/mp4, video/webm, video/quicktime`

Click **Create bucket**

## Step 2: Set Bucket Policies (Optional but Recommended)

For each bucket, you can set policies to control who can upload/delete files.

### Policy for Authenticated Users to Upload

```sql
-- Allow authenticated users to upload images
CREATE POLICY "Authenticated users can upload issue images"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (
  bucket_id = 'issue-images' AND
  auth.uid() IS NOT NULL
);

-- Allow authenticated users to upload videos
CREATE POLICY "Authenticated users can upload issue videos"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (
  bucket_id = 'issue-videos' AND
  auth.uid() IS NOT NULL
);

-- Allow anyone to view files (since buckets are public)
CREATE POLICY "Anyone can view issue images"
ON storage.objects FOR SELECT
TO public
USING (bucket_id = 'issue-images');

CREATE POLICY "Anyone can view issue videos"
ON storage.objects FOR SELECT
TO public
USING (bucket_id = 'issue-videos');

-- Only allow users to delete their own files
CREATE POLICY "Users can delete their own images"
ON storage.objects FOR DELETE
TO authenticated
USING (
  bucket_id = 'issue-images' AND
  owner = auth.uid()
);

CREATE POLICY "Users can delete their own videos"
ON storage.objects FOR DELETE
TO authenticated
USING (
  bucket_id = 'issue-videos' AND
  owner = auth.uid()
);
```

## Step 3: No Additional Environment Variables Needed!

Unlike AWS S3, Supabase Storage uses your existing Supabase credentials:
- `SUPABASE_URL` - Already configured
- `SUPABASE_SERVICE_KEY` - Already configured

No need for separate AWS keys! 🎉

## Step 4: Using the Upload API

The backend provides these endpoints:

### Upload Image
```bash
POST /api/uploads/image
Content-Type: multipart/form-data
Authorization: Bearer <your_jwt_token>

Body:
  file: <image_file>
```

### Upload Video
```bash
POST /api/uploads/video
Content-Type: multipart/form-data
Authorization: Bearer <your_jwt_token>

Body:
  file: <video_file>
```

### Response Format
```json
{
  "url": "https://xxxxx.supabase.co/storage/v1/object/public/issue-images/abc123.jpg",
  "path": "abc123.jpg",
  "bucket": "issue-images"
}
```

## Step 5: Using in Your Frontend

### Example: React Upload Component

```jsx
const uploadImage = async (file) => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch('http://localhost:8000/api/uploads/image', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${yourJwtToken}`
    },
    body: formData
  });

  const data = await response.json();
  return data.url; // Use this URL when creating an issue
};

// In your issue form:
const handleSubmit = async (e) => {
  e.preventDefault();
  
  // Upload image first
  const imageUrl = await uploadImage(selectedImageFile);
  
  // Then create issue with the image URL
  const issueData = {
    title: "Pothole on Main Street",
    description: "Large pothole causing issues",
    category: "roads",
    image_url: imageUrl, // <-- Use the uploaded image URL
    location: { /* ... */ }
  };
  
  await createIssue(issueData);
};
```

## File Naming Convention

Files are automatically renamed to prevent conflicts:
- Format: `{timestamp}_{uuid}_{original_filename}`
- Example: `1704123456_a1b2c3d4_pothole.jpg`

## File Size Limits

Default limits (can be changed in bucket settings):
- **Images**: 5MB
- **Videos**: 50MB

## Supported File Types

### Images
- JPEG/JPG (`.jpg`, `.jpeg`)
- PNG (`.png`)
- WebP (`.webp`)
- GIF (`.gif`)

### Videos
- MP4 (`.mp4`)
- WebM (`.webm`)
- QuickTime (`.mov`)

## Image Optimization (Automatic)

Supabase Storage automatically provides:
- **Resizing**: Add `?width=500&height=300` to URL
- **Quality**: Add `?quality=80` to reduce file size
- **Format conversion**: Add `?format=webp` for better compression

Example:
```
Original: https://xxx.supabase.co/storage/v1/object/public/issue-images/photo.jpg
Thumbnail: https://xxx.supabase.co/storage/v1/object/public/issue-images/photo.jpg?width=200&height=200
```

## Storage Quotas

### Free Tier
- **Storage**: 1GB
- **Transfer**: 2GB/month
- **API Requests**: 50,000/month

### Pro Tier ($25/month)
- **Storage**: 100GB
- **Transfer**: 200GB/month
- **API Requests**: Unlimited

## Viewing Your Files

1. Go to **Storage** in Supabase Dashboard
2. Click on `issue-images` or `issue-videos` bucket
3. Browse all uploaded files
4. Click any file to view/download/delete

## Troubleshooting

### Error: "Bucket not found"
- Make sure you created both buckets (`issue-images` and `issue-videos`)
- Check the bucket names match exactly (case-sensitive)

### Error: "File too large"
- Check your bucket's file size limit in Settings
- Compress images/videos before uploading
- Consider upgrading to Pro plan for larger files

### Error: "Invalid file type"
- Check allowed MIME types in bucket settings
- Make sure you're using supported file extensions

### Error: "Permission denied"
- Verify your JWT token is valid
- Check storage policies are set correctly
- Make sure buckets are marked as "Public"

## Security Best Practices

1. ✅ **Always validate file types** on the backend (already implemented)
2. ✅ **Scan uploaded files** for malware (consider adding)
3. ✅ **Set file size limits** to prevent abuse
4. ✅ **Use Row Level Security** policies for production
5. ✅ **Enable bucket versioning** for backup
6. ⚠️ **Never expose your SUPABASE_SERVICE_KEY** in frontend code

## Migration from AWS S3 (If Needed)

If you had AWS S3 data to migrate:

```python
# Example migration script
import boto3
from supabase import create_client

s3 = boto3.client('s3')
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# List all S3 objects
objects = s3.list_objects_v2(Bucket='your-bucket')

for obj in objects['Contents']:
    # Download from S3
    file_data = s3.get_object(Bucket='your-bucket', Key=obj['Key'])
    
    # Upload to Supabase
    supabase.storage.from_('issue-images').upload(
        obj['Key'],
        file_data['Body'].read()
    )
```

## Next Steps

1. ✅ Create storage buckets in Supabase
2. ✅ Set bucket policies (optional)
3. 🧪 Test upload endpoints at `http://localhost:8000/docs`
4. 📱 Integrate upload in your frontend
5. 🎨 Use image transformations for thumbnails

---

**Your images are now stored in Supabase Storage! No AWS needed! 🎉**

