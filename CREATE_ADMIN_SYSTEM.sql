-- ============================================
-- ADMIN SYSTEM SETUP
-- ============================================
-- Creates separate admin table and audit logging
-- Run this in Supabase SQL Editor
-- ============================================

-- 1. CREATE ADMINS TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS admins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) NOT NULL,
    password_hash TEXT NOT NULL,
    full_name VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    is_super_admin BOOLEAN DEFAULT false,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add index for faster email lookup
CREATE INDEX IF NOT EXISTS idx_admins_email ON admins(email);
CREATE INDEX IF NOT EXISTS idx_admins_active ON admins(is_active);

-- Add updated_at trigger
CREATE OR REPLACE FUNCTION update_admins_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER admins_updated_at_trigger
    BEFORE UPDATE ON admins
    FOR EACH ROW
    EXECUTE FUNCTION update_admins_updated_at();


-- ============================================
-- 2. CREATE ADMIN ACTION LOGS TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS admin_action_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_id UUID NOT NULL REFERENCES admins(id) ON DELETE CASCADE,
    action_type VARCHAR(100) NOT NULL,  -- e.g., 'user_suspended', 'issue_approved', 'user_deleted'
    resource_type VARCHAR(50) NOT NULL,  -- 'user', 'issue', 'system'
    resource_id UUID,  -- ID of affected resource
    details JSONB,  -- Additional context (reason, changes, etc.)
    ip_address VARCHAR(45),  -- IPv4 or IPv6
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_admin_action_logs_admin_id ON admin_action_logs(admin_id);
CREATE INDEX IF NOT EXISTS idx_admin_action_logs_action_type ON admin_action_logs(action_type);
CREATE INDEX IF NOT EXISTS idx_admin_action_logs_resource_type ON admin_action_logs(resource_type);
CREATE INDEX IF NOT EXISTS idx_admin_action_logs_created_at ON admin_action_logs(created_at DESC);

-- Composite index for admin activity queries
CREATE INDEX IF NOT EXISTS idx_admin_action_logs_admin_created ON admin_action_logs(admin_id, created_at DESC);


-- ============================================
-- 3. CREATE ADMIN ACCOUNT
-- ============================================

