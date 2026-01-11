-- ================================================
-- FAILSTATE DATABASE - SUPABASE SETUP QUERIES
-- ================================================
-- Copy and paste this ENTIRE file into your Supabase SQL Editor
-- and click "Run" to create all tables, functions, and default data
-- ================================================

-- Enable UUID extension (if not already enabled)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ================================================
-- DROP EXISTING TABLES (Optional - for clean setup)
-- ================================================
-- Uncomment these lines if you want to start fresh
-- WARNING: This will delete all data!

/*
DROP TABLE IF EXISTS rewards_history CASCADE;
DROP TABLE IF EXISTS claimed_items CASCADE;
DROP TABLE IF EXISTS user_milestones CASCADE;
DROP TABLE IF EXISTS user_badges CASCADE;
DROP TABLE IF EXISTS issue_upvotes CASCADE;
DROP TABLE IF EXISTS timeline_events CASCADE;
DROP TABLE IF EXISTS issues CASCADE;
DROP TABLE IF EXISTS user_rewards CASCADE;
DROP TABLE IF EXISTS redeemable_items CASCADE;
DROP TABLE IF EXISTS milestones CASCADE;
DROP TABLE IF EXISTS badges CASCADE;
DROP TABLE IF EXISTS users CASCADE;
*/

-- ================================================
-- 1. USERS TABLE
-- ================================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    credibility_score INTEGER DEFAULT 0,
    issues_posted INTEGER DEFAULT 0,
    issues_resolved INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- ================================================
-- 2. ISSUES TABLE
-- ================================================
CREATE TABLE IF NOT EXISTS issues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'unresolved',
    location_name VARCHAR(255) NOT NULL,
    location_lat DECIMAL(10, 8) NOT NULL,
    location_lng DECIMAL(11, 8) NOT NULL,
    image_url TEXT,
    video_url TEXT,
    reported_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reported_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE,
    upvotes INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_issues_status ON issues(status);
CREATE INDEX IF NOT EXISTS idx_issues_category ON issues(category);
CREATE INDEX IF NOT EXISTS idx_issues_reported_by ON issues(reported_by);
CREATE INDEX IF NOT EXISTS idx_issues_reported_at ON issues(reported_at DESC);
CREATE INDEX IF NOT EXISTS idx_issues_location ON issues(location_lat, location_lng);

-- ================================================
-- 3. TIMELINE EVENTS TABLE
-- ================================================
CREATE TABLE IF NOT EXISTS timeline_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_id UUID NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_timeline_events_issue_id ON timeline_events(issue_id);
CREATE INDEX IF NOT EXISTS idx_timeline_events_timestamp ON timeline_events(timestamp);

-- ================================================
-- 4. ISSUE UPVOTES TABLE
-- ================================================
CREATE TABLE IF NOT EXISTS issue_upvotes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_id UUID NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(issue_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_issue_upvotes_issue_id ON issue_upvotes(issue_id);
CREATE INDEX IF NOT EXISTS idx_issue_upvotes_user_id ON issue_upvotes(user_id);

-- ================================================
-- 5. BADGES TABLE
-- ================================================
CREATE TABLE IF NOT EXISTS badges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    icon VARCHAR(10) NOT NULL,
    description TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default badges
INSERT INTO badges (name, icon, description) VALUES
    ('First Reporter', '🎯', 'Reported your first issue'),
    ('Community Hero', '⭐', 'Reported 10+ issues'),
    ('Problem Solver', '✅', 'Had 5 issues resolved'),
    ('Eagle Eye', '👁️', 'Reported 25+ issues'),
    ('City Guardian', '🛡️', 'Reported 50+ issues'),
    ('Vigilant Citizen', '🔍', 'Maintained high credibility score'),
    ('Resolution Master', '🏆', 'Had 20+ issues resolved'),
    ('Community Leader', '👑', 'Top contributor for the month')
ON CONFLICT DO NOTHING;

-- ================================================
-- 6. USER BADGES TABLE
-- ================================================
CREATE TABLE IF NOT EXISTS user_badges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    badge_id UUID NOT NULL REFERENCES badges(id) ON DELETE CASCADE,
    earned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, badge_id)
);

