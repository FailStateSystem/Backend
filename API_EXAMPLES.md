# API Examples & Testing Guide

Complete examples for testing all FailState API endpoints.

## Setup

1. Start the server: `./start.sh` (or `start.bat` on Windows)
2. Server runs at: `http://localhost:8000`
3. API docs at: `http://localhost:8000/docs`

## Authentication Flow

### 1. Sign Up

**Request:**
```bash
curl -X POST "http://localhost:8000/api/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john.doe@example.com",
    "username": "johndoe",
    "password": "SecurePass123!"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 2. Login

**Request:**
```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john.doe@example.com",
    "password": "SecurePass123!"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**💡 Important:** Save the `access_token` - you'll need it for authenticated requests!

---

## User Endpoints

### Get Current User Profile

**Request:**
```bash
curl -X GET "http://localhost:8000/api/users/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "john.doe@example.com",
  "username": "johndoe",
  "credibility_score": 87,
  "issues_posted": 12,
  "issues_resolved": 5,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-10T00:00:00Z",
  "badges": [
    {
      "id": "badge-1",
      "name": "First Reporter",
      "icon": "🎯",
      "description": "Reported your first issue",
      "earned_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total_points": 312,
  "current_tier": "Observer II"
}
```

### Get User by ID

**Request:**
```bash
curl -X GET "http://localhost:8000/api/users/USER_ID"
```

### Get User Badges

**Request:**
```bash
curl -X GET "http://localhost:8000/api/users/me/badges" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## Issue Endpoints

### Create Issue (Report)

**Request:**
```bash
curl -X POST "http://localhost:8000/api/issues" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "title": "Pothole on Main Street causing vehicle damage",
    "description": "Large pothole approximately 2 feet wide and 6 inches deep. Multiple vehicles have been damaged.",
    "category": "infrastructure",
    "location": {
      "name": "Main Street & 5th Ave",
      "coordinates": {
        "lat": 40.7128,
        "lng": -74.0060
      }
    },
    "image_url": "https://example.com/image.jpg"
  }'
```

**Response:**
```json
{
  "id": "issue-123",
  "title": "Pothole on Main Street causing vehicle damage",
  "description": "Large pothole approximately 2 feet wide...",
  "category": "infrastructure",
  "status": "unresolved",
  "location": {
    "name": "Main Street & 5th Ave",
    "coordinates": {
      "lat": 40.7128,
      "lng": -74.0060
    }
  },
  "image_url": "https://example.com/image.jpg",
  "video_url": null,
  "reported_by": "user-123",
  "reported_at": "2024-01-10T10:00:00Z",
  "resolved_at": null,
  "upvotes": 0,
  "timeline": [
    {
      "id": "timeline-1",
      "issue_id": "issue-123",
      "type": "reported",
      "description": "Issue reported",
      "timestamp": "2024-01-10T10:00:00Z"
    }
  ]
}
```

**Categories available:**
- `infrastructure`
- `sanitation`
- `traffic`
- `environment`
- `public_safety`
- `utilities`
- `other`

### Get All Issues

**Request:**
```bash
# All issues
curl -X GET "http://localhost:8000/api/issues"

# Filter by status
curl -X GET "http://localhost:8000/api/issues?status=unresolved"

# Filter by category
curl -X GET "http://localhost:8000/api/issues?category=infrastructure"

# Pagination
curl -X GET "http://localhost:8000/api/issues?limit=10&offset=0"
```

**Status filters:**
- `unresolved`
- `in_progress`
- `resolved`

### Get Specific Issue

**Request:**
```bash
curl -X GET "http://localhost:8000/api/issues/ISSUE_ID"
```

### Update Issue

**Request:**
```bash
curl -X PATCH "http://localhost:8000/api/issues/ISSUE_ID" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "status": "in_progress",
    "description": "Updated description with more details"
  }'
```

**Updatable fields:**
- `title`
- `description`
- `category`
- `status`
- `location`
- `image_url`
- `video_url`

### Upvote Issue

**Request:**
```bash
curl -X POST "http://localhost:8000/api/issues/ISSUE_ID/upvote" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response:**
```json
{
  "message": "Issue upvoted successfully"
}
```

### Remove Upvote

**Request:**
```bash
curl -X DELETE "http://localhost:8000/api/issues/ISSUE_ID/upvote" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## Rewards Endpoints

### Get Rewards Summary

**Request:**
```bash
curl -X GET "http://localhost:8000/api/rewards/summary" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response:**
```json
{
  "user_id": "user-123",
  "total_points": 312,
  "current_tier": "Observer II",
  "next_tier": "Persistent I",
  "points_to_next_tier": 188,
  "milestones_reached": 3,
  "items_claimed": 1
}
```

### Get Milestones

**Request:**
```bash
curl -X GET "http://localhost:8000/api/rewards/milestones" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response:**
```json
[
  {
    "id": "milestone-1",
    "name": "Observer I",
    "points_required": 50,
    "status": "redeemed",
    "description": "First threshold. System acknowledgment recorded.",
    "unlocked_at": "2024-01-05T00:00:00Z"
  },
  {
    "id": "milestone-2",
    "name": "Observer II",
    "points_required": 150,
    "status": "reached",
    "description": "Continued observation. Pattern documented.",
    "unlocked_at": null
  },
  {
    "id": "milestone-3",
    "name": "Persistent I",
    "points_required": 300,
    "status": "locked",
    "description": "Sustained logging detected. Status elevated.",
    "unlocked_at": null
  }
]
```

**Milestone statuses:**
- `locked` - Not enough points yet
- `reached` - Ready to claim
- `redeemed` - Already claimed

### Claim Milestone

**Request:**
```bash
curl -X POST "http://localhost:8000/api/rewards/milestones/MILESTONE_ID/claim" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response:**
```json
{
  "message": "Milestone claimed successfully"
}
```

