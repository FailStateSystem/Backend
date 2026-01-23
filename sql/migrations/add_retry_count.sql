-- Add retry_count column to track verification attempts
-- This prevents infinite retry loops when OpenAI quota is exceeded

ALTER TABLE issues ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;

-- Add index for better query performance
CREATE INDEX IF NOT EXISTS idx_issues_verification_retry 
ON issues(verification_status, retry_count);

-- Update existing pending issues to have retry_count = 0
UPDATE issues 
SET retry_count = 0 
WHERE verification_status = 'pending' AND retry_count IS NULL;

-- View issues that need manual intervention (>= 3 retries)
-- Useful for monitoring
CREATE OR REPLACE VIEW issues_needs_manual_review AS
SELECT 
    id,
    title,
    description,
    verification_status,
    retry_count,
    reported_at,
    reported_by
FROM issues
WHERE verification_status = 'pending' AND retry_count >= 3
ORDER BY reported_at DESC;

COMMENT ON COLUMN issues.retry_count IS 'Number of AI verification attempts (max 3 before requiring manual intervention)';