CREATE INDEX IF NOT EXISTS idx_user_badges_user_id ON user_badges(user_id);
CREATE INDEX IF NOT EXISTS idx_user_badges_badge_id ON user_badges(badge_id);

-- ================================================
-- 7. USER REWARDS TABLE
-- ================================================
CREATE TABLE IF NOT EXISTS user_rewards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    total_points INTEGER DEFAULT 0,
    current_tier VARCHAR(50) DEFAULT 'Observer I',
    milestones_reached INTEGER DEFAULT 0,
    items_claimed INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_rewards_user_id ON user_rewards(user_id);

-- ================================================
-- 8. MILESTONES TABLE
-- ================================================
CREATE TABLE IF NOT EXISTS milestones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    points_required INTEGER NOT NULL,
    description TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default milestones
INSERT INTO milestones (name, points_required, description) VALUES
    ('Observer I', 50, 'First threshold. System acknowledgment recorded.'),
    ('Observer II', 150, 'Continued observation. Pattern documented.'),
    ('Persistent I', 300, 'Sustained logging detected. Status elevated.'),
    ('Persistent II', 500, 'Threshold pending. Continue documentation.'),
    ('Vigilant I', 750, 'Advanced recognition tier. Awaiting qualification.'),
    ('Vigilant II', 1000, 'High-tier acknowledgment. Reserved for persistent contributors.')
ON CONFLICT DO NOTHING;

-- ================================================
-- 9. USER MILESTONES TABLE
-- ================================================
CREATE TABLE IF NOT EXISTS user_milestones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    milestone_id UUID NOT NULL REFERENCES milestones(id) ON DELETE CASCADE,
    unlocked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, milestone_id)
);

CREATE INDEX IF NOT EXISTS idx_user_milestones_user_id ON user_milestones(user_id);
CREATE INDEX IF NOT EXISTS idx_user_milestones_milestone_id ON user_milestones(milestone_id);

-- ================================================
-- 10. REDEEMABLE ITEMS TABLE
-- ================================================
CREATE TABLE IF NOT EXISTS redeemable_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    points_required INTEGER NOT NULL,
    category VARCHAR(50) NOT NULL,
    available BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default redeemable items
INSERT INTO redeemable_items (name, description, points_required, category) VALUES
    ('Utility Bottle', 'Insulated vessel. 500ml capacity. Standard issue.', 150, 'utility'),
    ('City Badge', 'Identification marker. Magnetic attachment. Non-transferable.', 200, 'identification'),
    ('Reflective Band', 'High-visibility strip. Adjustable. Weather-resistant.', 100, 'safety'),
    ('Transit Credit', 'Pre-loaded transport allocation. 10 journeys. Local network.', 250, 'transport'),
    ('Field Notebook', 'Waterproof documentation pad. 120 pages. Grid format.', 180, 'documentation'),
    ('Observer Cap', 'Neutral headwear. Adjustable fit. Low-profile design.', 220, 'apparel'),
    ('Desk Plant', 'Low-maintenance specimen. Ceramic container included.', 300, 'environment'),
    ('System Access Card', 'Priority terminal access. Extended session duration.', 500, 'access')
ON CONFLICT DO NOTHING;

-- ================================================
-- 11. CLAIMED ITEMS TABLE
-- ================================================
CREATE TABLE IF NOT EXISTS claimed_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id UUID NOT NULL REFERENCES redeemable_items(id) ON DELETE CASCADE,
    claimed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, item_id)
);

CREATE INDEX IF NOT EXISTS idx_claimed_items_user_id ON claimed_items(user_id);
CREATE INDEX IF NOT EXISTS idx_claimed_items_item_id ON claimed_items(item_id);

-- ================================================
-- 12. REWARDS HISTORY TABLE
-- ================================================
CREATE TABLE IF NOT EXISTS rewards_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    points INTEGER,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rewards_history_user_id ON rewards_history(user_id);
CREATE INDEX IF NOT EXISTS idx_rewards_history_timestamp ON rewards_history(timestamp DESC);

