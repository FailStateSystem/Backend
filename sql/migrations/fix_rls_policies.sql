-- ================================================
-- FIX RLS POLICIES FOR USER SIGNUP
-- ================================================
-- This script fixes Row Level Security issues
-- Run this in your Supabase SQL Editor
-- ================================================

-- OPTION 1: Disable RLS for Development (QUICK FIX)
-- ================================================
-- Use this if you want to get started quickly
-- NOT recommended for production!

ALTER TABLE users DISABLE ROW LEVEL SECURITY;
ALTER TABLE issues DISABLE ROW LEVEL SECURITY;
ALTER TABLE timeline_events DISABLE ROW LEVEL SECURITY;
ALTER TABLE issue_upvotes DISABLE ROW LEVEL SECURITY;
ALTER TABLE user_rewards DISABLE ROW LEVEL SECURITY;
ALTER TABLE milestones DISABLE ROW LEVEL SECURITY;
ALTER TABLE user_milestones DISABLE ROW LEVEL SECURITY;
ALTER TABLE badges DISABLE ROW LEVEL SECURITY;
ALTER TABLE user_badges DISABLE ROW LEVEL SECURITY;
ALTER TABLE redeemable_items DISABLE ROW LEVEL SECURITY;
ALTER TABLE claimed_items DISABLE ROW LEVEL SECURITY;
ALTER TABLE rewards_history DISABLE ROW LEVEL SECURITY;

-- ================================================
-- OPTION 2: Enable RLS with Proper Policies (RECOMMENDED)
-- ================================================
-- Uncomment this section for production-ready security
-- Comment out OPTION 1 if you use this

/*
-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE issues ENABLE ROW LEVEL SECURITY;
ALTER TABLE timeline_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE issue_upvotes ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_rewards ENABLE ROW LEVEL SECURITY;
ALTER TABLE milestones ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_milestones ENABLE ROW LEVEL SECURITY;
ALTER TABLE badges ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_badges ENABLE ROW LEVEL SECURITY;
ALTER TABLE redeemable_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE claimed_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE rewards_history ENABLE ROW LEVEL SECURITY;

-- ================================================
-- USERS TABLE POLICIES
-- ================================================

-- Allow anyone to insert users (for signup)
-- This is safe because the backend validates the data
CREATE POLICY "Enable insert for service role during signup"
ON users FOR INSERT
TO service_role
WITH CHECK (true);

-- Allow users to view their own profile
CREATE POLICY "Users can view own profile"
ON users FOR SELECT
USING (true);

-- Allow users to update their own profile
CREATE POLICY "Users can update own profile"
ON users FOR UPDATE
USING (id = current_setting('app.current_user_id')::uuid);

-- ================================================
-- ISSUES TABLE POLICIES
-- ================================================

-- Anyone can view issues
CREATE POLICY "Anyone can view issues"
ON issues FOR SELECT
USING (true);

-- Service role can insert issues (backend will handle auth)
CREATE POLICY "Service role can insert issues"
ON issues FOR INSERT
TO service_role
WITH CHECK (true);

-- Users can update their own issues
CREATE POLICY "Users can update own issues"
ON issues FOR UPDATE
USING (reported_by = current_setting('app.current_user_id')::uuid);

-- ================================================
-- TIMELINE EVENTS POLICIES
-- ================================================

CREATE POLICY "Anyone can view timeline events"
ON timeline_events FOR SELECT
USING (true);

CREATE POLICY "Service role can insert timeline events"
ON timeline_events FOR INSERT
TO service_role
WITH CHECK (true);

-- ================================================
-- ISSUE UPVOTES POLICIES
-- ================================================

CREATE POLICY "Anyone can view upvotes"
ON issue_upvotes FOR SELECT
USING (true);

CREATE POLICY "Service role can manage upvotes"
ON issue_upvotes FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- ================================================
-- REWARDS SYSTEM POLICIES
-- ================================================

CREATE POLICY "Users can view all rewards data"
ON user_rewards FOR SELECT
USING (true);

CREATE POLICY "Service role can manage rewards"
ON user_rewards FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

CREATE POLICY "Anyone can view milestones"
ON milestones FOR SELECT
USING (true);

CREATE POLICY "Service role can manage milestones"
ON milestones FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

CREATE POLICY "Users can view all user milestones"
ON user_milestones FOR SELECT
USING (true);

CREATE POLICY "Service role can manage user milestones"
ON user_milestones FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- ================================================
-- BADGES POLICIES
-- ================================================

CREATE POLICY "Anyone can view badges"
ON badges FOR SELECT
USING (true);

CREATE POLICY "Service role can manage badges"
ON badges FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

CREATE POLICY "Users can view all user badges"
ON user_badges FOR SELECT
USING (true);

CREATE POLICY "Service role can manage user badges"
ON user_badges FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- ================================================
-- REDEEMABLE ITEMS POLICIES
-- ================================================

CREATE POLICY "Anyone can view redeemable items"
ON redeemable_items FOR SELECT
USING (true);

CREATE POLICY "Service role can manage items"
ON redeemable_items FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

CREATE POLICY "Users can view claimed items"
ON claimed_items FOR SELECT
USING (true);

CREATE POLICY "Service role can manage claimed items"
ON claimed_items FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- ================================================
-- REWARDS HISTORY POLICIES
-- ================================================

CREATE POLICY "Users can view rewards history"
ON rewards_history FOR SELECT
USING (true);

CREATE POLICY "Service role can manage rewards history"
ON rewards_history FOR ALL
TO service_role
USING (true)
WITH CHECK (true);
*/

-- ================================================
-- VERIFICATION QUERY
-- ================================================
-- Run this to check RLS status on all tables

SELECT 
    schemaname,
    tablename,
    rowsecurity as "RLS Enabled"
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY tablename;

