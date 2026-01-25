"""
AI Verification Service
Handles OpenAI integration for issue verification and enrichment
"""

import logging
import json
import base64
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from app.config import settings
import httpx

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = None
if settings.OPENAI_API_KEY:
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, timeout=settings.AI_TIMEOUT_SECONDS)


class AIVerificationResponse(BaseModel):
    """Structured response from AI verification"""
    is_genuine: bool
    is_civic_issue: bool  # CRITICAL: True only if public space + govt responsibility
    confidence_score: float = Field(ge=0.0, le=1.0)
    reasoning: str
    severity: str  # low | moderate | high
    generated_title: str
    generated_description: str
    public_impact: str
    tags: list[str] = Field(default_factory=list)
    content_warnings: list[str] = Field(default_factory=list)
    
    # Additional checks when pre-ingestion filters are unavailable
    is_nsfw: bool = False  # True if image contains NSFW content
    is_screenshot: bool = False  # True if image is a screenshot/meme


SYSTEM_PROMPT = """You are a civic issue verification and analysis engine.

Your job is to:
- Determine if a reported civic issue is genuine or fake.
- **CRITICAL: Determine if the issue is ACTUALLY a civic/public infrastructure issue under government responsibility.**
- Check if the image contains NSFW content (nudity, explicit content, violence, gore).
- Check if the image is a screenshot, meme, or social media post (rather than a real photo).
- Analyze the image and description together.
- Assess severity.
- Generate public-safe, factual, dramatic but non-defamatory content.
- Output strictly valid JSON.

You must be conservative.
If uncertain, mark the issue as NOT genuine OR NOT civic.

Never make accusations.
Never assign blame.
Never speculate intent.
Only describe observable reality.

Use neutral, factual language.

CRITICAL CIVIC ISSUE GATE (TRUST-CRITICAL):
An issue is ONLY civic if ALL three conditions are met:
1. Occurs in PUBLIC SPACE (not private property)
2. Maintained by GOVERNMENT / MUNICIPAL authority
3. Impacts GENERAL PUBLIC (not private business/residence)

Mark is_civic_issue=false if ANY of these apply:
- Private business (shop, restaurant, mall, office)
- Private property (apartment, house, personal residence)
- Shop signage (even if broken/unlit)
- Private bathroom (even if claimed as "public toilet")
- Private vehicle
- Indoor spaces (default to false unless unmistakably public/govt building)
- Anything owned by an individual or company

Even if image is real and problem exists, if it's private property → is_civic_issue=false

When ambiguous → REJECT (is_civic_issue=false, is_genuine=false)
Conservative bias is mandatory. False negatives are acceptable. False positives damage trust.

IMPORTANT CONTENT CHECKS:
- Mark is_nsfw=true if the image contains any nudity, sexual content, extreme violence, or gore.
- Mark is_screenshot=true if the image is clearly a screenshot of a phone/computer, a meme with text overlays, or a social media post.
- These checks are critical for content safety and quality."""


def create_user_prompt(description: str, lat: float, lng: float) -> str:
    """Create the user prompt for AI verification"""
    return f"""Analyze the following civic issue submission.

INPUTS:
User description: {description}
Location: {lat}, {lng}
Image: Provided in image content

TASKS:
1. **CONTENT SAFETY CHECKS** (Critical - check these first):
   - Check if image contains NSFW content (nudity, sexual content, extreme violence, gore)
   - Check if image is a screenshot, meme, or social media post
   
2. **CIVIC ISSUE GATE** (Trust-critical - apply strict rules):
   - Check if issue occurs in PUBLIC SPACE (not private property)
   - Check if maintained by GOVERNMENT (not private business/individual)
   - Check if impacts GENERAL PUBLIC (not private residence/shop)
   - Indoor scenes → default is_civic_issue=false unless unmistakably govt building
   - Shop signage, private bathrooms, private vehicles → is_civic_issue=false
   - When in doubt → is_civic_issue=false
   
3. Verify if this is a real-world, genuine image (not AI-generated, edited, or fake).
4. Check if the image and description are semantically consistent.
5. Assess severity: low, moderate, or high (only if civic issue).
6. Generate (only if is_genuine=true AND is_civic_issue=true):
   - A public-facing dramatic but factual title
   - A refined public description
   - A public impact explanation
   - A list of relevant tags

RULES:
- Do NOT name people.
- Do NOT accuse authorities.
- Do NOT speculate intent.
- Do NOT use political language.
- Do NOT use emotional manipulation.
- Do NOT invent facts.

OUTPUT FORMAT (JSON ONLY):
{{
  "is_genuine": true/false,
  "is_civic_issue": true/false,
  "is_nsfw": true/false,
  "is_screenshot": true/false,
  "confidence_score": 0-1,
  "reasoning": "Explain why genuine/fake AND why civic/not-civic. Be specific about ownership (public vs private).",
  "severity": "low | moderate | high",
  "generated_title": "",
  "generated_description": "",
  "public_impact": "",
  "tags": ["", "", ""],
  "content_warnings": []
}}

CRITICAL NOTES:
- If is_nsfw=true OR is_screenshot=true → set is_genuine=false
- If is_civic_issue=false (private property) → set is_genuine=false
- Only set is_genuine=true if BOTH: real image AND civic issue
- Reasoning MUST explain civic determination (public vs private space)"""


