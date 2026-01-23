-- ================================================
-- ENABLE POSTGIS EXTENSION FOR GEOSPATIAL SUPPORT
-- ================================================
-- Run this in your Supabase SQL Editor FIRST
-- PostGIS adds spatial functions like ST_Contains, ST_Distance, etc.
-- ================================================

-- Enable PostGIS extension (includes geometry types and spatial functions)
CREATE EXTENSION IF NOT EXISTS postgis;

-- Verify PostGIS is enabled
SELECT PostGIS_Version();

-- ================================================
-- COMPLETED
-- ================================================
-- PostGIS is now enabled in your database
-- You can now create spatial tables with GEOMETRY columns
-- and use spatial functions for point-in-polygon queries

