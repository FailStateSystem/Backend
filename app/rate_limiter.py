"""
Rate Limiting Service
Implements user-based and IP-based rate limiting with dynamic limits based on trust score
"""

import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RateLimit:
    """Rate limit configuration"""
    max_per_hour: int
    max_per_day: int
    cooldown_seconds: int = 60


@dataclass
class RateLimitResult:
    """Result of rate limit check"""
    allowed: bool
    reason: str = ""
    retry_after: Optional[int] = None  # Seconds until user can retry
    current_count: int = 0
    limit: int = 0


class RateLimiterService:
    """Handles user and IP-based rate limiting"""
    
    # Default rate limits
    DEFAULT_LIMITS = RateLimit(max_per_hour=10, max_per_day=50)
    LOW_TRUST_LIMITS = RateLimit(max_per_hour=3, max_per_day=10)
    HIGH_TRUST_LIMITS = RateLimit(max_per_hour=20, max_per_day=100)
    
    # IP rate limits (stricter)
    IP_LIMITS = RateLimit(max_per_hour=20, max_per_day=100)
    IP_REJECTION_LIMITS = RateLimit(max_per_hour=10, max_per_day=30)  # For rejected attempts
    
    def __init__(self, supabase_client):
        self.supabase = supabase_client
    
    def _get_user_limits(self, trust_score: int) -> RateLimit:
        """Get rate limits based on user trust score"""
        if trust_score < 30:
            return self.LOW_TRUST_LIMITS
        elif trust_score >= 80:
            return self.HIGH_TRUST_LIMITS
        else:
            return self.DEFAULT_LIMITS
    
    async def check_user_rate_limit(
        self,
        user_id: str,
        trust_score: int = 100
    ) -> RateLimitResult:
        """
        Check if user has exceeded rate limits
        
        Args:
            user_id: User UUID
            trust_score: User's current trust score (0-100)
        
        Returns:
            RateLimitResult indicating if request should be allowed
        """
        try:
            limits = self._get_user_limits(trust_score)
            
            # Check hourly limit
            hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
            hourly_result = self.supabase.table("user_rate_limit_tracking").select(
                "id", count="exact"
            ).eq("user_id", user_id).eq(
                "action_type", "issue_create"
            ).eq(
                "success", True
            ).gt("timestamp", hour_ago).execute()
            
            hourly_count = hourly_result.count or 0
            
            if hourly_count >= limits.max_per_hour:
                logger.warning(f"User {user_id} exceeded hourly limit: {hourly_count}/{limits.max_per_hour}")
                return RateLimitResult(
                    False,
                    f"Hourly limit exceeded ({limits.max_per_hour} issues per hour)",
                    retry_after=3600,
                    current_count=hourly_count,
                    limit=limits.max_per_hour
                )
            
            # Check daily limit
            day_ago = (datetime.utcnow() - timedelta(days=1)).isoformat()
            daily_result = self.supabase.table("user_rate_limit_tracking").select(
                "id", count="exact"
            ).eq("user_id", user_id).eq(
                "action_type", "issue_create"
            ).eq(
                "success", True
            ).gt("timestamp", day_ago).execute()
            
            daily_count = daily_result.count or 0
            
            if daily_count >= limits.max_per_day:
                logger.warning(f"User {user_id} exceeded daily limit: {daily_count}/{limits.max_per_day}")
                return RateLimitResult(
                    False,
                    f"Daily limit exceeded ({limits.max_per_day} issues per day)",
                    retry_after=86400,
                    current_count=daily_count,
                    limit=limits.max_per_day
                )
            
            logger.debug(f"User {user_id} rate limit OK: {hourly_count}h/{daily_count}d")
            return RateLimitResult(
                True,
                "Rate limit OK",
                current_count=hourly_count,
                limit=limits.max_per_hour
            )
            
        except Exception as e:
            logger.error(f"Rate limit check error for user {user_id}: {e}")
            # Fail open (allow) on error
            return RateLimitResult(True, f"Error: {str(e)}")
    
    async def check_ip_rate_limit(
        self,
        ip_address: str,
        check_rejections: bool = False
    ) -> RateLimitResult:
        """
        Check if IP has exceeded rate limits
        
        Args:
            ip_address: Client IP address
            check_rejections: If True, check rejected attempts instead of successful
        
        Returns:
            RateLimitResult indicating if request should be allowed
        """
        try:
            limits = self.IP_REJECTION_LIMITS if check_rejections else self.IP_LIMITS
            action_filter = False if check_rejections else True
            
            # Check hourly limit
            hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
            hourly_result = self.supabase.table("ip_rate_limit_tracking").select(
                "id", count="exact"
            ).eq("ip_address", ip_address).eq(
                "action_type", "issue_create"
            ).eq(
                "success", action_filter
            ).gt("timestamp", hour_ago).execute()
            
            hourly_count = hourly_result.count or 0
            
            if hourly_count >= limits.max_per_hour:
                logger.warning(f"IP {ip_address} exceeded hourly limit: {hourly_count}/{limits.max_per_hour}")
                return RateLimitResult(
                    False,
                    f"IP rate limit exceeded ({limits.max_per_hour} per hour)",
                    retry_after=3600,
                    current_count=hourly_count,
                    limit=limits.max_per_hour
                )
            
            # Check daily limit
            day_ago = (datetime.utcnow() - timedelta(days=1)).isoformat()
            daily_result = self.supabase.table("ip_rate_limit_tracking").select(
                "id", count="exact"
            ).eq("ip_address", ip_address).eq(
                "action_type", "issue_create"
            ).gt("timestamp", day_ago).execute()
            
            daily_count = daily_result.count or 0
            
            if daily_count >= limits.max_per_day:
                logger.warning(f"IP {ip_address} exceeded daily limit: {daily_count}/{limits.max_per_day}")
                return RateLimitResult(
                    False,
                    f"IP rate limit exceeded ({limits.max_per_day} per day)",
                    retry_after=86400,
                    current_count=daily_count,
                    limit=limits.max_per_day
                )
            
            logger.debug(f"IP {ip_address} rate limit OK: {hourly_count}h/{daily_count}d")
            return RateLimitResult(
                True,
                "IP rate limit OK",
                current_count=hourly_count,
                limit=limits.max_per_hour
            )
            
        except Exception as e:
            logger.error(f"IP rate limit check error for {ip_address}: {e}")
            # Fail open (allow) on error
            return RateLimitResult(True, f"Error: {str(e)}")
    
    async def check_ip_blacklist(self, ip_address: str) -> Tuple[bool, Optional[str]]:
        """
        Check if IP is blacklisted
        
        Returns:
            (is_blacklisted, reason)
        """
        try:
            result = self.supabase.table("ip_blacklist").select("*").eq(
                "ip_address", ip_address
            ).execute()
            
            if not result.data:
                return False, None
            
            ban = result.data[0]
            
            # Check if temporary ban has expired
            if ban.get('banned_until'):
                banned_until = datetime.fromisoformat(ban['banned_until'].replace('Z', '+00:00'))
                if datetime.utcnow().replace(tzinfo=banned_until.tzinfo) > banned_until:
                    # Ban expired, remove it
                    self.supabase.table("ip_blacklist").delete().eq(
                        "ip_address", ip_address
                    ).execute()
                    logger.info(f"Removed expired ban for IP {ip_address}")
                    return False, None
            
            # Still banned
            reason = ban.get('reason', 'IP blocked due to abuse')
            logger.warning(f"Blocked request from blacklisted IP {ip_address}: {reason}")
            return True, reason
            
        except Exception as e:
            logger.error(f"IP blacklist check error: {e}")
            return False, None
    
    async def record_attempt(
        self,
        user_id: str,
        ip_address: str,
        success: bool
    ):
        """Record a submission attempt"""
        try:
            # Record user tracking
            self.supabase.table("user_rate_limit_tracking").insert({
                "user_id": user_id,
                "action_type": "issue_create",
                "success": success
            }).execute()
            
            # Record IP tracking
            self.supabase.table("ip_rate_limit_tracking").insert({
                "ip_address": ip_address,
                "action_type": "issue_create",
                "success": success,
                "user_id": user_id
            }).execute()
            
        except Exception as e:
            logger.error(f"Failed to record attempt: {e}")
    
    async def escalate_ip_ban(
        self,
        ip_address: str,
        reason: str,
        violation_count: int
    ):
        """
        Escalate IP ban based on violation count
        
        - 1-2 violations: 1 hour ban
        - 3-5 violations: 24 hour ban
        - 6-10 violations: 7 day ban
        - 10+ violations: Permanent ban
        """
        try:
            ban_duration = None
            
            if violation_count <= 2:
                ban_duration = datetime.utcnow() + timedelta(hours=1)
            elif violation_count <= 5:
                ban_duration = datetime.utcnow() + timedelta(days=1)
            elif violation_count <= 10:
                ban_duration = datetime.utcnow() + timedelta(days=7)
            # else: Permanent (ban_duration = None)
            
            # Check if already banned
            existing = self.supabase.table("ip_blacklist").select("*").eq(
                "ip_address", ip_address
            ).execute()
            
            if existing.data:
                # Update existing ban
                self.supabase.table("ip_blacklist").update({
                    "violation_count": violation_count,
                    "reason": reason,
                    "banned_until": ban_duration.isoformat() if ban_duration else None
                }).eq("ip_address", ip_address).execute()
            else:
                # Create new ban
                self.supabase.table("ip_blacklist").insert({
                    "ip_address": ip_address,
                    "reason": reason,
                    "banned_until": ban_duration.isoformat() if ban_duration else None,
                    "violation_count": violation_count
                }).execute()
            
            duration_str = f"until {ban_duration}" if ban_duration else "permanently"
            logger.warning(f"🚫 IP {ip_address} banned {duration_str}: {reason}")
            
        except Exception as e:
            logger.error(f"Failed to escalate IP ban: {e}")

