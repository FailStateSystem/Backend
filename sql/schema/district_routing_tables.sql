-- ================================================
-- DISTRICT ROUTING TABLES AND SPATIAL INDEXES
-- ================================================
-- Prerequisites: PostGIS must be enabled (run ENABLE_POSTGIS.sql first)
-- ================================================

-- ================================================
-- 1. DISTRICT BOUNDARIES TABLE (Spatial)
-- ================================================
CREATE TABLE IF NOT EXISTS district_boundaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    district_name VARCHAR(255) NOT NULL,
    state_name VARCHAR(255),
    geometry GEOMETRY(MULTIPOLYGON, 4326) NOT NULL, -- WGS84 coordinate system
    centroid GEOMETRY(POINT, 4326), -- Precomputed for fallback distance calculations
    source VARCHAR(100) DEFAULT 'geoBoundaries ADM2',
    source_version VARCHAR(50) DEFAULT 'v5.0',
    shape_id VARCHAR(255), -- Original shapeID from geoBoundaries
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create spatial index for fast point-in-polygon queries (CRITICAL for performance)
CREATE INDEX IF NOT EXISTS idx_district_boundaries_geometry 
    ON district_boundaries USING GIST(geometry);

-- Create spatial index for centroid (used in fallback distance calculations)
CREATE INDEX IF NOT EXISTS idx_district_boundaries_centroid 
    ON district_boundaries USING GIST(centroid);

-- Create regular indexes for filtering
CREATE INDEX IF NOT EXISTS idx_district_boundaries_district_name 
    ON district_boundaries(district_name);

CREATE INDEX IF NOT EXISTS idx_district_boundaries_state_name 
    ON district_boundaries(state_name);

COMMENT ON TABLE district_boundaries IS 'Administrative district boundaries (ADM2 level) from geoBoundaries dataset. Used for point-in-polygon mapping of civic issues to districts.';

-- ================================================
-- 2. DISTRICT AUTHORITIES TABLE
-- ================================================
CREATE TABLE IF NOT EXISTS district_authorities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    district_id UUID NOT NULL REFERENCES district_boundaries(id) ON DELETE CASCADE,
    dm_office_email VARCHAR(255), -- Primary email for District Magistrate office
    fallback_email VARCHAR(255), -- Fallback if primary fails
    authority_name VARCHAR(255), -- e.g., "District Magistrate Office"
    phone_number VARCHAR(50),
    office_address TEXT,
    last_verified TIMESTAMP WITH TIME ZONE, -- When was this contact last verified as valid?
    confidence_score DECIMAL(3, 2) DEFAULT 0.50, -- 0.0 to 1.0 (how confident are we in this contact?)
    notes TEXT, -- Admin notes
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(district_id) -- One authority entry per district
);

CREATE INDEX IF NOT EXISTS idx_district_authorities_district_id 
    ON district_authorities(district_id);

CREATE INDEX IF NOT EXISTS idx_district_authorities_is_active 
    ON district_authorities(is_active);

COMMENT ON TABLE district_authorities IS 'Contact information for district authorities (DM offices). Maps district boundaries to responsible government officials for issue escalation.';

