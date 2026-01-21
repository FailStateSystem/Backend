# Geospatial Routing - Deployment Checklist

## Pre-Deployment Checklist

### ✅ Files Ready
- [x] `ENABLE_POSTGIS.sql` created
- [x] `CREATE_DISTRICT_ROUTING_TABLES.sql` created
- [x] `ingest_geoboundaries.py` created
- [x] `app/district_routing.py` created
- [x] `app/routers/districts.py` created
- [x] `app/verification_worker.py` updated
- [x] `app/models.py` updated
- [x] `app/main.py` updated
- [x] Documentation complete

### ✅ Prerequisites
- [x] GeoJSON file available: `../geoBoundaries-IND-ADM2_simplified.geojson`
- [x] Supabase project active
- [x] Render.com deployment configured
- [x] `.env` file has `SUPABASE_URL` and `SUPABASE_KEY`

---

## Deployment Steps

### Step 1: Database Setup (Supabase)

#### 1.1 Enable PostGIS
- [ ] Open Supabase SQL Editor
- [ ] Copy contents of `ENABLE_POSTGIS.sql`
- [ ] Paste and execute
- [ ] Verify output: `PostGIS_Version()` returns version number

**Expected output:**
```
3.3.2 r21765
```

**Time:** 30 seconds

---

#### 1.2 Create Tables and Functions
- [ ] Copy entire contents of `CREATE_DISTRICT_ROUTING_TABLES.sql`
- [ ] Paste into Supabase SQL Editor
- [ ] Execute
- [ ] Verify no errors

**Expected output:**
```
Success. No rows returned
```

**Tables created:**
- district_boundaries
- district_authorities
- district_routing_log
- dm_notification_queue

**Time:** 1 minute

---

#### 1.3 Add Unique Constraint
- [ ] Run in SQL Editor:

```sql
ALTER TABLE district_boundaries
ADD CONSTRAINT unique_shape_id UNIQUE (shape_id);
```

**Expected output:**
```
Success. No rows returned
```

**Time:** 10 seconds

---

#### 1.4 Create Ingestion RPC Function
- [ ] Run in SQL Editor:

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

**Expected output:**
```
Success. No rows returned
```

**Time:** 30 seconds

---

#### 1.5 Verify Database Setup
- [ ] Run verification query:

```sql
-- Check tables exist
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('district_boundaries', 'district_authorities', 'district_routing_log', 'dm_notification_queue');

-- Check spatial indexes
SELECT indexname FROM pg_indexes
WHERE tablename = 'district_boundaries'
AND indexname LIKE 'idx_%';

-- Check functions
SELECT routine_name FROM information_schema.routines
WHERE routine_schema = 'public'
AND routine_name IN ('find_district_by_point', 'queue_dm_notification', 'insert_district_boundary');
```

**Expected:**
- 4 tables
- 3+ indexes
- 3 functions

**Time:** 30 seconds

---

### Step 2: Data Ingestion (Local Machine)

#### 2.1 Prepare Environment
- [ ] Open terminal
- [ ] Navigate to backend directory:

```bash
cd /Users/rananjay.s/Downloads/failstate-hotsing/failstate-backend
```

- [ ] Verify `.env` file has correct credentials:

```bash
grep SUPABASE .env
```

**Expected:**
```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJxxx...
```

**Time:** 30 seconds

---

#### 2.2 Run Ingestion Script
- [ ] Execute:

```bash
python3 ingest_geoboundaries.py
```

- [ ] When prompted, type `yes` and press Enter
- [ ] Wait for completion (~2 minutes)

**Expected output:**
```
✅ Connected to Supabase
✅ Loaded GeoJSON: 735 features
✅ district_boundaries table exists
✅ GeoJSON file found
⚠️  Ready to ingest 735 districts into database. Continue? (yes/no): yes
🚀 Starting ingestion of 735 districts...
✅ [1/735] Inserted: Ashoknagar
✅ [2/735] Inserted: Balaghat
...
📊 INGESTION COMPLETE
✅ Successfully inserted: 735
⏭️  Skipped: 0
❌ Errors: 0
⏱️  Total time: 120.45 seconds
```

**Time:** 2-3 minutes

---

#### 2.3 Verify Ingestion
- [ ] Run in Supabase SQL Editor:

```sql
-- Count districts
SELECT COUNT(*) FROM district_boundaries;

-- Sample districts
SELECT district_name, state_name, source FROM district_boundaries LIMIT 10;

-- Check centroids computed
SELECT COUNT(*) FROM district_boundaries WHERE centroid IS NULL;
```

