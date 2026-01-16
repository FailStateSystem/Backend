"""
Pre-Ingestion Content Filtering Service
Blocks NSFW, duplicates, OCR/screenshots, garbage images, etc.
This runs BEFORE image upload and BEFORE AI enrichment
"""

import io
import logging
import hashlib
from typing import Tuple, Optional, Dict, Any
from datetime import datetime, timedelta
from PIL import Image
import imagehash
import cv2
import numpy as np
import exifread

logger = logging.getLogger(__name__)

# ============================================
# FILTER RESULT CLASS
# ============================================

class FilterResult:
    """Result of content filtering"""
    def __init__(
        self,
        passed: bool,
        filter_name: str,
        reason: str = "",
        severity: str = "low",
        details: Dict[str, Any] = None
    ):
        self.passed = passed
        self.filter_name = filter_name
        self.reason = reason
        self.severity = severity  # low, medium, high, critical
        self.details = details or {}
    
    def __bool__(self):
        return self.passed


# ============================================
# NSFW DETECTION
# ============================================

class NSFWDetector:
    """Detects NSFW content using NudeNet"""
    
    def __init__(self):
        self.detector = None
        self._initialize()
    
    def _initialize(self):
        """Lazy load NudeNet"""
        try:
            from nudenet import NudeDetector
            self.detector = NudeDetector()
            logger.info("✅ NSFWDetector initialized")
        except ImportError:
            logger.warning("⚠️ NudeNet not installed - NSFW detection disabled")
        except Exception as e:
            logger.error(f"Failed to initialize NSFWDetector: {e}")
    
    async def check(self, image_bytes: bytes) -> FilterResult:
        """Check if image is NSFW"""
        if not self.detector:
            logger.warning("NSFW detector not available - skipping check")
            return FilterResult(True, "nsfw", "Detector not available")
        
        try:
            # Save to temp file (NudeNet requires file path)
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp.write(image_bytes)
                tmp_path = tmp.name
            
            # Detect
            detections = self.detector.detect(tmp_path)
            
            # Clean up
            import os
            os.unlink(tmp_path)
            
            # Check results
            nsfw_labels = ['FEMALE_GENITALIA_EXPOSED', 'MALE_GENITALIA_EXPOSED', 
                          'FEMALE_BREAST_EXPOSED', 'BUTTOCKS_EXPOSED', 'ANUS_EXPOSED']
            
            nsfw_detected = any(
                det['class'] in nsfw_labels and det['score'] > 0.6
                for det in detections
            )
            
            if nsfw_detected:
                return FilterResult(
                    False,
                    "nsfw",
                    "NSFW content detected",
                    "critical",
                    {"detections": detections}
                )
            
            return FilterResult(True, "nsfw", "Clean")
            
        except Exception as e:
            logger.error(f"NSFW detection error: {e}")
            # Fail open (allow) on error to avoid blocking legitimate content
            return FilterResult(True, "nsfw", f"Error: {str(e)}")


# ============================================
# DUPLICATE DETECTION
# ============================================

class DuplicateDetector:
    """Detects duplicate/near-duplicate images using perceptual hashing"""
    
    def __init__(self, supabase_client):
        self.supabase = supabase_client
    
    def generate_hashes(self, image_bytes: bytes) -> Dict[str, str]:
        """Generate multiple perceptual hashes"""
        try:
            img = Image.open(io.BytesIO(image_bytes))
            
            return {
                'perceptual': str(imagehash.phash(img)),
                'average': str(imagehash.average_hash(img)),
                'difference': str(imagehash.dhash(img))
            }
        except Exception as e:
            logger.error(f"Hash generation error: {e}")
            return {}
    
    async def check(
        self,
        image_bytes: bytes,
        user_id: str,
        ip_address: str
    ) -> FilterResult:
        """Check for duplicate images"""
        try:
            # Generate hashes
            hashes = self.generate_hashes(image_bytes)
            if not hashes:
                return FilterResult(True, "duplicate", "Hash generation failed")
            
            # Check against recent uploads (last 30 days)
            cutoff_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
            
            # Check same user uploads
            user_duplicates = self.supabase.table("image_hashes").select("*").eq(
                "user_id", user_id
            ).eq(
                "perceptual_hash", hashes['perceptual']
            ).gt("uploaded_at", cutoff_date).execute()
            
            if user_duplicates.data:
                return FilterResult(
                    False,
                    "duplicate",
                    "You've already uploaded this image",
                    "medium",
                    {"match_type": "exact_user", "count": len(user_duplicates.data)}
                )
            
            # Check same IP uploads
            ip_duplicates = self.supabase.table("image_hashes").select("*").eq(
                "ip_address", ip_address
            ).eq(
                "perceptual_hash", hashes['perceptual']
            ).gt("uploaded_at", cutoff_date).execute()
            
            if ip_duplicates.data:
                return FilterResult(
                    False,
                    "duplicate",
                    "This image has been uploaded from your network recently",
                    "high",
                    {"match_type": "exact_ip", "count": len(ip_duplicates.data)}
                )
            
            # TODO: Check for near-duplicates using Hamming distance
            # This would require fetching all recent hashes and comparing
            
            return FilterResult(True, "duplicate", "No duplicates found")
            
        except Exception as e:
            logger.error(f"Duplicate detection error: {e}")
            return FilterResult(True, "duplicate", f"Error: {str(e)}")
    
    async def store_hash(
        self,
        image_bytes: bytes,
        user_id: str,
        ip_address: str,
        image_url: Optional[str] = None,
        issue_id: Optional[str] = None
    ):
        """Store image hash for future duplicate detection"""
        try:
            hashes = self.generate_hashes(image_bytes)
            if not hashes:
                return
            
            self.supabase.table("image_hashes").insert({
                "user_id": user_id,
                "perceptual_hash": hashes['perceptual'],
                "average_hash": hashes['average'],
                "difference_hash": hashes['difference'],
                "image_url": image_url,
                "issue_id": issue_id,
                "ip_address": ip_address
            }).execute()
            
        except Exception as e:
            logger.error(f"Failed to store image hash: {e}")


