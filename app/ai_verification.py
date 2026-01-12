"""
AI Verification Service
Handles OpenAI integration for issue verification and enrichment
"""

import logging
import json
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
    confidence_score: float = Field(ge=0.0, le=1.0)
    reasoning: str
    severity: str  # low | moderate | high
    generated_title: str
    generated_description: str
    public_impact: str
    tags: list[str] = Field(default_factory=list)
    content_warnings: list[str] = Field(default_factory=list)


SYSTEM_PROMPT = """You are a civic issue verification and analysis engine.

Your job is to:
- Determine if a reported civic issue is genuine or fake.
- Analyze the image and description together.
- Assess severity.
- Generate public-safe, factual, dramatic but non-defamatory content.
- Output strictly valid JSON.

You must be conservative.
If uncertain, mark the issue as NOT genuine.

Never make accusations.
Never assign blame.
Never speculate intent.
Only describe observable reality.

Use neutral, factual language."""


def create_user_prompt(description: str, lat: float, lng: float) -> str:
    """Create the user prompt for AI verification"""
    return f"""Analyze the following civic issue submission.

INPUTS:
User description: {description}
Location: {lat}, {lng}
Image: Provided in image content

TASKS:
1. Verify if this is a real-world, genuine civic/infrastructure issue.
2. Detect if the image appears AI-generated, edited, meme-like, or fake.
3. Check if the image and description are semantically consistent.
4. Assess severity: low, moderate, or high.
5. Generate:
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
  "confidence_score": 0-1,
  "reasoning": "Short explanation",
  "severity": "low | moderate | high",
  "generated_title": "",
  "generated_description": "",
  "public_impact": "",
  "tags": ["", "", ""],
  "content_warnings": []
}}"""


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
    
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"AI verification attempt {attempt}/{retries}")
            
            # Call OpenAI with vision
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
                                    "url": image_url,
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