**Expected:**
- Count: 735
- Sample: List of district names
- Null centroids: 0

**Time:** 30 seconds

---

### Step 3: Backend Deployment (Render.com)

#### 3.1 Commit Code
- [ ] Stage changes:

```bash
git add .
```

- [ ] Commit:

```bash
git commit -m "Add geospatial routing system

- Enable PostGIS for spatial queries
- Add district_boundaries and district_authorities tables
- Implement point-in-polygon lookup with fallback
- Integrate routing into AI verification pipeline
- Add admin API for district management
- Add observability logging
- 735 districts from geoBoundaries ADM2"
```

- [ ] Push:

```bash
git push origin main
```

**Time:** 1 minute

---

#### 3.2 Monitor Deployment
- [ ] Open Render dashboard: https://dashboard.render.com
- [ ] Navigate to your backend service
- [ ] Watch deployment logs
- [ ] Wait for "Build successful" and "Deploy live"

**Expected:**
```
==> Building...
==> Installing dependencies...
==> Build successful
==> Deploying...
==> Deploy live
```

**Time:** 3-5 minutes

---

#### 3.3 Verify Deployment
- [ ] Check health endpoint:

```bash
curl https://backend-13ck.onrender.com/health
```

**Expected:**
```json
{"status": "healthy"}
```

- [ ] Check API docs:

```bash
curl https://backend-13ck.onrender.com/docs
```

Should show new `/api/districts/*` endpoints.

**Time:** 1 minute

---

### Step 4: Testing

#### 4.1 Test Point-in-Polygon (Exact Match)
- [ ] Get JWT token (login via API)
- [ ] Test Delhi coordinates:

```bash
curl "https://backend-13ck.onrender.com/api/districts/boundaries/search/point?lat=28.6139&lng=77.2090" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Expected:**
```json
{
  "district_id": "UUID",
  "district_name": "New Delhi",
  "state_name": null,
  "routing_method": "point_in_polygon",
  "fallback_used": false,
  "fallback_distance_km": null,
  "confidence_score": 1.00
}
```

**Time:** 30 seconds

---

#### 4.2 Test Fallback (No Exact Match)
- [ ] Test ocean coordinates:

```bash
curl "https://backend-13ck.onrender.com/api/districts/boundaries/search/point?lat=18.0&lng=70.0" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Expected:**
```json
{
  "district_id": "UUID",
  "district_name": "Some District",
  "state_name": null,
  "routing_method": "fallback_nearest",
  "fallback_used": true,
  "fallback_distance_km": 123.45,
  "confidence_score": 0.60
}
```

**Time:** 30 seconds

---

#### 4.3 Test Admin API
- [ ] List districts:

```bash
curl "https://backend-13ck.onrender.com/api/districts/boundaries?limit=5" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Expected:** Array of 5 districts

**Time:** 30 seconds

---

#### 4.4 Test End-to-End Routing
- [ ] Submit a test issue via `/api/issues` with:
  - Valid image
  - Description
  - Location (lat/lng in India)
- [ ] Wait for AI verification (~30 seconds)
- [ ] Check issue via `/api/issues/my-issues`
- [ ] Verify `district_name` is populated

**Expected:** Issue has `district_name` field

**Time:** 2 minutes

---

#### 4.5 Test Routing Logs
- [ ] View routing logs:

```bash
curl "https://backend-13ck.onrender.com/api/districts/routing/logs?limit=10" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Expected:** Array of routing log entries

**Time:** 30 seconds

---

#### 4.6 Test Routing Statistics
- [ ] Get stats:

```bash
curl "https://backend-13ck.onrender.com/api/districts/routing/stats" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Expected:**
```json
{
  "total_routed": 1,
  "exact_matches": 1,
  "fallback_matches": 0,
  "avg_fallback_distance_km": null,
  "max_fallback_distance_km": null
}
```

**Time:** 30 seconds

---

### Step 5: Authority Configuration (Optional)

#### 5.1 Add Test Authority
- [ ] Create authority for Delhi:

```bash
curl -X POST "https://backend-13ck.onrender.com/api/districts/authorities" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "district_id": "GET_FROM_BOUNDARIES_API",
    "dm_office_email": "dm.delhi@nic.in",
    "authority_name": "District Magistrate Office - Delhi",
    "phone_number": "+91-11-XXXXXXXX",
    "office_address": "Delhi Secretariat",
    "confidence_score": 0.80,
    "notes": "Test authority"
  }'
