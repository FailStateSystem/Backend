# Quick Start Guide - FailState Backend

Get your FailState backend up and running in 5 minutes!

## 🚀 Quick Setup

### 1. Set Up Supabase (2 minutes)

1. Go to [supabase.com](https://supabase.com) and create a free account
2. Create a new project
3. Go to SQL Editor and run the entire `database_schema.sql` file
4. Go to Settings → API and copy your credentials

### 2. Configure Backend (1 minute)

```bash
cd failstate-backend
cp .env.example .env
```

Edit `.env` and add your Supabase credentials:
```env
SUPABASE_URL=your_project_url_here
SUPABASE_KEY=your_anon_key_here
DATABASE_URL=your_database_url_here
SECRET_KEY=run_openssl_rand_hex_32_to_generate
```

Generate SECRET_KEY:
```bash
openssl rand -hex 32
```

### 3. Install & Run (2 minutes)

**Option A: Using the startup script (Recommended)**

macOS/Linux:
```bash
./start.sh
```

Windows:
```bash
start.bat
```

**Option B: Manual setup**

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Option C: Using Docker**

```bash
docker-compose up -d
```

### 4. Test It! ✅

Visit: http://localhost:8000/docs

You should see the interactive API documentation!

Test the health endpoint:
```bash
curl http://localhost:8000/health
```

Response:
```json
{"status": "healthy"}
```

## 📚 API Endpoints

### Authentication
- `POST /api/auth/signup` - Create account
- `POST /api/auth/login` - Login

### Users
- `GET /api/users/me` - Get your profile
- `GET /api/users/me/badges` - Get your badges

### Issues
- `POST /api/issues` - Report an issue
- `GET /api/issues` - List all issues
- `GET /api/issues/{id}` - Get specific issue
- `POST /api/issues/{id}/upvote` - Upvote issue

### Rewards
- `GET /api/rewards/summary` - Your points & tier
- `GET /api/rewards/milestones` - View milestones
- `GET /api/rewards/items` - See redeemable items
- `POST /api/rewards/items/{id}/redeem` - Redeem item

## 🧪 Try It Out

### 1. Create an Account

```bash
curl -X POST http://localhost:8000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "username": "testuser",
    "password": "securepassword123"
  }'
```

### 2. Login

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "securepassword123"
  }'
```

Save the `access_token` from the response!

### 3. Report an Issue

```bash
curl -X POST http://localhost:8000/api/issues \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "title": "Pothole on Main Street",
    "description": "Large pothole causing vehicle damage",
    "category": "infrastructure",
    "location": {
      "name": "Main St & 5th Ave",
      "coordinates": {
        "lat": 40.7128,
        "lng": -74.0060
      }
    }
  }'
```

You just earned 25 points! 🎉

## 📖 Full Documentation

- **Detailed Setup**: See `SUPABASE_SETUP.md`
- **API Reference**: Visit http://localhost:8000/docs when server is running
- **Main README**: See `README.md`

## 🐛 Troubleshooting

**Server won't start?**
- Check your `.env` file is configured
- Make sure Supabase credentials are correct
- Verify Python 3.10+ is installed: `python3 --version`

**Database errors?**
- Did you run `database_schema.sql` in Supabase?
- Check your `DATABASE_URL` is correct
- Verify your Supabase project is active

**Module not found?**
- Make sure virtual environment is activated
- Run `pip install -r requirements.txt` again

## 🔗 Connect Your Frontend

Update your frontend app to use the backend API:

```typescript
const API_URL = 'http://localhost:8000/api';

// Login example
const response = await fetch(`${API_URL}/auth/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email, password })
});

const { access_token } = await response.json();
localStorage.setItem('token', access_token);

// Authenticated request example
const issues = await fetch(`${API_URL}/issues`, {
  headers: {
    'Authorization': `Bearer ${access_token}`
  }
});
```

## 🎉 You're Ready!

Your backend is now running and ready to power your FailState app!

Next steps:
1. ✅ Backend running
2. 🔌 Connect your Next.js frontend
3. 🧪 Test all features
4. 🚀 Deploy to production

**Need help?** Check out the full documentation or test endpoints in the Swagger UI at http://localhost:8000/docs

