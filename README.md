# FailState Backend

**A civic tech platform empowering citizens to report and track infrastructure issues with AI-powered verification.**

## 🚀 Overview

FailState is a comprehensive backend system that enables citizens to report infrastructure problems, automatically verifies submissions using AI, and routes verified issues to relevant authorities. The platform includes sophisticated abuse prevention, trust scoring, and administrative controls.

## ✨ Key Features

### Core Functionality
- 🔐 **User Authentication** - JWT-based auth with email verification
- 📸 **Issue Reporting** - Image upload with geolocation
- 🤖 **AI Verification** - GPT-4o Vision-powered issue validation
- 🗺️ **Geospatial Routing** - Automatic assignment to administrative districts
- 🏆 **Rewards System** - Points and badges for quality contributions
- 👮 **Admin Console** - Comprehensive system management and monitoring

### Security & Abuse Prevention
- 🛡️ **Pre-ingestion Filtering** - NSFW detection, duplicate detection, garbage image filtering
- 🔍 **Trust Scoring** - Dynamic user reputation system
- 📊 **Rate Limiting** - User and IP-based throttling
- 🚫 **Progressive Penalties** - Automated account warnings and suspensions
- 👻 **Shadow Banning** - Silent rejection for repeat offenders
- 📝 **Audit Logging** - Complete admin action history

## 🏗️ Architecture

```
┌─────────────────┐
│   Client App    │
└────────┬────────┘
         │
    ┌────▼────┐
    │ FastAPI │
    └────┬────┘
         │
    ┌────▼─────────────────────────┐
    │  Core Services               │
    ├──────────────────────────────┤
    │ • Authentication             │
    │ • Pre-ingestion Filter       │
    │ • AI Verification Worker     │
    │ • District Routing           │
    │ • Trust System               │
    │ • Rate Limiter               │
    └────┬─────────────────────────┘
         │
    ┌────▼────────────────────┐
    │   Supabase              │
    ├─────────────────────────┤
    │ • PostgreSQL + PostGIS  │
    │ • Storage (Images)      │
    │ • Row Level Security    │
    └─────────────────────────┘
```

## 📦 Tech Stack

- **Framework:** FastAPI (Python 3.9+)
- **Database:** PostgreSQL with PostGIS extension (via Supabase)
- **Storage:** Supabase Storage
- **AI:** OpenAI GPT-4o with Vision
- **Authentication:** JWT tokens with bcrypt password hashing
- **Image Processing:** OpenCV, NudeNet, ImageHash, Tesseract OCR
- **Email:** Resend API
- **Deployment:** Render (Docker)

## 🛠️ Setup

### Prerequisites

- Python 3.9+
- PostgreSQL with PostGIS
- Supabase account
- OpenAI API key
- Resend API key (for emails)

### Environment Variables

Create a `.env` file in the root directory:

```env
# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_service_key
SUPABASE_ANON_KEY=your_anon_key

# JWT
JWT_SECRET_KEY=your_jwt_secret
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=43200

# OpenAI
OPENAI_API_KEY=your_openai_key

# Email
RESEND_API_KEY=your_resend_key
FROM_EMAIL=noreply@yourdomain.com

# Frontend
FRONTEND_URL=https://yourdomain.com
```

### Installation

1. **Clone the repository:**
```bash
git clone <repository-url>
cd failstate-backend
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Set up the database:**
   - Run SQL files from `sql/schema/` in order:
     - `enable_postgis.sql`
     - `complete_schema.sql`
     - `ai_verification_tables.sql`
     - `district_routing_tables.sql`
     - `filtering_tables.sql`
   - Set up admin system: `sql/admin/setup_admin_system.sql`

4. **Run the application:**
```bash
# Development
uvicorn app.main:app --reload --port 8000

# Production
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## 📚 API Documentation

### Base URLs

- **Public API:** `/public/*` - Accessible to authenticated users
- **Admin API:** `/admin/*` - Requires admin authentication

### Key Endpoints

#### Public API
- `POST /public/auth/signup` - Register new user
- `POST /public/auth/login` - User login
- `GET /public/auth/verify-email` - Verify email address
- `POST /public/issues` - Submit new issue
- `GET /public/issues` - Get issue feed
- `GET /public/users/me` - Get current user profile
- `GET /public/rewards/leaderboard` - Get top contributors

