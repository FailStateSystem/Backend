from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging
from app.config import settings
from app.routers import auth, users, issues, rewards, uploads, districts
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

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(issues.router, prefix="/api/issues", tags=["Issues"])
app.include_router(rewards.router, prefix="/api/rewards", tags=["Rewards"])
app.include_router(uploads.router, prefix="/api/uploads", tags=["File Uploads"])
app.include_router(districts.router, prefix="/api/districts", tags=["Districts & Routing"])

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

