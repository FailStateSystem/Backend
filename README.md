# FailState Backend API

A FastAPI-based backend for the FailState civic issue reporting application.

## Features

- **User Authentication**: JWT-based authentication with signup and login
- **Issue Reporting**: Create, read, update issues with location tracking
- **File Uploads**: Image and video uploads to Supabase Storage with automatic optimization
- **Rewards System**: Gamification with points, milestones, and redeemable items
- **Timeline Tracking**: Track issue status changes and updates
- **Upvoting System**: Community engagement through upvotes
- **User Profiles**: Track credibility scores, badges, and statistics

## Tech Stack

- **FastAPI**: Modern Python web framework
- **Supabase**: PostgreSQL database + Storage for files
- **JWT**: Secure authentication
- **Pydantic**: Data validation
- **Pillow**: Image processing and optimization
- **Python 3.10+**

## Setup

### 1. Install Dependencies

```bash
cd failstate-backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your Supabase credentials:

```bash
cp .env.example .env
```

Update the following in `.env`:
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_KEY`: Your Supabase anon key
- `SUPABASE_SERVICE_KEY`: Your Supabase service role key
- `DATABASE_URL`: Your PostgreSQL connection string
- `SECRET_KEY`: Generate with `openssl rand -hex 32`

### 3. Set Up Database

Run the SQL queries provided in `database_schema.sql` on your Supabase SQL console to create all necessary tables and functions.

### 4. Set Up Storage (Optional but Recommended)

Create storage buckets in Supabase for image and video uploads:
1. Go to Supabase Dashboard → Storage
2. Create bucket: `issue-images` (Public)
3. Create bucket: `issue-videos` (Public)

See `SUPABASE_STORAGE_SETUP.md` for detailed instructions.

### 5. Run the Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### Authentication
- `POST /api/auth/signup` - Register a new user
- `POST /api/auth/login` - Login and get access token

### Users
- `GET /api/users/me` - Get current user profile
- `GET /api/users/{user_id}` - Get user by ID
- `GET /api/users/me/badges` - Get user's badges

### Issues
- `POST /api/issues` - Create a new issue
- `GET /api/issues` - Get all issues (with filters)
- `GET /api/issues/{issue_id}` - Get specific issue
- `PATCH /api/issues/{issue_id}` - Update an issue
- `POST /api/issues/{issue_id}/upvote` - Upvote an issue
- `DELETE /api/issues/{issue_id}/upvote` - Remove upvote

### Rewards
- `GET /api/rewards/summary` - Get rewards summary
- `GET /api/rewards/milestones` - Get all milestones
- `POST /api/rewards/milestones/{milestone_id}/claim` - Claim a milestone
- `GET /api/rewards/items` - Get redeemable items
- `POST /api/rewards/items/{item_id}/redeem` - Redeem an item
- `GET /api/rewards/claimed` - Get claimed items
- `GET /api/rewards/history` - Get rewards history

### File Uploads
- `POST /api/uploads/image` - Upload an image (max 5MB)
- `POST /api/uploads/video` - Upload a video (max 50MB)
- `DELETE /api/uploads/file` - Delete a file from storage

## Project Structure

```
failstate-backend/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI app initialization
│   ├── config.py         # Configuration and settings
│   ├── database.py       # Supabase client
│   ├── models.py         # Pydantic models
│   ├── auth.py           # Authentication utilities
│   ├── storage.py        # File upload service (Supabase Storage)
│   └── routers/
│       ├── __init__.py
│       ├── auth.py       # Auth endpoints
│       ├── users.py      # User endpoints
│       ├── issues.py     # Issue endpoints
│       ├── rewards.py    # Rewards endpoints
│       └── uploads.py    # File upload endpoints
├── requirements.txt
├── database_schema.sql
├── .env.example
├── .gitignore
├── README.md
├── QUICK_START.md
├── SUPABASE_SETUP.md
└── SUPABASE_STORAGE_SETUP.md
```

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black app/
```

### Type Checking

```bash
mypy app/
```

## Deployment

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables for Production

Make sure to set:
- `ENVIRONMENT=production`
- `DEBUG=False`
- Strong `SECRET_KEY`
- Proper `CORS_ORIGINS`

## Security Considerations

- Always use HTTPS in production
- Keep `SECRET_KEY` secure and never commit it
- Use strong passwords
- Implement rate limiting for API endpoints
- Validate and sanitize all user inputs
- Use environment variables for sensitive data

## License

MIT License

