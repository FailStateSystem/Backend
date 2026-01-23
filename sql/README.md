# Database SQL Files

This directory contains all SQL scripts for setting up and maintaining the FailState database.

## 📁 Directory Structure

### `schema/` - Core Database Schema

Run these in order during initial setup:

1. **`enable_postgis.sql`**
   - Enables PostGIS extension for geospatial features
   - Required for district routing functionality

2. **`complete_schema.sql`**
   - Main database schema with all core tables
   - Tables: users, issues, rewards, districts, etc.
   - Includes indexes, constraints, and basic RLS policies

3. **`ai_verification_tables.sql`**
   - Tables for AI verification pipeline
   - Stores verification results, confidence scores, enriched content

4. **`district_routing_tables.sql`**
   - Geospatial tables for administrative districts
   - Supports point-in-polygon and nearest neighbor routing

5. **`filtering_tables.sql`**
   - Pre-ingestion filter tracking tables
   - Logs NSFW detection, duplicates, garbage images, OCR results

6. **`supabase_queries.sql`**
   - Useful queries for database management and debugging

### `admin/` - Admin System

1. **`setup_admin_system.sql`**
   - Creates `admins` table with bcrypt password hashing
   - Creates `admin_action_logs` table for audit trail
   - Sets up helper functions and views
   - Inserts initial admin account

2. **`fix_admin_rls.sql`**
   - Fixes Row Level Security policies for admin tables
   - Run if admin login fails due to RLS restrictions

3. **`debug_admin_login.sql`**
   - Diagnostic queries for troubleshooting admin authentication
   - Check admin existence, RLS status, password hash format

### `migrations/` - Schema Migrations

Apply these as needed when features are added:

- **`add_email_verification.sql`** - Email verification system
- **`add_rejection_tracking.sql`** - Track rejection reasons
- **`add_retry_count.sql`** - Add retry limits for verification
- **`fix_rls_policies.sql`** - Update RLS policies

## 🚀 Initial Setup Order

For a fresh database:

```bash
# 1. Enable PostGIS
psql -d your_database -f sql/schema/enable_postgis.sql

# 2. Create core schema
psql -d your_database -f sql/schema/complete_schema.sql

# 3. Add AI verification tables
psql -d your_database -f sql/schema/ai_verification_tables.sql

# 4. Add district routing
psql -d your_database -f sql/schema/district_routing_tables.sql

# 5. Add filtering tables
psql -d your_database -f sql/schema/filtering_tables.sql

# 6. Set up admin system
psql -d your_database -f sql/admin/setup_admin_system.sql
```

Or in Supabase SQL Editor:
- Copy and paste each file's contents in the order above
- Execute one at a time

## 🔧 Common Maintenance Tasks

### Reset Admin Password

```sql
UPDATE admins 
SET password_hash = 'your_bcrypt_hash',
    updated_at = NOW()
WHERE email = 'admin@failstate.in';
```

### Check System Stats

```sql
-- Total users
SELECT COUNT(*) FROM users;

-- Issues by status
SELECT verification_status, COUNT(*) 
FROM issues 
GROUP BY verification_status;

-- Admin activity
SELECT * FROM admin_action_logs 
ORDER BY timestamp DESC 
LIMIT 20;
```

### Clean Up Old Data

```sql
-- Delete rejected issues older than 30 days
DELETE FROM issues 
WHERE verification_status = 'rejected' 
AND created_at < NOW() - INTERVAL '30 days';

-- Clean up old filter logs
DELETE FROM filter_decision_log 
WHERE timestamp < NOW() - INTERVAL '90 days';
```

## ⚠️ Important Notes

1. **Backup First:** Always backup your database before running migrations
2. **PostGIS Required:** Make sure PostGIS extension is enabled before other scripts
3. **RLS Policies:** Row Level Security is enabled - ensure service keys are configured
4. **Admin Setup:** Change the default admin password immediately after setup
5. **Migrations:** Run migrations in chronological order to avoid conflicts

## 🔐 Security

- All passwords are hashed with bcrypt (12 rounds)
- RLS policies protect sensitive data
- Admin actions are fully logged
- Service role required for backend operations

## 📊 Schema Overview

### Core Tables
- `users` - User accounts with trust scores
- `issues` - Submitted issues (all states)
- `issues_verified` - Verified issues only
- `districts` - Administrative boundaries (geospatial)
- `rewards` - User points and badges

### Filtering & Verification
- `filter_decision_log` - Pre-ingestion filter results
- `image_hashes` - Duplicate detection
- `verification_results` - AI verification outcomes
- `enriched_content` - AI-generated metadata

### Admin & Security
- `admins` - Admin accounts (separate from users)
- `admin_action_logs` - Complete audit trail
- `abuse_logs` - Trust system violations
- `rate_limits` - API throttling state

### Supporting Tables
- `email_verification_tokens` - Email confirmation
- `notification_queue` - Outbound notifications
- `rejection_reasons` - Issue rejection history

---

**Last Updated:** January 23, 2026