-- ================================================
-- 3. ADD DISTRICT ROUTING COLUMNS TO ISSUES
-- ================================================
ALTER TABLE issues
ADD COLUMN IF NOT EXISTS district_id UUID REFERENCES district_boundaries(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS district_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS state_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS routing_status VARCHAR(50) DEFAULT 'pending',
ADD COLUMN IF NOT EXISTS routing_method VARCHAR(50), -- 'point_in_polygon' or 'fallback_nearest'
ADD COLUMN IF NOT EXISTS routed_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS dm_notification_sent BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS dm_notification_sent_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX IF NOT EXISTS idx_issues_district_id ON issues(district_id);
CREATE INDEX IF NOT EXISTS idx_issues_routing_status ON issues(routing_status);
CREATE INDEX IF NOT EXISTS idx_issues_dm_notification_sent ON issues(dm_notification_sent);

COMMENT ON COLUMN issues.district_id IS 'Mapped district boundary ID (spatial lookup)';
COMMENT ON COLUMN issues.routing_status IS 'Routing state: pending, routed, notification_sent, failed';
COMMENT ON COLUMN issues.routing_method IS 'How was district determined: point_in_polygon (exact) or fallback_nearest (approximation)';

-- ================================================
-- 4. ADD DISTRICT ROUTING COLUMNS TO ISSUES_VERIFIED
-- ================================================
ALTER TABLE issues_verified
ADD COLUMN IF NOT EXISTS district_id UUID REFERENCES district_boundaries(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS district_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS state_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS routing_status VARCHAR(50) DEFAULT 'pending',
ADD COLUMN IF NOT EXISTS routing_method VARCHAR(50),
ADD COLUMN IF NOT EXISTS routed_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS dm_notification_sent BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS dm_notification_sent_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX IF NOT EXISTS idx_issues_verified_district_id ON issues_verified(district_id);
CREATE INDEX IF NOT EXISTS idx_issues_verified_routing_status ON issues_verified(routing_status);

-- ================================================
-- 5. DISTRICT ROUTING LOG (Observability)
-- ================================================
CREATE TABLE IF NOT EXISTS district_routing_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_id UUID REFERENCES issues(id) ON DELETE SET NULL,
    original_issue_id UUID, -- For issues_verified table
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    district_id UUID REFERENCES district_boundaries(id) ON DELETE SET NULL,
    district_name VARCHAR(255),
    state_name VARCHAR(255),
    routing_method VARCHAR(50) NOT NULL, -- 'point_in_polygon', 'fallback_nearest', 'manual_override'
    fallback_used BOOLEAN DEFAULT FALSE,
    fallback_distance_km DECIMAL(10, 2), -- Distance to nearest district if fallback used
    confidence_score DECIMAL(3, 2), -- How confident are we in this routing?
    error_message TEXT, -- If routing failed
    processing_time_ms INTEGER, -- How long did the lookup take?
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_district_routing_log_issue_id ON district_routing_log(issue_id);
CREATE INDEX IF NOT EXISTS idx_district_routing_log_district_id ON district_routing_log(district_id);
CREATE INDEX IF NOT EXISTS idx_district_routing_log_fallback_used ON district_routing_log(fallback_used);
CREATE INDEX IF NOT EXISTS idx_district_routing_log_created_at ON district_routing_log(created_at DESC);

COMMENT ON TABLE district_routing_log IS 'Observability log for district routing. Tracks all point-in-polygon lookups, fallbacks, and errors.';

-- ================================================
-- 6. DM NOTIFICATION QUEUE (Severity-based dispatch)
-- ================================================
CREATE TABLE IF NOT EXISTS dm_notification_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_id UUID, -- Can be from issues or issues_verified
    original_issue_id UUID, -- For verified issues
    district_id UUID NOT NULL REFERENCES district_boundaries(id) ON DELETE CASCADE,
    authority_id UUID NOT NULL REFERENCES district_authorities(id) ON DELETE CASCADE,
    severity VARCHAR(20) NOT NULL, -- 'high', 'moderate', 'low'
    dispatch_priority VARCHAR(20) NOT NULL, -- 'instant', 'daily_batch', 'weekly_batch'
    scheduled_for TIMESTAMP WITH TIME ZONE NOT NULL, -- When should this be sent?
    status VARCHAR(50) DEFAULT 'queued', -- 'queued', 'sent', 'failed', 'cancelled'
    sent_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dm_notification_queue_status ON dm_notification_queue(status);
CREATE INDEX IF NOT EXISTS idx_dm_notification_queue_scheduled_for ON dm_notification_queue(scheduled_for);
CREATE INDEX IF NOT EXISTS idx_dm_notification_queue_district_id ON dm_notification_queue(district_id);
CREATE INDEX IF NOT EXISTS idx_dm_notification_queue_severity ON dm_notification_queue(severity);

COMMENT ON TABLE dm_notification_queue IS 'Queue for sending notifications to DM offices. Supports severity-based dispatch scheduling.';

-- ================================================
-- 7. POINT-IN-POLYGON LOOKUP FUNCTION
-- ================================================
CREATE OR REPLACE FUNCTION find_district_by_point(
    p_latitude DECIMAL,
    p_longitude DECIMAL
)
RETURNS TABLE(
    district_id UUID,
    district_name VARCHAR(255),
    state_name VARCHAR(255),
    routing_method VARCHAR(50),
    fallback_used BOOLEAN,
    fallback_distance_km DECIMAL(10, 2),
    confidence_score DECIMAL(3, 2)
) AS $$
DECLARE
    v_point GEOMETRY;
    v_found BOOLEAN := FALSE;
BEGIN
    -- Create point geometry from lat/lng (SRID 4326 = WGS84)
    v_point := ST_SetSRID(ST_MakePoint(p_longitude, p_latitude), 4326);
    
    -- Try exact point-in-polygon match
    RETURN QUERY
    SELECT 
        db.id,
        db.district_name,
        db.state_name,
        'point_in_polygon'::VARCHAR(50),
        FALSE,
        NULL::DECIMAL(10, 2),
        1.00::DECIMAL(3, 2)
    FROM district_boundaries db
    WHERE ST_Contains(db.geometry, v_point)
    LIMIT 1;
    
    -- Check if we found a match
    GET DIAGNOSTICS v_found = ROW_COUNT;
    
    -- If no exact match, use fallback: find nearest district by centroid distance
    IF NOT v_found THEN
        RETURN QUERY
        SELECT 
            db.id,
            db.district_name,
            db.state_name,
            'fallback_nearest'::VARCHAR(50),
            TRUE,
            (ST_Distance(db.centroid::geography, v_point::geography) / 1000)::DECIMAL(10, 2), -- Convert meters to km
            0.60::DECIMAL(3, 2) -- Lower confidence for fallback
        FROM district_boundaries db
        WHERE db.centroid IS NOT NULL
        ORDER BY db.centroid <-> v_point -- <-> is distance operator (fast with GIST index)
        LIMIT 1;
    END IF;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION find_district_by_point IS 'Spatial lookup: finds district containing a lat/lng point. Uses exact point-in-polygon first, falls back to nearest district if no match.';

-- ================================================
-- 8. TRIGGER TO AUTO-COMPUTE CENTROIDS
-- ================================================
CREATE OR REPLACE FUNCTION compute_centroid()
RETURNS TRIGGER AS $$
BEGIN
    NEW.centroid := ST_Centroid(NEW.geometry);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_compute_centroid
BEFORE INSERT OR UPDATE OF geometry ON district_boundaries
FOR EACH ROW
EXECUTE FUNCTION compute_centroid();

COMMENT ON FUNCTION compute_centroid IS 'Auto-computes district centroid when geometry is inserted/updated. Used for fallback distance calculations.';

-- ================================================
-- 9. HELPER FUNCTION: Queue DM Notification
-- ================================================
CREATE OR REPLACE FUNCTION queue_dm_notification(
    p_issue_id UUID,
    p_original_issue_id UUID,
    p_district_id UUID,
    p_severity VARCHAR(20)
)
RETURNS UUID AS $$
DECLARE
    v_authority_id UUID;
    v_dispatch_priority VARCHAR(20);
    v_scheduled_for TIMESTAMP WITH TIME ZONE;
    v_queue_id UUID;
BEGIN
    -- Find district authority
    SELECT id INTO v_authority_id
    FROM district_authorities
    WHERE district_id = p_district_id AND is_active = TRUE
    LIMIT 1;
    
    -- If no authority found, skip queue
    IF v_authority_id IS NULL THEN
        RAISE NOTICE 'No active authority found for district %', p_district_id;
        RETURN NULL;
    END IF;
    
    -- Determine dispatch priority and schedule based on severity
    CASE p_severity
        WHEN 'high' THEN
            v_dispatch_priority := 'instant';
            v_scheduled_for := NOW();
        WHEN 'moderate', 'medium' THEN
            v_dispatch_priority := 'daily_batch';
            v_scheduled_for := DATE_TRUNC('day', NOW()) + INTERVAL '18 hours'; -- Next 6 PM
        ELSE
            v_dispatch_priority := 'weekly_batch';
            v_scheduled_for := DATE_TRUNC('week', NOW()) + INTERVAL '7 days'; -- Next Monday
    END CASE;
    
    -- Insert into queue
    INSERT INTO dm_notification_queue (
        issue_id,
        original_issue_id,
        district_id,
        authority_id,
        severity,
        dispatch_priority,
        scheduled_for
    ) VALUES (
        p_issue_id,
        p_original_issue_id,
        p_district_id,
        p_severity,
        v_dispatch_priority,
        v_scheduled_for
    )
    RETURNING id INTO v_queue_id;
    
    RETURN v_queue_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION queue_dm_notification IS 'Queues a notification to district authority based on issue severity. High = instant, Moderate = daily batch, Low = weekly batch.';

-- ================================================
-- 10. VIEW: District Authority Summary
-- ================================================
CREATE OR REPLACE VIEW district_authority_summary AS
SELECT 
    db.id AS district_id,
    db.district_name,
    db.state_name,
    da.dm_office_email,
    da.authority_name,
    da.is_active,
    da.confidence_score,
    COUNT(DISTINCT i.id) AS total_issues_routed,
    COUNT(DISTINCT CASE WHEN i.dm_notification_sent THEN i.id END) AS issues_with_notifications,
    MAX(i.routed_at) AS last_issue_routed_at
FROM district_boundaries db
LEFT JOIN district_authorities da ON db.id = da.district_id
LEFT JOIN issues i ON db.id = i.district_id
GROUP BY db.id, db.district_name, db.state_name, da.dm_office_email, da.authority_name, da.is_active, da.confidence_score
ORDER BY total_issues_routed DESC;

COMMENT ON VIEW district_authority_summary IS 'Admin view: Summary of district routing status and authority contacts';

-- ================================================
-- 11. VIEW: Routing Statistics
-- ================================================
CREATE OR REPLACE VIEW routing_statistics AS
SELECT 
    COUNT(*) AS total_routed,
    COUNT(CASE WHEN routing_method = 'point_in_polygon' THEN 1 END) AS exact_matches,
    COUNT(CASE WHEN routing_method = 'fallback_nearest' THEN 1 END) AS fallback_matches,
    ROUND(AVG(CASE WHEN fallback_used THEN fallback_distance_km END)::NUMERIC, 2) AS avg_fallback_distance_km,
    MAX(fallback_distance_km) AS max_fallback_distance_km
FROM district_routing_log
WHERE created_at > NOW() - INTERVAL '30 days';

COMMENT ON VIEW routing_statistics IS 'Real-time stats: Routing accuracy and fallback usage (last 30 days)';

-- ================================================
-- 12. CLEANUP FUNCTION (Optional)
-- ================================================
CREATE OR REPLACE FUNCTION cleanup_old_routing_logs()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Delete routing logs older than 90 days
    DELETE FROM district_routing_log WHERE created_at < NOW() - INTERVAL '90 days';
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_old_routing_logs IS 'Maintenance: Deletes routing logs older than 90 days to prevent table bloat';

-- ================================================
-- COMPLETED
-- ================================================
-- District routing tables are now created
-- Next step: Run the GeoJSON ingestion script to populate district_boundaries
-- Then configure district_authorities with DM office emails

