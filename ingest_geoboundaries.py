#!/usr/bin/env python3
"""
GeoJSON Ingestion Script - geoBoundaries ADM2 (India Districts)
================================================================
ONE-TIME JOB: Loads district boundaries from GeoJSON into PostGIS database

Prerequisites:
1. PostGIS enabled (run ENABLE_POSTGIS.sql)
2. district_boundaries table created (run CREATE_DISTRICT_ROUTING_TABLES.sql)
3. geoBoundaries-IND-ADM2_simplified.geojson in parent directory

Usage:
    python3 ingest_geoboundaries.py

Environment:
    Requires SUPABASE_URL and SUPABASE_KEY from .env file
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client
import logging
from typing import Dict, List, Any
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Path to GeoJSON file (parent directory)
GEOJSON_FILE = Path(__file__).parent.parent / 'geoBoundaries-IND-ADM2_simplified.geojson'


def connect_supabase() -> Client:
    """Connect to Supabase"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("SUPABASE_URL and SUPABASE_KEY must be set in .env")
        sys.exit(1)
    
    try:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("✅ Connected to Supabase")
        return client
    except Exception as e:
        logger.error(f"❌ Failed to connect to Supabase: {e}")
        sys.exit(1)


def load_geojson() -> Dict[str, Any]:
    """Load and parse GeoJSON file"""
    if not GEOJSON_FILE.exists():
        logger.error(f"❌ GeoJSON file not found: {GEOJSON_FILE}")
        sys.exit(1)
    
    try:
        with open(GEOJSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        feature_count = len(data.get('features', []))
        logger.info(f"✅ Loaded GeoJSON: {feature_count} features")
        return data
    except Exception as e:
        logger.error(f"❌ Failed to load GeoJSON: {e}")
        sys.exit(1)


def extract_state_from_district(district_name: str) -> str:
    """
    Extract state name from district name if possible.
    geoBoundaries ADM2 doesn't include state in properties,
    so we'll need to infer or leave blank for manual entry.
    
    For now, returning empty string - can be populated later via admin panel
    """
    # TODO: Implement state extraction logic if needed
    # Could use a district-to-state mapping file
    return ""


def convert_geometry_to_wkt(geometry: Dict[str, Any]) -> str:
    """
    Convert GeoJSON geometry to WKT (Well-Known Text) format for PostGIS
    
    Handles both Polygon and MultiPolygon types
    
    WKT Format:
    - MULTIPOLYGON(((x1 y1, x2 y2, x3 y3, x1 y1)), ((x1 y1, x2 y2, x3 y3, x1 y1)))
    """
    geom_type = geometry['type']
    coordinates = geometry['coordinates']
    
    if geom_type == 'Polygon':
        # Convert Polygon to MULTIPOLYGON (for consistency in DB)
        # Polygon coordinates: [[[lon, lat], [lon, lat], ...], ...]
        # First array is outer ring, rest are holes (inner rings)
        rings = []
        for ring in coordinates:
            points = ', '.join([f"{lon} {lat}" for lon, lat in ring])
            rings.append(f"({points})")
        # Join rings with commas (outer ring, hole1, hole2, ...)
        polygon_interior = ', '.join(rings)
        # Wrap in MULTIPOLYGON with correct nesting: MULTIPOLYGON(((ring1), (ring2)))
        return f"MULTIPOLYGON(({polygon_interior}))"
    
    elif geom_type == 'MultiPolygon':
        # Convert MultiPolygon to WKT
        # MultiPolygon coordinates: [[[[lon, lat], ...], ...], [[[lon, lat], ...], ...]]
        polygons = []
        for polygon in coordinates:
            rings = []
            for ring in polygon:
                points = ', '.join([f"{lon} {lat}" for lon, lat in ring])
                rings.append(f"({points})")
            # Join rings for this polygon
            polygon_interior = ', '.join(rings)
            polygons.append(f"({polygon_interior})")
        # Join all polygons
        multi_polygon_wkt = ', '.join(polygons)
        return f"MULTIPOLYGON({multi_polygon_wkt})"
    
    else:
        raise ValueError(f"Unsupported geometry type: {geom_type}")


def validate_polygon(coordinates: List) -> bool:
    """
    Validate polygon coordinates
    - Must have at least 4 points (3 vertices + closing point)
    - First and last point must be identical (closed ring)
    """
    if not coordinates or len(coordinates) == 0:
        return False
    
    # Check outer ring
    outer_ring = coordinates[0]
    if len(outer_ring) < 4:
        return False
    
    # Check if ring is closed
    if outer_ring[0] != outer_ring[-1]:
        logger.warning(f"Ring not closed: {outer_ring[0]} != {outer_ring[-1]}")
        return False
    
    return True


def ingest_districts(supabase: Client, geojson_data: Dict[str, Any]) -> None:
    """
    Ingest district boundaries from GeoJSON into database
    """
    features = geojson_data.get('features', [])
    total_features = len(features)
    
    logger.info(f"🚀 Starting ingestion of {total_features} districts...")
    
    success_count = 0
    error_count = 0
    skipped_count = 0
    
    for idx, feature in enumerate(features, 1):
        try:
            # Extract properties
            properties = feature.get('properties', {})
            district_name = properties.get('shapeName', '').strip()
            shape_id = properties.get('shapeID', '')
            
            # Skip if no district name
            if not district_name:
                logger.warning(f"⚠️ [{idx}/{total_features}] Skipping feature with no district name")
                skipped_count += 1
                continue
            
            # Extract geometry
            geometry = feature.get('geometry')
            if not geometry:
                logger.warning(f"⚠️ [{idx}/{total_features}] Skipping {district_name}: No geometry")
                skipped_count += 1
                continue
            
            # Validate geometry
            geom_type = geometry['type']
            coordinates = geometry['coordinates']
            
            if geom_type == 'Polygon':
                if not validate_polygon(coordinates):
                    logger.warning(f"⚠️ [{idx}/{total_features}] Skipping {district_name}: Invalid polygon")
                    skipped_count += 1
                    continue
            elif geom_type == 'MultiPolygon':
                # Validate each polygon in multipolygon
                valid = all(validate_polygon(poly) for poly in coordinates)
                if not valid:
                    logger.warning(f"⚠️ [{idx}/{total_features}] Skipping {district_name}: Invalid multipolygon")
                    skipped_count += 1
                    continue
            else:
                logger.warning(f"⚠️ [{idx}/{total_features}] Skipping {district_name}: Unsupported geometry type {geom_type}")
                skipped_count += 1
                continue
            
            # Convert geometry to WKT
            try:
                wkt = convert_geometry_to_wkt(geometry)
            except Exception as e:
                logger.error(f"❌ [{idx}/{total_features}] Failed to convert geometry for {district_name}: {e}")
                error_count += 1
                continue
            
            # Extract or infer state name
            state_name = extract_state_from_district(district_name)
            
            # Insert into database using raw SQL (PostGIS ST_GeomFromText)
            # We use RPC call to execute raw SQL
            try:
                result = supabase.rpc(
                    'insert_district_boundary',
                    {
                        'p_district_name': district_name,
                        'p_state_name': state_name if state_name else None,
                        'p_shape_id': shape_id,
                        'p_geometry_wkt': wkt
                    }
                ).execute()
                
                logger.info(f"✅ [{idx}/{total_features}] Inserted: {district_name}")
                success_count += 1
                
            except Exception as e:
                error_msg = str(e)
                
                # Check if it's a duplicate (unique constraint violation)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    logger.info(f"⏭️  [{idx}/{total_features}] Already exists: {district_name}")
                    skipped_count += 1
                else:
                    logger.error(f"❌ [{idx}/{total_features}] Failed to insert {district_name}: {error_msg}")
                    error_count += 1
            
            # Progress update every 50 records
            if idx % 50 == 0:
                logger.info(f"📊 Progress: {idx}/{total_features} processed ({success_count} success, {skipped_count} skipped, {error_count} errors)")
            
            # Small delay to avoid rate limiting
            time.sleep(0.05)
            
        except Exception as e:
            logger.error(f"❌ [{idx}/{total_features}] Unexpected error: {e}")
            error_count += 1
            continue
    
    # Final summary
    logger.info("=" * 60)
    logger.info("📊 INGESTION COMPLETE")
    logger.info(f"✅ Successfully inserted: {success_count}")
    logger.info(f"⏭️  Skipped (already exists or invalid): {skipped_count}")
    logger.info(f"❌ Errors: {error_count}")
    logger.info(f"📈 Total processed: {total_features}")
    logger.info("=" * 60)


def create_ingestion_function(supabase: Client) -> None:
    """
    Create the RPC function for inserting district boundaries
    This function will be called by the ingestion script
    """
    logger.info("🔧 Creating ingestion RPC function...")
    
    # SQL for creating the RPC function
    sql = """
    CREATE OR REPLACE FUNCTION insert_district_boundary(
        p_district_name VARCHAR,
        p_state_name VARCHAR,
        p_shape_id VARCHAR,
        p_geometry_wkt TEXT
    )
    RETURNS UUID AS $$
    DECLARE
        v_district_id UUID;
    BEGIN
        -- Insert district boundary with geometry from WKT
        INSERT INTO district_boundaries (
            district_name,
            state_name,
            shape_id,
            geometry
        ) VALUES (
            p_district_name,
            p_state_name,
            p_shape_id,
            ST_GeomFromText(p_geometry_wkt, 4326)::GEOMETRY(MULTIPOLYGON, 4326)
        )
        ON CONFLICT (shape_id) DO NOTHING
        RETURNING id INTO v_district_id;
        
        RETURN v_district_id;
    END;
    $$ LANGUAGE plpgsql;
    """
    
    # Execute SQL (requires SQL Editor or database admin access)
    # For Supabase, this needs to be run manually in SQL Editor
    logger.info("⚠️  The RPC function must be created manually in Supabase SQL Editor")
    logger.info("⚠️  Copy the SQL below and run it in your Supabase dashboard:")
    logger.info("=" * 60)
    print(sql)
    logger.info("=" * 60)
    input("Press Enter after you've run the SQL in Supabase SQL Editor...")


def check_prerequisites(supabase: Client) -> bool:
    """
    Check if all prerequisites are met before ingestion
    """
    logger.info("🔍 Checking prerequisites...")
    
    # Check if district_boundaries table exists
    try:
        result = supabase.table('district_boundaries').select('id').limit(1).execute()
        logger.info("✅ district_boundaries table exists")
    except Exception as e:
        logger.error(f"❌ district_boundaries table not found. Run CREATE_DISTRICT_ROUTING_TABLES.sql first")
        return False
    
    # Check if GeoJSON file exists
    if not GEOJSON_FILE.exists():
        logger.error(f"❌ GeoJSON file not found: {GEOJSON_FILE}")
        return False
    else:
        logger.info(f"✅ GeoJSON file found: {GEOJSON_FILE}")
    
    return True


def main():
    """Main ingestion workflow"""
    logger.info("=" * 60)
    logger.info("🌍 geoBoundaries ADM2 Ingestion Script")
    logger.info("=" * 60)
    
    # Connect to Supabase
    supabase = connect_supabase()
    
    # Check prerequisites
    if not check_prerequisites(supabase):
        logger.error("❌ Prerequisites not met. Exiting.")
        sys.exit(1)
    
    # Load GeoJSON
    geojson_data = load_geojson()
    
    # Create ingestion function (one-time setup)
    create_ingestion_function(supabase)
    
    # Confirm before starting ingestion
    confirmation = input("\n⚠️  Ready to ingest 735 districts into database. Continue? (yes/no): ")
    if confirmation.lower() != 'yes':
        logger.info("❌ Ingestion cancelled by user")
        sys.exit(0)
    
    # Start ingestion
    start_time = time.time()
    ingest_districts(supabase, geojson_data)
    elapsed_time = time.time() - start_time
    
    logger.info(f"⏱️  Total time: {elapsed_time:.2f} seconds")
    logger.info("✅ Ingestion script completed")


if __name__ == '__main__':
    main()