-- ================================================
-- FUNCTIONS AND TRIGGERS
-- ================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_issues_updated_at ON issues;
CREATE TRIGGER update_issues_updated_at BEFORE UPDATE ON issues
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_user_rewards_updated_at ON user_rewards;
CREATE TRIGGER update_user_rewards_updated_at BEFORE UPDATE ON user_rewards
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ================================================
-- UTILITY FUNCTIONS
-- ================================================

-- Increment issue upvotes
CREATE OR REPLACE FUNCTION increment_issue_upvotes(issue_id UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE issues SET upvotes = upvotes + 1 WHERE id = issue_id;
END;
$$ LANGUAGE plpgsql;

-- Decrement issue upvotes
CREATE OR REPLACE FUNCTION decrement_issue_upvotes(issue_id UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE issues SET upvotes = GREATEST(0, upvotes - 1) WHERE id = issue_id;
END;
$$ LANGUAGE plpgsql;

-- Increment user issues posted
CREATE OR REPLACE FUNCTION increment_user_issues_posted(user_id UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE users SET issues_posted = issues_posted + 1 WHERE id = user_id;
END;
$$ LANGUAGE plpgsql;

-- Increment user issues resolved
CREATE OR REPLACE FUNCTION increment_user_issues_resolved(user_id UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE users SET issues_resolved = issues_resolved + 1 WHERE id = user_id;
END;
$$ LANGUAGE plpgsql;

-- Add points to user and update tier
CREATE OR REPLACE FUNCTION add_user_points(user_id UUID, points INTEGER)
RETURNS VOID AS $$
DECLARE
    current_points INTEGER;
    new_total INTEGER;
    new_tier VARCHAR(50);
BEGIN
    -- Get current points
    SELECT total_points INTO current_points FROM user_rewards WHERE user_rewards.user_id = add_user_points.user_id;
    
    -- Calculate new total
    new_total := current_points + points;
    
    -- Determine new tier
    IF new_total >= 1000 THEN
        new_tier := 'Vigilant II';
    ELSIF new_total >= 750 THEN
        new_tier := 'Vigilant I';
    ELSIF new_total >= 500 THEN
        new_tier := 'Persistent II';
    ELSIF new_total >= 300 THEN
        new_tier := 'Persistent I';
    ELSIF new_total >= 150 THEN
        new_tier := 'Observer II';
    ELSE
        new_tier := 'Observer I';
    END IF;
    
    -- Update user rewards
    UPDATE user_rewards 
    SET total_points = new_total, current_tier = new_tier
    WHERE user_rewards.user_id = add_user_points.user_id;
END;
$$ LANGUAGE plpgsql;

-- Increment user milestones
CREATE OR REPLACE FUNCTION increment_user_milestones(user_id UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE user_rewards SET milestones_reached = milestones_reached + 1 WHERE user_rewards.user_id = increment_user_milestones.user_id;
END;
$$ LANGUAGE plpgsql;

-- Increment user items claimed
CREATE OR REPLACE FUNCTION increment_user_items_claimed(user_id UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE user_rewards SET items_claimed = items_claimed + 1 WHERE user_rewards.user_id = increment_user_items_claimed.user_id;
END;
$$ LANGUAGE plpgsql;

-- ================================================
-- VERIFICATION QUERIES
-- ================================================

-- Run these queries to verify your setup:

-- 1. List all tables
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;

-- 2. Count default data
-- SELECT 'Badges' as table_name, COUNT(*) as count FROM badges
-- UNION ALL SELECT 'Milestones', COUNT(*) FROM milestones
-- UNION ALL SELECT 'Redeemable Items', COUNT(*) FROM redeemable_items;

-- 3. List all functions
-- SELECT proname FROM pg_proc WHERE pronamespace = 'public'::regnamespace AND proname LIKE '%user%' OR proname LIKE '%issue%';

-- ================================================
-- SETUP COMPLETE!
-- ================================================
-- Your database is now ready to use with the FailState backend.
-- 
-- Next steps:
-- 1. Configure your .env file with Supabase credentials
-- 2. Start your backend server: ./start.sh
-- 3. Test the API at http://localhost:8000/docs
-- ================================================

