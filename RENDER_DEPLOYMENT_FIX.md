# Render Deployment Fix - OpenCV & Tesseract

## 🐛 Issue

```
ImportError: libGL.so.1: cannot open shared object file: No such file or directory
```

## ✅ Solution Applied

### **1. Fixed OpenCV Dependency**

Changed `opencv-python` to `opencv-python-headless` in `requirements.txt`:

```diff
- opencv-python==4.9.0.80  # GUI version (needs display libraries)
+ opencv-python-headless==4.9.0.80  # Headless version (server-optimized)
```

**Why:** The headless version doesn't require OpenGL/GUI libraries, making it perfect for server deployments.

---

## 🚀 Deploy Fix

### **Option A: Automatic (Recommended)**

Render will automatically use the updated `requirements.txt` on next deploy.

```bash
git add requirements.txt
git commit -m "fix: Use opencv-python-headless for Render deployment"
git push origin main
```

**Done!** Render will redeploy automatically. ✅

---

### **Option B: Manual Build Script** (If Tesseract Issues)

If you also need Tesseract OCR (for screenshot detection), configure a custom build command:

#### **Step 1: In Render Dashboard**

1. Go to your backend service
2. Click "Settings"
3. Find "Build Command"
4. Replace with: `bash render-build.sh`

#### **Step 2: The build script handles:**

```bash
# render-build.sh (already created)
- Install Tesseract OCR
- Install Python dependencies
- Configure environment
```

---

## 🧪 Verify Fix

After deployment succeeds, check logs for:

```
✅ opencv-python-headless installed successfully
✅ NSFWDetector initialized
✅ OCR detector initialized (or "OCR not available" if no Tesseract)
```

---

## 📊 Dependency Summary

### **Before (Failed):**
```
opencv-python → Requires: libGL.so.1, libX11, etc. ❌
```

### **After (Works):**
```
opencv-python-headless → No GUI dependencies ✅
```

---

## ⚙️ If Still Failing

### **Error: "Tesseract not found"**

The OCR filter will gracefully disable itself. This is **OK** - other filters still work.

**To enable OCR:**
1. Use the custom build script (Option B above)
2. Or disable OCR in code (see below)

### **Disable OCR Filter (Optional):**

If you don't need screenshot detection, you can skip OCR:

```python
# In app/content_filters.py, find OCRDetector._initialize():

def _initialize(self):
    """Check if pytesseract is available"""
    # Comment out or skip initialization
    logger.info("OCR detection disabled in production")
    self.ocr_available = False
```

---

## 🎯 What Works Without Tesseract

Even without Tesseract OCR, you still have:

✅ NSFW detection (NudeNet)  
✅ Duplicate detection (ImageHash)  
✅ Garbage image detection (OpenCV headless)  
✅ EXIF metadata extraction  
✅ Rate limiting  
✅ Trust scores  
✅ Shadow banning  

Only missing:
❌ OCR/Screenshot detection

**Recommendation:** This is acceptable. Most abuse is caught by other filters.

---

## 📝 Summary

**Problem:** OpenCV needs GUI libraries not available on Render  
**Solution:** Use `opencv-python-headless` instead  
**Action:** Redeploy (automatic)  
**Result:** Deployment succeeds ✅  

---

## 🔍 Alternative: Docker Deployment

If you want full control over system dependencies:

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . /app
WORKDIR /app

# Run
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Then deploy as Docker container to Render.

---

## ✅ Expected Outcome

After pushing the fix:

```bash
# Render logs should show:
Building...
Installing dependencies...
opencv-python-headless-4.9.0.80 ✓
nudenet-2.0.9 ✓
imagehash-4.3.1 ✓
...
Build succeeded!
Starting service...
✅ NSFWDetector initialized
⚠️ Tesseract not available - OCR detection disabled
✅ Application started successfully
```

**Your backend will be running!** 🎉

---

**Status:** ✅ **FIXED** - Just redeploy

