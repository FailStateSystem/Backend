from fastapi import APIRouter, HTTPException, status, Depends
from datetime import timedelta
from app.models import UserCreate, UserLogin, Token, User
from app.auth import get_password_hash, verify_password, create_access_token
from app.database import get_supabase
from app.config import settings

router = APIRouter()

@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
async def signup(user_data: UserCreate):
    """Register a new user"""
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
        
        # Create user
        new_user = {
            "email": user_data.email,
            "username": user_data.username,
            "password_hash": hashed_password,
            "credibility_score": 0,
            "issues_posted": 0,
            "issues_resolved": 0
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

