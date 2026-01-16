"""
Trust Score and Abuse Tracking System
Manages user trust scores, abuse logging, shadow banning, and bot detection
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TrustSystemService:
    """Manages trust scores, abuse logs, and shadow bans"""
    
    # Trust score deltas for various violations
    TRUST_DELTAS = {
        'nsfw': -30,
        'duplicate': -10,
        'ocr': -5,
        'garbage': -5,
        'rate_limit': -3,
        'bot_behavior': -20,
        'verified_issue': +2,
        'issue_resolved': +5,
    }
    
    # Shadow ban thresholds
    SHADOW_BAN_TRUST_THRESHOLD = 20
    SHADOW_BAN_VIOLATION_THRESHOLD = 5  # 5 violations in 24 hours
    
    def __init__(self, supabase_client):
        self.supabase = supabase_client
    
    async def get_user_trust_score(self, user_id: str) -> int:
        """Get user's current trust score"""
        try:
            result = self.supabase.table("users").select("trust_score").eq(
                "id", user_id
            ).execute()
            
            if not result.data:
                return 100  # Default
            
            return result.data[0].get('trust_score', 100)
            
        except Exception as e:
            logger.error(f"Failed to get trust score for {user_id}: {e}")
            return 100  # Default on error
    
    async def update_trust_score(
        self,
        user_id: str,
        delta: int,
        reason: str
    ) -> int:
        """
        Update user trust score
        
        Args:
            user_id: User UUID
            delta: Amount to change trust score (positive or negative)
            reason: Reason for change
        
        Returns:
            New trust score
        """
        try:
            # Use database function for atomic update
            result = self.supabase.rpc("update_trust_score", {
                "p_user_id": user_id,
                "p_delta": delta
            }).execute()
            
            new_score = result.data if result.data else 100
            
            logger.info(f"Trust score for {user_id}: {new_score} (delta: {delta:+d}, reason: {reason})")
            
            # Check if trust score is critically low
            if new_score <= self.SHADOW_BAN_TRUST_THRESHOLD:
                await self._consider_shadow_ban(user_id, f"Trust score dropped to {new_score}")
            
            return new_score
            
        except Exception as e:
            logger.error(f"Failed to update trust score for {user_id}: {e}")
            return 100
    
    async def log_abuse(
        self,
        user_id: str,
        ip_address: str,
        violation_type: str,
        severity: str,
        details: Dict[str, Any],
        action_taken: str
    ):
        """
        Log an abuse attempt
        
        Args:
            user_id: User UUID
            ip_address: Client IP
            violation_type: Type of violation (nsfw, duplicate, etc.)
            severity: low, medium, high, critical
            details: Additional details as JSON
            action_taken: Action taken (rejected, trust_decreased, etc.)
        """
        try:
            # Log to abuse_logs table
            self.supabase.rpc("log_abuse", {
                "p_user_id": user_id,
                "p_ip_address": ip_address,
                "p_violation_type": violation_type,
                "p_severity": severity,
                "p_details": details,
                "p_action_taken": action_taken
            }).execute()
            
            # Update filtering stats
            self.supabase.rpc("increment_filter_stat", {
                "p_filter_type": violation_type,
                "p_blocked": True
            }).execute()
            
            logger.warning(
                f"📝 Abuse logged: user={user_id}, ip={ip_address}, "
                f"type={violation_type}, severity={severity}"
            )
            
            # Check if we should escalate actions
            await self._check_escalation(user_id, ip_address, violation_type)
            
        except Exception as e:
            logger.error(f"Failed to log abuse: {e}")
    
    async def _check_escalation(
        self,
        user_id: str,
        ip_address: str,
        violation_type: str
    ):
        """Check if we should escalate actions (shadow ban, IP ban)"""
        try:
            # Count recent violations (last 24 hours)
            day_ago = (datetime.utcnow() - timedelta(days=1)).isoformat()
            
            result = self.supabase.table("abuse_logs").select(
                "id", count="exact"
            ).eq("user_id", user_id).gt("timestamp", day_ago).execute()
            
            violation_count = result.count or 0
            
            # Shadow ban if too many violations
            if violation_count >= self.SHADOW_BAN_VIOLATION_THRESHOLD:
                await self.shadow_ban_user(
                    user_id,
                    f"{violation_count} violations in 24 hours"
                )
            
            # Check IP violations for IP ban
            ip_result = self.supabase.table("abuse_logs").select(
                "id", count="exact"
            ).eq("ip_address", ip_address).gt("timestamp", day_ago).execute()
            
            ip_violation_count = ip_result.count or 0
            
            if ip_violation_count >= 10:
                logger.warning(f"IP {ip_address} has {ip_violation_count} violations - consider IP ban")
            
        except Exception as e:
            logger.error(f"Failed to check escalation: {e}")
    
    async def _consider_shadow_ban(self, user_id: str, reason: str):
        """Consider shadow banning a user"""
        try:
            # Check if already shadow banned
            result = self.supabase.table("users").select("is_shadow_banned").eq(
                "id", user_id
            ).execute()
            
            if result.data and result.data[0].get('is_shadow_banned'):
                return  # Already shadow banned
            
            await self.shadow_ban_user(user_id, reason)
            
        except Exception as e:
            logger.error(f"Failed to consider shadow ban: {e}")
    
    async def shadow_ban_user(
        self,
        user_id: str,
        reason: str,
        duration: Optional[timedelta] = None
    ):
        """
        Shadow ban a user
        
        Shadow banned users:
        - Can still submit (no error message)
        - Submissions are accepted but not processed
        - No AI calls
        - No storage
        - No rewards
        - No public visibility
        """
        try:
            banned_until = None
            if duration:
                banned_until = (datetime.utcnow() + duration).isoformat()
            
            self.supabase.table("users").update({
                "is_shadow_banned": True,
                "ban_reason": reason,
                "banned_until": banned_until
            }).eq("id", user_id).execute()
            
            logger.warning(f"🚫 User {user_id} shadow banned: {reason}")
            
        except Exception as e:
            logger.error(f"Failed to shadow ban user {user_id}: {e}")
    
    async def is_shadow_banned(self, user_id: str) -> bool:
        """Check if user is shadow banned"""
        try:
            result = self.supabase.table("users").select(
                "is_shadow_banned, banned_until"
            ).eq("id", user_id).execute()
            
            if not result.data:
                return False
            
            user = result.data[0]
            
            # Check if temporary ban expired
            if user.get('banned_until'):
                banned_until = datetime.fromisoformat(user['banned_until'].replace('Z', '+00:00'))
                if datetime.utcnow().replace(tzinfo=banned_until.tzinfo) > banned_until:
                    # Ban expired, remove it
                    await self.unshadow_ban_user(user_id)
                    return False
            
            return user.get('is_shadow_banned', False)
            
        except Exception as e:
            logger.error(f"Failed to check shadow ban for {user_id}: {e}")
            return False
    
    async def unshadow_ban_user(self, user_id: str):
        """Remove shadow ban from user"""
        try:
            self.supabase.table("users").update({
                "is_shadow_banned": False,
                "ban_reason": None,
                "banned_until": None
            }).eq("id", user_id).execute()
            
            logger.info(f"User {user_id} shadow ban removed")
            
        except Exception as e:
            logger.error(f"Failed to unshadow ban user {user_id}: {e}")
    
    async def store_shadow_banned_submission(
        self,
        user_id: str,
        ip_address: str,
        submission_data: Dict[str, Any]
    ):
        """Store shadow banned user's submission (for later review/evidence)"""
        try:
            self.supabase.table("shadow_banned_submissions").insert({
                "user_id": user_id,
                "ip_address": ip_address,
                "submission_data": submission_data
            }).execute()
            
            logger.info(f"Stored shadow banned submission from {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to store shadow banned submission: {e}")
    
    async def detect_coordinated_attack(
        self,
        image_hash: str,
        user_ids: List[str],
        ip_addresses: List[str]
    ) -> bool:
        """
        Detect coordinated attacks (same image from multiple accounts/IPs)
        
        Returns:
            True if coordinated attack detected
        """
        try:
            # Check if same hash used by multiple users in short time
            hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
            
            result = self.supabase.table("image_hashes").select(
                "user_id", count="exact"
            ).eq("perceptual_hash", image_hash).gt(
                "uploaded_at", hour_ago
            ).execute()
            
            unique_users = len(set(result.data if result.data else []))
            
            # If same image from 3+ different users in 1 hour = coordinated attack
            if unique_users >= 3:
                logger.critical(
                    f"🚨 Coordinated attack detected: same image from {unique_users} users"
                )
                
                # Log bot detection pattern
                self.supabase.table("bot_detection_patterns").insert({
                    "pattern_type": "coordinated_image",
                    "pattern_data": {
                        "image_hash": image_hash,
                        "user_count": unique_users
                    },
                    "user_ids": user_ids,
                    "ip_addresses": ip_addresses,
                    "confidence_score": 0.95
                }).execute()
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to detect coordinated attack: {e}")
            return False
    
    async def get_user_violation_history(
        self,
        user_id: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get user's violation history"""
        try:
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            result = self.supabase.table("abuse_logs").select("*").eq(
                "user_id", user_id
            ).gt("timestamp", cutoff).order("timestamp", desc=True).execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"Failed to get violation history for {user_id}: {e}")
            return []

