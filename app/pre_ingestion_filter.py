"""
Pre-Ingestion Filter Orchestrator
Main entry point for all filtering - runs BEFORE image upload and BEFORE AI calls
This is the protection layer that shields expensive operations
"""

import logging
from typing import Tuple, Dict, Any, Optional
from dataclasses import dataclass

from app.content_filters import ContentFilterService
from app.rate_limiter import RateLimiterService
from app.trust_system import TrustSystemService

logger = logging.getLogger(__name__)


@dataclass
class FilteringDecision:
    """Result of the complete filtering process"""
    allowed: bool
    reason: str
    severity: str = "low"  # low, medium, high, critical
    retry_after: Optional[int] = None
    trust_score: int = 100
    details: Dict[str, Any] = None
    is_shadow_banned: bool = False
    
    def __bool__(self):
        return self.allowed


class PreIngestionFilter:
    """
    Orchestrates ALL pre-ingestion filters in the mandated order:
    1. Shadow ban check
    2. IP blacklist check
    3. User rate limit
    4. IP rate limit
    5. NSFW detection
    6. Duplicate detection
    7. OCR / screenshot detection
    8. Garbage image detection
    9. EXIF metadata check
    10. Trust score evaluation
    
    Only if ALL pass → proceed to image upload + AI pipeline
    """
    
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.content_filters = ContentFilterService(supabase_client)
        self.rate_limiter = RateLimiterService(supabase_client)
        self.trust_system = TrustSystemService(supabase_client)
    
    async def run_all_checks(
        self,
        user_id: str,
        ip_address: str,
        image_bytes: bytes,
        submission_data: Dict[str, Any]
    ) -> FilteringDecision:
        """
        Run ALL filtering checks in order
        
        This is the main entry point - call this BEFORE any expensive operations
        
        Args:
            user_id: User UUID
            ip_address: Client IP address
            image_bytes: Image data (not yet uploaded)
            submission_data: Full submission data (for shadow ban storage)
        
        Returns:
            FilteringDecision indicating if submission should proceed
        """
        
        logger.info(f"🛡️ Starting pre-ingestion filter for user {user_id} from IP {ip_address}")
        
        # ============================================
        # STEP 0: SHADOW BAN CHECK (HIGHEST PRIORITY)
        # ============================================
        logger.info("Step 0: Checking shadow ban status")
        is_shadow_banned = await self.trust_system.is_shadow_banned(user_id)
        
        if is_shadow_banned:
            # Store submission but don't process
            await self.trust_system.store_shadow_banned_submission(
                user_id, ip_address, submission_data
            )
            
            logger.warning(f"🚫 Shadow banned user {user_id} - faking acceptance")
            
            # Return success to hide shadow ban from user
            return FilteringDecision(
                allowed=False,
                reason="Shadow banned (hidden from user)",
                severity="critical",
                is_shadow_banned=True,
                details={"shadow_banned": True}
            )
        
        # ============================================
        # STEP 1: IP BLACKLIST CHECK
        # ============================================
        logger.info("Step 1: Checking IP blacklist")
        is_blacklisted, blacklist_reason = await self.rate_limiter.check_ip_blacklist(ip_address)
        
        if is_blacklisted:
            logger.warning(f"🚫 Blacklisted IP {ip_address}: {blacklist_reason}")
            
            await self.trust_system.log_abuse(
                user_id, ip_address,
                "ip_blacklisted", "critical",
                {"reason": blacklist_reason},
                "rejected"
            )
            
            return FilteringDecision(
                allowed=False,
                reason=f"IP blocked: {blacklist_reason}",
                severity="critical",
                details={"ip_blacklisted": True}
            )
        
        # Get user trust score (needed for rate limits)
        trust_score = await self.trust_system.get_user_trust_score(user_id)
        logger.info(f"User {user_id} trust score: {trust_score}")
        
        # ============================================
        # STEP 2: USER RATE LIMIT
        # ============================================
        logger.info("Step 2: Checking user rate limit")
        user_rate_result = await self.rate_limiter.check_user_rate_limit(user_id, trust_score)
        
        if not user_rate_result.allowed:
            logger.warning(f"❌ User {user_id} rate limit exceeded: {user_rate_result.reason}")
            
            # Record failed attempt
            await self.rate_limiter.record_attempt(user_id, ip_address, False)
            
            # Log and decrease trust
            await self.trust_system.log_abuse(
                user_id, ip_address,
                "rate_limit", "low",
                {"reason": user_rate_result.reason},
                "rejected"
            )
            
            new_trust = await self.trust_system.update_trust_score(
                user_id,
                self.trust_system.TRUST_DELTAS['rate_limit'],
                "Rate limit exceeded"
            )
            
            return FilteringDecision(
                allowed=False,
                reason=user_rate_result.reason,
                severity="low",
                retry_after=user_rate_result.retry_after,
                trust_score=new_trust,
                details={"rate_limit": True}
            )
        
        # ============================================
        # STEP 3: IP RATE LIMIT
        # ============================================
        logger.info("Step 3: Checking IP rate limit")
        ip_rate_result = await self.rate_limiter.check_ip_rate_limit(ip_address)
        
        if not ip_rate_result.allowed:
            logger.warning(f"❌ IP {ip_address} rate limit exceeded: {ip_rate_result.reason}")
            
            # Record failed attempt
            await self.rate_limiter.record_attempt(user_id, ip_address, False)
            
            # Log abuse
            await self.trust_system.log_abuse(
                user_id, ip_address,
                "ip_rate_limit", "medium",
                {"reason": ip_rate_result.reason},
                "rejected"
            )
            
            return FilteringDecision(
                allowed=False,
                reason=ip_rate_result.reason,
                severity="medium",
                retry_after=ip_rate_result.retry_after,
                trust_score=trust_score,
                details={"ip_rate_limit": True}
            )
        
        # ============================================
        # STEP 4-8: CONTENT FILTERS
        # (NSFW, Duplicate, OCR, Garbage, EXIF)
        # ============================================
        logger.info("Steps 4-8: Running content filters")
        content_passed, content_results = await self.content_filters.run_all_filters(
            image_bytes, user_id, ip_address
        )
        
        if not content_passed:
            # Find which filter failed
            failed_filter = None
            for filter_name, result in content_results.items():
                if not result.passed:
                    failed_filter = result
                    break
            
            logger.warning(f"❌ Content filter failed: {failed_filter.filter_name} - {failed_filter.reason}")
            
            # Record failed attempt
            await self.rate_limiter.record_attempt(user_id, ip_address, False)
            
            # Log abuse
            await self.trust_system.log_abuse(
                user_id, ip_address,
                failed_filter.filter_name,
                failed_filter.severity,
                failed_filter.details,
                "rejected"
            )
            
            # Update trust score
            trust_delta = self.trust_system.TRUST_DELTAS.get(failed_filter.filter_name, -5)
            new_trust = await self.trust_system.update_trust_score(
                user_id,
                trust_delta,
                f"{failed_filter.filter_name} violation"
            )
            
            # Update filtering stats
            try:
                self.supabase.rpc("increment_filter_stat", {
                    "p_filter_type": failed_filter.filter_name,
                    "p_blocked": True
                }).execute()
            except:
                pass
            
            # Check for coordinated attack (if duplicate)
            if failed_filter.filter_name == "duplicate":
                # TODO: Implement coordinated attack detection
                pass
            
            return FilteringDecision(
                allowed=False,
                reason=failed_filter.reason,
                severity=failed_filter.severity,
                trust_score=new_trust,
                details={"filter": failed_filter.filter_name, **failed_filter.details}
            )
        
        # ============================================
        # STEP 9: TRUST SCORE EVALUATION
        # ============================================
        logger.info("Step 9: Evaluating trust score")
        
        # If trust score is very low but not shadow banned yet, apply stricter checks
        if trust_score < 30:
            logger.warning(f"⚠️ User {user_id} has low trust score ({trust_score})")
            # Could add additional checks here
        
        # ============================================
        # ALL CHECKS PASSED ✅
        # ============================================
        
        # Record successful attempt
        await self.rate_limiter.record_attempt(user_id, ip_address, True)
        
        # Update filtering stats for all passed filters
        for filter_name in content_results.keys():
            try:
                self.supabase.rpc("increment_filter_stat", {
                    "p_filter_type": filter_name,
                    "p_blocked": False
                }).execute()
            except:
                pass
        
        logger.info(f"✅ All pre-ingestion filters passed for user {user_id}")
        
        return FilteringDecision(
            allowed=True,
            reason="All checks passed",
            severity="low",
            trust_score=trust_score,
            details={"all_filters_passed": True, "filter_results": {
                k: v.reason for k, v in content_results.items()
            }}
        )
    
    async def post_upload_actions(
        self,
        user_id: str,
        ip_address: str,
        image_bytes: bytes,
        image_url: str,
        issue_id: str
    ):
        """
        Actions to run AFTER successful upload
        (Store hashes, update stats, etc.)
        """
        try:
            # Store image hash for future duplicate detection
            await self.content_filters.store_image_hash(
                image_bytes, user_id, ip_address, image_url, issue_id
            )
            
            logger.info(f"Post-upload actions completed for issue {issue_id}")
            
        except Exception as e:
            logger.error(f"Post-upload actions failed: {e}")