### Get Redeemable Items

**Request:**
```bash
curl -X GET "http://localhost:8000/api/rewards/items" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response:**
```json
[
  {
    "id": "item-1",
    "name": "Utility Bottle",
    "description": "Insulated vessel. 500ml capacity. Standard issue.",
    "points_required": 150,
    "category": "utility",
    "available": true
  },
  {
    "id": "item-2",
    "name": "City Badge",
    "description": "Identification marker. Magnetic attachment.",
    "points_required": 200,
    "category": "identification",
    "available": true
  }
]
```

### Redeem Item

**Request:**
```bash
curl -X POST "http://localhost:8000/api/rewards/items/ITEM_ID/redeem" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response:**
```json
{
  "message": "Item redeemed successfully"
}
```

### Get Claimed Items

**Request:**
```bash
curl -X GET "http://localhost:8000/api/rewards/claimed" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response:**
```json
[
  {
    "id": "item-1",
    "name": "Utility Bottle",
    "description": "Insulated vessel. 500ml capacity.",
    "points_required": 150,
    "category": "utility",
    "available": true,
    "claimed_at": "2024-01-08T00:00:00Z",
    "user_id": "user-123"
  }
]
```

### Get Rewards History

**Request:**
```bash
curl -X GET "http://localhost:8000/api/rewards/history" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response:**
```json
[
  {
    "id": "history-1",
    "user_id": "user-123",
    "timestamp": "2024-01-10T10:05:00Z",
    "type": "points_earned",
    "description": "Verified report logged",
    "points": 25
  },
  {
    "id": "history-2",
    "user_id": "user-123",
    "timestamp": "2024-01-08T00:00:00Z",
    "type": "item_claimed",
    "description": "Item claimed: Utility Bottle",
    "points": null
  },
  {
    "id": "history-3",
    "user_id": "user-123",
    "timestamp": "2024-01-05T00:00:00Z",
    "type": "milestone_unlocked",
    "description": "Threshold reached: Observer I",
    "points": null
  }
]
```

**History types:**
- `points_earned` - Earned points from action
- `milestone_unlocked` - Reached a milestone
- `item_claimed` - Redeemed an item

---

## Complete Workflow Example

### 1. User Signs Up and Reports an Issue

```bash
# Sign up
SIGNUP_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "citizen@example.com",
    "username": "concernedcitizen",
    "password": "SecurePass123!"
  }')

TOKEN=$(echo $SIGNUP_RESPONSE | jq -r '.access_token')

# Report issue (earns 25 points automatically)
curl -X POST "http://localhost:8000/api/issues" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "title": "Broken streetlight",
    "description": "Streetlight has been out for a week",
    "category": "public_safety",
    "location": {
      "name": "Elm Street",
      "coordinates": {"lat": 40.7282, "lng": -74.0776}
    }
  }'

# Check rewards
curl -X GET "http://localhost:8000/api/rewards/summary" \
  -H "Authorization: Bearer $TOKEN"
```

### 2. Another User Upvotes the Issue

```bash
# Login as different user
LOGIN_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "other@example.com",
    "password": "password123"
  }')

TOKEN2=$(echo $LOGIN_RESPONSE | jq -r '.access_token')

# Upvote the issue
curl -X POST "http://localhost:8000/api/issues/ISSUE_ID/upvote" \
  -H "Authorization: Bearer $TOKEN2"
```

### 3. User Reaches Milestone and Redeems Item

```bash
# After reporting multiple issues and earning points...

# Check milestones
curl -X GET "http://localhost:8000/api/rewards/milestones" \
  -H "Authorization: Bearer $TOKEN"

# Claim milestone
curl -X POST "http://localhost:8000/api/rewards/milestones/MILESTONE_ID/claim" \
  -H "Authorization: Bearer $TOKEN"

# View redeemable items
curl -X GET "http://localhost:8000/api/rewards/items" \
  -H "Authorization: Bearer $TOKEN"

# Redeem item
curl -X POST "http://localhost:8000/api/rewards/items/ITEM_ID/redeem" \
  -H "Authorization: Bearer $TOKEN"

# Check history
curl -X GET "http://localhost:8000/api/rewards/history" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Testing with Postman

1. Import the API: Use the OpenAPI spec from `http://localhost:8000/openapi.json`
2. Set up environment variables:
   - `base_url`: `http://localhost:8000`
   - `access_token`: (set after login)
3. Create a collection with these requests
4. Use `{{base_url}}` and `{{access_token}}` in your requests

---

## Common Error Responses

### 401 Unauthorized
```json
{
  "detail": "Could not validate credentials"
}
```
**Solution:** Include valid Bearer token in Authorization header

### 400 Bad Request
```json
{
  "detail": "Email already registered"
}
```
**Solution:** Use a different email or login instead

### 404 Not Found
```json
{
  "detail": "Issue not found"
}
```
**Solution:** Verify the ID exists

### 422 Validation Error
```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```
**Solution:** Check request body matches the expected schema

---

## Points System

**How to earn points:**
- Report an issue: +25 points
- Issue gets resolved: +50 points (bonus)
- Receive upvotes: +5 points per upvote (future feature)

**Tiers:**
- Observer I: 0-49 points
- Observer II: 50-149 points
- Persistent I: 150-299 points
- Persistent II: 300-499 points
- Vigilant I: 500-749 points
- Vigilant II: 750+ points

---

Happy testing! 🚀

