"""
Supabase Storage Service
Handles file uploads to Supabase Storage buckets
"""

from fastapi import UploadFile, HTTPException, status
from supabase import Client
from typing import Tuple, Optional
import uuid
from datetime import datetime
import os
from PIL import Image
import io

# Allowed file types
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "image/webp": [".webp"],
    "image/gif": [".gif"]
}

ALLOWED_VIDEO_TYPES = {
    "video/mp4": [".mp4"],
    "video/webm": [".webm"],
    "video/quicktime": [".mov"]
}

# File size limits (in bytes)
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50MB

# Storage buckets
IMAGES_BUCKET = "issue-images"
VIDEOS_BUCKET = "issue-videos"


def validate_file_type(file: UploadFile, allowed_types: dict) -> bool:
    """Validate if file type is allowed"""
    content_type = file.content_type
    filename = file.filename or ""
    file_ext = os.path.splitext(filename)[1].lower()
    
    if content_type not in allowed_types:
        return False
    
    allowed_extensions = allowed_types[content_type]
    return file_ext in allowed_extensions


def validate_file_size(file: UploadFile, max_size: int) -> bool:
    """Validate file size"""
    # Read file size
    file.file.seek(0, 2)  # Seek to end
    size = file.file.tell()
    file.file.seek(0)  # Reset to start
    
    return size <= max_size


def generate_unique_filename(original_filename: str) -> str:
    """Generate a unique filename to prevent conflicts"""
    timestamp = int(datetime.utcnow().timestamp())
    unique_id = str(uuid.uuid4())[:8]
    file_ext = os.path.splitext(original_filename)[1].lower()
    
    # Remove extension from original name and clean it
    base_name = os.path.splitext(original_filename)[0]
    # Remove special characters, keep only alphanumeric and hyphens
    clean_name = "".join(c if c.isalnum() or c in ['-', '_'] else '_' for c in base_name)
    clean_name = clean_name[:50]  # Limit length
    
    return f"{timestamp}_{unique_id}_{clean_name}{file_ext}"


async def optimize_image(file: UploadFile, max_dimension: int = 1920) -> bytes:
    """
    Optimize image by resizing if too large and compressing
    Returns optimized image bytes
    """
    try:
        # Read original image
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        
        # Convert RGBA to RGB if needed (for JPEG)
        if image.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        
        # Resize if too large
        if max(image.size) > max_dimension:
            ratio = max_dimension / max(image.size)
            new_size = tuple(int(dim * ratio) for dim in image.size)
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        # Save optimized image
        output = io.BytesIO()
        image_format = 'JPEG' if file.content_type == 'image/jpeg' else image.format or 'PNG'
        image.save(output, format=image_format, quality=85, optimize=True)
        output.seek(0)
        
        return output.read()
    except Exception as e:
        # If optimization fails, return original
        await file.seek(0)
        return await file.read()


async def upload_image(supabase: Client, file: UploadFile, user_id: str) -> Tuple[str, str]:
    """
    Upload image to Supabase Storage
    
    Args:
        supabase: Supabase client
        file: Uploaded file
        user_id: ID of user uploading the file
    
    Returns:
        Tuple of (public_url, file_path)
    
    Raises:
        HTTPException: If validation or upload fails
    """
    # Validate file type
    if not validate_file_type(file, ALLOWED_IMAGE_TYPES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_IMAGE_TYPES.keys())}"
        )
    
    # Validate file size
    if not validate_file_size(file, MAX_IMAGE_SIZE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {MAX_IMAGE_SIZE / (1024*1024)}MB"
        )
    
    try:
        # Generate unique filename
        unique_filename = generate_unique_filename(file.filename or "image.jpg")
        
        # Optimize image
        optimized_data = await optimize_image(file, max_dimension=1920)
        
        # Upload to Supabase Storage
        result = supabase.storage.from_(IMAGES_BUCKET).upload(
            path=unique_filename,
            file=optimized_data,
            file_options={
                "content-type": file.content_type,
                "cache-control": "3600",
                "upsert": "false"
            }
        )
        
        # Get public URL
        public_url = supabase.storage.from_(IMAGES_BUCKET).get_public_url(unique_filename)
        
        return public_url, unique_filename
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload image: {str(e)}"
        )


async def upload_video(supabase: Client, file: UploadFile, user_id: str) -> Tuple[str, str]:
    """
    Upload video to Supabase Storage
    
    Args:
        supabase: Supabase client
        file: Uploaded file
        user_id: ID of user uploading the file
    
    Returns:
        Tuple of (public_url, file_path)
    
    Raises:
        HTTPException: If validation or upload fails
    """
    # Validate file type
    if not validate_file_type(file, ALLOWED_VIDEO_TYPES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_VIDEO_TYPES.keys())}"
        )
    
    # Validate file size
    if not validate_file_size(file, MAX_VIDEO_SIZE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {MAX_VIDEO_SIZE / (1024*1024)}MB"
        )
    
    try:
        # Generate unique filename
        unique_filename = generate_unique_filename(file.filename or "video.mp4")
        
        # Read file contents
        contents = await file.read()
        
        # Upload to Supabase Storage
        result = supabase.storage.from_(VIDEOS_BUCKET).upload(
            path=unique_filename,
            file=contents,
            file_options={
                "content-type": file.content_type,
                "cache-control": "3600",
                "upsert": "false"
            }
        )
        
        # Get public URL
        public_url = supabase.storage.from_(VIDEOS_BUCKET).get_public_url(unique_filename)
        
        return public_url, unique_filename
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload video: {str(e)}"
        )


async def delete_file(supabase: Client, bucket: str, file_path: str) -> bool:
    """
    Delete a file from Supabase Storage
    
    Args:
        supabase: Supabase client
        bucket: Bucket name
        file_path: Path to file in bucket
    
    Returns:
        True if successful
    """
    try:
        supabase.storage.from_(bucket).remove([file_path])
        return True
    except Exception:
        return False


def get_image_thumbnail_url(image_url: str, width: int = 200, height: int = 200) -> str:
    """
    Generate thumbnail URL for an image using Supabase transformation
    
    Args:
        image_url: Original image URL
        width: Desired width
        height: Desired height
    
    Returns:
        Thumbnail URL with transformation parameters
    """
    if not image_url:
        return ""
    
    # Add transformation parameters to URL
    separator = "&" if "?" in image_url else "?"
    return f"{image_url}{separator}width={width}&height={height}&resize=cover"