# ============================================
# OCR / SCREENSHOT DETECTION
# ============================================

class OCRDetector:
    """Detects screenshots and memes using OCR"""
    
    def __init__(self):
        self.ocr_available = False
        self._initialize()
    
    def _initialize(self):
        """Check if pytesseract is available"""
        try:
            import pytesseract
            # Test if tesseract is installed
            pytesseract.get_tesseract_version()
            self.ocr_available = True
            logger.info("✅ OCR detector initialized")
        except Exception as e:
            logger.warning(f"⚠️ Tesseract not available - OCR detection disabled: {e}")
    
    async def check(self, image_bytes: bytes) -> FilterResult:
        """Check if image is a screenshot/meme"""
        if not self.ocr_available:
            logger.debug("OCR not available - skipping check")
            return FilterResult(True, "ocr", "OCR not available")
        
        try:
            import pytesseract
            
            # Convert to PIL Image
            img = Image.open(io.BytesIO(image_bytes))
            
            # Extract text
            text = pytesseract.image_to_string(img)
            text_length = len(text.strip())
            
            # Check for UI patterns (common in screenshots)
            ui_indicators = ['button', 'click', 'menu', 'settings', 'login', 
                           'password', 'username', 'submit', 'cancel', 'ok']
            ui_count = sum(1 for word in ui_indicators if word.lower() in text.lower())
            
            # Thresholds
            if text_length > 500:  # Lots of text = likely screenshot/document
                return FilterResult(
                    False,
                    "ocr",
                    "Image contains excessive text (likely screenshot or document)",
                    "medium",
                    {"text_length": text_length}
                )
            
            if ui_count >= 3:  # Multiple UI elements = likely screenshot
                return FilterResult(
                    False,
                    "ocr",
                    "Image appears to be a screenshot",
                    "medium",
                    {"ui_indicators": ui_count}
                )
            
            return FilterResult(True, "ocr", "No screenshot detected")
            
        except Exception as e:
            logger.error(f"OCR detection error: {e}")
            return FilterResult(True, "ocr", f"Error: {str(e)}")


# ============================================
# GARBAGE IMAGE DETECTION
# ============================================

class GarbageDetector:
    """Detects low-quality/garbage images"""
    
    async def check(self, image_bytes: bytes) -> FilterResult:
        """Check if image is garbage (pure black, pure white, blurry, etc.)"""
        try:
            # Convert to numpy array
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                return FilterResult(False, "garbage", "Invalid image", "medium")
            
            # Convert to grayscale for analysis
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Check 1: Pure black or pure white
            mean_brightness = np.mean(gray)
            if mean_brightness < 5:
                return FilterResult(False, "garbage", "Image is pure black", "medium")
            if mean_brightness > 250:
                return FilterResult(False, "garbage", "Image is pure white", "medium")
            
            # Check 2: Very low contrast
            std_dev = np.std(gray)
            if std_dev < 10:
                return FilterResult(
                    False,
                    "garbage",
                    "Image has very low contrast",
                    "medium",
                    {"std_dev": float(std_dev)}
                )
            
            # Check 3: Blur detection (Laplacian variance)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            if laplacian_var < 50:
                return FilterResult(
                    False,
                    "garbage",
                    "Image is extremely blurry",
                    "low",
                    {"blur_score": float(laplacian_var)}
                )
            
            # Check 4: Entropy (information content)
            from skimage.filters.rank import entropy
            from skimage.morphology import disk
            entropy_img = entropy(gray, disk(5))
            mean_entropy = np.mean(entropy_img)
            
            if mean_entropy < 2.0:
                return FilterResult(
                    False,
                    "garbage",
                    "Image has very low information content",
                    "medium",
                    {"entropy": float(mean_entropy)}
                )
            
            # Check 5: Image too small
            height, width = img.shape[:2]
            if height < 100 or width < 100:
                return FilterResult(
                    False,
                    "garbage",
                    f"Image too small ({width}x{height})",
                    "low",
                    {"width": width, "height": height}
                )
            
            return FilterResult(True, "garbage", "Image quality OK")
            
        except Exception as e:
            logger.error(f"Garbage detection error: {e}")
            return FilterResult(True, "garbage", f"Error: {str(e)}")


