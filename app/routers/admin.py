"""
Admin Console API
==================
Comprehensive admin endpoints for monitoring, management, and control

All endpoints require admin authentication
All actions are logged for audit trail
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from app.database import get_supabase
from app.admin_auth import (
    get_current_admin,
    AdminTokenData,
    AdminLoginRequest,
    authenticate_admin,
    create_admin_access_token,
    log_admin_action,
    require_super_admin
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================
# ADMIN AUTHENTICATION
# ============================================

@router.post("/login")
async def admin_login(request: Request, login_data: AdminLoginRequest):
    """
    Admin login endpoint
    
    Separate from user login - uses admins table
    Returns admin JWT token
    """
    try:
        admin = await authenticate_admin(login_data.email, login_data.password)
        
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create admin token
        access_token = create_admin_access_token(
            data={
                "sub": admin["id"],
                "email": admin["email"],
                "username": admin["username"],
                "is_super_admin": admin["is_super_admin"]
            }
        )
        
        # Log login action
        admin_token = AdminTokenData(
            admin_id=admin["id"],
            email=admin["email"],
            username=admin["username"],
            is_super_admin=admin["is_super_admin"]
        )
        
        await log_admin_action(
            admin=admin_token,
            action_type="admin_login",
            resource_type="auth",
            details={"login_method": "password"},
            request=request
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "admin": {
                "id": admin["id"],
                "email": admin["email"],
                "username": admin["username"],
                "full_name": admin.get("full_name"),
                "is_super_admin": admin["is_super_admin"]
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.get("/me")
async def get_admin_profile(admin: AdminTokenData = Depends(get_current_admin)):
    """Get current admin profile"""
    try:
        from app.admin_auth import get_admin_by_id, get_admin_activity_summary
        
        admin_data = await get_admin_by_id(admin.admin_id)
        activity = await get_admin_activity_summary(admin.admin_id)
        
        if not admin_data:
            raise HTTPException(status_code=404, detail="Admin not found")
        
        return {
            "id": admin_data["id"],
            "email": admin_data["email"],
            "username": admin_data["username"],
            "full_name": admin_data.get("full_name"),
            "is_super_admin": admin_data["is_super_admin"],
            "last_login_at": admin_data.get("last_login_at"),
            "created_at": admin_data["created_at"],
            "activity": activity
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get admin profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# DASHBOARD & OVERVIEW
# ============================================

@router.get("/dashboard")
async def get_admin_dashboard(
    request: Request,
    admin: AdminTokenData = Depends(get_current_admin)
) -> Dict[str, Any]:
    """
    Admin Dashboard - High-level overview of entire system
    
    Returns comprehensive stats for admin console homepage
    """
    try:
        supabase = get_supabase()
        
        # User statistics
        total_users = supabase.table("users").select("id", count="exact").execute()
        active_users_today = supabase.table("users").select("id", count="exact").gte(
            "created_at", (datetime.utcnow() - timedelta(days=1)).isoformat()
        ).execute()
        suspended_users = supabase.table("users").select("id", count="exact").eq(
            "account_status", "suspended"
        ).execute()
        
        # Issue statistics
        total_issues = supabase.table("issues").select("id", count="exact").execute()
        pending_verification = supabase.table("issues").select("id", count="exact").eq(
            "verification_status", "pending"
        ).execute()
        verified_issues = supabase.table("issues").select("id", count="exact").eq(
            "verification_status", "verified"
        ).execute()
        rejected_issues = supabase.table("issues").select("id", count="exact").eq(
            "verification_status", "rejected"
        ).execute()
        
        # Issues by severity (from verified)
        high_severity = supabase.table("issues_verified").select("id", count="exact").eq(
            "severity", "high"
        ).execute()
        moderate_severity = supabase.table("issues_verified").select("id", count="exact").eq(
            "severity", "moderate"
        ).execute()
        low_severity = supabase.table("issues_verified").select("id", count="exact").eq(
            "severity", "low"
        ).execute()
        
        # Routing statistics
        routed_issues = supabase.table("issues_verified").select("id", count="exact").not_.is_(
            "district_id", "null"
        ).execute()
        
        # Abuse & filtering
        abuse_today = supabase.table("abuse_logs").select("id", count="exact").gte(
            "timestamp", (datetime.utcnow() - timedelta(days=1)).isoformat()
        ).execute()
        
        return {
            "users": {
                "total": total_users.count or 0,
                "new_today": active_users_today.count or 0,
                "suspended": suspended_users.count or 0
            },
            "issues": {
                "total": total_issues.count or 0,
                "pending_verification": pending_verification.count or 0,
                "verified": verified_issues.count or 0,
                "rejected": rejected_issues.count or 0,
                "verification_rate": round(
                    (verified_issues.count or 0) / max(total_issues.count or 1, 1) * 100, 2
                )
            },
            "severity": {
                "high": high_severity.count or 0,
                "moderate": moderate_severity.count or 0,
                "low": low_severity.count or 0
            },
            "routing": {
                "routed": routed_issues.count or 0,
                "pending": (verified_issues.count or 0) - (routed_issues.count or 0)
            },
            "abuse": {
                "violations_today": abuse_today.count or 0
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Failed to get admin dashboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================
# ANALYTICS & REPORTING
# ============================================

@router.get("/analytics/districts")
async def get_district_analytics(
    from_date: Optional[str] = Query(None, description="Start date (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)"),
    to_date: Optional[str] = Query(None, description="End date (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)"),
    sort_by: str = Query("unresolved_count", description="Sort field: unresolved_count, high_severity_count, total_issues, district_name"),
    sort_order: str = Query("DESC", description="Sort order: ASC or DESC"),
    admin: AdminTokenData = Depends(get_current_admin)
) -> Dict[str, Any]:
    """
    Get district-wise analytics for admin console
    
    **PURPOSE:**
    Provides aggregated district-level analytics for:
    - District heatmaps showing failure hotspots
    - Failure rankings by unresolved count or severity
    - Escalation prioritization for authority contacts
    
    **DATA RETURNED PER DISTRICT:**
    - Basic info: district_id, district_name, state_name
    - Issue counts: total_issues, verified_issues, unresolved_issues
    - Severity breakdown: high/moderate/low severity counts
    - Time metrics: oldest_unresolved_issue_age_days, last_issue_reported_at
    - Meta: percentage_unresolved, authority_contact_status
    
    **ANALYTICS LOGIC:**
    - "Unresolved" = issues NOT marked resolved (status NOT IN 'resolved', 'closed', 'completed')
    - Severity counts from AI-verified issues only (issues_verified table)
    - Districts with zero issues still appear (with counts = 0)
    - Uses SQL aggregation with LEFT JOINs - optimized for ~750 districts
    
    **QUERY PARAMS:**
    - from_date: Filter issues reported after this date (optional)
    - to_date: Filter issues reported before this date (default: now)
    - sort_by: Sort field (unresolved_count, high_severity_count, total_issues, district_name)
    - sort_order: ASC or DESC (default: DESC)
    
    **AUTHORITY CONTACT STATUS:**
    - 'configured': Has active email, is_active=true
    - 'inactive': Authority exists but is_active=false
    - 'missing': No authority OR email is NULL
    - 'unknown': No data available
    
    **PERFORMANCE:**
    - Query time: ~100-500ms for 750 districts
    - Uses indexed aggregation with CTEs
    - No N+1 queries - single RPC call
    
    **RETURNS:**
    ```json
    {
        "districts": [
            {
                "district_id": "uuid",
                "district_name": "Mumbai",
                "state_name": "Maharashtra",
                "total_issues": 150,
                "verified_issues": 140,
                "unresolved_issues": 75,
                "high_severity_count": 20,
                "moderate_severity_count": 35,
                "low_severity_count": 20,
                "oldest_unresolved_issue_age_days": 45,
                "percentage_unresolved": 50.00,
                "last_issue_reported_at": "2026-01-23T10:30:00Z",
                "authority_contact_status": "configured"
            },
            ...
        ],
        "metadata": {
            "total_districts": 750,
            "districts_with_issues": 523,
            "date_range": {
                "from": "2025-01-01T00:00:00Z",
                "to": "2026-01-23T23:59:59Z"
            },
            "sort": {
                "by": "unresolved_count",
                "order": "DESC"
            }
        },
        "summary": {
            "total_issues_all_districts": 12500,
            "total_unresolved_all_districts": 6200,
            "districts_with_configured_authority": 450,
            "districts_with_missing_authority": 300
        }
    }
    ```
    """
    try:
        supabase = get_supabase()
        
        # Validate and parse dates
        from_date_ts = None
        to_date_ts = datetime.utcnow()
        
        if from_date:
            try:
                from_date_ts = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid from_date format. Use ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ"
                )
        
        if to_date:
            try:
                to_date_ts = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid to_date format. Use ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ"
                )
        
        # Validate sort parameters
        valid_sort_fields = ['unresolved_count', 'high_severity_count', 'total_issues', 'district_name']
        if sort_by not in valid_sort_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sort_by. Must be one of: {', '.join(valid_sort_fields)}"
            )
        
        if sort_order.upper() not in ['ASC', 'DESC']:
            raise HTTPException(status_code=400, detail="Invalid sort_order. Must be ASC or DESC")
        
        # Call the district analytics function via Supabase RPC
        # This executes the optimized SQL function defined in district_analytics_function.sql
        result = supabase.rpc(
            'get_district_analytics',
            {
                'p_from_date': from_date_ts.isoformat() if from_date_ts else None,
                'p_to_date': to_date_ts.isoformat(),
                'p_sort_by': sort_by,
                'p_sort_order': sort_order.upper()
            }
        ).execute()
        
        districts = result.data if result.data else []
        
        # Calculate summary statistics
        total_districts = len(districts)
        districts_with_issues = len([d for d in districts if d['total_issues'] > 0])
        total_issues_sum = sum(d['total_issues'] for d in districts)
        total_unresolved_sum = sum(d['unresolved_issues'] for d in districts)
        configured_authority_count = len([d for d in districts if d['authority_contact_status'] == 'configured'])
        missing_authority_count = len([d for d in districts if d['authority_contact_status'] == 'missing'])
        
        return {
            "districts": districts,
            "metadata": {
                "total_districts": total_districts,
                "districts_with_issues": districts_with_issues,
                "date_range": {
                    "from": from_date_ts.isoformat() if from_date_ts else None,
                    "to": to_date_ts.isoformat()
                },
                "sort": {
                    "by": sort_by,
                    "order": sort_order.upper()
                }
            },
            "summary": {
                "total_issues_all_districts": total_issues_sum,
                "total_unresolved_all_districts": total_unresolved_sum,
                "districts_with_configured_authority": configured_authority_count,
                "districts_with_missing_authority": missing_authority_count
            }
        }
    
    except HTTPException:
        # Re-raise validation errors
        raise
    except Exception as e:
        logger.error(f"Failed to get district analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve district analytics: {str(e)}"
        )


# ============================================
# USER MANAGEMENT
# ============================================

@router.get("/users")
async def list_users(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by account_status"),
    search: Optional[str] = Query(None, description="Search by email or username"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    admin: AdminTokenData = Depends(get_current_admin)
) -> Dict[str, Any]:
    """
    List all users with filtering and pagination
    """
    try:
        supabase = get_supabase()
        
        query = supabase.table("users").select(
            "id, email, username, credibility_score, issues_posted, issues_resolved, "
            "account_status, trust_score, is_shadow_banned, created_at, updated_at"
        )
        
        # Only filter by status if it's not "all"
        if status and status != "all":
            query = query.eq("account_status", status)
        
        if search:
            query = query.or_(f"email.ilike.%{search}%,username.ilike.%{search}%")
        
        query = query.range(offset, offset + limit - 1).order("created_at", desc=True)
        
        result = query.execute()
        
        count_result = supabase.table("users").select("id", count="exact").execute()
        
        return {
            "users": result.data if result.data else [],
            "total": count_result.count or 0,
            "limit": limit,
            "offset": offset
        }
    
    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/{user_id}")
async def get_user_details(
    user_id: str,
    request: Request,
    admin: AdminTokenData = Depends(get_current_admin)
) -> Dict[str, Any]:
    """
    Get detailed user information including activity and violations
    """
    try:
        supabase = get_supabase()
        
        # User basic info
        user_result = supabase.table("users").select("*").eq("id", user_id).limit(1).execute()
        
        if not user_result.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        user = user_result.data[0]
        
        # User's issues
        issues_result = supabase.table("issues").select(
            "id, title, verification_status, rejection_reason, reported_at"
        ).eq("reported_by", user_id).order("reported_at", desc=True).limit(20).execute()
        
        # Penalties
        penalties_result = supabase.table("user_penalties").select("*").eq(
            "user_id", user_id
        ).order("created_at", desc=True).limit(10).execute()
        
        # Abuse logs
        abuse_result = supabase.table("abuse_logs").select("*").eq(
            "user_id", user_id
        ).order("timestamp", desc=True).limit(10).execute()
        
        # User rewards
        rewards_result = supabase.table("user_rewards").select("*").eq(
            "user_id", user_id
        ).limit(1).execute()
        
        return {
            "user": user,
            "recent_issues": issues_result.data if issues_result.data else [],
            "penalties": penalties_result.data if penalties_result.data else [],
            "abuse_logs": abuse_result.data if abuse_result.data else [],
            "rewards": rewards_result.data[0] if rewards_result.data else None
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/users/{user_id}/unsuspend")
async def unsuspend_user(
    user_id: str,
    request: Request,
    reset_penalties: bool = Query(False, description="Also reset penalty count"),
    admin: AdminTokenData = Depends(get_current_admin)
):
    """
    Unsuspend/unblock a user account
    """
    try:
        supabase = get_supabase()
        
        # Get user info before update
        user_result = supabase.table("users").select("email, username").eq("id", user_id).limit(1).execute()
        if not user_result.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_info = user_result.data[0]
        
        update_data = {
            "account_status": "active",
            "ban_reason": None,
            "banned_until": None
        }
        
        result = supabase.table("users").update(update_data).eq("id", user_id).execute()
        
        # Optionally reset penalty count
        if reset_penalties:
            supabase.table("user_penalties").update({
                "rejection_count": 0
            }).eq("user_id", user_id).execute()
        
        # Log action
        await log_admin_action(
            admin=admin,
            action_type="user_unsuspended",
            resource_type="user",
            resource_id=user_id,
            details={
                "user_email": user_info["email"],
                "penalties_reset": reset_penalties
            },
            request=request
        )
        
        logger.info(f"✅ Admin {admin.email} unsuspended user {user_id}")
        
        return {
            "message": "User unsuspended successfully",
            "user_id": user_id,
            "penalties_reset": reset_penalties
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unsuspend user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/users/{user_id}/suspend")
async def suspend_user(
    user_id: str,
    request: Request,
    reason: str = Query(..., description="Reason for suspension"),
    permanent: bool = Query(False, description="Permanent suspension"),
    admin: AdminTokenData = Depends(get_current_admin)
):
    """
    Suspend a user account
    """
    try:
        supabase = get_supabase()
        
        # Get user info
        user_result = supabase.table("users").select("email, username").eq("id", user_id).limit(1).execute()
        if not user_result.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_info = user_result.data[0]
        
        update_data = {
            "account_status": "suspended",
            "ban_reason": reason
        }
        
        if not permanent:
            update_data["banned_until"] = (datetime.utcnow() + timedelta(days=30)).isoformat()
        
        result = supabase.table("users").update(update_data).eq("id", user_id).execute()
        
        # Log action
        await log_admin_action(
            admin=admin,
            action_type="user_suspended",
            resource_type="user",
            resource_id=user_id,
            details={
                "user_email": user_info["email"],
                "reason": reason,
                "permanent": permanent
            },
            request=request
        )
        
        logger.warning(f"🚫 Admin {admin.email} suspended user {user_id}: {reason}")
        
        return {
            "message": f"User suspended {'permanently' if permanent else 'for 30 days'}",
            "user_id": user_id,
            "reason": reason
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to suspend user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    request: Request,
    reason: str = Query(..., description="Reason for deletion"),
    admin: AdminTokenData = Depends(get_current_admin)
):
    """
    Permanently delete a user account
    
    ⚠️ WARNING: This is irreversible!
    - Deletes user from users table
    - CASCADE deletes all related data (issues, rewards, etc.)
    """
    try:
        supabase = get_supabase()
        
        # Get user info before deletion
        user_result = supabase.table("users").select("email, username").eq("id", user_id).limit(1).execute()
        
        if not user_result.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_info = user_result.data[0]
        
        # Delete user (CASCADE will handle related tables)
        result = supabase.table("users").delete().eq("id", user_id).execute()
        
        # Log action
        await log_admin_action(
            admin=admin,
            action_type="user_deleted",
            resource_type="user",
            resource_id=user_id,
            details={
                "user_email": user_info["email"],
                "user_username": user_info["username"],
                "reason": reason
            },
            request=request
        )
        
        logger.critical(f"🗑️ Admin {admin.email} DELETED user {user_id} ({user_info['email']}): {reason}")
        
        return {
            "message": "User permanently deleted",
            "user_id": user_id,
            "email": user_info['email'],
            "username": user_info['username'],
            "reason": reason,
            "warning": "This action is irreversible"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/users/{user_id}/trust-score")
async def update_user_trust_score(
    user_id: str,
    new_score: int = Query(..., ge=0, le=100, description="New trust score (0-100)"),
    reason: str = Query(..., description="Reason for change"),
    admin: AdminTokenData = Depends(get_current_admin)
):
    """
    Manually update a user's trust score
    """
    try:
        supabase = get_supabase()
        
        result = supabase.table("users").update({
            "trust_score": new_score
        }).eq("id", user_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        logger.info(f"📝 Admin {admin.admin_id} set trust score for {user_id} to {new_score}: {reason}")
        
        return {
            "message": "Trust score updated",
            "user_id": user_id,
            "new_trust_score": new_score,
            "reason": reason
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update trust score: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/users/{user_id}/reset-penalties")
async def reset_user_penalties(
    user_id: str,
    reason: str = Query(..., description="Reason for reset"),
    admin: AdminTokenData = Depends(get_current_admin)
):
    """
    Reset user penalties (forgive past violations)
    """
    try:
        supabase = get_supabase()
        
        # Reset rejection count in user_penalties
        result = supabase.table("user_penalties").update({
            "rejection_count": 0
        }).eq("user_id", user_id).execute()
        
        # Also restore trust score to default
        supabase.table("users").update({
            "trust_score": 80  # Default trust score
        }).eq("id", user_id).execute()
        
        logger.info(f"🔄 Admin {admin.admin_id} reset penalties for user {user_id}: {reason}")
        
        return {
            "message": "User penalties reset successfully",
            "user_id": user_id,
            "reason": reason
        }
    
    except Exception as e:
        logger.error(f"Failed to reset penalties: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# ISSUE MANAGEMENT
# ============================================

@router.get("/issues/pending")
async def list_pending_issues(
    page: Optional[int] = Query(None, ge=1, description="Page number (starts at 1)"),
    page_size: Optional[int] = Query(None, ge=1, le=500, description="Items per page"),
    limit: int = Query(100, ge=1, le=500, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    admin: AdminTokenData = Depends(get_current_admin)
):
    """
    List all pending issues (awaiting AI verification)
    
    Supports two pagination styles:
    - page/page_size: page=1&page_size=20
    - limit/offset: limit=20&offset=0
    """
    try:
        supabase = get_supabase()
        
        # Convert page/page_size to limit/offset if provided
        if page is not None and page_size is not None:
            limit = page_size
            offset = (page - 1) * page_size
        
        result = supabase.table("issues").select(
            "id, title, description, category, location_name, location_lat, location_lng, "
            "image_url, reported_by, reported_at, verification_status, retry_count",
            count="exact"
        ).eq("verification_status", "pending").range(
            offset, offset + limit - 1
        ).order("reported_at", desc=True).execute()
        
        # Also get reporter info for each issue
        for issue in (result.data if result.data else []):
            user_result = supabase.table("users").select(
                "email, username, trust_score"
            ).eq("id", issue["reported_by"]).limit(1).execute()
            
            if user_result.data:
                issue["reporter"] = user_result.data[0]
        
        return {
            "issues": result.data if result.data else [],
            "total": result.count or 0,
            "limit": limit,
            "offset": offset
        }
    
    except Exception as e:
        logger.error(f"Failed to list pending issues: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/issues/rejected")
async def list_rejected_issues(
    page: Optional[int] = Query(None, ge=1, description="Page number (starts at 1)"),
    page_size: Optional[int] = Query(None, ge=1, le=500, description="Items per page"),
    reason: Optional[str] = Query(None, description="Filter by rejection reason"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    admin: AdminTokenData = Depends(get_current_admin)
):
    """
    List all rejected issues with rejection reasons
    
    Supports two pagination styles:
    - page/page_size: page=1&page_size=20
    - limit/offset: limit=20&offset=0
    """
    try:
        supabase = get_supabase()
        
        # Convert page/page_size to limit/offset if provided
        if page is not None and page_size is not None:
            limit = page_size
            offset = (page - 1) * page_size
        
        query = supabase.table("issues").select(
            "id, title, description, category, image_url, reported_by, reported_at, "
            "verification_status, rejection_reason, processed_at, rejection_count",
            count="exact"
        ).eq("verification_status", "rejected")
        
        if reason:
            query = query.eq("rejection_reason", reason)
        
        query = query.range(offset, offset + limit - 1).order("processed_at", desc=True)
        
        result = query.execute()
        
        # Get detailed rejection info and reporter info
        for issue in (result.data if result.data else []):
            rejected_detail = supabase.table("issues_rejected").select(
                "ai_reasoning, confidence_score"
            ).eq("original_issue_id", issue["id"]).limit(1).execute()
            
            if rejected_detail.data:
                issue["ai_reasoning"] = rejected_detail.data[0].get("ai_reasoning")
                issue["ai_confidence"] = rejected_detail.data[0].get("confidence_score")
            
            # Get reporter info
            user_result = supabase.table("users").select(
                "email, username, trust_score"
            ).eq("id", issue["reported_by"]).limit(1).execute()
            
            if user_result.data:
                issue["reporter"] = user_result.data[0]
        
        return {
            "issues": result.data if result.data else [],
            "total": result.count or 0,
            "limit": limit,
            "offset": offset
        }
    
    except Exception as e:
        logger.error(f"Failed to list rejected issues: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/issues/verified")
async def list_verified_issues(
    page: Optional[int] = Query(None, ge=1, description="Page number (starts at 1)"),
    page_size: Optional[int] = Query(None, ge=1, le=500, description="Items per page"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    district_id: Optional[str] = Query(None, description="Filter by district"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    admin: AdminTokenData = Depends(get_current_admin)
):
    """
    List all verified issues with AI analysis
    
    Supports two pagination styles:
    - page/page_size: page=1&page_size=20
    - limit/offset: limit=20&offset=0
    """
    try:
        supabase = get_supabase()
        
        # Convert page/page_size to limit/offset if provided
        if page is not None and page_size is not None:
            limit = page_size
            offset = (page - 1) * page_size
        
        query = supabase.table("issues_verified").select(
            "id, original_issue_id, generated_title, generated_description, "
            "severity, ai_confidence_score, district_id, district_name, state_name, "
            "routing_status, dm_notification_sent, verified_at, reported_by, "
            "image_url, video_url, location_name, location_lat, location_lng, category",
            count="exact"
        )
        
        if severity:
            query = query.eq("severity", severity)
        
        if district_id:
            query = query.eq("district_id", district_id)
        
        query = query.range(offset, offset + limit - 1).order("verified_at", desc=True)
        
        result = query.execute()
        
        return {
            "issues": result.data if result.data else [],
            "total": result.count or 0,
            "limit": limit,
            "offset": offset
        }
    
    except Exception as e:
        logger.error(f"Failed to list verified issues: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/issues/{issue_id}")
async def get_issue_details(
    issue_id: str,
    admin: AdminTokenData = Depends(get_current_admin)
):
    """
    Get detailed information about a specific issue
    
    Accepts either:
    - Original issue ID (from issues table)
    - Verified issue ID (from issues_verified table)
    
    Returns comprehensive data including:
    - Original issue data
    - Verification/rejection details
    - Reporter info
    - District routing info
    - Timeline/history
    """
    try:
        supabase = get_supabase()
        
        # Try to get from issues table first
        issue_result = supabase.table("issues").select("*").eq("id", issue_id).limit(1).execute()
        
        # If not found, check if this is a verified issue ID
        if not issue_result.data:
            verified_result = supabase.table("issues_verified").select("*, original_issue_id").eq(
                "id", issue_id
            ).limit(1).execute()
            
            if verified_result.data:
                # Get the original issue using original_issue_id
                original_id = verified_result.data[0]["original_issue_id"]
                issue_result = supabase.table("issues").select("*").eq("id", original_id).limit(1).execute()
                
                if issue_result.data:
                    issue = issue_result.data[0]
                    # Already have verification details from the verified_result
                    issue["verification_details"] = verified_result.data[0]
                else:
                    raise HTTPException(status_code=404, detail="Original issue not found")
            else:
                raise HTTPException(status_code=404, detail="Issue not found")
        else:
            issue = issue_result.data[0]
        
        # Get reporter info
        user_result = supabase.table("users").select(
            "id, email, username, trust_score, account_status"
        ).eq("id", issue["reported_by"]).limit(1).execute()
        
        if user_result.data:
            issue["reporter"] = user_result.data[0]
        
        # Get verification/rejection details if not already fetched
        if "verification_details" not in issue:
            if issue["verification_status"] == "verified":
                verified_result = supabase.table("issues_verified").select("*").eq(
                    "original_issue_id", issue["id"]
                ).limit(1).execute()
                
                if verified_result.data:
                    issue["verification_details"] = verified_result.data[0]
            
            elif issue["verification_status"] == "rejected":
                rejected_result = supabase.table("issues_rejected").select("*").eq(
                    "original_issue_id", issue["id"]
                ).limit(1).execute()
                
                if rejected_result.data:
                    issue["rejection_details"] = rejected_result.data[0]
        
        # Get timeline events
        try:
            timeline_result = supabase.table("timeline_events").select("*").eq(
                "issue_id", issue["id"]
            ).order("timestamp", desc=False).execute()
            
            if timeline_result.data:
                issue["timeline"] = timeline_result.data
        except Exception as timeline_error:
            # Timeline query failed - skip it
            logger.debug(f"Timeline query skipped: {timeline_error}")
            issue["timeline"] = []
        
        return issue
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get issue details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/issues/{issue_id}/approve")
async def approve_pending_issue(
    issue_id: str,
    request: Request,
    reason: str = Query(..., description="Reason for manual approval"),
    severity: str = Query("moderate", description="Severity level"),
    admin: AdminTokenData = Depends(get_current_admin)
):
    """
    Manually approve a pending issue (bypass AI verification)
    
    Use this to verify legitimate issues that are stuck in pending
    """
    try:
        supabase = get_supabase()
        
        # Get original issue
        issue_result = supabase.table("issues").select("*").eq("id", issue_id).limit(1).execute()
        
        if not issue_result.data:
            raise HTTPException(status_code=404, detail="Issue not found")
        
        issue = issue_result.data[0]
        
        if issue["verification_status"] != "pending":
            raise HTTPException(status_code=400, detail=f"Issue is not pending (status: {issue['verification_status']})")
        
        # Create verified entry
        verified_data = {
            "original_issue_id": issue["id"],
            "is_genuine": True,
            "ai_confidence_score": 0.50,
            "ai_reasoning": f"Manually approved by admin: {reason}",
            "severity": severity,
            "generated_title": issue["title"],
            "generated_description": issue["description"],
            "public_impact": "Manually verified issue - requires attention",
            "tags": ["manual-review", "admin-approved"],
            "content_warnings": [],
            "category": issue["category"],
            "location_name": issue["location_name"],
            "location_lat": issue["location_lat"],
            "location_lng": issue["location_lng"],
            "image_url": issue.get("image_url"),
            "video_url": issue.get("video_url"),
            "reported_by": issue["reported_by"],
            "status": issue.get("status", "unresolved"),
            "upvotes": issue.get("upvotes", 0),
            "reported_at": issue["reported_at"],
            "verified_at": datetime.utcnow().isoformat()
        }
        
        result = supabase.table("issues_verified").insert(verified_data).execute()
        
        # Update original issue
        supabase.table("issues").update({
            "verification_status": "verified",
            "processed_at": datetime.utcnow().isoformat()
        }).eq("id", issue_id).execute()
        
        # Award points to user
        try:
            supabase.rpc("add_user_points", {
                "user_id": issue["reported_by"],
                "points": 10,
                "reason": "Manual issue approval by admin"
            }).execute()
        except Exception as e:
            logger.error(f"Failed to award points: {e}")
        
        # Log action
        await log_admin_action(
            admin=admin,
            action_type="issue_approved_pending",
            resource_type="issue",
            resource_id=issue_id,
            details={
                "reason": reason,
                "severity": severity,
                "issue_title": issue["title"]
            },
            request=request
        )
        
        logger.warning(f"✅ Admin {admin.email} manually approved issue {issue_id}: {reason}")
        
        return {
            "message": "Issue manually approved and published",
            "issue_id": issue_id,
            "verified_issue_id": result.data[0]["id"] if result.data else None
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to approve issue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/issues/{issue_id}/approve-rejected")
async def approve_rejected_issue(
    issue_id: str,
    request: Request,
    reason: str = Query(..., description="Reason for overriding rejection"),
    severity: str = Query("moderate", description="Severity level"),
    admin: AdminTokenData = Depends(get_current_admin)
):
    """
    Approve a rejected issue (override AI decision - false negative fix)
    
    Use this when AI incorrectly rejected a legitimate issue
    """
    try:
        supabase = get_supabase()
        
        # Get original issue
        issue_result = supabase.table("issues").select("*").eq("id", issue_id).limit(1).execute()
        
        if not issue_result.data:
            raise HTTPException(status_code=404, detail="Issue not found")
        
        issue = issue_result.data[0]
        
        if issue["verification_status"] != "rejected":
            raise HTTPException(status_code=400, detail=f"Issue is not rejected (status: {issue['verification_status']})")
        
        # Create verified entry
        verified_data = {
            "original_issue_id": issue["id"],
            "is_genuine": True,
            "ai_confidence_score": 0.50,
            "ai_reasoning": f"AI rejection overridden by admin: {reason}",
            "severity": severity,
            "generated_title": issue["title"],
            "generated_description": issue["description"],
            "public_impact": "False negative corrected - legitimate issue",
            "tags": ["manual-review", "ai-override", "false-negative-fix"],
            "content_warnings": [],
            "category": issue["category"],
            "location_name": issue["location_name"],
            "location_lat": issue["location_lat"],
            "location_lng": issue["location_lng"],
            "image_url": issue.get("image_url"),
            "video_url": issue.get("video_url"),
            "reported_by": issue["reported_by"],
            "status": issue.get("status", "unresolved"),
            "upvotes": issue.get("upvotes", 0),
            "reported_at": issue["reported_at"],
            "verified_at": datetime.utcnow().isoformat()
        }
        
        result = supabase.table("issues_verified").insert(verified_data).execute()
        
        # Update original issue
        supabase.table("issues").update({
            "verification_status": "verified",
            "processed_at": datetime.utcnow().isoformat(),
            "rejection_reason": None
        }).eq("id", issue_id).execute()
        
        # Delete from rejected table
        supabase.table("issues_rejected").delete().eq("original_issue_id", issue_id).execute()
        
        # Award points + bonus for false negative
        try:
            supabase.rpc("add_user_points", {
                "user_id": issue["reported_by"],
                "points": 15,
                "reason": "Issue approved after false rejection - bonus points"
            }).execute()
        except Exception as e:
            logger.error(f"Failed to award points: {e}")
        
        # Log action
        await log_admin_action(
            admin=admin,
            action_type="issue_approved_rejected",
            resource_type="issue",
            resource_id=issue_id,
            details={
                "reason": reason,
                "severity": severity,
                "issue_title": issue["title"],
                "original_rejection_reason": issue.get("rejection_reason")
            },
            request=request
        )
        
        logger.warning(f"🔄 Admin {admin.email} overrode rejection for issue {issue_id}: {reason}")
        
        return {
            "message": "Rejected issue approved and published (AI override)",
            "issue_id": issue_id,
            "verified_issue_id": result.data[0]["id"] if result.data else None,
            "note": "User received bonus points for false negative"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to approve rejected issue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/issues/{issue_id}/reject")
async def manually_reject_issue(
    issue_id: str,
    request: Request,
    rejection_reason: str = Query(..., description="Rejection reason: not_civic_issue, inappropriate_content, duplicate, spam, other"),
    reasoning: str = Query(..., description="Detailed explanation for rejection"),
    apply_penalty: bool = Query(False, description="Apply penalty to user"),
    admin: AdminTokenData = Depends(get_current_admin)
):
    """
    Manually reject an issue (admin override)
    
    Use this when:
    - AI verified an issue that shouldn't be on the platform
    - Issue is not a civic issue (private property)
    - Issue is duplicate, spam, or inappropriate
    
    Valid rejection_reason values:
    - not_civic_issue (private property/business)
    - inappropriate_content
    - duplicate
    - spam
    - other
    """
    try:
        supabase = get_supabase()
        
        # Get original issue
        issue_result = supabase.table("issues").select("*").eq("id", issue_id).limit(1).execute()
        
        if not issue_result.data:
            raise HTTPException(status_code=404, detail="Issue not found")
        
        issue = issue_result.data[0]
        
        # Check current status
        if issue["verification_status"] == "rejected":
            raise HTTPException(status_code=400, detail="Issue is already rejected")
        
        # Create rejected entry
        rejected_data = {
            "original_issue_id": issue_id,
            "rejection_reason": rejection_reason,
            "is_civic_issue": False if rejection_reason == "not_civic_issue" else None,
            "ai_reasoning": f"MANUAL ADMIN REJECTION: {reasoning}",
            "confidence_score": 1.0,  # Admin decision = 100% confidence
            "rejected_by": f"admin:{admin.email}"
        }
        
        supabase.table("issues_rejected").insert(rejected_data).execute()
        
        # Update issue status
        supabase.table("issues").update({
            "verification_status": "rejected",
            "rejection_reason": rejection_reason,
            "processed_at": datetime.utcnow().isoformat()
        }).eq("id", issue_id).execute()
        
        # Delete from issues_verified if exists
        supabase.table("issues_verified").delete().eq("original_issue_id", issue_id).execute()
        
        # Apply penalty if requested
        penalty_info = None
        if apply_penalty:
            try:
                result = supabase.rpc("apply_fake_submission_penalty", {
                    "p_user_id": issue["reported_by"],
                    "p_issue_id": issue_id,
                    "p_rejection_reason": rejection_reason,
                    "p_ai_reasoning": f"Admin rejection: {reasoning}",
                    "p_confidence_score": 1.0
                }).execute()
                
                if result.data:
                    penalty_info = result.data[0] if isinstance(result.data, list) else result.data
                    logger.warning(f"⚠️ Applied penalty to user {issue['reported_by']} for rejected issue {issue_id}")
            except Exception as penalty_error:
                logger.error(f"Failed to apply penalty: {penalty_error}")
        
        # Log admin action
        await log_admin_action(
            admin=admin,
            action_type="reject_issue",
            resource_type="issue",
            resource_id=issue_id,
            details={
                "rejection_reason": rejection_reason,
                "reasoning": reasoning,
                "penalty_applied": apply_penalty,
                "penalty_info": penalty_info,
                "previous_status": issue["verification_status"]
            },
            request=request
        )
        
        logger.warning(f"🚫 Admin {admin.email} manually rejected issue {issue_id}: {rejection_reason}")
        
        return {
            "message": "Issue rejected successfully",
            "issue_id": issue_id,
            "rejection_reason": rejection_reason,
            "penalty_applied": apply_penalty,
            "penalty_info": penalty_info
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reject issue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/issues/{issue_id}")
async def delete_issue(
    issue_id: str,
    request: Request,
    reason: str = Query(..., description="Reason for deletion"),
    admin: AdminTokenData = Depends(get_current_admin)
):
    """
    Delete an issue permanently (HARD DELETE)
    
    Accepts either:
    - Original issue ID (from issues table)
    - Verified issue ID (from issues_verified table)
    
    ⚠️ WARNING: This is irreversible!
    
    Deletes from ALL tables:
    - issues (main table)
    - issues_verified
    - issues_rejected
    - timeline_events
    - issue_upvotes
    - dm_notification_queue
    - All related records (CASCADE)
    """
    try:
        supabase = get_supabase()
        
        # Try to find the issue in issues table first
        issue_result = supabase.table("issues").select("id, title, reported_by, verification_status").eq(
            "id", issue_id
        ).limit(1).execute()
        
        # If not found, check if this is a verified issue ID
        if not issue_result.data:
            verified_result = supabase.table("issues_verified").select(
                "original_issue_id, generated_title"
            ).eq("id", issue_id).limit(1).execute()
            
            if verified_result.data:
                # Get the original issue ID
                original_id = verified_result.data[0]["original_issue_id"]
                issue_result = supabase.table("issues").select(
                    "id, title, reported_by, verification_status"
                ).eq("id", original_id).limit(1).execute()
                
                if issue_result.data:
                    issue_info = issue_result.data[0]
                    issue_info["was_verified_id"] = True
                else:
                    raise HTTPException(status_code=404, detail="Original issue not found")
            else:
                raise HTTPException(status_code=404, detail="Issue not found in any table")
        else:
            issue_info = issue_result.data[0]
            issue_info["was_verified_id"] = False
        
        original_issue_id = issue_info["id"]
        title = issue_info["title"]
        
        # HARD DELETE: Delete from all tables manually (in case CASCADE doesn't work)
        # 1. Delete from issues_verified
        try:
            supabase.table("issues_verified").delete().eq("original_issue_id", original_issue_id).execute()
            logger.info(f"Deleted from issues_verified for issue {original_issue_id}")
        except Exception as e:
            logger.warning(f"Could not delete from issues_verified: {e}")
        
        # 2. Delete from issues_rejected
        try:
            supabase.table("issues_rejected").delete().eq("original_issue_id", original_issue_id).execute()
            logger.info(f"Deleted from issues_rejected for issue {original_issue_id}")
        except Exception as e:
            logger.warning(f"Could not delete from issues_rejected: {e}")
        
        # 3. Delete from timeline_events
        try:
            supabase.table("timeline_events").delete().eq("issue_id", original_issue_id).execute()
            logger.info(f"Deleted from timeline_events for issue {original_issue_id}")
        except Exception as e:
            logger.warning(f"Could not delete from timeline_events: {e}")
        
        # 4. Delete from dm_notification_queue
        try:
            supabase.table("dm_notification_queue").delete().eq("original_issue_id", original_issue_id).execute()
            logger.info(f"Deleted from dm_notification_queue for issue {original_issue_id}")
        except Exception as e:
            logger.warning(f"Could not delete from dm_notification_queue: {e}")
        
        # 5. Delete from issue_upvotes
        try:
            supabase.table("issue_upvotes").delete().eq("issue_id", original_issue_id).execute()
            logger.info(f"Deleted from issue_upvotes for issue {original_issue_id}")
        except Exception as e:
            logger.warning(f"Could not delete from issue_upvotes: {e}")
        
        # 6. Finally, delete from main issues table
        result = supabase.table("issues").delete().eq("id", original_issue_id).execute()
        
        # Log admin action
        await log_admin_action(
            admin=admin,
            action_type="delete_issue",
            resource_type="issue",
            resource_id=original_issue_id,
            details={
                "title": title,
                "reason": reason,
                "reported_by": issue_info.get("reported_by"),
                "verification_status": issue_info.get("verification_status"),
                "was_verified_id_provided": issue_info.get("was_verified_id", False),
                "provided_id": issue_id
            },
            request=request
        )
        
        logger.critical(f"🗑️ Admin {admin.email} HARD DELETED issue {original_issue_id} ({title}): {reason}")
        
        return {
            "message": "Issue permanently deleted from all tables",
            "original_issue_id": original_issue_id,
            "provided_id": issue_id,
            "title": title,
            "reason": reason,
            "deleted_from_tables": [
                "issues",
                "issues_verified",
                "issues_rejected",
                "timeline_events",
                "dm_notification_queue",
                "issue_upvotes"
            ],
            "warning": "This action is irreversible"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete issue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/issues/{issue_id}/process")
async def manually_process_issue(
    issue_id: str,
    admin: AdminTokenData = Depends(get_current_admin)
):
    """
    Manually trigger AI verification for a pending issue
    """
    try:
        from app.verification_worker import verify_issue_async
        import asyncio
        
        # Reset retry count
        supabase = get_supabase()
        supabase.table("issues").update({"retry_count": 0}).eq("id", issue_id).execute()
        
        # Trigger verification
        asyncio.create_task(verify_issue_async(issue_id))
        
        logger.info(f"🔄 Admin {admin.admin_id} triggered verification for issue {issue_id}")
        
        return {
            "message": "Verification queued for processing",
            "issue_id": issue_id,
            "note": "Check logs for processing status"
        }
    
    except Exception as e:
        logger.error(f"Failed to manually process issue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# ABUSE & SECURITY
# ============================================

@router.get("/abuse/recent")
async def get_recent_abuse(
    severity: Optional[str] = Query(None, description="Filter by severity"),
    violation_type: Optional[str] = Query(None, description="Filter by type"),
    hours: int = Query(24, ge=1, le=168, description="Look back hours"),
    limit: int = Query(100, ge=1, le=500),
    admin: AdminTokenData = Depends(get_current_admin)
):
    """
    View recent abuse attempts and violations
    """
    try:
        supabase = get_supabase()
        
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        
        query = supabase.table("abuse_logs").select("*").gt("timestamp", cutoff)
        
        if severity:
            query = query.eq("severity", severity)
        
        if violation_type:
            query = query.eq("violation_type", violation_type)
        
        query = query.limit(limit).order("timestamp", desc=True)
        
        result = query.execute()
        
        return {
            "abuse_logs": result.data if result.data else [],
            "total": len(result.data) if result.data else 0,
            "period_hours": hours
        }
    
    except Exception as e:
        logger.error(f"Failed to get recent abuse: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system/health")
async def get_system_health(
    admin: AdminTokenData = Depends(get_current_admin)
):
    """
    System health check with component status
    """
    try:
        supabase = get_supabase()
        
        # Check database connection
        db_healthy = True
        try:
            supabase.table("users").select("id").limit(1).execute()
        except:
            db_healthy = False
        
        # Check AI verification queue
        pending_count = supabase.table("issues").select("id", count="exact").eq(
            "verification_status", "pending"
        ).execute()
        
        # Check for stuck issues
        hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        stuck_issues = supabase.table("issues").select("id", count="exact").eq(
            "verification_status", "pending"
        ).lt("reported_at", hour_ago).execute()
        
        health_status = "healthy"
        issues_found = []
        
        if not db_healthy:
            health_status = "critical"
            issues_found.append("Database connection failed")
        
        if (stuck_issues.count or 0) > 10:
            health_status = "degraded" if health_status == "healthy" else health_status
            issues_found.append(f"{stuck_issues.count} issues stuck in pending")
        
        return {
            "status": health_status,
            "components": {
                "database": "healthy" if db_healthy else "critical",
                "ai_verification_queue": "healthy" if (pending_count.count or 0) < 100 else "warning"
            },
            "alerts": issues_found,
            "metrics": {
                "pending_verification": pending_count.count or 0,
                "stuck_issues": stuck_issues.count or 0
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Failed to get system health: {e}")
        return {
            "status": "critical",
            "components": {},
            "alerts": [f"Health check failed: {str(e)}"],
            "timestamp": datetime.utcnow().isoformat()
        }
