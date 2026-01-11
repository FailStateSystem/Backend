from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from app.models import User, UserProfile, Badge, TokenData
from app.auth import get_current_user
from app.database import get_supabase

router = APIRouter()

@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(current_user: TokenData = Depends(get_current_user)):
    """Get current user's profile"""
    supabase = get_supabase()
    
    try:
        # Get user data
        user_result = supabase.table("users").select("*").eq("id", current_user.user_id).execute()
        if not user_result.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        user = user_result.data[0]
        
        # Get user badges
        badges_result = supabase.table("user_badges")\
            .select("badges(*)").eq("user_id", current_user.user_id).execute()
        
        badges = []
        if badges_result.data:
            for badge_data in badges_result.data:
                if badge_data.get("badges"):
                    badges.append(Badge(**badge_data["badges"]))
        
        # Get rewards info
        rewards_result = supabase.table("user_rewards").select("*").eq("user_id", current_user.user_id).execute()
        rewards = rewards_result.data[0] if rewards_result.data else {}
        
        return UserProfile(
            **user,
            badges=badges,
            total_points=rewards.get("total_points", 0),
            current_tier=rewards.get("current_tier", "Observer I")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.get("/{user_id}", response_model=UserProfile)
async def get_user_by_id(user_id: str):
    """Get user profile by ID"""
    supabase = get_supabase()
    
    try:
        # Get user data
        user_result = supabase.table("users").select("*").eq("id", user_id).execute()
        if not user_result.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        user = user_result.data[0]
        
        # Get user badges
        badges_result = supabase.table("user_badges")\
            .select("badges(*)").eq("user_id", user_id).execute()
        
        badges = []
        if badges_result.data:
            for badge_data in badges_result.data:
                if badge_data.get("badges"):
                    badges.append(Badge(**badge_data["badges"]))
        
        # Get rewards info
        rewards_result = supabase.table("user_rewards").select("*").eq("user_id", user_id).execute()
        rewards = rewards_result.data[0] if rewards_result.data else {}
        
        return UserProfile(
            **user,
            badges=badges,
            total_points=rewards.get("total_points", 0),
            current_tier=rewards.get("current_tier", "Observer I")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.get("/me/badges", response_model=List[Badge])
async def get_user_badges(current_user: TokenData = Depends(get_current_user)):
    """Get current user's badges"""
    supabase = get_supabase()
    
    try:
        result = supabase.table("user_badges")\
            .select("badges(*), earned_at").eq("user_id", current_user.user_id).execute()
        
        badges = []
        if result.data:
            for badge_data in result.data:
                if badge_data.get("badges"):
                    badge = Badge(**badge_data["badges"])
                    badge.earned_at = badge_data.get("earned_at")
                    badge.user_id = current_user.user_id
                    badges.append(badge)
        
        return badges
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

