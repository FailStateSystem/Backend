-- ================================================
-- DISTRICT ANALYTICS FUNCTION FOR ADMIN CONSOLE
-- ================================================
-- Purpose: Provide aggregated district-level analytics for admin dashboard
-- Performance: Optimized for ~750 districts with LEFT JOINs
-- ================================================

CREATE OR REPLACE FUNCTION get_district_analytics(
    p_from_date TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    p_to_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    p_sort_by VARCHAR(50) DEFAULT 'unresolved_count',
    p_sort_order VARCHAR(4) DEFAULT 'DESC'
)
RETURNS TABLE(
    district_id UUID,
    district_name VARCHAR(255),
    state_name VARCHAR(255),
    total_issues BIGINT,
    verified_issues BIGINT,
    unresolved_issues BIGINT,
    high_severity_count BIGINT,
    moderate_severity_count BIGINT,
    low_severity_count BIGINT,
    oldest_unresolved_issue_age_days INTEGER,
    percentage_unresolved NUMERIC(5,2),
    last_issue_reported_at TIMESTAMP WITH TIME ZONE,
    authority_contact_status VARCHAR(20)
) AS $$
BEGIN
    RETURN QUERY
    WITH 
    -- CTE 1: Get all base issue counts per district (from issues table)
    issue_counts AS (
        SELECT 
            i.district_id,
            COUNT(i.id) AS total_count,
            -- Count unresolved issues (status NOT in resolved states)
            COUNT(CASE 
                WHEN i.status NOT IN ('resolved', 'closed', 'completed') 
                AND i.resolved_at IS NULL 
                THEN 1 
            END) AS unresolved_count,
            -- Calculate age of oldest unresolved issue in days
            EXTRACT(DAY FROM (NOW() - MIN(
                CASE 
                    WHEN i.status NOT IN ('resolved', 'closed', 'completed') 
                    AND i.resolved_at IS NULL 
                    THEN i.reported_at 
                END
            )))::INTEGER AS oldest_unresolved_age,
            -- Get most recent issue timestamp
            MAX(i.reported_at) AS last_reported
        FROM issues i
        WHERE 
            i.district_id IS NOT NULL
            -- Apply date filtering if provided
            AND (p_from_date IS NULL OR i.reported_at >= p_from_date)
            AND i.reported_at <= p_to_date
        GROUP BY i.district_id
    ),
    
    -- CTE 2: Get verified issue counts per district (from issues_verified via issues)
    verified_counts AS (
        SELECT 
            i.district_id,
            COUNT(DISTINCT iv.id) AS verified_count
        FROM issues i
        INNER JOIN issues_verified iv ON i.id = iv.original_issue_id
        WHERE 
            i.district_id IS NOT NULL
            AND (p_from_date IS NULL OR i.reported_at >= p_from_date)
            AND i.reported_at <= p_to_date
        GROUP BY i.district_id
    ),
    
    -- CTE 3: Get severity breakdown (from issues_verified)
    severity_counts AS (
        SELECT 
            i.district_id,
            COUNT(CASE WHEN iv.severity = 'high' THEN 1 END) AS high_count,
            COUNT(CASE WHEN iv.severity = 'moderate' THEN 1 END) AS moderate_count,
            COUNT(CASE WHEN iv.severity = 'low' THEN 1 END) AS low_count
        FROM issues i
        INNER JOIN issues_verified iv ON i.id = iv.original_issue_id
        WHERE 
            i.district_id IS NOT NULL
            AND (p_from_date IS NULL OR i.reported_at >= p_from_date)
            AND i.reported_at <= p_to_date
        GROUP BY i.district_id
    ),
    
    -- CTE 4: Get authority contact status per district
    authority_status AS (
        SELECT 
            da.district_id,
            CASE 
                WHEN da.dm_office_email IS NOT NULL AND da.is_active = TRUE THEN 'configured'
                WHEN da.id IS NOT NULL AND da.is_active = FALSE THEN 'inactive'
                WHEN da.id IS NOT NULL AND da.dm_office_email IS NULL THEN 'missing'
                ELSE 'missing'
            END AS contact_status
        FROM district_authorities da
    ),
    
    -- CTE 5: Combine all metrics
    combined_metrics AS (
        SELECT 
            db.id AS dist_id,
            db.district_name AS dist_name,
            db.state_name AS st_name,
            COALESCE(ic.total_count, 0) AS total_iss,
            COALESCE(vc.verified_count, 0) AS verified_iss,
            COALESCE(ic.unresolved_count, 0) AS unresolved_iss,
            COALESCE(sc.high_count, 0) AS high_sev,
            COALESCE(sc.moderate_count, 0) AS moderate_sev,
            COALESCE(sc.low_count, 0) AS low_sev,
            ic.oldest_unresolved_age AS oldest_age,
            -- Calculate percentage unresolved (avoid division by zero)
            CASE 
                WHEN COALESCE(ic.total_count, 0) > 0 
                THEN ROUND((COALESCE(ic.unresolved_count, 0)::NUMERIC / ic.total_count::NUMERIC) * 100, 2)
                ELSE 0.00
            END AS pct_unresolved,
            ic.last_reported AS last_reported_ts,
            COALESCE(ast.contact_status, 'unknown') AS auth_status
        FROM district_boundaries db
        -- LEFT JOIN ensures districts with NO issues still appear in results
        LEFT JOIN issue_counts ic ON db.id = ic.district_id
        LEFT JOIN verified_counts vc ON db.id = vc.district_id
        LEFT JOIN severity_counts sc ON db.id = sc.district_id
        LEFT JOIN authority_status ast ON db.id = ast.district_id
    )
    
    -- Final SELECT with dynamic sorting
    SELECT 
        cm.dist_id,
        cm.dist_name,
        cm.st_name,
        cm.total_iss,
        cm.verified_iss,
        cm.unresolved_iss,
        cm.high_sev,
        cm.moderate_sev,
        cm.low_sev,
        cm.oldest_age,
        cm.pct_unresolved,
        cm.last_reported_ts,
        cm.auth_status
    FROM combined_metrics cm
    ORDER BY
        CASE WHEN p_sort_by = 'unresolved_count' AND p_sort_order = 'DESC' THEN cm.unresolved_iss END DESC NULLS LAST,
        CASE WHEN p_sort_by = 'unresolved_count' AND p_sort_order = 'ASC' THEN cm.unresolved_iss END ASC NULLS LAST,
        CASE WHEN p_sort_by = 'high_severity_count' AND p_sort_order = 'DESC' THEN cm.high_sev END DESC NULLS LAST,
        CASE WHEN p_sort_by = 'high_severity_count' AND p_sort_order = 'ASC' THEN cm.high_sev END ASC NULLS LAST,
        CASE WHEN p_sort_by = 'total_issues' AND p_sort_order = 'DESC' THEN cm.total_iss END DESC NULLS LAST,
        CASE WHEN p_sort_by = 'total_issues' AND p_sort_order = 'ASC' THEN cm.total_iss END ASC NULLS LAST,
        CASE WHEN p_sort_by = 'district_name' AND p_sort_order = 'ASC' THEN cm.dist_name END ASC NULLS LAST,
        CASE WHEN p_sort_by = 'district_name' AND p_sort_order = 'DESC' THEN cm.dist_name END DESC NULLS LAST,
        -- Default sort: unresolved DESC, then district name ASC
        cm.unresolved_iss DESC NULLS LAST,
        cm.dist_name ASC;
