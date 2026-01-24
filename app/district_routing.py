"""
District Routing Service
========================
Geospatial point-in-polygon lookup for mapping civic issues to administrative districts

Features:
- Point-in-polygon lookup using PostGIS ST_Contains
- Automatic fallback to nearest district if no exact match
- Observability logging for all routing decisions
- Severity-based DM notification queueing
- Performance optimized with spatial indexes

DO NOT modify AI verification pipeline
"""

import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from decimal import Decimal
from app.database import get_supabase
from postgrest.exceptions import APIError

logger = logging.getLogger(__name__)


class DistrictRoutingService:
    """
    Service for routing civic issues to administrative districts
    """
    
    def __init__(self):
        self.supabase = get_supabase()
    
    def find_district(
        self,
        latitude: float,
        longitude: float
    ) -> Optional[Dict[str, Any]]:
        """
        Find district containing the given lat/lng point
        
        Uses PostGIS point-in-polygon with automatic fallback
        
        Args:
            latitude: Latitude (-90 to 90)
            longitude: Longitude (-180 to 180)
        
        Returns:
            dict with keys:
                - district_id: UUID
                - district_name: str
                - state_name: str (may be None)
                - routing_method: 'point_in_polygon' or 'fallback_nearest'
                - fallback_used: bool
                - fallback_distance_km: float (if fallback used)
                - confidence_score: float (0.0 to 1.0)
            
            Returns None if no district found (should never happen with fallback)
        """
        try:
            # Call PostGIS function
            result = self.supabase.rpc(
                'find_district_by_point',
                {
                    'p_latitude': latitude,
                    'p_longitude': longitude
                }
            ).execute()
            
            # Extract result
            if result.data and len(result.data) > 0:
                district_data = result.data[0]
                
                logger.info(
                    f"✅ District routing: {district_data['district_name']} "
                    f"({district_data['routing_method']}, "
                    f"confidence={district_data['confidence_score']})"
                )
                
                return district_data
            else:
                logger.error(f"❌ No district found for ({latitude}, {longitude})")
                return None
        
        except Exception as e:
            logger.error(f"❌ District routing error: {e}")
            return None
    
    def log_routing_decision(
        self,
        issue_id: Optional[str],
        original_issue_id: Optional[str],
        latitude: float,
        longitude: float,
        district_data: Optional[Dict[str, Any]],
        processing_time_ms: int,
        error_message: Optional[str] = None
    ) -> None:
        """
        Log routing decision for observability
        
        Args:
            issue_id: ID from issues table (if raw issue)
            original_issue_id: ID from issues_verified table (if verified)
            latitude: Latitude of issue
            longitude: Longitude of issue
            district_data: Result from find_district() or None if error
            processing_time_ms: Time taken for routing (milliseconds)
            error_message: Error message if routing failed
        """
        try:
            log_entry = {
                'issue_id': issue_id,
                'original_issue_id': original_issue_id,
                'latitude': latitude,
                'longitude': longitude,
                'processing_time_ms': processing_time_ms,
                'created_at': datetime.utcnow().isoformat()
            }
            
            if district_data:
                log_entry.update({
                    'district_id': district_data['district_id'],
                    'district_name': district_data['district_name'],
                    'state_name': district_data.get('state_name'),
                    'routing_method': district_data['routing_method'],
                    'fallback_used': district_data['fallback_used'],
                    'fallback_distance_km': district_data.get('fallback_distance_km'),
                    'confidence_score': district_data['confidence_score']
                })
            else:
                log_entry['error_message'] = error_message or 'Unknown error'
            
            # Insert log
            self.supabase.table('district_routing_log').insert(log_entry).execute()
            
        except Exception as e:
            logger.error(f"⚠️ Failed to log routing decision: {e}")
            # Don't raise - logging failure shouldn't break routing
    
    def route_issue(
        self,
        issue_id: str,
        latitude: float,
        longitude: float,
        table_name: str = 'issues'
    ) -> bool:
        """
        Route an issue to a district and update the issue record
        
        Args:
            issue_id: ID of the issue to route
            latitude: Issue latitude
            longitude: Issue longitude
            table_name: 'issues' or 'issues_verified'
        
        Returns:
            True if routing successful, False otherwise
        """
        start_time = datetime.utcnow()
        
        try:
            # Find district
            district_data = self.find_district(latitude, longitude)
            
            if not district_data:
                processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                self.log_routing_decision(
                    issue_id if table_name == 'issues' else None,
                    issue_id if table_name == 'issues_verified' else None,
                    latitude,
                    longitude,
                    None,
                    processing_time_ms,
                    "No district found"
                )
                return False
            
            # Update issue with district info
            update_data = {
                'district_id': district_data['district_id'],
                'district_name': district_data['district_name'],
                'state_name': district_data.get('state_name'),
                'routing_status': 'routed',
                'routing_method': district_data['routing_method'],
                'routed_at': datetime.utcnow().isoformat()
            }
            
            self.supabase.table(table_name).update(update_data).eq('id', issue_id).execute()
            
            # Log routing decision
            processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            self.log_routing_decision(
                issue_id if table_name == 'issues' else None,
                issue_id if table_name == 'issues_verified' else None,
                latitude,
                longitude,
                district_data,
                processing_time_ms
            )
            
            logger.info(f"✅ Routed issue {issue_id} to {district_data['district_name']}")
            return True
        
        except Exception as e:
            processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            error_message = str(e)
            logger.error(f"❌ Failed to route issue {issue_id}: {error_message}")
            
            self.log_routing_decision(
                issue_id if table_name == 'issues' else None,
                issue_id if table_name == 'issues_verified' else None,
                latitude,
                longitude,
                None,
                processing_time_ms,
                error_message
            )
            return False
    
    def queue_dm_notification(
        self,
        issue_id: str,
        original_issue_id: Optional[str],
        district_id: str,
        severity: str
    ) -> Optional[str]:
        """
        Queue a notification to district authority based on severity
        
        Args:
            issue_id: ID from issues table
            original_issue_id: ID from issues_verified table (if applicable)
            district_id: UUID of district
            severity: 'high', 'moderate', or 'low'
        
        Returns:
            Queue entry ID if successful, None otherwise
        """
        try:
            result = self.supabase.rpc(
                'queue_dm_notification',
                {
                    'p_issue_id': issue_id,
                    'p_original_issue_id': original_issue_id,
                    'p_district_id': district_id,
                    'p_severity': severity
                }
            ).execute()
            
            if result.data:
                queue_id = result.data
                logger.info(f"✅ Queued DM notification: {queue_id} (severity={severity})")
                return queue_id
            else:
                logger.warning(f"⚠️ No authority found for district {district_id}")
                return None
        
        except Exception as e:
            logger.error(f"❌ Failed to queue DM notification: {e}")
            return None
    
    def get_district_authority(
        self,
        district_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get district authority contact information
        
        Args:
            district_id: UUID of district
        
        Returns:
            dict with authority details or None if not found
        """
        try:
            result = self.supabase.table('district_authorities')\
                .select('*')\
                .eq('district_id', district_id)\
                .eq('is_active', True)\
                .limit(1)\
                .execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            else:
                logger.warning(f"⚠️ No active authority found for district {district_id}")
                return None
        
        except Exception as e:
            logger.error(f"❌ Failed to get district authority: {e}")
            return None
    
    def route_and_notify(
        self,
        issue_id: str,
        original_issue_id: Optional[str],
        latitude: float,
        longitude: float,
        severity: str,
        table_name: str = 'issues_verified'
    ) -> Tuple[bool, Optional[str]]:
        """
        Complete routing workflow: find district + queue notification
        
        Args:
            issue_id: ID from issues table
            original_issue_id: ID from issues_verified table (if applicable)
            latitude: Issue latitude
            longitude: Issue longitude
            severity: 'high', 'moderate', or 'low' (from AI analysis)
            table_name: 'issues' or 'issues_verified'
        
        Returns:
            (routing_success: bool, queue_id: Optional[str])
        """
        # Route issue
        routing_success = self.route_issue(issue_id, latitude, longitude, table_name)
        
        if not routing_success:
            return False, None
        
        # Get district_id from updated record
        try:
            result = self.supabase.table(table_name)\
                .select('district_id')\
                .eq('id', issue_id)\
                .limit(1)\
                .execute()
            
            if not result.data or len(result.data) == 0:
                logger.error(f"❌ Failed to retrieve district_id for issue {issue_id}")
                return True, None  # Routing succeeded but notification failed
            
            district_id = result.data[0]['district_id']
            
            # Queue notification
            queue_id = self.queue_dm_notification(
                issue_id,
                original_issue_id,
                district_id,
                severity
            )
            
            return True, queue_id
        
        except Exception as e:
            logger.error(f"❌ Failed to queue notification for issue {issue_id}: {e}")
            return True, None  # Routing succeeded but notification failed


# Singleton instance
_routing_service: Optional[DistrictRoutingService] = None


def get_routing_service() -> DistrictRoutingService:
    """
    Get singleton instance of DistrictRoutingService
    """
    global _routing_service
    if _routing_service is None:
        _routing_service = DistrictRoutingService()
    return _routing_service


def route_verified_issue(
    issue_id: str,
    original_issue_id: str,
    latitude: float,
    longitude: float,
    severity: str
) -> bool:
    """
    Convenience function: Route a verified issue and queue DM notification
    
    Called after AI verification succeeds
    
    Args:
        issue_id: ID from issues table (original issue)
        original_issue_id: ID from issues_verified table
        latitude: Issue latitude
        longitude: Issue longitude
        severity: AI-determined severity ('high', 'moderate', 'low')
    
    Returns:
        True if routing successful, False otherwise
    """
    try:
        routing_service = get_routing_service()
        
        # Route and notify (updates issues_verified table)
        routing_success, queue_id = routing_service.route_and_notify(
            original_issue_id,  # Use verified issue ID
            original_issue_id,
            latitude,
            longitude,
            severity,
            table_name='issues_verified'
        )
        
        if routing_success:
            # CRITICAL FIX: Also update the original issues table with district info
            try:
                # Get district info from issues_verified
                verified_result = routing_service.supabase.table('issues_verified')\
                    .select('district_id, district_name, state_name, routing_status, routing_method, routed_at')\
                    .eq('id', original_issue_id)\
                    .limit(1)\
                    .execute()
                
                if verified_result.data and len(verified_result.data) > 0:
                    district_info = verified_result.data[0]
                    
                    # Update original issues table
                    routing_service.supabase.table('issues').update({
                        'district_id': district_info['district_id'],
                        'district_name': district_info['district_name'],
                        'state_name': district_info.get('state_name'),
                        'routing_status': district_info.get('routing_status'),
                        'routing_method': district_info.get('routing_method'),
                        'routed_at': district_info.get('routed_at')
                    }).eq('id', issue_id).execute()
                    
                    logger.info(f"✅ Updated original issue {issue_id} with district info")
            except Exception as copy_error:
                logger.error(f"⚠️ Failed to copy district info to issues table: {copy_error}")
                # Don't fail the whole process if this copy fails
            
            if queue_id:
                logger.info(f"✅ Issue {original_issue_id} routed and queued for DM notification")
            else:
                logger.warning(f"⚠️ Issue {original_issue_id} routed but no authority to notify")
            return True
        else:
            logger.error(f"❌ Failed to route issue {original_issue_id}")
            return False
    
    except Exception as e:
        logger.error(f"❌ Routing error for issue {original_issue_id}: {e}")
        return False

