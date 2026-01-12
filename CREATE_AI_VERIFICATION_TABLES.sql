-- ================================================
-- AI VERIFICATION PIPELINE - DATABASE SCHEMA
-- ================================================
-- Run this in Supabase SQL Editor
-- ================================================

-- Add verification status to existing issues table (non-breaking)
ALTER TABLE issues 
ADD COLUMN IF NOT EXISTS verification_status VARCHAR(50) DEFAULT 'pending',
ADD COLUMN IF NOT EXISTS processed_at TIMESTAMP WITH TIME ZONE;

-- Index for querying unprocessed issues
CREATE INDEX IF NOT EXISTS idx_issues_verification_status ON issues(verification_status);

-- ================================================
-- VERIFIED ISSUES TABLE (Public, Rewardable)
-- ================================================
CREATE TABLE IF NOT EXISTS issues_verified (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_issue_id UUID NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    
    -- AI Verification Fields
    is_genuine BOOLEAN NOT NULL DEFAULT true,
    ai_confidence_score DECIMAL(3,2) NOT NULL CHECK (ai_confidence_score >= 0 AND ai_confidence_score <= 1),
    ai_reasoning TEXT NOT NULL,
    
    -- AI Enriched Content
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('low', 'moderate', 'high')),
    generated_title VARCHAR(255) NOT NULL,
    generated_description TEXT NOT NULL,
    public_impact TEXT NOT NULL,
    tags TEXT[] DEFAULT '{}',
    content_warnings TEXT[] DEFAULT '{}',
    
    -- Original Data (denormalized for performance)
    category VARCHAR(50) NOT NULL,
    location_name VARCHAR(255) NOT NULL,
    location_lat DECIMAL(10, 8) NOT NULL,
    location_lng DECIMAL(11, 8) NOT NULL,
    image_url TEXT,
    video_url TEXT,
    reported_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Status & Metrics
    status VARCHAR(50) DEFAULT 'unresolved',
    upvotes INTEGER DEFAULT 0,
    
    -- Timestamps
    reported_at TIMESTAMP WITH TIME ZONE NOT NULL,
    verified_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(original_issue_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_verified_status ON issues_verified(status);
CREATE INDEX IF NOT EXISTS idx_verified_category ON issues_verified(category);
CREATE INDEX IF NOT EXISTS idx_verified_reporter ON issues_verified(reported_by);
CREATE INDEX IF NOT EXISTS idx_verified_severity ON issues_verified(severity);
CREATE INDEX IF NOT EXISTS idx_verified_location ON issues_verified(location_lat, location_lng);
CREATE INDEX IF NOT EXISTS idx_verified_reported_at ON issues_verified(reported_at DESC);
CREATE INDEX IF NOT EXISTS idx_verified_tags ON issues_verified USING GIN(tags);

-- ================================================
-- REJECTED ISSUES TABLE (Never Public)
-- ================================================
CREATE TABLE IF NOT EXISTS issues_rejected (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_issue_id UUID NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    
    -- Rejection Details
    rejection_reason TEXT NOT NULL,
    ai_reasoning TEXT NOT NULL,
    confidence_score DECIMAL(3,2) NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
    
    -- Metadata
    rejected_by VARCHAR(50) DEFAULT 'ai_verification',
    rejected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(original_issue_id)
);

-- Index for analytics
CREATE INDEX IF NOT EXISTS idx_rejected_reason ON issues_rejected(rejection_reason);
CREATE INDEX IF NOT EXISTS idx_rejected_created_at ON issues_rejected(created_at DESC);

-- ================================================
-- VERIFICATION AUDIT LOG
-- ================================================
CREATE TABLE IF NOT EXISTS verification_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_id UUID NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    
    -- Processing Details
    status VARCHAR(50) NOT NULL, -- pending, processing, verified, rejected, failed
    attempt_number INTEGER DEFAULT 1,
    error_message TEXT,
    
    -- AI Response
    ai_raw_response JSONB,
    ai_model_used VARCHAR(50),
    processing_time_ms INTEGER,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for monitoring
CREATE INDEX IF NOT EXISTS idx_audit_issue ON verification_audit_log(issue_id);
CREATE INDEX IF NOT EXISTS idx_audit_status ON verification_audit_log(status);
CREATE INDEX IF NOT EXISTS idx_audit_created_at ON verification_audit_log(created_at DESC);

-- ================================================
-- HELPER FUNCTIONS
-- ================================================

-- Function to get pending verification count
CREATE OR REPLACE FUNCTION get_pending_verification_count()
RETURNS INTEGER AS $$
BEGIN
    RETURN (SELECT COUNT(*) FROM issues WHERE verification_status = 'pending');
END;
$$ LANGUAGE plpgsql;

-- Function to mark issue as processed
CREATE OR REPLACE FUNCTION mark_issue_processed(issue_uuid UUID, new_status VARCHAR)
RETURNS VOID AS $$
BEGIN
    UPDATE issues 
    SET verification_status = new_status,
        processed_at = NOW(),
        updated_at = NOW()
    WHERE id = issue_uuid;
END;
$$ LANGUAGE plpgsql;

-- ================================================
-- VERIFICATION COMPLETE
-- ================================================
-- Verify tables were created
SELECT 
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public' 
AND table_name IN ('issues_verified', 'issues_rejected', 'verification_audit_log')
ORDER BY table_name;

-- Check issues table was updated
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'issues' 
AND column_name IN ('verification_status', 'processed_at')
ORDER BY column_name;

