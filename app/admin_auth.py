"""
Admin Authentication & Action Logging
======================================
Separate authentication system for admin users

Key Features:
- Separate admin authentication (admins table)
- Action logging for audit trail
- Admin JWT tokens
- IP and user agent tracking
"""

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pydantic import BaseModel
from passlib.context import CryptContext
import logging

from app.config import settings
from app.database import get_supabase

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


# ============================================
# MODELS
# ============================================

class AdminTokenData(BaseModel):
    """Admin JWT token data"""
    admin_id: str
    email: str
    username: str
    is_super_admin: bool = False


class AdminLoginRequest(BaseModel):
    """Admin login request"""
    email: str
    password: str


class AdminActionLog(BaseModel):
    """Admin action log entry"""
    action_type: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


# ============================================
# AUTHENTICATION FUNCTIONS
# ============================================

def verify_admin_password(plain_password: str, hashed_password: str) -> bool:
    """Verify admin password"""
    return pwd_context.verify(plain_password, hashed_password)


def create_admin_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT token for admin"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=8)  # Admin tokens expire in 8 hours
    
    to_encode.update({
        "exp": expire,
        "type": "admin"  # Mark as admin token
    })
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def authenticate_admin(email: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticate admin user
    
    Returns admin dict if successful, None otherwise
    """
    try:
        supabase = get_supabase()
        
        # Get admin from admins table
        result = supabase.table("admins").select("*").eq("email", email).eq("is_active", True).limit(1).execute()
        
        if not result.data:
            logger.warning(f"Admin login failed: email not found ({email})")
            return None
        
        admin = result.data[0]
        
        # Verify password
        if not verify_admin_password(password, admin["password_hash"]):
            logger.warning(f"Admin login failed: incorrect password ({email})")
            return None
        
        # Update last login
        try:
            supabase.rpc("update_admin_last_login", {"p_admin_id": admin["id"]}).execute()
        except Exception as e:
            logger.error(f"Failed to update admin last login: {e}")
        
        logger.info(f"✅ Admin logged in: {email}")
        return admin
    
    except Exception as e:
        logger.error(f"Admin authentication error: {e}")
        return None


async def get_current_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> AdminTokenData:
    """
    Dependency to get current authenticated admin
    
    Validates JWT token and checks if user is admin
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate admin credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        
        # Decode JWT
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        admin_id: str = payload.get("sub")
        email: str = payload.get("email")
        username: str = payload.get("username")
        token_type: str = payload.get("type")
        is_super_admin: bool = payload.get("is_super_admin", False)
        
        if admin_id is None or email is None or token_type != "admin":
            logger.warning("Invalid admin token: missing fields or not admin token")
            raise credentials_exception
        
        # Verify admin still exists and is active
        supabase = get_supabase()
        result = supabase.table("admins").select("id, is_active").eq("id", admin_id).limit(1).execute()
        
        if not result.data or not result.data[0]["is_active"]:
            logger.warning(f"Admin token invalid: admin not found or inactive ({email})")
            raise credentials_exception
        
        return AdminTokenData(
            admin_id=admin_id,
            email=email,
            username=username,
            is_super_admin=is_super_admin
        )
    
    except JWTError as e:
        logger.error(f"JWT decode error: {e}")
        raise credentials_exception
    except Exception as e:
        logger.error(f"Admin authentication error: {e}")
        raise credentials_exception


# ============================================
# ACTION LOGGING
# ============================================

async def log_admin_action(
    admin: AdminTokenData,
    action_type: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None
):
    """
    Log admin action for audit trail
    
    Args:
        admin: Current admin user
        action_type: Type of action (e.g., 'user_suspended', 'issue_approved')
        resource_type: Type of resource (e.g., 'user', 'issue')
        resource_id: ID of affected resource
        details: Additional context (reason, changes, etc.)
        request: FastAPI request object (for IP and user agent)
    """
    try:
        supabase = get_supabase()
        
        # Extract IP and user agent from request
        ip_address = None
        user_agent = None
        
        if request:
            # Get real IP (considering proxies)
            ip_address = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            if not ip_address:
                ip_address = request.headers.get("X-Real-IP")
            if not ip_address:
                ip_address = request.client.host if request.client else None
            
            user_agent = request.headers.get("User-Agent")
        
        # Log action
        log_data = {
            "admin_id": admin.admin_id,
            "action_type": action_type,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
            "ip_address": ip_address,
            "user_agent": user_agent
        }
        
        result = supabase.table("admin_action_logs").insert(log_data).execute()
        
        logger.info(
            f"📝 Admin action logged: {action_type} by {admin.email} "
            f"(resource: {resource_type}/{resource_id})"
        )
        
        return result.data[0]["id"] if result.data else None
    
    except Exception as e:
        logger.error(f"Failed to log admin action: {e}")
        # Don't fail the request if logging fails
        return None


def require_super_admin(admin: AdminTokenData = Depends(get_current_admin)) -> AdminTokenData:
    """
    Dependency to require super admin access
    
    Use this for sensitive operations that only super admins should perform
    """
    if not admin.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )
    return admin


# ============================================
# ADMIN UTILITY FUNCTIONS
# ============================================

async def get_admin_by_id(admin_id: str) -> Optional[Dict[str, Any]]:
    """Get admin by ID"""
    try:
        supabase = get_supabase()
        result = supabase.table("admins").select("*").eq("id", admin_id).limit(1).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Failed to get admin by ID: {e}")
        return None


async def get_admin_action_logs(
    admin_id: Optional[str] = None,
    action_type: Optional[str] = None,
    resource_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> list:
    """Get admin action logs with filters"""
    try:
        supabase = get_supabase()
        
        query = supabase.table("admin_action_logs").select(
            "*, admins!inner(email, username)"
        )
        
        if admin_id:
            query = query.eq("admin_id", admin_id)
        
        if action_type:
            query = query.eq("action_type", action_type)
        
        if resource_type:
            query = query.eq("resource_type", resource_type)
        
        query = query.range(offset, offset + limit - 1).order("created_at", desc=True)
        
        result = query.execute()
        return result.data if result.data else []
    
    except Exception as e:
        logger.error(f"Failed to get admin action logs: {e}")
        return []


async def get_admin_activity_summary(admin_id: str) -> Optional[Dict[str, Any]]:
    """Get activity summary for specific admin"""
    try:
        supabase = get_supabase()
        result = supabase.table("admin_activity_summary").select("*").eq("id", admin_id).limit(1).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Failed to get admin activity summary: {e}")
        return None
