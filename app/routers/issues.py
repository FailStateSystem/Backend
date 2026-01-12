from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from datetime import datetime
from app.models import Issue, IssueCreate, IssueUpdate, TimelineEvent, IssueStatus, IssueCategory, TokenData, TimelineEventType
from app.auth import get_current_user
from app.database import get_supabase
from app.storage import upload_base64_image, IMAGES_BUCKET
from app.verification_worker import verify_issue_async
import json
import base64
import uuid
import asyncio
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("", response_model=Issue, status_code=status.HTTP_201_CREATED)
async def create_issue(issue_data: IssueCreate, current_user: TokenData = Depends(get_current_user)):
    """Create a new issue report"""
    supabase = get_supabase()
    
    try:
        # Handle image upload if base64 data is provided
        image_url = issue_data.image_url
        
        if issue_data.image and issue_data.image.startswith('data:image'):
            try:
                # Upload base64 image to Supabase Storage
                public_url, file_path = await upload_base64_image(
                    supabase, 
                    issue_data.image, 
                    current_user.user_id
                )
                image_url = public_url
            except Exception as upload_error:
                print(f"Image upload failed: {str(upload_error)}")
                # Continue without image if upload fails
                image_url = None
        
        # Create issue
        new_issue = {
            "title": issue_data.title,
            "description": issue_data.description,
            "category": issue_data.category.value,
            "status": IssueStatus.UNRESOLVED.value,
            "location_name": issue_data.location.name,
            "location_lat": issue_data.location.coordinates.lat,
            "location_lng": issue_data.location.coordinates.lng,
            "image_url": image_url,
            "video_url": issue_data.video_url,
            "reported_by": current_user.user_id,
            "upvotes": 0
        }
        
        result = supabase.table("issues").insert(new_issue).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create issue"
            )
        
        issue = result.data[0]
        
        # Create initial timeline event
        timeline_event = {
            "issue_id": issue["id"],
            "type": TimelineEventType.REPORTED.value,
            "description": "Issue reported - pending AI verification",
            "timestamp": datetime.utcnow().isoformat()
        }
        supabase.table("timeline_events").insert(timeline_event).execute()
        
        # Update user stats
        supabase.rpc("increment_user_issues_posted", {"user_id": current_user.user_id}).execute()
        
        # Trigger async AI verification (fire and forget)
        # Note: Rewards will be awarded ONLY after successful verification
        asyncio.create_task(verify_issue_async(issue["id"]))
        logger.info(f"Issue {issue['id']} created - queued for AI verification")
        
        # Return the created issue (from original issues table, not verified yet)
        return await build_issue_response(issue)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.get("", response_model=List[Issue])
