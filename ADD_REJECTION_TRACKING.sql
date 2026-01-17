-- ================================================
-- ADD REJECTION TRACKING AND PENALTY SYSTEM
-- ================================================

-- 1. Add columns to users table for account suspension
ALTER TABLE users
ADD COLUMN IF NOT EXISTS account_status VARCHAR(20) DEFAULT 'active';

CREATE INDEX IF NOT EXISTS idx_users_account_status ON users(account_status);

-- 2. Add rejection tracking to issues table
ALTER TABLE issues
ADD COLUMN IF NOT EXISTS rejection_reason TEXT,
ADD COLUMN IF NOT EXISTS rejection_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_rejection_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX IF NOT EXISTS idx_issues_rejection_reason ON issues(rejection_reason);
CREATE INDEX IF NOT EXISTS idx_issues_rejection_count ON issues(rejection_count);

-- 3. Create user_penalties table to track progressive enforcement
CREATE TABLE IF NOT EXISTS user_penalties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    penalty_type VARCHAR(50) NOT NULL,  -- 'warning', 'points_deduction', 'account_suspended'
    points_deducted INTEGER DEFAULT 0,
    reason TEXT NOT NULL,
    rejection_count_at_time INTEGER NOT NULL,  -- How many rejections when penalty applied
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_penalties_user_id ON user_penalties(user_id);
CREATE INDEX IF NOT EXISTS idx_user_penalties_type ON user_penalties(penalty_type);
CREATE INDEX IF NOT EXISTS idx_user_penalties_created_at ON user_penalties(created_at);

-- 4. Function to apply progressive penalties
CREATE OR REPLACE FUNCTION apply_fake_submission_penalty(
    p_user_id UUID,
    p_issue_id UUID,
    p_rejection_reason TEXT,
    p_ai_reasoning TEXT,
    p_confidence_score DECIMAL(5, 4)
) RETURNS JSON AS $$
DECLARE
    v_rejection_count INTEGER;
    v_penalty_type VARCHAR(50);
    v_points_to_deduct INTEGER := 0;
    v_account_status VARCHAR(20) := 'active';
    v_message TEXT;
    v_current_points INTEGER;
BEGIN
    -- Get current rejection count for user
    SELECT COALESCE(COUNT(*), 0)
    INTO v_rejection_count
    FROM issues
    WHERE reported_by = p_user_id
    AND verification_status = 'rejected';
    
    -- Update issue with rejection info
    UPDATE issues
    SET 
        rejection_reason = p_rejection_reason,
        rejection_count = v_rejection_count,
        last_rejection_at = NOW()
    WHERE id = p_issue_id;
    
    -- Determine penalty based on rejection count
    IF v_rejection_count = 1 THEN
        -- First rejection: Warning only
        v_penalty_type := 'first_warning';
        v_message := 'First warning: Submitting non-genuine civic issues violates our terms. Please only submit real infrastructure problems.';
        
    ELSIF v_rejection_count = 2 THEN
        -- Second rejection: Second warning
        v_penalty_type := 'second_warning';
        v_message := 'Second warning: Continued submission of fake issues will result in point deductions and account suspension.';
        
    ELSIF v_rejection_count = 3 THEN
        -- Third rejection: Deduct 10 points
        v_penalty_type := 'points_deduction';
        v_points_to_deduct := 10;
        v_message := 'Penalty applied: 10 points deducted for repeatedly submitting fake issues. Two more violations will result in account suspension.';
        
        -- Deduct points using the RPC function (if it exists)
        BEGIN
            PERFORM add_user_points(p_user_id, -v_points_to_deduct);
        EXCEPTION WHEN OTHERS THEN
            -- If add_user_points doesn't exist, just log the penalty
            NULL;
        END;
        
    ELSIF v_rejection_count = 4 THEN
        -- Fourth rejection: Deduct 25 points + final warning
        v_penalty_type := 'severe_penalty';
        v_points_to_deduct := 25;
        v_message := 'FINAL WARNING: 25 points deducted. One more fake submission will result in permanent account suspension.';
        
        -- Deduct points using the RPC function (if it exists)
        BEGIN
            PERFORM add_user_points(p_user_id, -v_points_to_deduct);
        EXCEPTION WHEN OTHERS THEN
            NULL;
        END;
        
    ELSIF v_rejection_count >= 5 THEN
        -- Fifth+ rejection: Suspend account
        v_penalty_type := 'account_suspended';
        v_points_to_deduct := 50;
        v_account_status := 'suspended';
        v_message := 'Account suspended for repeated violations. You have submitted multiple fake issues despite warnings. Contact support to appeal.';
        
        -- Deduct points and suspend account
        BEGIN
            PERFORM add_user_points(p_user_id, -v_points_to_deduct);
        EXCEPTION WHEN OTHERS THEN
            NULL;
        END;
        
        -- Suspend account
        UPDATE users
        SET account_status = 'suspended'
        WHERE id = p_user_id;
    END IF;
    
    -- Log penalty
    INSERT INTO user_penalties (
        user_id,
        penalty_type,
        points_deducted,
        reason,
        rejection_count_at_time
    ) VALUES (
        p_user_id,
        v_penalty_type,
        v_points_to_deduct,
        p_ai_reasoning,
        v_rejection_count
    );
    
    -- Get current points (if points system exists)
    BEGIN
        SELECT points INTO v_current_points
        FROM users
        WHERE id = p_user_id;
    EXCEPTION WHEN OTHERS THEN
        v_current_points := 0;
    END;
    
    -- Return penalty info
    RETURN json_build_object(
        'penalty_applied', v_penalty_type,
        'rejection_count', v_rejection_count,
        'points_deducted', v_points_to_deduct,
        'current_points', v_current_points,
        'account_status', v_account_status,
        'message', v_message
    );
END;
$$ LANGUAGE plpgsql;

-- 5. View for monitoring penalties
CREATE OR REPLACE VIEW penalty_summary AS
SELECT 
    u.id as user_id,
    u.email,
    u.username,
    u.account_status,
    COUNT(DISTINCT i.id) as total_rejections,
    COUNT(DISTINCT up.id) as total_penalties,
    MAX(i.last_rejection_at) as last_rejection_at,
    MAX(up.created_at) as last_penalty_at,
    SUM(up.points_deducted) as total_points_deducted
FROM users u
LEFT JOIN issues i ON u.id = i.reported_by AND i.verification_status = 'rejected'
LEFT JOIN user_penalties up ON u.id = up.user_id
GROUP BY u.id, u.email, u.username, u.account_status
HAVING COUNT(DISTINCT i.id) > 0  -- Only users with rejections
ORDER BY total_rejections DESC;

COMMENT ON VIEW penalty_summary IS 'Summary of user penalties and rejection counts';

