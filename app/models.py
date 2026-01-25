from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

# Enums
class IssueStatus(str, Enum):
    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"
    IN_PROGRESS = "in_progress"

class IssueCategory(str, Enum):
    INFRASTRUCTURE = "infrastructure"
    SANITATION = "sanitation"
    TRAFFIC = "traffic"
    ENVIRONMENT = "environment"
    PUBLIC_SAFETY = "public_safety"
    UTILITIES = "utilities"
    OTHER = "other"

class TimelineEventType(str, Enum):
    REPORTED = "reported"
    EMAIL_SENT = "email_sent"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"

class MilestoneStatus(str, Enum):
    LOCKED = "locked"
    REACHED = "reached"
    REDEEMED = "redeemed"

class RedeemableItemStatus(str, Enum):
    AVAILABLE = "available"
    CLAIMED = "claimed"
    INSUFFICIENT = "insufficient"

class HistoryEntryType(str, Enum):
    POINTS_EARNED = "points_earned"
    MILESTONE_UNLOCKED = "milestone_unlocked"
    ITEM_CLAIMED = "item_claimed"

# Location Models
class Coordinates(BaseModel):
    lat: float
    lng: float

class Location(BaseModel):
    name: str
    coordinates: Coordinates

# User Models
class UserBase(BaseModel):
    email: EmailStr
    username: str

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class User(UserBase):
    id: str
    credibility_score: int = 0
    issues_posted: int = 0
    issues_resolved: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Badge Models
class Badge(BaseModel):
    id: str
    name: str
    icon: str
    description: str
    user_id: Optional[str] = None
    earned_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class UserProfile(User):
    badges: List[Badge] = []
    total_points: int = 0
    current_tier: str = "Observer I"

# Timeline Event Models
class TimelineEvent(BaseModel):
    id: str
    issue_id: str
    type: TimelineEventType
    description: str
    timestamp: datetime

    class Config:
        from_attributes = True

# District Models
class DistrictBoundary(BaseModel):
    id: str
    district_name: str
    state_name: Optional[str] = None
    source: str = "geoBoundaries ADM2"
    created_at: datetime
    
    class Config:
        from_attributes = True

class DistrictAuthority(BaseModel):
    id: str
    district_id: str
    district_name: Optional[str] = None
    state_name: Optional[str] = None
    dm_office_email: Optional[str] = None
    fallback_email: Optional[str] = None
    authority_name: Optional[str] = None
    phone_number: Optional[str] = None
    office_address: Optional[str] = None
    last_verified: Optional[datetime] = None
    confidence_score: Optional[float] = 0.50
    is_active: bool = True
    notes: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class DistrictAuthorityCreate(BaseModel):
    district_id: str
    dm_office_email: Optional[str] = None
    fallback_email: Optional[str] = None
    authority_name: Optional[str] = None
    phone_number: Optional[str] = None
    office_address: Optional[str] = None
    confidence_score: Optional[float] = 0.50
    notes: Optional[str] = None

class DistrictAuthorityUpdate(BaseModel):
    dm_office_email: Optional[str] = None
    fallback_email: Optional[str] = None
    authority_name: Optional[str] = None
    phone_number: Optional[str] = None
    office_address: Optional[str] = None
    last_verified: Optional[datetime] = None
    confidence_score: Optional[float] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None

class RoutingLog(BaseModel):
    id: str
    issue_id: Optional[str] = None
    latitude: float
    longitude: float
    district_id: Optional[str] = None
    district_name: Optional[str] = None
    state_name: Optional[str] = None
    routing_method: str  # 'point_in_polygon' or 'fallback_nearest'
    fallback_used: bool = False
    fallback_distance_km: Optional[float] = None
    confidence_score: Optional[float] = None
    processing_time_ms: Optional[int] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# Issue Models
class IssueBase(BaseModel):
    title: str
    description: str
    category: IssueCategory
    location: Location

class IssueCreate(IssueBase):
    image: Optional[str] = None  # Base64 encoded image data
    image_url: Optional[str] = None  # Direct URL (for backward compatibility)
    video_url: Optional[str] = None

class IssueUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[IssueCategory] = None
    status: Optional[IssueStatus] = None
    location: Optional[Location] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None

class Issue(IssueBase):
    id: str
    status: IssueStatus = IssueStatus.UNRESOLVED
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    reported_by: str
    reported_at: datetime
    resolved_at: Optional[datetime] = None
    upvotes: int = 0
    timeline: List[TimelineEvent] = []
    verification_status: Optional[str] = "pending"  # AI verification status
    processed_at: Optional[datetime] = None  # When AI verification completed
    rejection_reason: Optional[str] = None  # Reason for rejection (if rejected)
    # District routing fields
    district_id: Optional[str] = None
    district_name: Optional[str] = None
    state_name: Optional[str] = None
    routing_status: Optional[str] = "pending"
    routing_method: Optional[str] = None
    routed_at: Optional[datetime] = None
    # Notification fields
    dm_notification_sent: Optional[bool] = False
    dm_notification_sent_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Rewards Models
class UserRewards(BaseModel):
    user_id: str
    total_points: int = 0
    current_tier: str = "Observer I"
    next_tier: str = "Observer II"
    points_to_next_tier: int = 50
    milestones_reached: int = 0
    items_claimed: int = 0

class Milestone(BaseModel):
    id: str
    name: str
    points_required: int
    status: MilestoneStatus
    description: str
    unlocked_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class RedeemableItem(BaseModel):
    id: str
    name: str
    description: str
    points_required: int
    category: str
    available: bool = True

    class Config:
        from_attributes = True

class ClaimedItem(RedeemableItem):
    claimed_at: datetime
    user_id: str

class HistoryEntry(BaseModel):
    id: str
    user_id: str
    timestamp: datetime
    type: HistoryEntryType
    description: str
    points: Optional[int] = None

    class Config:
        from_attributes = True

# Token Models
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None

