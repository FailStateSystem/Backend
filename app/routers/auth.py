from fastapi import APIRouter, HTTPException, status, Depends
from datetime import timedelta, datetime
from app.models import UserCreate, UserLogin, Token, User
from app.auth import get_password_hash, verify_password, create_access_token
from app.database import get_supabase
from app.config import settings
from app.email_service import send_verification_email, send_welcome_email
import secrets
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(user_data: UserCreate):
    """Register a new user and send verification email"""
    supabase = get_supabase()
    
    try:
        # Check if user already exists
        existing_user = supabase.table("users").select("*").eq("email", user_data.email).execute()
        if existing_user.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Check if username is taken
        existing_username = supabase.table("users").select("*").eq("username", user_data.username).execute()
        if existing_username.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
        
        # Hash password
        hashed_password = get_password_hash(user_data.password)
        
        # Generate verification token
        verification_token = secrets.token_urlsafe(32)
        verification_expires = datetime.utcnow() + timedelta(hours=24)
        
        # Create user
        new_user = {
            "email": user_data.email,
            "username": user_data.username,
            "password_hash": hashed_password,
            "credibility_score": 0,
            "issues_posted": 0,
            "issues_resolved": 0,
            "email_verified": False,
            "verification_token": verification_token,
            "verification_token_expires": verification_expires.isoformat()
        }
        
        result = supabase.table("users").insert(new_user).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )
        
        user = result.data[0]
        
        # Create user rewards entry
        user_rewards = {
            "user_id": user["id"],
            "total_points": 0,
            "current_tier": "Observer I",
            "milestones_reached": 0,
            "items_claimed": 0
        }
        supabase.table("user_rewards").insert(user_rewards).execute()
        
        # Send verification email (don't block if it fails)
        verification_link = f"{settings.BACKEND_URL}/api/auth/verify-email?token={verification_token}"
        email_sent = False
        try:
            email_sent = send_verification_email(user_data.email, user_data.username, verification_link)
        except Exception as e:
            logger.error(f"Failed to send verification email: {str(e)}")
        
        return {
            "message": "Account created successfully. Please check your email to verify your account." if email_sent else "Account created. Email service unavailable - contact support for verification.",
            "email": user_data.email,
            "username": user_data.username,
            "email_sent": email_sent
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.post("/login", response_model=Token)
async def login(login_data: UserLogin):
    """Authenticate user and return token"""
    supabase = get_supabase()
    
    try:
        # Get user by email
        result = supabase.table("users").select("*").eq("email", login_data.email).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        user = result.data[0]
        
        # Verify password
        if not verify_password(login_data.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Check if email is verified
        if not user.get("email_verified", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email not verified. Please check your email for the verification link."
            )
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user["id"], "email": user["email"]},
            expires_delta=access_token_expires
        )
        
        return Token(access_token=access_token, token_type="bearer")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )


@router.get("/verify-email")
async def verify_email(token: str):
    """Verify user's email address"""
    supabase = get_supabase()
    
    try:
        # Find user by verification token
        result = supabase.table("users").select("*").eq("verification_token", token).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification token"
            )
        
        user = result.data[0]
        
        # Check if token is expired
        token_expires = datetime.fromisoformat(user["verification_token_expires"].replace('Z', '+00:00'))
        if datetime.utcnow().replace(tzinfo=token_expires.tzinfo) > token_expires:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification token has expired. Please request a new one."
            )
        
        # Check if already verified
        if user.get("email_verified", False):
            # Redirect to frontend with success message
            return {
                "message": "Email already verified. You can now log in.",
                "redirect_url": f"{settings.FRONTEND_URL}/login?verified=true"
            }
        
        # Update user as verified
        supabase.table("users").update({
            "email_verified": True,
            "verification_token": None,
            "verification_token_expires": None
        }).eq("id", user["id"]).execute()
        
        # Send welcome email (don't block if it fails)
        login_link = f"{settings.FRONTEND_URL}/login"
        try:
            send_welcome_email(user["email"], user["username"], login_link)
        except Exception as e:
            logger.error(f"Failed to send welcome email: {str(e)}")
        
        # Return success with redirect
        return {
            "message": "Email verified successfully! Welcome to FailState. Check your email for next steps.",
            "redirect_url": f"{settings.FRONTEND_URL}/login?verified=true"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )


@router.post("/resend-verification")
async def resend_verification(email: str):
    """Resend verification email"""
    supabase = get_supabase()
    
    try:
        # Find user by email
        result = supabase.table("users").select("*").eq("email", email).execute()
        
        if not result.data:
            # Don't reveal if email exists or not
            return {"message": "If the email exists, a verification link has been sent."}
        
        user = result.data[0]
        
        # Check if already verified
        if user.get("email_verified", False):
            return {"message": "Email is already verified. You can log in."}
        
        # Generate new verification token
        verification_token = secrets.token_urlsafe(32)
        verification_expires = datetime.utcnow() + timedelta(hours=24)
        
        # Update user with new token
        supabase.table("users").update({
            "verification_token": verification_token,
            "verification_token_expires": verification_expires.isoformat()
        }).eq("id", user["id"]).execute()
        
        # Send verification email (don't block if it fails)
        verification_link = f"{settings.BACKEND_URL}/api/auth/verify-email?token={verification_token}"
        try:
            send_verification_email(user["email"], user["username"], verification_link)
            return {"message": "Verification email sent. Please check your inbox."}
        except Exception as e:
            logger.error(f"Failed to resend verification email: {str(e)}")
            return {"message": "Failed to send email. Please try again later or contact support."}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