-- Password: FailState@2026!Secure#Admin
-- This is a strong password - CHANGE IT IMMEDIATELY after first login!
-- Hashed with bcrypt (you'll need to generate this with your backend)

-- STEP 1: Generate password hash (run in your backend)
-- Use this Python code to generate the hash:
/*
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
password = "7fu5$$v3Y8,_K4604e^S-iH-"
hashed = pwd_context.hash(password)
print(hashed)
*/

-- STEP 2: Insert admin with the generated hash
-- Replace 'YOUR_BCRYPT_HASH_HERE' with the actual hash from step 1

INSERT INTO admins (
    email,
    username,
    password_hash,
    full_name,
    is_super_admin,
    is_active
) VALUES (
    'admin@failstate.in',
    'admin',
    -- Hash for password: FailState@2026!Secure#Admin
    '$2b$12$hVw73qD.xNtuh2eFR2cTNe66PXPdmzv0wIUKiSYf9t19YIaqEmTbK',
    'FailState Administrator',
    true,
    true
) ON CONFLICT (email) DO NOTHING;

-- Note: The above hash is for password: "FailState@2026!Secure#Admin"
-- ⚠️ CHANGE THIS PASSWORD IMMEDIATELY AFTER FIRST LOGIN!

-- Default Credentials:
-- Email: admin@failstate.in
-- Password: FailState@2026!Secure#Admin


-- ============================================
-- 4. CREATE VIEW FOR ADMIN ACTIVITY SUMMARY
-- ============================================

CREATE OR REPLACE VIEW admin_activity_summary AS
SELECT
    a.id,
    a.email,
    a.username,
    a.full_name,
    a.is_super_admin,
    a.last_login_at,
    COUNT(aal.id) as total_actions,
    COUNT(CASE WHEN aal.created_at > NOW() - INTERVAL '24 hours' THEN 1 END) as actions_today,
    COUNT(CASE WHEN aal.created_at > NOW() - INTERVAL '7 days' THEN 1 END) as actions_this_week,
    MAX(aal.created_at) as last_action_at
FROM admins a
LEFT JOIN admin_action_logs aal ON a.id = aal.admin_id
WHERE a.is_active = true
GROUP BY a.id, a.email, a.username, a.full_name, a.is_super_admin, a.last_login_at;


-- ============================================
-- 5. CREATE HELPER FUNCTIONS
-- ============================================

-- Function to log admin actions
CREATE OR REPLACE FUNCTION log_admin_action(
    p_admin_id UUID,
    p_action_type VARCHAR(100),
    p_resource_type VARCHAR(50),
    p_resource_id UUID DEFAULT NULL,
    p_details JSONB DEFAULT NULL,
    p_ip_address VARCHAR(45) DEFAULT NULL,
    p_user_agent TEXT DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_log_id UUID;
BEGIN
    INSERT INTO admin_action_logs (
        admin_id,
        action_type,
        resource_type,
        resource_id,
        details,
        ip_address,
        user_agent
    ) VALUES (
        p_admin_id,
        p_action_type,
        p_resource_type,
        p_resource_id,
        p_details,
        p_ip_address,
        p_user_agent
    ) RETURNING id INTO v_log_id;
    
    RETURN v_log_id;
END;
$$ LANGUAGE plpgsql;


-- Function to update admin last login
CREATE OR REPLACE FUNCTION update_admin_last_login(p_admin_id UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE admins
    SET last_login_at = NOW()
    WHERE id = p_admin_id;
END;
$$ LANGUAGE plpgsql;


-- ============================================
-- 6. GRANT PERMISSIONS (if using RLS)
-- ============================================

-- Disable RLS for admins table (admins authenticate separately)
ALTER TABLE admins ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_action_logs ENABLE ROW LEVEL SECURITY;

-- Create policy for admins (only accessible by service role)
CREATE POLICY "Service role can access admins" ON admins
    FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role can access admin logs" ON admin_action_logs
    FOR ALL
    USING (auth.role() = 'service_role');


-- ============================================
-- 7. VERIFICATION QUERIES
-- ============================================

-- Verify admin was created
SELECT 
    id,
    email,
    username,
    full_name,
    is_super_admin,
    is_active,
    created_at
FROM admins;

-- Check tables exist
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('admins', 'admin_action_logs');

-- Check indexes
SELECT 
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename IN ('admins', 'admin_action_logs')
ORDER BY tablename, indexname;


-- ============================================
-- 8. SAMPLE QUERIES FOR ADMIN CONSOLE
-- ============================================

-- Get admin activity summary
SELECT * FROM admin_activity_summary;

-- Get recent admin actions
SELECT 
    aal.*,
    a.email as admin_email,
    a.username as admin_username
FROM admin_action_logs aal
JOIN admins a ON aal.admin_id = a.id
ORDER BY aal.created_at DESC
LIMIT 100;

-- Get actions by specific admin
SELECT 
    action_type,
    resource_type,
    resource_id,
    details,
    created_at
FROM admin_action_logs
WHERE admin_id = 'YOUR_ADMIN_ID'
ORDER BY created_at DESC;

-- Get actions by type
SELECT 
    action_type,
    COUNT(*) as action_count,
    COUNT(DISTINCT admin_id) as unique_admins
FROM admin_action_logs
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY action_type
ORDER BY action_count DESC;


-- ============================================
-- NOTES
-- ============================================

/*
DEFAULT ADMIN CREDENTIALS (⚠️ CHANGE IMMEDIATELY):
Email: admin@failstate.in
Password: FailState@2026!Secure#Admin

IMPORTANT:
1. Change the password immediately after first login
2. Store the new password securely (password manager)
3. Consider adding 2FA in production
4. Monitor admin_action_logs regularly
5. Review admin_activity_summary weekly

SECURITY BEST PRACTICES:
- Separate admin authentication from user authentication
- Log all admin actions for audit trail
- Use strong passwords (min 16 characters)
- Rotate passwords every 90 days
- Review logs for suspicious activity
- Disable inactive admin accounts
- Use HTTPS only for admin access
*/


-- ============================================
-- DEPLOYMENT CHECKLIST
-- ============================================

/*
✅ Run this SQL script in Supabase
✅ Verify admin account created
✅ Verify tables and indexes created
✅ Test admin login (see backend update)
✅ Change default password
✅ Document new password securely
✅ Update backend admin authentication
✅ Test admin action logging
✅ Set up log monitoring alerts
*/
