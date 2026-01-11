# Supabase Database Setup Guide

This guide will walk you through setting up the PostgreSQL database for FailState using Supabase.

## Prerequisites

- A Supabase account (sign up at https://supabase.com)
- Your Supabase project created

## Step 1: Create a New Supabase Project

1. Go to https://app.supabase.com
2. Click "New Project"
3. Fill in:
   - **Name**: failstate-db (or any name you prefer)
   - **Database Password**: Create a strong password (save this!)
   - **Region**: Choose the closest region to your users
4. Click "Create new project"
5. Wait for the project to finish setting up (2-3 minutes)

## Step 2: Get Your Credentials

Once your project is ready:

1. Go to **Settings** → **API**
2. Copy the following values:
   - **Project URL** → Use this for `SUPABASE_URL`
   - **anon/public key** → Use this for `SUPABASE_KEY`
   - **service_role key** → Use this for `SUPABASE_SERVICE_KEY` (⚠️ Keep this secret!)

3. Go to **Settings** → **Database**
4. Scroll down to **Connection string** → **URI**
5. Copy the connection string → Use this for `DATABASE_URL`
   - Replace `[YOUR-PASSWORD]` with your database password

## Step 3: Run the Database Schema

1. In your Supabase Dashboard, go to **SQL Editor**
2. Click **New query**
3. Open the `database_schema.sql` file from this project
4. Copy the **ENTIRE CONTENTS** of the file
5. Paste it into the SQL Editor in Supabase
6. Click **Run** or press `Ctrl/Cmd + Enter`

The script will create:
- ✅ All tables (users, issues, rewards, etc.)
- ✅ Indexes for performance
- ✅ Database functions for common operations
- ✅ Default data (badges, milestones, redeemable items)

## Step 4: Verify the Setup

Run this query in the SQL Editor to verify all tables were created:

```sql
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;
```

You should see these tables:
- badges
- claimed_items
- issue_upvotes
- issues
- milestones
- redeemable_items
- rewards_history
- timeline_events
- user_badges
- user_milestones
- user_rewards
- users

## Step 5: Configure Your Backend

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and fill in your credentials:
   ```env
   SUPABASE_URL=https://xxxxxxxxxxxxx.supabase.co
   SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.xxxxxxxxxxxxx.supabase.co:5432/postgres
   
   SECRET_KEY=generate-this-with-openssl-rand-hex-32
   ```

3. Generate a secure `SECRET_KEY`:
   ```bash
   openssl rand -hex 32
   ```

## Step 6: Test the Connection

Start your backend server:

```bash
./start.sh    # On macOS/Linux
# or
start.bat     # On Windows
```

The server should start at http://localhost:8000

Test the API:
```bash
curl http://localhost:8000/health
```

You should see:
```json
{"status": "healthy"}
```

## Database Structure Overview

### Core Tables

**users**
- Stores user accounts, credentials, and statistics
- Tracks credibility score, issues posted/resolved

**issues**
- Main table for civic issue reports
- Includes location (lat/lng), category, status, media URLs
- Links to the reporter (user)

**timeline_events**
- Tracks the lifecycle of each issue
- Events: reported, email_sent, in_progress, resolved

**issue_upvotes**
- Many-to-many relationship for issue upvoting
- Prevents duplicate upvotes from same user

### Rewards System Tables

**user_rewards**
- Aggregates user's total points, tier, and stats
- One record per user

**milestones**
- Defines achievement tiers (Observer I, Observer II, etc.)
- Points required to unlock each tier

**user_milestones**
- Tracks which milestones each user has unlocked

**redeemable_items**
- Catalog of items users can redeem with points
- Includes point cost and categories

**claimed_items**
- Records of items claimed by users

**rewards_history**
- Complete history of points earned, milestones unlocked, items claimed

**badges**
- Achievement badges (First Reporter, Community Hero, etc.)

**user_badges**
- Tracks which badges each user has earned

## Common SQL Queries

### View All Issues
```sql
SELECT * FROM issues ORDER BY reported_at DESC LIMIT 10;
```

### View User Stats
```sql
SELECT 
    u.username,
    u.credibility_score,
    u.issues_posted,
    u.issues_resolved,
    ur.total_points,
    ur.current_tier
FROM users u
LEFT JOIN user_rewards ur ON u.id = ur.user_id;
```

### View Top Contributors
```sql
SELECT 
    u.username,
    u.issues_posted,
    ur.total_points
FROM users u
LEFT JOIN user_rewards ur ON u.id = ur.user_id
ORDER BY ur.total_points DESC
LIMIT 10;
```

### View Issue Timeline
```sql
SELECT 
    i.title,
    te.type,
    te.description,
    te.timestamp
FROM issues i
JOIN timeline_events te ON i.id = te.issue_id
WHERE i.id = 'YOUR_ISSUE_ID'
ORDER BY te.timestamp;
```

## Troubleshooting

### Error: "relation does not exist"
- Make sure you ran the entire `database_schema.sql` script
- Check the SQL Editor for any error messages

### Error: "permission denied"
- Verify you're using the correct `SUPABASE_SERVICE_KEY` for admin operations
- Some operations require service role key instead of anon key

### Connection Timeout
- Check your `DATABASE_URL` is correct
- Verify your Supabase project is running (not paused)
- Check your network/firewall settings

### Functions Not Working
- Verify all PostgreSQL functions were created
- Run this query to list all functions:
  ```sql
  SELECT proname FROM pg_proc WHERE pronamespace = 'public'::regnamespace;
  ```

## Security Notes

⚠️ **IMPORTANT**: Never commit your `.env` file or expose your `SUPABASE_SERVICE_KEY`!

- The `service_role` key bypasses Row Level Security (RLS)
- Use `anon` key for client-side operations
- Use `service_role` key only for server-side admin operations
- Enable RLS policies in production (see commented section in schema)

## Row Level Security (RLS)

The schema includes commented RLS policies. To enable them:

1. Uncomment the RLS section at the end of `database_schema.sql`
2. Customize policies based on your security requirements
3. Test thoroughly before deploying to production

Example RLS policy:
```sql
ALTER TABLE issues ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can view issues" 
ON issues FOR SELECT 
USING (true);

CREATE POLICY "Authenticated users can create issues" 
ON issues FOR INSERT 
WITH CHECK (auth.uid() = reported_by);
```

## Next Steps

1. ✅ Database setup complete
2. ✅ Backend configured
3. 📁 **Setup Supabase Storage** - See `SUPABASE_STORAGE_SETUP.md` for image/video uploads
4. 📱 Update your frontend to point to `http://localhost:8000/api`
5. 🧪 Test the API endpoints using the Swagger docs at `http://localhost:8000/docs`
6. 🚀 Deploy to production when ready

## Need Help?

- Supabase Docs: https://supabase.com/docs
- FastAPI Docs: https://fastapi.tiangolo.com
- PostgreSQL Docs: https://www.postgresql.org/docs

---

**Happy Building! 🎉**