# ============================================
# EXIF METADATA CHECKER
# ============================================

class EXIFChecker:
    """Checks and extracts EXIF metadata"""
    
    async def check(self, image_bytes: bytes) -> FilterResult:
        """Check EXIF metadata"""
        try:
            # Read EXIF data
            tags = exifread.process_file(io.BytesIO(image_bytes), details=False)
            
            metadata = {
                'has_exif': len(tags) > 0,
                'has_gps': any('GPS' in str(tag) for tag in tags.keys()),
                'has_camera': any('Image Model' in str(tag) or 'Image Make' in str(tag) for tag in tags.keys()),
                'has_timestamp': 'EXIF DateTimeOriginal' in tags or 'Image DateTime' in tags
            }
            
            # Extract useful metadata
            if 'Image Make' in tags:
                metadata['camera_make'] = str(tags['Image Make'])
            if 'Image Model' in tags:
                metadata['camera_model'] = str(tags['Image Model'])
            if 'EXIF DateTimeOriginal' in tags:
                metadata['timestamp'] = str(tags['EXIF DateTimeOriginal'])
            
            # Suspicious if NO metadata at all (could be edited/generated)
            if not metadata['has_exif']:
                return FilterResult(
                    True,  # Still pass, but flag it
                    "exif",
                    "No EXIF data found (possible edited/generated image)",
                    "low",
                    metadata
                )
            
            # High-quality camera metadata increases trust
            if metadata['has_camera'] and metadata['has_timestamp']:
                return FilterResult(
                    True,
                    "exif",
                    "Good metadata present",
                    "low",
                    metadata
                )
            
            return FilterResult(True, "exif", "EXIF checked", "low", metadata)
            
        except Exception as e:
            logger.error(f"EXIF check error: {e}")
            return FilterResult(True, "exif", f"Error: {str(e)}")


# ============================================
# MAIN CONTENT FILTER ORCHESTRATOR
# ============================================

class ContentFilterService:
    """Orchestrates all content filters in the correct order"""
    
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.nsfw_detector = NSFWDetector()
        self.duplicate_detector = DuplicateDetector(supabase_client)
        self.ocr_detector = OCRDetector()
        self.garbage_detector = GarbageDetector()
        self.exif_checker = EXIFChecker()
    
    async def run_all_filters(
        self,
        image_bytes: bytes,
        user_id: str,
        ip_address: str
    ) -> Tuple[bool, Dict[str, FilterResult]]:
        """
        Run all content filters in order
        
        Returns:
            (all_passed, results_dict)
        """
        results = {}
        
        # 1. NSFW Detection (CRITICAL - must pass)
        logger.info(f"🔍 Running NSFW filter for user {user_id}")
        nsfw_result = await self.nsfw_detector.check(image_bytes)
        results['nsfw'] = nsfw_result
        if not nsfw_result.passed:
            logger.warning(f"❌ NSFW detected for user {user_id}")
            return False, results
        
        # 2. Duplicate Detection (HIGH - must pass)
        logger.info(f"🔍 Running duplicate filter for user {user_id}")
        duplicate_result = await self.duplicate_detector.check(image_bytes, user_id, ip_address)
        results['duplicate'] = duplicate_result
        if not duplicate_result.passed:
            logger.warning(f"❌ Duplicate detected for user {user_id}")
            return False, results
        
        # 3. OCR / Screenshot Detection (MEDIUM - must pass)
        logger.info(f"🔍 Running OCR filter for user {user_id}")
        ocr_result = await self.ocr_detector.check(image_bytes)
        results['ocr'] = ocr_result
        if not ocr_result.passed:
            logger.warning(f"❌ Screenshot/OCR detected for user {user_id}")
            return False, results
        
        # 4. Garbage Image Detection (MEDIUM - must pass)
        logger.info(f"🔍 Running garbage filter for user {user_id}")
        garbage_result = await self.garbage_detector.check(image_bytes)
        results['garbage'] = garbage_result
        if not garbage_result.passed:
            logger.warning(f"❌ Garbage image detected for user {user_id}")
            return False, results
        
        # 5. EXIF Metadata Check (INFO ONLY - always passes)
        logger.info(f"🔍 Running EXIF check for user {user_id}")
        exif_result = await self.exif_checker.check(image_bytes)
        results['exif'] = exif_result
        
        logger.info(f"✅ All filters passed for user {user_id}")
        return True, results
    
    async def store_image_hash(
        self,
        image_bytes: bytes,
        user_id: str,
        ip_address: str,
        image_url: Optional[str] = None,
        issue_id: Optional[str] = None
    ):
        """Store image hash after successful upload"""
        await self.duplicate_detector.store_hash(
            image_bytes, user_id, ip_address, image_url, issue_id
        )