END;
$$ LANGUAGE plpgsql;

-- Add helpful comment
COMMENT ON FUNCTION get_district_analytics IS 
'Admin analytics: Aggregated district-level metrics including issue counts, severity breakdown, resolution rates, and authority contact status. Optimized with CTEs and LEFT JOINs to include districts with zero issues. Supports date range filtering and dynamic sorting.';

-- ================================================
-- PERFORMANCE INDEXES (if not already present)
-- ================================================
-- These indexes are critical for fast aggregation queries

-- Already created in district_routing_tables.sql but included here for completeness:
-- CREATE INDEX IF NOT EXISTS idx_issues_district_id ON issues(district_id);
-- CREATE INDEX IF NOT EXISTS idx_issues_status ON issues(status);
-- CREATE INDEX IF NOT EXISTS idx_issues_reported_at ON issues(reported_at DESC);
-- CREATE INDEX IF NOT EXISTS idx_issues_resolved_at ON issues(resolved_at);
-- CREATE INDEX IF NOT EXISTS idx_issues_verified_district_id ON issues_verified(district_id);

-- Composite index for analytics performance
CREATE INDEX IF NOT EXISTS idx_issues_analytics 
    ON issues(district_id, status, reported_at DESC) 
    WHERE district_id IS NOT NULL;

-- Index for join performance
CREATE INDEX IF NOT EXISTS idx_issues_verified_original_issue 
    ON issues_verified(original_issue_id);

-- ================================================
-- USAGE EXAMPLES
-- ================================================

-- Get all district analytics (default: sorted by unresolved count DESC)
-- SELECT * FROM get_district_analytics(NULL, NOW(), 'unresolved_count', 'DESC');

-- Get district analytics for last 30 days, sorted by high severity
-- SELECT * FROM get_district_analytics(NOW() - INTERVAL '30 days', NOW(), 'high_severity_count', 'DESC');

-- Get district analytics for specific date range
-- SELECT * FROM get_district_analytics('2026-01-01'::TIMESTAMP, '2026-01-31'::TIMESTAMP, 'total_issues', 'DESC');

-- Get districts with highest unresolved rates
-- SELECT * FROM get_district_analytics(NULL, NOW(), 'unresolved_count', 'DESC') LIMIT 50;

-- ================================================
-- NOTES FOR ADMIN CONSOLE FRONTEND
-- ================================================
-- 
-- 1. UNRESOLVED LOGIC:
--    An issue is considered "unresolved" if:
--    - status NOT IN ('resolved', 'closed', 'completed')
--    - AND resolved_at IS NULL
--
-- 2. VERIFIED ISSUES:
--    Only issues that have passed AI verification (exist in issues_verified table)
--
-- 3. SEVERITY COUNTS:
--    Derived from issues_verified.severity (low/moderate/high)
--    These represent AI-assessed severity, not user-reported
--
-- 4. AUTHORITY CONTACT STATUS:
--    - 'configured': Has active email and is_active = true
--    - 'inactive': Authority exists but is_active = false
--    - 'missing': No authority record OR email is NULL
--    - 'unknown': No data available
--
-- 5. DISTRICTS WITH ZERO ISSUES:
--    Will still appear in results with all counts = 0
--    This is intentional for comprehensive district monitoring
--
-- 6. PERFORMANCE:
--    Function uses CTEs with LEFT JOINs - optimized for ~750 districts
--    Expected query time: 100-500ms depending on data volume
--    All critical columns are indexed for fast aggregation
--
-- ================================================
