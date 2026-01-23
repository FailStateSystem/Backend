-- Pre-Ingestion Filtering System Database Schema
-- This must be run BEFORE deploying the filtering code

-- ============================================
-- 1. ADD TRUST SCORE TO USERS TABLE
-- ============================================

ALTER TABLE users ADD COLUMN IF NOT EXISTS trust_score INTEGER DEFAULT 100;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_shadow_banned BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS ban_reason TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS banned_until TIMESTAMP WITH TIME ZONE;

CREATE INDEX IF NOT EXISTS idx_users_trust_score ON users(trust_score);
CREATE INDEX IF NOT EXISTS idx_users_shadow_banned ON users(is_shadow_banned);

COMMENT ON COLUMN users.trust_score IS 'User trust score (0-100). Decreased by violations, increased by good behavior. Low scores get stricter limits.';
COMMENT ON COLUMN users.is_shadow_banned IS 'Shadow banned users: submissions accepted but not processed';
COMMENT ON COLUMN users.ban_reason IS 'Reason for ban/shadow ban';
COMMENT ON COLUMN users.banned_until IS 'Temporary ban expiration. NULL = permanent';


-- ============================================
-- 2. IMAGE HASHES (DUPLICATE DETECTION)
-- ============================================

CREATE TABLE IF NOT EXISTS image_hashes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    perceptual_hash TEXT NOT NULL,
    average_hash TEXT NOT NULL,
    difference_hash TEXT NOT NULL,
    image_url TEXT,
    issue_id UUID,
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ip_address INET
);

CREATE INDEX IF NOT EXISTS idx_image_hashes_perceptual ON image_hashes(perceptual_hash);
CREATE INDEX IF NOT EXISTS idx_image_hashes_user ON image_hashes(user_id);
CREATE INDEX IF NOT EXISTS idx_image_hashes_uploaded ON image_hashes(uploaded_at);
CREATE INDEX IF NOT EXISTS idx_image_hashes_ip ON image_hashes(ip_address);

COMMENT ON TABLE image_hashes IS 'Stores perceptual hashes for duplicate detection';


-- ============================================
-- 3. USER RATE LIMITS TRACKING
-- ============================================

CREATE TABLE IF NOT EXISTS user_rate_limit_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action_type VARCHAR(50) NOT NULL,  -- 'issue_create', 'issue_attempt', etc.
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    success BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_user_rate_limit_user ON user_rate_limit_tracking(user_id);
CREATE INDEX IF NOT EXISTS idx_user_rate_limit_timestamp ON user_rate_limit_tracking(timestamp);
CREATE INDEX IF NOT EXISTS idx_user_rate_limit_action ON user_rate_limit_tracking(action_type);

COMMENT ON TABLE user_rate_limit_tracking IS 'Tracks user actions for rate limiting';


-- ============================================
-- 4. IP RATE LIMITS TRACKING
-- ============================================

CREATE TABLE IF NOT EXISTS ip_rate_limit_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ip_address INET NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    success BOOLEAN DEFAULT TRUE,
    user_id UUID  -- May be NULL for unauthenticated requests
);

CREATE INDEX IF NOT EXISTS idx_ip_rate_limit_ip ON ip_rate_limit_tracking(ip_address);
CREATE INDEX IF NOT EXISTS idx_ip_rate_limit_timestamp ON ip_rate_limit_tracking(timestamp);
CREATE INDEX IF NOT EXISTS idx_ip_rate_limit_action ON ip_rate_limit_tracking(action_type);

COMMENT ON TABLE ip_rate_limit_tracking IS 'Tracks IP-based rate limiting';


-- ============================================
-- 5. ABUSE LOGS
-- ============================================

CREATE TABLE IF NOT EXISTS abuse_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    ip_address INET NOT NULL,
    violation_type VARCHAR(100) NOT NULL,  -- 'nsfw', 'duplicate', 'ocr', 'garbage', 'rate_limit', 'bot_behavior'
    severity VARCHAR(20) NOT NULL,  -- 'low', 'medium', 'high', 'critical'
    details JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    action_taken VARCHAR(100)  -- 'rejected', 'trust_decreased', 'cooldown', 'shadow_ban', 'ip_block'
);

CREATE INDEX IF NOT EXISTS idx_abuse_logs_user ON abuse_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_abuse_logs_ip ON abuse_logs(ip_address);
CREATE INDEX IF NOT EXISTS idx_abuse_logs_timestamp ON abuse_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_abuse_logs_violation ON abuse_logs(violation_type);
CREATE INDEX IF NOT EXISTS idx_abuse_logs_severity ON abuse_logs(severity);

