-- ============================================
-- DEBUG ADMIN LOGIN
-- ============================================
-- Run these queries to debug the login issue
-- ============================================

-- 1. Check if admin exists
SELECT 
    id,
    email,
    username,
    is_active,
    is_super_admin,
    password_hash,
    created_at
FROM admins
WHERE email = 'admin@failstate.in';

-- Expected: 1 row with is_active = true


-- 2. Check RLS is enabled
SELECT 
    schemaname,
    tablename,
    rowsecurity
FROM pg_tables
WHERE tablename IN ('admins', 'admin_action_logs');

-- Expected: rowsecurity = true for both


-- 3. Check policies exist
SELECT 
    tablename,
    policyname,
    cmd,
    permissive
FROM pg_policies
WHERE tablename IN ('admins', 'admin_action_logs')
ORDER BY tablename, policyname;

-- Expected: Multiple policies showing


-- 4. Test if we can SELECT from admins (simulate backend query)
SET ROLE anon;
SELECT 
    id,
    email,
    is_active
FROM admins
WHERE email = 'admin@failstate.in' AND is_active = true;
RESET ROLE;

-- Expected: 1 row (if this fails, RLS is blocking)


-- 5. Check password hash format
SELECT 
    email,
    LEFT(password_hash, 7) as hash_prefix,
    LENGTH(password_hash) as hash_length
FROM admins
WHERE email = 'admin@failstate.in';

-- Expected: hash_prefix = '$2b$12$', hash_length = 60


-- 6. Verify admin table structure
SELECT 
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'admins'
ORDER BY ordinal_position;
