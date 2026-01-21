"""
District Management API
=======================
Admin endpoints for managing district boundaries, authorities, and routing

Authentication: Requires valid JWT token
Authorization: Admin-only endpoints (TODO: Add admin role checking)
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.models import (
    DistrictBoundary,
    DistrictAuthority,
    DistrictAuthorityCreate,
    DistrictAuthorityUpdate,
    RoutingLog,
    TokenData
)
from app.auth import get_current_user
from app.database import get_supabase
from app.district_routing import get_routing_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# ================================================
# DISTRICT BOUNDARIES
# ================================================

@router.get("/boundaries", response_model=List[DistrictBoundary])
async def list_district_boundaries(
    state_name: Optional[str] = Query(None, description="Filter by state name"),
    search: Optional[str] = Query(None, description="Search district name"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: TokenData = Depends(get_current_user)
):
    """
    List all district boundaries (without geometry for performance)
    
    Query params:
    - state_name: Filter by state
    - search: Search district names (case-insensitive)
    - limit: Max results (default 100, max 1000)
    - offset: Pagination offset
    """
    try:
        supabase = get_supabase()
        
        # Build query
        query = supabase.table('district_boundaries').select(
            'id, district_name, state_name, source, source_version, created_at'
        )
        
        # Apply filters
        if state_name:
            query = query.eq('state_name', state_name)
        
        if search:
            query = query.ilike('district_name', f'%{search}%')
        
        # Apply pagination
        query = query.range(offset, offset + limit - 1).order('district_name')
        
        result = query.execute()
        
        return result.data if result.data else []
    
    except Exception as e:
        logger.error(f"Failed to list district boundaries: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve district boundaries: {str(e)}"
        )


@router.get("/boundaries/{district_id}", response_model=DistrictBoundary)
async def get_district_boundary(
    district_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Get a specific district boundary by ID"""
    try:
        supabase = get_supabase()
        
        result = supabase.table('district_boundaries').select(
            'id, district_name, state_name, source, source_version, shape_id, created_at'
        ).eq('id', district_id).limit(1).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"District boundary not found: {district_id}"
            )
        
        return result.data[0]
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get district boundary {district_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/boundaries/search/point")
async def find_district_by_coordinates(
    lat: float = Query(..., description="Latitude", ge=-90, le=90),
    lng: float = Query(..., description="Longitude", ge=-180, le=180),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Find district containing a lat/lng point (point-in-polygon lookup)
    
    Returns district info + routing metadata (fallback, confidence, etc.)
    """
    try:
        routing_service = get_routing_service()
        district_data = routing_service.find_district(lat, lng)
        
        if not district_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No district found for coordinates ({lat}, {lng})"
            )
        
        return district_data
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to find district for ({lat}, {lng}): {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ================================================
# DISTRICT AUTHORITIES
# ================================================

@router.get("/authorities", response_model=List[DistrictAuthority])
async def list_district_authorities(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    state_name: Optional[str] = Query(None, description="Filter by state"),
    has_email: Optional[bool] = Query(None, description="Filter by email presence"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: TokenData = Depends(get_current_user)
):
    """
    List all district authorities with contact information
    
    Query params:
    - is_active: Filter by active/inactive status
    - state_name: Filter by state
    - has_email: Show only authorities with/without email
    - limit: Max results
    - offset: Pagination offset
    """
    try:
        supabase = get_supabase()
        
        # Build query with join to get district info
        query = supabase.table('district_authorities').select(
            '''
            id,
            district_id,
            dm_office_email,
            fallback_email,
            authority_name,
            phone_number,
            office_address,
            last_verified,
            confidence_score,
            is_active,
            notes,
            created_at,
            district_boundaries!inner(district_name, state_name)
            '''
        )
        
        # Apply filters
        if is_active is not None:
            query = query.eq('is_active', is_active)
        
        if state_name:
            query = query.eq('district_boundaries.state_name', state_name)
        
        # Apply pagination
        query = query.range(offset, offset + limit - 1)
        
        result = query.execute()
        
        # Flatten the nested district_boundaries data
        authorities = []
        for item in (result.data if result.data else []):
            authority = {**item}
            if 'district_boundaries' in authority:
                authority['district_name'] = authority['district_boundaries'].get('district_name')
                authority['state_name'] = authority['district_boundaries'].get('state_name')
                del authority['district_boundaries']
            authorities.append(authority)
        
        return authorities
    
    except Exception as e:
        logger.error(f"Failed to list district authorities: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/authorities/{authority_id}", response_model=DistrictAuthority)
async def get_district_authority(
    authority_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Get a specific district authority by ID"""
    try:
        supabase = get_supabase()
        
        result = supabase.table('district_authorities').select(
            '''
            id,
            district_id,
            dm_office_email,
            fallback_email,
            authority_name,
            phone_number,
            office_address,
            last_verified,
            confidence_score,
            is_active,
            notes,
            created_at,
            district_boundaries!inner(district_name, state_name)
            '''
        ).eq('id', authority_id).limit(1).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"District authority not found: {authority_id}"
            )
        
        # Flatten nested data
        authority = result.data[0]
        if 'district_boundaries' in authority:
            authority['district_name'] = authority['district_boundaries'].get('district_name')
            authority['state_name'] = authority['district_boundaries'].get('state_name')
            del authority['district_boundaries']
        
        return authority
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get district authority {authority_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/authorities", response_model=DistrictAuthority, status_code=status.HTTP_201_CREATED)
async def create_district_authority(
    authority_data: DistrictAuthorityCreate,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Create a new district authority entry
    
    Admin only
    """
    try:
        supabase = get_supabase()
        
        # Verify district exists
        district_result = supabase.table('district_boundaries').select('id').eq(
            'id', authority_data.district_id
        ).limit(1).execute()
        
        if not district_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"District not found: {authority_data.district_id}"
            )
        
        # Check if authority already exists for this district
        existing = supabase.table('district_authorities').select('id').eq(
            'district_id', authority_data.district_id
        ).limit(1).execute()
        
        if existing.data:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Authority already exists for district: {authority_data.district_id}"
            )
        
        # Insert authority
        result = supabase.table('district_authorities').insert(
            authority_data.dict()
        ).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create district authority"
            )
        
        # Fetch complete data with district info
        return await get_district_authority(result.data[0]['id'], current_user)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create district authority: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.patch("/authorities/{authority_id}", response_model=DistrictAuthority)
async def update_district_authority(
    authority_id: str,
    authority_data: DistrictAuthorityUpdate,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Update a district authority
    
    Admin only
    """
    try:
        supabase = get_supabase()
        
        # Only update provided fields
        update_dict = {k: v for k, v in authority_data.dict().items() if v is not None}
        
        if not update_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        result = supabase.table('district_authorities').update(update_dict).eq(
            'id', authority_id
        ).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"District authority not found: {authority_id}"
            )
        
        # Return updated authority
        return await get_district_authority(authority_id, current_user)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update district authority {authority_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/authorities/{authority_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_district_authority(
    authority_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Delete a district authority
    
    Admin only - USE WITH CAUTION
    """
    try:
        supabase = get_supabase()
        
        result = supabase.table('district_authorities').delete().eq(
            'id', authority_id
        ).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"District authority not found: {authority_id}"
            )
        
        return None
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete district authority {authority_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ================================================
# ROUTING LOGS & STATISTICS
# ================================================

@router.get("/routing/logs", response_model=List[RoutingLog])
async def get_routing_logs(
    district_id: Optional[str] = Query(None, description="Filter by district"),
    fallback_only: bool = Query(False, description="Show only fallback routes"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Get routing logs for observability
    
    Query params:
    - district_id: Filter by district
    - fallback_only: Show only routes that used fallback
    - limit: Max results
    - offset: Pagination
    """
    try:
        supabase = get_supabase()
        
        query = supabase.table('district_routing_log').select('*')
        
        if district_id:
            query = query.eq('district_id', district_id)
        
        if fallback_only:
            query = query.eq('fallback_used', True)
        
        query = query.range(offset, offset + limit - 1).order('created_at', desc=True)
        
        result = query.execute()
        
        return result.data if result.data else []
    
    except Exception as e:
        logger.error(f"Failed to get routing logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/routing/stats")
async def get_routing_statistics(
    current_user: TokenData = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get routing statistics (accuracy, fallback rate, etc.)
    """
    try:
        supabase = get_supabase()
        
        # Use the pre-created view
        result = supabase.table('routing_statistics').select('*').limit(1).execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0]
        else:
            return {
                "total_routed": 0,
                "exact_matches": 0,
                "fallback_matches": 0,
                "avg_fallback_distance_km": 0,
                "max_fallback_distance_km": 0
            }
    
    except Exception as e:
        logger.error(f"Failed to get routing statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/authorities/summary")
async def get_authority_summary(
    current_user: TokenData = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get summary of all districts with authority status and issue counts
    """
    try:
        supabase = get_supabase()
        
        # Use the pre-created view
        result = supabase.table('district_authority_summary').select('*').execute()
        
        return result.data if result.data else []
    
    except Exception as e:
        logger.error(f"Failed to get authority summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