async def download_image_as_base64(image_url: str) -> Optional[str]:
    """
    Download image from Supabase and convert to base64 to avoid OpenAI timeout
    
    OpenAI has issues downloading directly from some Supabase URLs due to timeouts.
    This function downloads the image first and sends it as base64 data URI.
    """
    try:
        logger.info(f"📥 Downloading image from Supabase: {image_url[:80]}...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(image_url)
            response.raise_for_status()
            
            # Get content type
            content_type = response.headers.get('content-type', 'image/jpeg')
            
            # Convert to base64
            image_data = response.content
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            # Create data URI
            data_uri = f"data:{content_type};base64,{base64_image}"
            
            logger.info(f"✅ Downloaded and encoded image ({len(image_data)} bytes)")
            return data_uri
            
    except Exception as e:
        logger.error(f"Failed to download image from {image_url}: {e}")
        return None


async def verify_issue_with_ai(
    image_url: str,
    description: str,
    lat: float,
    lng: float,
    max_retries: Optional[int] = None
) -> Optional[AIVerificationResponse]:
    """
    Verify an issue using OpenAI Vision API
    
    Args:
        image_url: URL of the issue image
        description: User's description
        lat: Latitude
        lng: Longitude
        max_retries: Maximum retry attempts
    
    Returns:
        AIVerificationResponse if successful, None if failed
    """
    if not client:
        logger.error("OpenAI client not initialized. Check OPENAI_API_KEY.")
        return None
    
    if not image_url:
        logger.warning("No image provided for AI verification")
        return None
    
    retries = max_retries or settings.AI_MAX_RETRIES
    user_prompt = create_user_prompt(description, lat, lng)
    
    # Download image and convert to base64 to avoid OpenAI timeout issues
    image_data_uri = await download_image_as_base64(image_url)
    
    if not image_data_uri:
        logger.error("Failed to download image for AI verification")
        return None
    
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"AI verification attempt {attempt}/{retries}")
            
            # Call OpenAI with vision using base64-encoded image
            response = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_data_uri,  # Use base64 data URI
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=1000,
                temperature=0.3  # Low temperature for consistency
            )
            
            # Parse response
            content = response.choices[0].message.content
            logger.info(f"AI raw response: {content}")
            
            # Parse JSON
            try:
                data = json.loads(content)
                verification = AIVerificationResponse(**data)
                logger.info(f"✅ AI verification successful: is_genuine={verification.is_genuine}")
                return verification
                
            except (json.JSONDecodeError, Exception) as parse_error:
                logger.error(f"Failed to parse AI response: {parse_error}")
                logger.error(f"Raw content: {content}")
                
                if attempt < retries:
                    logger.info("Retrying due to parse error...")
                    continue
                else:
                    logger.error("Max retries reached for parsing")
                    return None
        
        except Exception as e:
            logger.error(f"AI verification error (attempt {attempt}/{retries}): {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            
            # Don't retry on quota/rate limit errors - these need manual intervention
            error_type = type(e).__name__
            if error_type in ["RateLimitError", "InsufficientQuotaError"] or "quota" in str(e).lower():
                logger.error(f"⚠️ Quota/Rate limit error detected. Issue will remain pending for manual processing.")
                return None  # Return None immediately without retrying
            
            if attempt < retries:
                logger.info("Retrying after error...")
                continue
            else:
                logger.error("Max retries reached")
                return None
    
    return None


async def verify_issue_without_ai(description: str) -> AIVerificationResponse:
    """
    Fallback: Create a basic verification response without AI
    Used when AI is disabled or unavailable
    """
    logger.warning("AI verification disabled or unavailable - using fallback")
    
    return AIVerificationResponse(
        is_genuine=True,  # Assume genuine when AI unavailable
        is_civic_issue=True,  # Assume civic when AI unavailable (requires manual review)
        confidence_score=0.5,
        reasoning="AI verification unavailable - manual review required",
        severity="moderate",
        generated_title=description[:100] if description else "Civic Issue Reported",
        generated_description=description or "No description provided",
        public_impact="This issue requires manual review and verification",
        tags=["pending-review", "unverified"],
        content_warnings=["unverified"]
    )


async def batch_verify_issues(issues: list[Dict[str, Any]]) -> list[tuple[str, Optional[AIVerificationResponse]]]:
    """
    Verify multiple issues in batch
    
    Args:
        issues: List of issue dictionaries with id, image_url, description, lat, lng
    
    Returns:
        List of tuples (issue_id, verification_response)
    """
    results = []
    
    for issue in issues:
        issue_id = issue.get('id')
        image_url = issue.get('image_url')
        description = issue.get('description', '')
        lat = issue.get('location_lat', 0)
        lng = issue.get('location_lng', 0)
        
        if not image_url:
            logger.warning(f"Issue {issue_id} has no image - skipping AI verification")
            verification = await verify_issue_without_ai(description)
        else:
            verification = await verify_issue_with_ai(image_url, description, lat, lng)
            
            if not verification:
                logger.error(f"AI verification failed for issue {issue_id} - using fallback")
                verification = await verify_issue_without_ai(description)
        
        results.append((issue_id, verification))
    
    return results

