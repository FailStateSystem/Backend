from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import auth, users, issues, rewards

app = FastAPI(
    title="FailState Backend API",
    description="Backend API for civic issue reporting and rewards system",
    version="1.0.0"
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

