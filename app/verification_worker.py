"""
Background Verification Worker
Processes issues through AI verification pipeline
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional
from app.database import get_supabase
from app.ai_verification import verify_issue_with_ai, verify_issue_without_ai, AIVerificationResponse
from app.config import settings
import traceback

logger = logging.getLogger(__name__)


class VerificationWorker:
    """
    Background worker that processes pending issues through AI verification
    """
    
    def __init__(self):
        self.supabase = get_supabase()
        self.processing_lock = set()  # In-memory lock for idempotency
    
    async def log_audit(self, issue_id: str, status: str, attempt: int = 1, 
                       error_msg: Optional[str] = None, ai_response: Optional[dict] = None,
                       processing_time_ms: Optional[int] = None):
        """Log verification attempt to audit table"""
        try:
            audit_entry = {
                "issue_id": issue_id,
                "status": status,
                "attempt_number": attempt,
                "error_message": error_msg,
                "ai_raw_response": ai_response,
                "ai_model_used": settings.OPENAI_MODEL if ai_response else None,
                "processing_time_ms": processing_time_ms
            }
            self.supabase.table("verification_audit_log").insert(audit_entry).execute()
        except Exception as e:
            logger.error(f"Failed to log audit: {e}")
    
    async def mark_issue_processed(self, issue_id: str, status: str):
        """Mark issue as processed in issues table"""
        try:
            self.supabase.table("issues").update({
                "verification_status": status,
                "processed_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", issue_id).execute()
        except Exception as e:
            logger.error(f"Failed to mark issue {issue_id} as processed: {e}")
    
    async def increment_retry_count(self, issue_id: str) -> int:
        """Increment retry count for an issue and return new count"""
        try:
            # Get current retry count
            result = self.supabase.table("issues").select("retry_count").eq("id", issue_id).execute()
            
            if not result.data:
                return 0
            
            current_count = result.data[0].get("retry_count", 0) or 0
            new_count = current_count + 1
            
            # Update retry count
            self.supabase.table("issues").update({
                "retry_count": new_count
            }).eq("id", issue_id).execute()
            
            logger.info(f"Issue {issue_id} retry count: {new_count}/3")
            return new_count
            
        except Exception as e:
            logger.error(f"Failed to increment retry count: {e}")
            return 0
    
    async def create_verified_issue(self, original_issue: dict, verification: AIVerificationResponse):
        """Create entry in issues_verified table"""
        try:
            verified_data = {
                "original_issue_id": original_issue["id"],
                "is_genuine": verification.is_genuine,
                "ai_confidence_score": verification.confidence_score,
                "ai_reasoning": verification.reasoning,
                "severity": verification.severity,
                "generated_title": verification.generated_title,
                "generated_description": verification.generated_description,
                "public_impact": verification.public_impact,
                "tags": verification.tags,
                "content_warnings": verification.content_warnings,
                # Denormalized fields from original
                "category": original_issue["category"],
                "location_name": original_issue["location_name"],
                "location_lat": original_issue["location_lat"],
                "location_lng": original_issue["location_lng"],
                "image_url": original_issue.get("image_url"),
                "video_url": original_issue.get("video_url"),
                "reported_by": original_issue["reported_by"],
                "status": original_issue.get("status", "unresolved"),
                "upvotes": original_issue.get("upvotes", 0),
                "reported_at": original_issue["reported_at"],
                "verified_at": datetime.utcnow().isoformat()
            }
            
            result = self.supabase.table("issues_verified").insert(verified_data).execute()
            
            if result.data:
                logger.info(f"✅ Created verified issue for {original_issue['id']}")
                return result.data[0]
            else:
                logger.error(f"Failed to create verified issue - no data returned")
                return None
                
        except Exception as e:
            logger.error(f"Failed to create verified issue: {e}")
            logger.error(traceback.format_exc())
            return None
    
    async def create_rejected_issue(self, original_issue: dict, verification: AIVerificationResponse):
        """Create entry in issues_rejected table"""
        try:
            # Determine rejection reason based on AI response
            rejection_reason = "ai_verification_failed"
            
            if verification.is_nsfw:
                rejection_reason = "nsfw_content_detected"
            elif verification.is_screenshot:
                rejection_reason = "screenshot_or_meme_detected"
            elif not verification.is_genuine:
                rejection_reason = "not_genuine_civic_issue"
            
            rejected_data = {
                "original_issue_id": original_issue["id"],
                "rejection_reason": rejection_reason,
                "ai_reasoning": verification.reasoning,
                "confidence_score": verification.confidence_score,
                "rejected_by": "ai_verification"
            }
            
            result = self.supabase.table("issues_rejected").insert(rejected_data).execute()
            
            if result.data:
                logger.info(f"✅ Created rejected issue for {original_issue['id']} - Reason: {rejection_reason}")
                return result.data[0]
            else:
                logger.error(f"Failed to create rejected issue - no data returned")
                return None
                
        except Exception as e:
            logger.error(f"Failed to create rejected issue: {e}")
            logger.error(traceback.format_exc())
            return None
    
    async def apply_fake_submission_penalty(self, original_issue: dict, verification: AIVerificationResponse):
        """
        Apply penalty for fake submission using database function
        """
        try:
            user_id = original_issue["reported_by"]
            issue_id = original_issue["id"]
            
            # Determine rejection reason
            rejection_reason = "not_genuine_civic_issue"
            if verification.is_nsfw:
                rejection_reason = "nsfw_content_detected"
            elif verification.is_screenshot:
                rejection_reason = "screenshot_or_meme_detected"
            
            # Call database function to apply penalty
            # Note: Supabase RPC with JSON return can throw APIError even on success
            penalty_info = None
            try:
                result = self.supabase.rpc("apply_fake_submission_penalty", {
                    "p_user_id": user_id,
                    "p_issue_id": issue_id,
                    "p_rejection_reason": rejection_reason,
                    "p_ai_reasoning": verification.reasoning,
                    "p_confidence_score": verification.confidence_score
                }).execute()
                
                # RPC function returns JSON, data will be in result.data
                if result.data:
                    # If data is a list, get first element (Supabase RPC returns single value as list)
                    penalty_info = result.data[0] if isinstance(result.data, list) else result.data
                    
            except Exception as rpc_error:
                # Supabase throws APIError when RPC returns raw JSON, but penalty is actually applied
                # Try to extract the penalty info from the error message
                error_str = str(rpc_error)
                if "penalty_applied" in error_str and "rejection_count" in error_str:
                    # Parse the JSON from error message (it's actually the successful response)
                    try:
                        import json
                        # Extract JSON from error string
                        json_start = error_str.find("{")
                        json_end = error_str.rfind("}") + 1
                        if json_start >= 0 and json_end > json_start:
                            penalty_info = json.loads(error_str[json_start:json_end])
                            logger.info(f"✅ Extracted penalty info from RPC 'error' (actually success)")
                    except:
                        pass
                
                if not penalty_info:
                    # True error - penalty really failed
                    logger.error(f"❌ RPC call actually failed: {rpc_error}")
            
            # Send email with penalty info
            if penalty_info:
                penalty_applied = penalty_info.get("penalty_applied")
                points_deducted = penalty_info.get("points_deducted", 0)
                account_status = penalty_info.get("account_status")
                message = penalty_info.get("message")
                
                logger.info(f"⚠️ Penalty applied to user {user_id}: {penalty_applied}")
                logger.info(f"   Points deducted: {points_deducted}, Status: {account_status}")
                logger.info(f"   Message: {message}")
                
                # Send email notification about rejection and penalty
                await self.send_rejection_email(
                    original_issue,
                    rejection_reason,
                    penalty_applied,
                    points_deducted,
                    account_status,
                    message
                )
            else:
                # Truly failed - send generic rejection email without penalty details
                logger.error(f"Failed to apply penalty - sending generic rejection email")
                await self.send_rejection_email(
                    original_issue,
                    rejection_reason,
                    "system_error",
                    0,
                    "active",
                    "This submission violates our guidelines. Repeated violations may result in penalties."
                )
            
        except Exception as e:
            logger.error(f"Failed to apply fake submission penalty: {e}")
            logger.error(traceback.format_exc())
    
    async def send_rejection_email(
        self,
        original_issue: dict,
        rejection_reason: str,
        penalty_applied: str,
        points_deducted: int,
        account_status: str,
        message: str
    ):
        """
        Send email notification about issue rejection
        """
        try:
            from app.email_service import send_rejection_notification
            
            user_id = original_issue["reported_by"]
            
            # Get user email
            user_result = self.supabase.table("users").select("email, username").eq("id", user_id).execute()
            
            if not user_result.data or len(user_result.data) == 0:
                logger.error(f"User {user_id} not found for rejection email")
                return
            
            user = user_result.data[0]
            
            await send_rejection_notification(
                to_email=user["email"],
                username=user["username"],
                issue_description=original_issue.get("description", ""),
                rejection_reason=rejection_reason,
                penalty_applied=penalty_applied,
                points_deducted=points_deducted,
                account_status=account_status,
                warning_message=message
            )
            
            logger.info(f"📧 Sent rejection email to {user['email']}")
            
        except Exception as e:
            logger.error(f"Failed to send rejection email: {e}")
            logger.error(traceback.format_exc())
    
    async def trigger_post_verification_hooks(self, verified_issue: dict, original_issue: dict):
        """
        Trigger post-verification hooks:
        - Reward points
        - Email notifications
        - Timeline events
        """
        try:
            user_id = original_issue["reported_by"]
            
            # Award points for verified issue
            try:
                self.supabase.rpc("add_user_points", {
                    "user_id": user_id,
                    "points": 25
                }).execute()
                logger.info(f"✅ Awarded points to user {user_id}")
            except Exception as e:
                logger.error(f"Failed to award points: {e}")
            
            # Send success email notification
            try:
                await self.send_verification_success_email(original_issue, verified_issue)
            except Exception as e:
                logger.error(f"Failed to send verification success email: {e}")
            
            # Create timeline event
            try:
                timeline_event = {
                    "issue_id": verified_issue["id"],
                    "type": "verified",
                    "description": f"Issue verified and published (Confidence: {verified_issue['ai_confidence_score']})",
                    "timestamp": datetime.utcnow().isoformat()
                }
                # Note: This would need to reference verified issue's ID in timeline
                # For now, we'll skip this or create a separate timeline for verified issues
                logger.info("Timeline event creation skipped - needs verified issue timeline table")
            except Exception as e:
                logger.error(f"Failed to create timeline event: {e}")
            
            # TODO: Trigger email notifications to authorities
            # This should be implemented based on location/category
            
        except Exception as e:
            logger.error(f"Failed to trigger post-verification hooks: {e}")
    
    async def send_verification_success_email(self, original_issue: dict, verified_issue: dict):
        """
        Send email notification about successful verification
        """
        try:
            from app.email_service import send_verification_success_notification
            
            user_id = original_issue["reported_by"]
            
            # Get user email
            user_result = self.supabase.table("users").select("email, username").eq("id", user_id).execute()
            
            if not user_result.data or len(user_result.data) == 0:
                logger.error(f"User {user_id} not found for success email")
                return
            
            user = user_result.data[0]
            
            await send_verification_success_notification(
                to_email=user["email"],
                username=user["username"],
                issue_title=verified_issue.get("generated_title", ""),
                issue_description=verified_issue.get("generated_description", ""),
                severity=verified_issue.get("severity", "moderate"),
                confidence_score=verified_issue.get("ai_confidence_score", 0),
                points_awarded=25
            )
            
            logger.info(f"📧 Sent verification success email to {user['email']}")
            
        except Exception as e:
            logger.error(f"Failed to send verification success email: {e}")
            logger.error(traceback.format_exc())
    
    async def process_issue(self, issue: dict) -> bool:
        """
        Process a single issue through verification pipeline
        
        Returns:
            True if processed successfully, False otherwise
        """
        issue_id = issue["id"]
        
        # Idempotency check - skip if already processing
        if issue_id in self.processing_lock:
            logger.warning(f"Issue {issue_id} already being processed - skipping")
            return False
        
        try:
            self.processing_lock.add(issue_id)
            start_time = datetime.utcnow()
            
            logger.info(f"🔄 Processing issue {issue_id}")
            await self.log_audit(issue_id, "processing")
            
            # Increment retry count
            new_retry_count = await self.increment_retry_count(issue_id)
            
            # Check if max retries exceeded
            if new_retry_count >= 3:
                logger.error(f"⛔ Issue {issue_id} has exceeded max retries (3). Requires manual intervention.")
                await self.log_audit(
                    issue_id,
                    "pending_manual",
                    error_msg=f"Max retries ({new_retry_count}) exceeded - requires manual processing"
                )
                # Keep as pending but won't be picked up automatically anymore
                return False
            
            # Get image and description
            image_url = issue.get("image_url")
            description = issue.get("description", "")
            lat = issue.get("location_lat", 0)
            lng = issue.get("location_lng", 0)
            
            # Verify with AI
            if settings.AI_VERIFICATION_ENABLED and image_url:
                verification = await verify_issue_with_ai(image_url, description, lat, lng)
                
                if not verification:
                    # AI failed - keep issue in pending state for later retry
                    logger.warning(f"⚠️ AI verification unavailable for {issue_id} (attempt {new_retry_count}/3)")
                    await self.log_audit(
                        issue_id, 
                        "pending",
                        error_msg=f"AI service unavailable (attempt {new_retry_count}/3) - quota exceeded or service down"
                    )
                    # Don't mark as failed - leave in pending for later retry (if < 3 attempts)
                    return False
            else:
                logger.info(f"AI verification disabled or no image - using fallback")
                verification = await verify_issue_without_ai(description)
            
            processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Check for content violations first
            should_reject = False
            rejection_type = None
            
            if verification.is_nsfw:
                should_reject = True
                rejection_type = "NSFW content"
                logger.warning(f"🚫 Issue {issue_id} contains NSFW content")
            elif verification.is_screenshot:
                should_reject = True
                rejection_type = "Screenshot/Meme"
                logger.warning(f"🚫 Issue {issue_id} is a screenshot or meme")
            elif not verification.is_genuine:
                should_reject = True
                rejection_type = "Not genuine"
                logger.info(f"❌ Issue {issue_id} is not a genuine civic issue")
            
            # Log successful verification
            await self.log_audit(
                issue_id, 
                "rejected" if should_reject else "verified",
                ai_response=verification.dict(),
                processing_time_ms=processing_time
            )
            
            # Route based on verification result
            if should_reject:
                logger.info(f"❌ Issue {issue_id} REJECTED - {rejection_type} (confidence: {verification.confidence_score})")
                
                rejected_issue = await self.create_rejected_issue(issue, verification)
                
                if rejected_issue:
                    await self.mark_issue_processed(issue_id, "rejected")
                    
                    # Apply penalty for fake submission
                    await self.apply_fake_submission_penalty(issue, verification)
                    
                    return True
                else:
                    await self.mark_issue_processed(issue_id, "failed")
                    return False
            else:
                logger.info(f"✅ Issue {issue_id} verified as GENUINE (confidence: {verification.confidence_score})")
                
                verified_issue = await self.create_verified_issue(issue, verification)
                
                if verified_issue:
                    await self.mark_issue_processed(issue_id, "verified")
                    await self.trigger_post_verification_hooks(verified_issue, issue)
                    return True
                else:
                    await self.mark_issue_processed(issue_id, "failed")
                    return False
        
        except Exception as e:
            logger.error(f"❌ Failed to process issue {issue_id}: {e}")
            logger.error(traceback.format_exc())
            await self.log_audit(issue_id, "failed", error_msg=str(e))
            await self.mark_issue_processed(issue_id, "failed")
            return False
        
        finally:
            self.processing_lock.discard(issue_id)
    
    async def process_pending_issues(self, batch_size: int = 10) -> int:
        """
        Process a batch of pending issues (only those with retry_count < 3)
        
        Returns:
            Number of issues processed
        """
        try:
            # Get pending issues that haven't exceeded max retries
            # Only process issues with retry_count < 3
            result = self.supabase.table("issues").select("*").eq(
                "verification_status", "pending"
            ).lt("retry_count", 3).limit(batch_size).execute()
            
            pending_issues = result.data if result.data else []
            
            if not pending_issues:
                logger.debug("No pending issues to process (all have exceeded max retries)")
                return 0
            
            logger.info(f"📦 Found {len(pending_issues)} pending issues to process")
            
            # Process each issue
            processed_count = 0
            for issue in pending_issues:
                success = await self.process_issue(issue)
                if success:
                    processed_count += 1
            
            logger.info(f"✅ Processed {processed_count}/{len(pending_issues)} issues")
            return processed_count
        
        except Exception as e:
            logger.error(f"Failed to process pending issues: {e}")
            logger.error(traceback.format_exc())
            return 0


# Global worker instance
worker = VerificationWorker()


async def verify_issue_async(issue_id: str) -> bool:
    """
    Verify a single issue asynchronously
    Can be called from API endpoint
    """
    try:
        result = worker.supabase.table("issues").select("*").eq("id", issue_id).execute()
        
        if not result.data:
            logger.error(f"Issue {issue_id} not found")
            return False
        
        issue = result.data[0]
        return await worker.process_issue(issue)
    
    except Exception as e:
        logger.error(f"Failed to verify issue {issue_id}: {e}")
        return False


async def process_verification_queue():
    """
    Main worker loop - processes verification queue continuously
    This can be run as a background task
    """
    logger.info("🚀 Verification worker started")
    
    while True:
        try:
            processed = await worker.process_pending_issues(batch_size=5)
            
            # Sleep longer if no issues to process
            if processed == 0:
                await asyncio.sleep(30)  # Check every 30 seconds when idle
            else:
                await asyncio.sleep(5)   # Check every 5 seconds when active
        
        except Exception as e:
            logger.error(f"Error in verification worker loop: {e}")
            await asyncio.sleep(60)  # Wait a bit longer on error

