"""
File Upload Endpoints
Handles image and video uploads to Supabase Storage
"""

from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File
from pydantic import BaseModel
from app.auth import get_current_user
from app.models import TokenData
from app.database import get_supabase
from app.storage import upload_image, upload_video, delete_file, IMAGES_BUCKET, VIDEOS_BUCKET

router = APIRouter()


class UploadResponse(BaseModel):
    """Response model for file upload"""
    url: str
    path: str
    bucket: str
    message: str = "File uploaded successfully"


class DeleteRequest(BaseModel):
    """Request model for file deletion"""
    file_path: str
    bucket: str


@router.post("/image", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_image_endpoint(
    file: UploadFile = File(..., description="Image file to upload (max 5MB)"),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Upload an image to Supabase Storage
    
    - **file**: Image file (JPEG, PNG, WebP, GIF)
    - **max size**: 5MB
    - **authentication**: Required
    
    Returns the public URL of the uploaded image
    """
    supabase = get_supabase()
    
    try:
        # Upload image
        public_url, file_path = await upload_image(supabase, file, current_user.user_id)
        
        return UploadResponse(
            url=public_url,
            path=file_path,
            bucket=IMAGES_BUCKET,
            message="Image uploaded successfully"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during upload: {str(e)}"
        )


@router.post("/video", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_video_endpoint(
    file: UploadFile = File(..., description="Video file to upload (max 50MB)"),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Upload a video to Supabase Storage
    
    - **file**: Video file (MP4, WebM, MOV)
    - **max size**: 50MB
    - **authentication**: Required
    
    Returns the public URL of the uploaded video
    """
    supabase = get_supabase()
    
    try:
        # Upload video
        public_url, file_path = await upload_video(supabase, file, current_user.user_id)
        
        return UploadResponse(
            url=public_url,
            path=file_path,
            bucket=VIDEOS_BUCKET,
            message="Video uploaded successfully"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during upload: {str(e)}"
        )


@router.delete("/file", status_code=status.HTTP_200_OK)
async def delete_file_endpoint(
    delete_request: DeleteRequest,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Delete a file from Supabase Storage
    
    - **file_path**: Path to the file in the bucket
    - **bucket**: Bucket name (issue-images or issue-videos)
    - **authentication**: Required
    
    Note: Users can only delete their own files (enforced by storage policies)
    """
    supabase = get_supabase()
    
    # Validate bucket name
    if delete_request.bucket not in [IMAGES_BUCKET, VIDEOS_BUCKET]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid bucket. Must be '{IMAGES_BUCKET}' or '{VIDEOS_BUCKET}'"
        )
    
    try:
        # Delete file
        success = await delete_file(supabase, delete_request.bucket, delete_request.file_path)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found or already deleted"
            )
        
        return {
            "message": "File deleted successfully",
            "file_path": delete_request.file_path,
            "bucket": delete_request.bucket
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )


@router.get("/health")
async def storage_health():
    """Check if storage service is healthy"""
    return {
        "status": "healthy",
        "service": "Supabase Storage",
        "buckets": {
            "images": IMAGES_BUCKET,
            "videos": VIDEOS_BUCKET
        }
    }