COMMENT ON TABLE abuse_logs IS 'Comprehensive logging of all abuse attempts and violations';


-- ============================================
-- 6. IP BLACKLIST
-- ============================================

CREATE TABLE IF NOT EXISTS ip_blacklist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ip_address INET NOT NULL UNIQUE,
    reason TEXT NOT NULL,
    banned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    banned_until TIMESTAMP WITH TIME ZONE,  -- NULL = permanent
    banned_by UUID REFERENCES users(id),  -- Admin who issued ban
    violation_count INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_ip_blacklist_ip ON ip_blacklist(ip_address);
CREATE INDEX IF NOT EXISTS idx_ip_blacklist_banned_until ON ip_blacklist(banned_until);

COMMENT ON TABLE ip_blacklist IS 'IP addresses that are temporarily or permanently banned';


-- ============================================
-- 7. BOT DETECTION PATTERNS
-- ============================================

CREATE TABLE IF NOT EXISTS bot_detection_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_type VARCHAR(50) NOT NULL,  -- 'coordinated_image', 'gps_cluster', 'description_similarity'
    pattern_data JSONB NOT NULL,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    user_ids UUID[],
    ip_addresses INET[],
    confidence_score DECIMAL(3, 2) NOT NULL,  -- 0.00 to 1.00
    status VARCHAR(20) DEFAULT 'active'  -- 'active', 'resolved', 'false_positive'
);

CREATE INDEX IF NOT EXISTS idx_bot_patterns_type ON bot_detection_patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_bot_patterns_detected ON bot_detection_patterns(detected_at);
CREATE INDEX IF NOT EXISTS idx_bot_patterns_status ON bot_detection_patterns(status);

COMMENT ON TABLE bot_detection_patterns IS 'Tracks detected bot and coordinated attack patterns';


-- ============================================
-- 8. FILTERING STATS (OBSERVABILITY)
-- ============================================

CREATE TABLE IF NOT EXISTS filtering_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    filter_type VARCHAR(50) NOT NULL,  -- 'nsfw', 'duplicate', 'ocr', 'garbage', 'rate_limit', etc.
    blocked_count INTEGER DEFAULT 0,
    passed_count INTEGER DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(date, filter_type)
);

CREATE INDEX IF NOT EXISTS idx_filtering_stats_date ON filtering_stats(date);
CREATE INDEX IF NOT EXISTS idx_filtering_stats_filter ON filtering_stats(filter_type);

COMMENT ON TABLE filtering_stats IS 'Daily statistics for monitoring filter effectiveness';


-- ============================================
-- 9. SHADOW BANNED SUBMISSIONS
-- ============================================

CREATE TABLE IF NOT EXISTS shadow_banned_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    submission_data JSONB NOT NULL,
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ip_address INET
);

CREATE INDEX IF NOT EXISTS idx_shadow_submissions_user ON shadow_banned_submissions(user_id);
CREATE INDEX IF NOT EXISTS idx_shadow_submissions_submitted ON shadow_banned_submissions(submitted_at);

COMMENT ON TABLE shadow_banned_submissions IS 'Stores submissions from shadow-banned users (fake acceptance)';


-- ============================================
-- HELPER FUNCTIONS
-- ============================================

-- Function to log abuse
CREATE OR REPLACE FUNCTION log_abuse(
    p_user_id UUID,
    p_ip_address INET,
    p_violation_type VARCHAR(100),
    p_severity VARCHAR(20),
    p_details JSONB,
    p_action_taken VARCHAR(100)
) RETURNS UUID AS $$
DECLARE
    log_id UUID;
BEGIN
    INSERT INTO abuse_logs (user_id, ip_address, violation_type, severity, details, action_taken)
    VALUES (p_user_id, p_ip_address, p_violation_type, p_severity, p_details, p_action_taken)
    RETURNING id INTO log_id;
    
    RETURN log_id;
END;
$$ LANGUAGE plpgsql;


-- Function to update trust score
CREATE OR REPLACE FUNCTION update_trust_score(
    p_user_id UUID,
    p_delta INTEGER
) RETURNS INTEGER AS $$
DECLARE
    new_score INTEGER;
BEGIN
    UPDATE users
    SET trust_score = GREATEST(0, LEAST(100, trust_score + p_delta))
    WHERE id = p_user_id
    RETURNING trust_score INTO new_score;
    
    RETURN new_score;
END;
$$ LANGUAGE plpgsql;


