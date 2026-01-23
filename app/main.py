from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging
from app.config import settings
from app.routers import auth, users, issues, rewards, uploads, districts, admin
from app.verification_worker import process_verification_queue

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup: Start background verification worker
    worker_task = asyncio.create_task(process_verification_queue())
    logger.info("🚀 Background AI verification worker started")
    
    yield
    
    # Shutdown: Cancel background worker
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    logger.info("🛑 Background AI verification worker stopped")

app = FastAPI(
    title="FailState Backend API",
    description="Backend API for civic issue reporting with AI verification",
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include public routers (accessible to all authenticated users)
app.include_router(auth.router, prefix="/public/auth", tags=["Public - Authentication"])
app.include_router(users.router, prefix="/public/users", tags=["Public - Users"])
app.include_router(issues.router, prefix="/public/issues", tags=["Public - Issues"])
app.include_router(rewards.router, prefix="/public/rewards", tags=["Public - Rewards"])
app.include_router(uploads.router, prefix="/public/uploads", tags=["Public - File Uploads"])
app.include_router(districts.router, prefix="/public/districts", tags=["Public - Districts"])

# Include admin routers (TODO: Add admin role checking)
app.include_router(admin.router, prefix="/admin", tags=["Admin Console"])

@app.get("/")
async def root():
    return {
        "message": "FailState Backend API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