#### Admin API
- `POST /admin/login` - Admin authentication
- `GET /admin/dashboard` - System overview stats
- `GET /admin/users` - List all users
- `PATCH /admin/users/{id}/unsuspend` - Unsuspend user
- `DELETE /admin/users/{id}` - Delete user
- `POST /admin/issues/{id}/approve` - Manually approve issue
- `POST /admin/issues/{id}/reject` - Manually reject issue
- `DELETE /admin/issues/{id}` - Delete issue
- `GET /admin/activity/recent` - Recent admin actions

**Full API documentation:** Visit `/docs` (Swagger UI) or `/redoc` after starting the server

## 🔐 Admin System

### Default Admin Credentials

**⚠️ Change these immediately after deployment!**

- **Email:** `admin@failstate.in`
- **Password:** `FailState@2026!Secure#Admin`

### Admin Features

- Dashboard with real-time system stats
- User management (suspend, unsuspend, delete)
- Issue moderation (approve, reject, delete)
- Abuse monitoring and filtering controls
- Complete audit trail of all admin actions
- Super admin role support

## 🗂️ Project Structure

```
failstate-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Configuration management
│   ├── database.py                # Supabase client
│   ├── models.py                  # Pydantic models
│   ├── auth.py                    # User authentication
│   ├── admin_auth.py              # Admin authentication
│   ├── storage.py                 # File upload handling
│   ├── email_service.py           # Email notifications
│   ├── rate_limiter.py            # Rate limiting
│   ├── trust_system.py            # User reputation
│   ├── content_filters.py         # Basic content validation
│   ├── pre_ingestion_filter.py    # Advanced pre-filtering
│   ├── ai_verification.py         # AI-powered verification
│   ├── verification_worker.py     # Background processing
│   ├── district_routing.py        # Geospatial assignment
│   └── routers/
│       ├── auth.py                # Auth endpoints
│       ├── users.py               # User endpoints
│       ├── issues.py              # Issue endpoints
│       ├── rewards.py             # Rewards endpoints
│       ├── uploads.py             # File upload endpoints
│       ├── districts.py           # District endpoints
│       └── admin.py               # Admin endpoints
├── sql/
│   ├── schema/                    # Database schemas
│   ├── migrations/                # Schema migrations
│   └── admin/                     # Admin system SQL
├── requirements.txt               # Python dependencies
├── Dockerfile                     # Docker configuration
├── docker-compose.yml             # Local development setup
├── render-build.sh                # Render deployment script
└── README.md                      # This file
```

## 🚢 Deployment

### Render (Recommended)

1. Connect your GitHub repository to Render
2. Configure environment variables in Render dashboard
3. Build command: `./render-build.sh`
4. Start command: `gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`

### Docker

```bash
# Build image
docker build -t failstate-backend .

# Run container
docker run -p 8000:8000 --env-file .env failstate-backend
```

### Docker Compose (Local Development)

```bash
docker-compose up
```

## 🧪 Testing

The platform includes comprehensive validation and error handling:

- Input validation via Pydantic models
- Database constraints and triggers
- Rate limiting and abuse detection
- Image content filtering
- AI verification with confidence scoring

## 📊 Monitoring

Key metrics tracked:
- User signups and active users
- Issue submission rates
- Verification success/rejection rates
- Filter effectiveness (NSFW, duplicates, garbage)
- Admin actions and audit logs
- Trust score distribution

## 🔒 Security Features

- **Password Security:** Bcrypt hashing with salt rounds
- **JWT Tokens:** Signed with secret key, short expiration
- **Email Verification:** Required for account activation
- **Row Level Security:** Database-level access control
- **Rate Limiting:** Per-user and per-IP throttling
- **Content Filtering:** Multi-layer abuse prevention
- **Audit Logging:** Complete admin action history
- **Shadow Banning:** Silent rejection for repeat offenders

## 🤝 Contributing

This is a closed-source project. For bug reports or feature requests, contact the development team.

## 📄 License

Proprietary - All rights reserved

## 🆘 Support

For technical support or questions:
- **Email:** admin@failstate.in
- **Documentation:** Check `/docs` endpoint for API reference

## 🎯 Roadmap

- [ ] Mobile app integration
- [ ] Real-time notifications
- [ ] Authority dashboard for issue resolution
- [ ] Analytics and reporting tools
- [ ] Multi-language support
- [ ] Automated issue status updates
- [ ] Public API for third-party integrations

---

**Built with ❤️ for civic engagement**
