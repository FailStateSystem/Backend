from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from datetime import datetime
from app.models import Issue, IssueCreate, IssueUpdate, TimelineEvent, IssueStatus, IssueCategory, TokenData, TimelineEventType
from app.auth import get_current_user
from app.database import get_supabase
import json

router = APIRouter()

@router.post("", response_model=Issue, status_code=status.HTTP_201_CREATED)
async def create_issue(issue_data: IssueCreate, current_user: TokenData = Depends(get_current_user)):
    """Create a new issue report"""
    supabase = get_supabase()
    
    try:
        # Create issue
        new_issue = {
            "title": issue_data.title,
            "description": issue_data.description,
            "category": issue_data.category.value,
            "status": IssueStatus.UNRESOLVED.value,
            "location_name": issue_data.location.name,
            "location_lat": issue_data.location.coordinates.lat,
            "location_lng": issue_data.location.coordinates.lng,
            "image_url": issue_data.image_url,
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
            "description": "Issue reported",
            "timestamp": datetime.utcnow().isoformat()
        }
        supabase.table("timeline_events").insert(timeline_event).execute()
        
        # Update user stats
        supabase.rpc("increment_user_issues_posted", {"user_id": current_user.user_id}).execute()
        
        # Award points for reporting
        await award_points(current_user.user_id, 25, "Verified report logged")
        
        return await get_issue_by_id(issue["id"])
        
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
    """Get all issues with optional filters"""
    supabase = get_supabase()
    
    try:
        query = supabase.table("issues").select("*")
        
        if status:
            query = query.eq("status", status.value)
        
        if category:
            query = query.eq("category", category.value)
        
        query = query.order("reported_at", desc=True).range(offset, offset + limit - 1)
        result = query.execute()
        
        issues = []
        for issue_data in result.data:
            issue = await build_issue_response(issue_data)
            issues.append(issue)
        
        return issues
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.get("/{issue_id}", response_model=Issue)
async def get_issue_by_id(issue_id: str):
    """Get a specific issue by ID"""
    supabase = get_supabase()
    
    try:
        result = supabase.table("issues").select("*").eq("id", issue_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
        
        return await build_issue_response(result.data[0])
        
    except HTTPException:
        raise
    except Exception as e:
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

# Helper functions
async def build_issue_response(issue_data: dict) -> Issue:
    """Build issue response with related data"""
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

