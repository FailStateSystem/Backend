# Geospatial Routing - Quick Start Guide

## 5-Minute Setup

### Step 1: Enable PostGIS (1 minute)

Open Supabase SQL Editor → Paste → Run:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
SELECT PostGIS_Version();
```

### Step 2: Create Tables (2 minutes)

Copy entire contents of `CREATE_DISTRICT_ROUTING_TABLES.sql` → Paste in SQL Editor → Run

**Creates:**
- 4 tables
- 15+ indexes
- 3 functions
- 2 views

### Step 3: Add Unique Constraint (30 seconds)

```sql
ALTER TABLE district_boundaries
ADD CONSTRAINT unique_shape_id UNIQUE (shape_id);
```

### Step 4: Create Ingestion Function (30 seconds)

```sql
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
```

### Step 5: Ingest Districts (2 minutes)

**On your local machine:**

```bash
cd /Users/rananjay.s/Downloads/failstate-hotsing/failstate-backend
python3 ingest_geoboundaries.py
```

Type `yes` when prompted.

**Wait for:**
```
✅ Successfully inserted: 735
```

### Step 6: Deploy Backend (auto)

```bash
git add .
git commit -m "Add geospatial routing"
git push origin main
```

Render will auto-deploy in ~3 minutes.

### Step 7: Test (30 seconds)

```bash
# Test Delhi coordinates
curl "https://backend-13ck.onrender.com/api/districts/boundaries/search/point?lat=28.6139&lng=77.2090" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Expected:**
```json
{
  "district_name": "New Delhi",
  "routing_method": "point_in_polygon",
  "confidence_score": 1.00
}
```

---

## What Just Happened?

1. ✅ PostGIS enabled (spatial database)
2. ✅ 735 districts loaded with boundaries
3. ✅ Point-in-polygon lookup working
4. ✅ Auto-routing integrated with AI pipeline

**All verified issues now automatically:**
- Get mapped to district
- Queue DM notification (severity-based)
- Log routing decision

---

## Next Steps (Optional)

### Add District Authorities

**Option 1: Via API**

```bash
curl -X POST https://backend-13ck.onrender.com/api/districts/authorities \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "district_id": "GET_FROM_BOUNDARIES_API",
    "dm_office_email": "dm.district@nic.in",
    "authority_name": "District Magistrate Office",
    "confidence_score": 0.80
  }'
```

**Option 2: Bulk SQL**

```sql
-- Example: Add placeholder authorities for all districts
INSERT INTO district_authorities (district_id, dm_office_email, authority_name, confidence_score)
SELECT 
    id,
    LOWER(REPLACE(district_name, ' ', '.')) || '@nic.in',
    'DM Office - ' || district_name,
    0.50
FROM district_boundaries;
```

---

## Verify It's Working

### Check Routing Logs

```bash
curl "https://backend-13ck.onrender.com/api/districts/routing/logs?limit=10" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Check Routing Stats

```bash
curl "https://backend-13ck.onrender.com/api/districts/routing/stats" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Check Issues with Districts

```bash
curl "https://backend-13ck.onrender.com/api/issues" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

Look for `district_name` field in response.

---

## Troubleshooting

### "PostGIS not enabled"

Run in SQL Editor:
```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

### "Table district_boundaries does not exist"

Run `CREATE_DISTRICT_ROUTING_TABLES.sql` in SQL Editor.

### "Function insert_district_boundary does not exist"

Run Step 4 SQL in SQL Editor.

### "No districts found"

Run `python3 ingest_geoboundaries.py` again.

### "Routing not happening"

Check backend logs for errors. Ensure:
1. PostGIS enabled
2. Tables created
3. Districts ingested
4. Backend deployed

---

## Admin Panel URLs

- **List districts:** `/api/districts/boundaries`
- **List authorities:** `/api/districts/authorities`
- **Routing logs:** `/api/districts/routing/logs`
- **Routing stats:** `/api/districts/routing/stats`
- **Authority summary:** `/api/districts/authorities/summary`

---

## Done! 🎉

Your geospatial routing system is now live.

Every verified issue will automatically:
- ✅ Get mapped to a district
- ✅ Queue notification to DM office
- ✅ Log routing decision

**No code changes needed for existing APIs.**

See `GEOSPATIAL_ROUTING_COMPLETE.md` for full documentation.