```

**Expected:** Authority object with ID

**Time:** 1 minute

---

#### 5.2 Verify Authority
- [ ] List authorities:

```bash
curl "https://backend-13ck.onrender.com/api/districts/authorities?limit=10" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Expected:** Array with 1 authority

**Time:** 30 seconds

---

### Step 6: Monitoring Setup

#### 6.1 Verify Observability
- [ ] Check routing logs in Supabase:

```sql
SELECT * FROM district_routing_log
ORDER BY created_at DESC
LIMIT 10;
```

**Expected:** Recent routing decisions

**Time:** 1 minute

---

#### 6.2 Set Up Alerts (Optional)
- [ ] Create alert for routing failures:

```sql
-- Query to check for failures
SELECT COUNT(*) FROM district_routing_log
WHERE error_message IS NOT NULL
AND created_at > NOW() - INTERVAL '24 hours';
```

- [ ] Set up Supabase webhook or cron job to alert if count > 10

**Time:** 5 minutes (optional)

---

## Post-Deployment Verification

### ✅ Checklist

- [ ] PostGIS enabled
- [ ] 735 districts ingested
- [ ] Spatial indexes created
- [ ] RPC functions working
- [ ] Backend deployed successfully
- [ ] Point-in-polygon working
- [ ] Fallback working
- [ ] Admin API accessible
- [ ] Routing logs being created
- [ ] Statistics endpoint working
- [ ] End-to-end routing working (issue → AI → district)

---

## Rollback Plan (If Needed)

### If Database Issues

1. Drop tables:
```sql
DROP TABLE IF EXISTS dm_notification_queue CASCADE;
DROP TABLE IF EXISTS district_routing_log CASCADE;
DROP TABLE IF EXISTS district_authorities CASCADE;
DROP TABLE IF EXISTS district_boundaries CASCADE;
```

2. Drop functions:
```sql
DROP FUNCTION IF EXISTS find_district_by_point;
DROP FUNCTION IF EXISTS queue_dm_notification;
DROP FUNCTION IF EXISTS insert_district_boundary;
DROP FUNCTION IF EXISTS compute_centroid;
```

3. Disable PostGIS (optional):
```sql
DROP EXTENSION IF EXISTS postgis CASCADE;
```

### If Backend Issues

1. Revert code:
```bash
git revert HEAD
git push origin main
```

2. Render will auto-deploy previous version

---

## Success Criteria

✅ **Deployment successful if:**

1. ✅ PostGIS enabled (query returns version)
2. ✅ 735 districts in database
3. ✅ Point-in-polygon returns district for Delhi coordinates
4. ✅ Fallback returns nearest district for ocean coordinates
5. ✅ Admin API returns district list
6. ✅ Test issue gets routed to district
7. ✅ Routing logs show entries
8. ✅ Statistics endpoint returns data
9. ✅ No errors in backend logs
10. ✅ No errors in Supabase logs

---

## Troubleshooting

### Issue: "PostGIS not enabled"
**Solution:** Run `ENABLE_POSTGIS.sql` in SQL Editor

### Issue: "Table does not exist"
**Solution:** Run `CREATE_DISTRICT_ROUTING_TABLES.sql` in SQL Editor

### Issue: "Function does not exist"
**Solution:** Create RPC function (Step 1.4)

### Issue: "No districts found"
**Solution:** Run `ingest_geoboundaries.py` again

### Issue: "Ingestion fails"
**Solution:** Check `.env` has correct Supabase credentials

### Issue: "Backend not deploying"
**Solution:** Check Render logs for errors

### Issue: "Routing not happening"
**Solution:** Check backend logs, verify PostGIS enabled

### Issue: "API returns 404"
**Solution:** Verify backend deployed, check URL

---

## Next Steps After Deployment

### Immediate
1. Monitor routing logs for 24 hours
2. Check for any errors
3. Verify routing accuracy

### Short-term (1 week)
1. Add authorities for top 10 districts
2. Review fallback routes
3. Update documentation if needed

### Long-term (1 month)
1. Add authorities for all districts
2. Implement email notification worker
3. Build admin dashboard UI

---

## Deployment Completed ✅

**Date:** _______________

**Deployed by:** _______________

**Verification:**
- [ ] All tests passed
- [ ] No errors in logs
- [ ] Routing working end-to-end
- [ ] Documentation reviewed

**Notes:**
_______________________________________
_______________________________________
_______________________________________

---

**End of Deployment Checklist**

