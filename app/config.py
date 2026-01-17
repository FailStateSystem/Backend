from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_SERVICE_KEY: Optional[str] = None
    DATABASE_URL: str
    
    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Email (Optional - Resend recommended for cloud platforms)
    RESEND_API_KEY: Optional[str] = None  # Recommended: works on all platforms
    SMTP_HOST: Optional[str] = None       # Fallback: may be blocked on some platforms
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    
    # AI Verification
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"  # gpt-4o supports vision + JSON
    AI_VERIFICATION_ENABLED: bool = True
    AI_MAX_RETRIES: int = 3
    AI_TIMEOUT_SECONDS: int = 30
    
    # Content Filtering (optional toggles for production tuning)
    ENABLE_NSFW_FILTER: bool = False     # Disabled - AI fallback handles this
    ENABLE_DUPLICATE_FILTER: bool = True
    ENABLE_OCR_FILTER: bool = False      # Disabled - AI fallback handles this
    ENABLE_GARBAGE_FILTER: bool = True
    ENABLE_EXIF_CHECK: bool = True
    
    # Application
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    CORS_ORIGINS: str = "http://localhost:3000"
    FRONTEND_URL: str = "http://localhost:3000"  # For email verification links
    BACKEND_URL: str = "http://localhost:8000"   # For API verification endpoint
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