-- Function to increment filtering stats
CREATE OR REPLACE FUNCTION increment_filter_stat(
    p_filter_type VARCHAR(50),
    p_blocked BOOLEAN
) RETURNS VOID AS $$
BEGIN
    INSERT INTO filtering_stats (date, filter_type, blocked_count, passed_count)
    VALUES (
        CURRENT_DATE,
        p_filter_type,
        CASE WHEN p_blocked THEN 1 ELSE 0 END,
        CASE WHEN p_blocked THEN 0 ELSE 1 END
    )
    ON CONFLICT (date, filter_type) DO UPDATE
    SET 
        blocked_count = filtering_stats.blocked_count + CASE WHEN p_blocked THEN 1 ELSE 0 END,
        passed_count = filtering_stats.passed_count + CASE WHEN p_blocked THEN 0 ELSE 1 END,
        last_updated = NOW();
END;
$$ LANGUAGE plpgsql;


-- ============================================
-- MONITORING VIEWS
-- ============================================

-- View: Recent abuse by user
CREATE OR REPLACE VIEW recent_abuse_by_user AS
SELECT 
    u.id,
    u.username,
    u.email,
    u.trust_score,
    u.is_shadow_banned,
    COUNT(*) as violation_count,
    MAX(al.timestamp) as last_violation,
    array_agg(DISTINCT al.violation_type) as violation_types
FROM users u
JOIN abuse_logs al ON u.id = al.user_id
WHERE al.timestamp > NOW() - INTERVAL '7 days'
GROUP BY u.id, u.username, u.email, u.trust_score, u.is_shadow_banned
ORDER BY violation_count DESC;


-- View: Recent abuse by IP
CREATE OR REPLACE VIEW recent_abuse_by_ip AS
SELECT 
    ip_address,
    COUNT(*) as violation_count,
    MAX(timestamp) as last_violation,
    array_agg(DISTINCT violation_type) as violation_types,
    array_agg(DISTINCT user_id) as user_ids
FROM abuse_logs
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY ip_address
ORDER BY violation_count DESC;


-- View: Daily filtering summary
CREATE OR REPLACE VIEW daily_filtering_summary AS
SELECT 
    date,
    SUM(blocked_count) as total_blocked,
    SUM(passed_count) as total_passed,
    ROUND(100.0 * SUM(blocked_count) / NULLIF(SUM(blocked_count) + SUM(passed_count), 0), 2) as block_rate
FROM filtering_stats
GROUP BY date
ORDER BY date DESC;


-- View: Low trust users
CREATE OR REPLACE VIEW low_trust_users AS
SELECT 
    id,
    username,
    email,
    trust_score,
    is_shadow_banned,
    created_at,
    (SELECT COUNT(*) FROM abuse_logs WHERE user_id = users.id) as total_violations,
    (SELECT COUNT(*) FROM abuse_logs WHERE user_id = users.id AND timestamp > NOW() - INTERVAL '7 days') as recent_violations
FROM users
WHERE trust_score < 50 OR is_shadow_banned = TRUE
ORDER BY trust_score ASC, recent_violations DESC;


-- ============================================
-- CLEANUP FUNCTIONS (RUN PERIODICALLY)
-- ============================================

-- Clean old rate limit tracking (keep 7 days)
CREATE OR REPLACE FUNCTION cleanup_old_rate_limits() RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
    additional_count INTEGER;
BEGIN
    DELETE FROM user_rate_limit_tracking WHERE timestamp < NOW() - INTERVAL '7 days';
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    DELETE FROM ip_rate_limit_tracking WHERE timestamp < NOW() - INTERVAL '7 days';
    GET DIAGNOSTICS additional_count = ROW_COUNT;
    
    deleted_count := deleted_count + additional_count;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;


-- Clean expired IP bans
CREATE OR REPLACE FUNCTION cleanup_expired_ip_bans() RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM ip_blacklist 
    WHERE banned_until IS NOT NULL 
    AND banned_until < NOW();
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;


-- Clean old image hashes (keep 90 days for duplicate detection)
CREATE OR REPLACE FUNCTION cleanup_old_image_hashes() RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM image_hashes WHERE uploaded_at < NOW() - INTERVAL '90 days';
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- INITIAL DATA
-- ============================================

-- Set default trust scores for existing users
UPDATE users SET trust_score = 100 WHERE trust_score IS NULL;
UPDATE users SET is_shadow_banned = FALSE WHERE is_shadow_banned IS NULL;

COMMENT ON DATABASE postgres IS 'Pre-ingestion filtering system installed';