async def get_issues(
    status: Optional[IssueStatus] = None,
    category: Optional[IssueCategory] = None,
    limit: int = Query(default=50, le=100),
    offset: int = 0
):
    """Get all verified issues with optional filters (public feed)"""
    supabase = get_supabase()
    
    try:
        # Query issues_verified and join with original issues for complete data
        query = supabase.table("issues_verified").select(
            "*, issues!inner(*)"
        )
        
        if status:
            query = query.eq("issues.status", status.value)
        
        if category:
            query = query.eq("issues.category", category.value)
        
        query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
        result = query.execute()
        
        issues = []
        for verified_data in result.data:
            issue = await build_verified_issue_response(verified_data)
            issues.append(issue)
        
        return issues
        
    except Exception as e:
        logger.error(f"Error fetching verified issues: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.get("/my-issues", response_model=List[Issue])
async def get_my_issues(
    current_user: TokenData = Depends(get_current_user)
):
    """Get all issues created by the current user (including pending/rejected)"""
    supabase = get_supabase()
    
    try:
        # Query original issues table (shows all statuses)
        result = supabase.table("issues").select("*").eq(
            "reported_by", current_user.user_id
        ).order("reported_at", desc=True).execute()
        
        issues = []
        for issue_data in result.data:
            issue = await build_issue_response(issue_data)
            issues.append(issue)
        
        return issues
        
    except Exception as e:
        logger.error(f"Error fetching user's issues: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.get("/{issue_id}", response_model=Issue)
async def get_issue_by_id(issue_id: str):
    """Get a specific verified issue by ID (public endpoint)"""
    supabase = get_supabase()
    
    try:
        # Try to find in verified issues first (by original_issue_id or id)
        result = supabase.table("issues_verified").select(
            "*, issues!inner(*)"
        ).or_(f"id.eq.{issue_id},original_issue_id.eq.{issue_id}").execute()
        
        if result.data:
            return await build_verified_issue_response(result.data[0])
        
        # If not found, check if it exists but is not verified yet
        original = supabase.table("issues").select("verification_status").eq("id", issue_id).execute()
        
        if original.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=f"Issue is pending verification (status: {original.data[0].get('verification_status', 'unknown')})"
            )
        
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching issue {issue_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.get("/{issue_id}/verification-status")
async def get_verification_status(
    issue_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Check AI verification status of an issue (requires authentication)"""
    supabase = get_supabase()
    
    try:
        # Check original issue
        result = supabase.table("issues").select(
            "id, verification_status, processed_at, reported_by"
        ).eq("id", issue_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
        
        issue_data = result.data[0]
        
        # Only allow the issue reporter or admin to check status
        if issue_data["reported_by"] != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this issue's verification status"
            )
        
        # Check if verified
        verified = supabase.table("issues_verified").select("id, created_at").eq(
            "original_issue_id", issue_id
        ).execute()
        
        # Check if rejected
        rejected = supabase.table("issues_rejected").select(
            "rejection_reason, ai_reasoning, created_at"
        ).eq("original_issue_id", issue_id).execute()
        
        return {
            "issue_id": issue_id,
            "verification_status": issue_data["verification_status"],
            "processed_at": issue_data.get("processed_at"),
            "is_verified": bool(verified.data),
            "is_rejected": bool(rejected.data),
            "verified_at": verified.data[0]["created_at"] if verified.data else None,
            "rejection_reason": rejected.data[0]["rejection_reason"] if rejected.data else None,
            "rejection_details": rejected.data[0]["ai_reasoning"] if rejected.data else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking verification status for {issue_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.patch("/{issue_id}", response_model=Issue)
async def update_issue(
    issue_id: str,
    issue_update: IssueUpdate,
    current_user: TokenData = Depends(get_current_user)
):
    """Update an issue"""
    supabase = get_supabase()
    
    try:
        # Check if issue exists
        existing_issue = supabase.table("issues").select("*").eq("id", issue_id).execute()
        if not existing_issue.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
        
        # Build update data
        update_data = {}
        if issue_update.title:
            update_data["title"] = issue_update.title
        if issue_update.description:
            update_data["description"] = issue_update.description
        if issue_update.category:
            update_data["category"] = issue_update.category.value
        if issue_update.status:
            update_data["status"] = issue_update.status.value
            # Add timeline event for status change
            if issue_update.status == IssueStatus.IN_PROGRESS:
                await add_timeline_event(issue_id, TimelineEventType.IN_PROGRESS, "Issue is now in progress")
            elif issue_update.status == IssueStatus.RESOLVED:
                update_data["resolved_at"] = datetime.utcnow().isoformat()
                await add_timeline_event(issue_id, TimelineEventType.RESOLVED, "Issue has been resolved")
        if issue_update.location:
            update_data["location_name"] = issue_update.location.name
            update_data["location_lat"] = issue_update.location.coordinates.lat
            update_data["location_lng"] = issue_update.location.coordinates.lng
        if issue_update.image_url:
            update_data["image_url"] = issue_update.image_url
        if issue_update.video_url:
            update_data["video_url"] = issue_update.video_url
        
        update_data["updated_at"] = datetime.utcnow().isoformat()
        
        result = supabase.table("issues").update(update_data).eq("id", issue_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update issue"
            )
        
        return await get_issue_by_id(issue_id)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.post("/{issue_id}/upvote")
async def upvote_issue(issue_id: str, current_user: TokenData = Depends(get_current_user)):
    """Upvote an issue"""
    supabase = get_supabase()
    
    try:
        # Check if already upvoted
        existing_upvote = supabase.table("issue_upvotes")\
            .select("*").eq("issue_id", issue_id).eq("user_id", current_user.user_id).execute()
        
        if existing_upvote.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Already upvoted this issue"
            )
        
        # Add upvote
        upvote_data = {
            "issue_id": issue_id,
            "user_id": current_user.user_id
        }
        supabase.table("issue_upvotes").insert(upvote_data).execute()
        
        # Increment upvotes count
        supabase.rpc("increment_issue_upvotes", {"issue_id": issue_id}).execute()
        
        return {"message": "Issue upvoted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.delete("/{issue_id}/upvote")
async def remove_upvote(issue_id: str, current_user: TokenData = Depends(get_current_user)):
    """Remove upvote from an issue"""
    supabase = get_supabase()
    
    try:
        # Remove upvote
        result = supabase.table("issue_upvotes")\
            .delete().eq("issue_id", issue_id).eq("user_id", current_user.user_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Upvote not found"
            )
        
        # Decrement upvotes count
        supabase.rpc("decrement_issue_upvotes", {"issue_id": issue_id}).execute()
        
        return {"message": "Upvote removed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.get("/admin/stats")
async def admin_get_verification_stats(
    current_user: TokenData = Depends(get_current_user)
):
    """
    Admin endpoint: Get verification statistics
    Shows counts of pending, verified, rejected issues
    """
    supabase = get_supabase()
    
    try:
        # TODO: Add admin role check here
        
        # Count by verification status
        pending = supabase.table("issues").select("id", count="exact").eq(
            "verification_status", "pending"
        ).execute()
        
        verified = supabase.table("issues").select("id", count="exact").eq(
            "verification_status", "verified"
        ).execute()
        
        rejected = supabase.table("issues").select("id", count="exact").eq(
            "verification_status", "rejected"
        ).execute()
        
        failed = supabase.table("issues").select("id", count="exact").eq(
            "verification_status", "failed"
        ).execute()
        
        return {
            "verification_stats": {
                "pending": pending.count,
                "verified": verified.count,
                "rejected": rejected.count,
                "failed": failed.count,
                "total": pending.count + verified.count + rejected.count + failed.count
            },
            "message": "Use POST /api/issues/admin/process-pending to process pending issues"
        }
        
    except Exception as e:
        logger.error(f"Error fetching verification stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.post("/admin/process-pending")
async def admin_process_pending_issues(
    batch_size: int = Query(default=50, le=200),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Admin endpoint: Manually trigger processing of pending issues
    Useful when OpenAI quota is restored or after service outage
    """
    supabase = get_supabase()
    
    try:
        # TODO: Add admin role check here
        # For now, any authenticated user can trigger this
        # In production, add: if current_user.role != "admin": raise HTTPException(403)
        
        logger.info(f"Admin {current_user.user_id} triggered batch processing of pending issues")
        
        # Get pending issues
        result = supabase.table("issues").select("*").eq(
            "verification_status", "pending"
        ).order("reported_at", desc=False).limit(batch_size).execute()
        
        pending_count = len(result.data)
        
        if pending_count == 0:
            return {
                "message": "No pending issues to process",
                "pending_count": 0,
                "processed_count": 0
            }
        
        # Trigger async verification for each pending issue
        for issue in result.data:
            asyncio.create_task(verify_issue_async(issue["id"]))
        
        logger.info(f"✅ Queued {pending_count} pending issues for verification")
        
        return {
            "message": f"Successfully queued {pending_count} issues for verification",
            "pending_count": pending_count,
            "note": "Processing will happen in background. Check logs or verification status."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing pending issues: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

# Helper functions
async def build_issue_response(issue_data: dict) -> Issue:
    """Build issue response with related data (for original issues table)"""
    supabase = get_supabase()
    
    # Get timeline events
    timeline_result = supabase.table("timeline_events")\
        .select("*").eq("issue_id", issue_data["id"]).order("timestamp").execute()
    
    timeline = [TimelineEvent(**event) for event in timeline_result.data]
    
    from app.models import Coordinates, Location
    
    return Issue(
        id=issue_data["id"],
        title=issue_data["title"],
        description=issue_data["description"],
        category=IssueCategory(issue_data["category"]),
        status=IssueStatus(issue_data["status"]),
        location=Location(
            name=issue_data["location_name"],
            coordinates=Coordinates(
                lat=issue_data["location_lat"],
                lng=issue_data["location_lng"]
            )
        ),
        image_url=issue_data.get("image_url"),
        video_url=issue_data.get("video_url"),
        reported_by=issue_data["reported_by"],
        reported_at=issue_data["reported_at"],
        resolved_at=issue_data.get("resolved_at"),
        upvotes=issue_data["upvotes"],
        timeline=timeline
    )

async def build_verified_issue_response(verified_data: dict) -> Issue:
    """Build issue response from verified issue (with AI-enriched content)"""
    supabase = get_supabase()
    
    # Extract the original issue data from the join
    original_issue = verified_data.get("issues", {})
    
    # Get timeline events from original issue
    original_issue_id = verified_data.get("original_issue_id")
    timeline_result = supabase.table("timeline_events")\
        .select("*").eq("issue_id", original_issue_id).order("timestamp").execute()
    
    timeline = [TimelineEvent(**event) for event in timeline_result.data]
    
    from app.models import Coordinates, Location
    
    # Use AI-generated title and description, but keep original issue metadata
    return Issue(
        id=original_issue.get("id"),  # Use original issue ID for consistency
        title=verified_data.get("generated_title"),  # AI-enriched
        description=verified_data.get("generated_description"),  # AI-enriched
        category=IssueCategory(original_issue.get("category")),
        status=IssueStatus(original_issue.get("status")),
        location=Location(
            name=verified_data.get("location_name") or original_issue.get("location_name"),
            coordinates=Coordinates(
                lat=verified_data.get("location_lat") or original_issue.get("location_lat"),
                lng=verified_data.get("location_lng") or original_issue.get("location_lng")
            )
        ),
        image_url=verified_data.get("image_url") or original_issue.get("image_url"),
        video_url=verified_data.get("video_url") or original_issue.get("video_url"),
        reported_by=verified_data.get("reported_by") or original_issue.get("reported_by"),
        reported_at=original_issue.get("reported_at"),
        resolved_at=original_issue.get("resolved_at"),
        upvotes=original_issue.get("upvotes", 0),
        timeline=timeline
    )

async def add_timeline_event(issue_id: str, event_type: TimelineEventType, description: str):
    """Add a timeline event to an issue"""
    supabase = get_supabase()
    
    timeline_event = {
        "issue_id": issue_id,
        "type": event_type.value,
        "description": description,
        "timestamp": datetime.utcnow().isoformat()
    }
    supabase.table("timeline_events").insert(timeline_event).execute()

async def award_points(user_id: str, points: int, description: str):
    """Award points to a user"""
    supabase = get_supabase()
    
    # Update user rewards
    supabase.rpc("add_user_points", {"user_id": user_id, "points": points}).execute()
    
    # Add history entry
    history_entry = {
        "user_id": user_id,
        "type": "points_earned",
        "description": description,
        "points": points
    }
    supabase.table("rewards_history").insert(history_entry).execute()

