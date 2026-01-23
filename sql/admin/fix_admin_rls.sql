-- ============================================
-- FIX ADMIN TABLE RLS POLICIES
-- ============================================
-- Run this in Supabase SQL Editor to fix admin login
-- ============================================

-- Drop the restrictive policy
DROP POLICY IF EXISTS "Service role can access admins" ON admins;

-- For admins table: Allow backend to SELECT (for login), but restrict other operations
CREATE POLICY "Allow SELECT for authentication" ON admins
    FOR SELECT
    USING (true);  -- Allow reading for authentication

CREATE POLICY "Only service role can modify admins" ON admins
    FOR ALL
    USING (auth.role() = 'service_role');

-- For admin_action_logs: Allow backend to INSERT logs
DROP POLICY IF EXISTS "Service role can access admin logs" ON admin_action_logs;

CREATE POLICY "Allow INSERT for logging" ON admin_action_logs
    FOR INSERT
    WITH CHECK (true);  -- Allow inserting logs

CREATE POLICY "Allow SELECT for reading logs" ON admin_action_logs
    FOR SELECT
    USING (true);  -- Allow reading logs

CREATE POLICY "Only service role can modify logs" ON admin_action_logs
    FOR UPDATE
    USING (auth.role() = 'service_role');

CREATE POLICY "Only service role can delete logs" ON admin_action_logs
    FOR DELETE
    USING (auth.role() = 'service_role');


-- ============================================
-- VERIFICATION
-- ============================================

-- Check policies are created
SELECT 
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd,
    qual,
    with_check
FROM pg_policies
WHERE tablename IN ('admins', 'admin_action_logs')
ORDER BY tablename, policyname;

-- Test admin exists
SELECT 
    id,
    email,
    username,
    is_active,
    created_at
FROM admins
WHERE email = 'admin@failstate.in';
