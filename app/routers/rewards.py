from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from datetime import datetime
from app.models import UserRewards, Milestone, RedeemableItem, ClaimedItem, HistoryEntry, TokenData
from app.auth import get_current_user
from app.database import get_supabase

router = APIRouter()

@router.get("/summary", response_model=UserRewards)
async def get_rewards_summary(current_user: TokenData = Depends(get_current_user)):
    """Get user's rewards summary"""
    supabase = get_supabase()
    
    try:
        result = supabase.table("user_rewards").select("*").eq("user_id", current_user.user_id).execute()
        
        if not result.data:
            # Create default rewards entry if not exists
            default_rewards = {
                "user_id": current_user.user_id,
                "total_points": 0,
                "current_tier": "Observer I",
                "milestones_reached": 0,
                "items_claimed": 0
            }
            create_result = supabase.table("user_rewards").insert(default_rewards).execute()
            rewards_data = create_result.data[0]
        else:
            rewards_data = result.data[0]
        
        # Calculate next tier info
        current_points = rewards_data["total_points"]
        tiers = [
            ("Observer I", 0),
            ("Observer II", 50),
            ("Persistent I", 150),
            ("Persistent II", 300),
            ("Vigilant I", 500),
            ("Vigilant II", 750)
        ]
        
        current_tier = rewards_data["current_tier"]
        next_tier = "Max Level"
        points_to_next = 0
        
        for i, (tier_name, tier_points) in enumerate(tiers):
            if tier_name == current_tier and i < len(tiers) - 1:
                next_tier = tiers[i + 1][0]
                points_to_next = tiers[i + 1][1] - current_points
                break
        
        return UserRewards(
            user_id=rewards_data["user_id"],
            total_points=current_points,
            current_tier=current_tier,
            next_tier=next_tier,
            points_to_next_tier=max(0, points_to_next),
            milestones_reached=rewards_data["milestones_reached"],
            items_claimed=rewards_data["items_claimed"]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.get("/milestones", response_model=List[Milestone])
async def get_milestones(current_user: TokenData = Depends(get_current_user)):
    """Get all milestones and user's progress"""
    supabase = get_supabase()
    
    try:
        # Get user's total points
        rewards_result = supabase.table("user_rewards").select("*").eq("user_id", current_user.user_id).execute()
        user_points = rewards_result.data[0]["total_points"] if rewards_result.data else 0
        
        # Get all milestones
        milestones_result = supabase.table("milestones").select("*").order("points_required").execute()
        
        # Get user's unlocked milestones
        user_milestones_result = supabase.table("user_milestones")\
            .select("milestone_id, unlocked_at").eq("user_id", current_user.user_id).execute()
        
        unlocked_map = {um["milestone_id"]: um["unlocked_at"] for um in user_milestones_result.data}
        
        milestones = []
        for milestone_data in milestones_result.data:
            milestone_id = milestone_data["id"]
            
            if milestone_id in unlocked_map:
                status = "redeemed"
                unlocked_at = unlocked_map[milestone_id]
            elif user_points >= milestone_data["points_required"]:
                status = "reached"
                unlocked_at = None
            else:
                status = "locked"
                unlocked_at = None
            
            milestones.append(Milestone(
                id=milestone_data["id"],
                name=milestone_data["name"],
                points_required=milestone_data["points_required"],
                status=status,
                description=milestone_data["description"],
                unlocked_at=unlocked_at
            ))
        
        return milestones
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.post("/milestones/{milestone_id}/claim")
async def claim_milestone(milestone_id: str, current_user: TokenData = Depends(get_current_user)):
    """Claim a reached milestone"""
    supabase = get_supabase()
    
    try:
        # Get milestone
        milestone_result = supabase.table("milestones").select("*").eq("id", milestone_id).execute()
        if not milestone_result.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found")
        
        milestone = milestone_result.data[0]
        
        # Check if user has enough points
        rewards_result = supabase.table("user_rewards").select("*").eq("user_id", current_user.user_id).execute()
        user_points = rewards_result.data[0]["total_points"] if rewards_result.data else 0
        
        if user_points < milestone["points_required"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient points to claim this milestone"
            )
        
        # Check if already claimed
        existing_claim = supabase.table("user_milestones")\
            .select("*").eq("user_id", current_user.user_id).eq("milestone_id", milestone_id).execute()
        
        if existing_claim.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Milestone already claimed"
            )
        
        # Claim milestone
        claim_data = {
            "user_id": current_user.user_id,
            "milestone_id": milestone_id
        }
        supabase.table("user_milestones").insert(claim_data).execute()
        
        # Update milestones count
        supabase.rpc("increment_user_milestones", {"user_id": current_user.user_id}).execute()
        
        # Add history entry
        history_entry = {
            "user_id": current_user.user_id,
            "type": "milestone_unlocked",
            "description": f"Threshold reached: {milestone['name']}"
        }
        supabase.table("rewards_history").insert(history_entry).execute()
        
        return {"message": "Milestone claimed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.get("/items", response_model=List[RedeemableItem])
async def get_redeemable_items(current_user: TokenData = Depends(get_current_user)):
    """Get all redeemable items"""
    supabase = get_supabase()
    
    try:
        result = supabase.table("redeemable_items").select("*").eq("available", True).order("points_required").execute()
        
        items = [RedeemableItem(**item) for item in result.data]
        return items
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.post("/items/{item_id}/redeem")
async def redeem_item(item_id: str, current_user: TokenData = Depends(get_current_user)):
    """Redeem a reward item"""
    supabase = get_supabase()
    
    try:
        # Get item
        item_result = supabase.table("redeemable_items").select("*").eq("id", item_id).execute()
        if not item_result.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        
        item = item_result.data[0]
        
        if not item["available"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item is not available"
            )
        
        # Get user points
        rewards_result = supabase.table("user_rewards").select("*").eq("user_id", current_user.user_id).execute()
        if not rewards_result.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User rewards not found"
            )
        
        user_points = rewards_result.data[0]["total_points"]
        
        if user_points < item["points_required"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient points to redeem this item"
            )
        
        # Check if already claimed
        existing_claim = supabase.table("claimed_items")\
            .select("*").eq("user_id", current_user.user_id).eq("item_id", item_id).execute()
        
        if existing_claim.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item already claimed"
            )
        
        # Redeem item
        claim_data = {
            "user_id": current_user.user_id,
            "item_id": item_id
        }
        supabase.table("claimed_items").insert(claim_data).execute()
        
        # Deduct points and update items claimed count
        new_points = user_points - item["points_required"]
        supabase.table("user_rewards").update({
            "total_points": new_points
        }).eq("user_id", current_user.user_id).execute()
        
        supabase.rpc("increment_user_items_claimed", {"user_id": current_user.user_id}).execute()
        
        # Add history entry
        history_entry = {
            "user_id": current_user.user_id,
            "type": "item_claimed",
            "description": f"Item claimed: {item['name']}"
        }
        supabase.table("rewards_history").insert(history_entry).execute()
        
        return {"message": "Item redeemed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.get("/claimed", response_model=List[ClaimedItem])
async def get_claimed_items(current_user: TokenData = Depends(get_current_user)):
    """Get user's claimed items"""
    supabase = get_supabase()
    
    try:
        result = supabase.table("claimed_items")\
            .select("*, redeemable_items(*)").eq("user_id", current_user.user_id).execute()
        
        claimed_items = []
        for claim in result.data:
            if claim.get("redeemable_items"):
                item = ClaimedItem(
                    **claim["redeemable_items"],
                    claimed_at=claim["claimed_at"],
                    user_id=current_user.user_id
                )
                claimed_items.append(item)
        
        return claimed_items
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.get("/history", response_model=List[HistoryEntry])
async def get_rewards_history(current_user: TokenData = Depends(get_current_user)):
    """Get user's rewards history"""
    supabase = get_supabase()
    
    try:
        result = supabase.table("rewards_history")\
            .select("*").eq("user_id", current_user.user_id).order("timestamp", desc=True).execute()
        
        history = [HistoryEntry(**entry) for entry in result.data]
        return history
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

