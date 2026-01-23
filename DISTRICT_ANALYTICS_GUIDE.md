# District Analytics Endpoint - Implementation Guide

## Overview

The district analytics endpoint provides **aggregated, district-level metrics** for the admin console, enabling:

- **District heatmaps** showing failure hotspots
- **Failure rankings** by unresolved count or severity  
- **Escalation prioritization** for authority contacts
- **Performance monitoring** across ~750 districts

This is a **systems analytics endpoint** built for operational insights, not vanity metrics.

---

## Endpoint Details

### **GET /admin/analytics/districts**

**Authentication:** Admin token required  
**Method:** GET  
**Base URL:** `https://api.failstate.in/admin/analytics/districts`

---

## Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `from_date` | ISO datetime | `null` | Filter issues after this date (optional) |
| `to_date` | ISO datetime | `NOW()` | Filter issues before this date |
| `sort_by` | string | `unresolved_count` | Sort field: `unresolved_count`, `high_severity_count`, `total_issues`, `district_name` |
| `sort_order` | string | `DESC` | Sort order: `ASC` or `DESC` |

**Date format examples:**
- `2026-01-01` (date only)
- `2026-01-23T10:30:00Z` (full ISO timestamp)
- `2026-01-23T10:30:00+05:30` (with timezone)

---

## Response Structure

```json
{
  "districts": [
    {
      "district_id": "a1b2c3d4-...",
      "district_name": "Mumbai",
      "state_name": "Maharashtra",
      "total_issues": 150,
      "verified_issues": 140,
      "unresolved_issues": 75,
      "high_severity_count": 20,
      "moderate_severity_count": 35,
      "low_severity_count": 20,
      "oldest_unresolved_issue_age_days": 45,
      "percentage_unresolved": 50.00,
      "last_issue_reported_at": "2026-01-23T10:30:00Z",
      "authority_contact_status": "configured"
    },
    ...
  ],
  "metadata": {
    "total_districts": 750,
    "districts_with_issues": 523,
    "date_range": {
      "from": "2025-01-01T00:00:00Z",
      "to": "2026-01-23T23:59:59Z"
    },
    "sort": {
      "by": "unresolved_count",
      "order": "DESC"
    }
  },
  "summary": {
    "total_issues_all_districts": 12500,
    "total_unresolved_all_districts": 6200,
    "districts_with_configured_authority": 450,
    "districts_with_missing_authority": 300
  }
}
```

---

## Field Definitions

### District Object Fields

| Field | Type | Description |
|-------|------|-------------|
| `district_id` | UUID | Unique district identifier |
| `district_name` | string | District name (e.g., "Mumbai") |
| `state_name` | string | State/province name |
| `total_issues` | integer | Total issues reported in this district |
| `verified_issues` | integer | Issues that passed AI verification |
| `unresolved_issues` | integer | Issues NOT marked resolved (status ≠ resolved/closed/completed) |
| `high_severity_count` | integer | Count of AI-verified high severity issues |
| `moderate_severity_count` | integer | Count of AI-verified moderate severity issues |
| `low_severity_count` | integer | Count of AI-verified low severity issues |
| `oldest_unresolved_issue_age_days` | integer | Days since oldest unresolved issue was reported (null if none) |
| `percentage_unresolved` | decimal | (unresolved / total) * 100 |
| `last_issue_reported_at` | ISO datetime | Timestamp of most recent issue (null if no issues) |
| `authority_contact_status` | enum | `configured` / `inactive` / `missing` / `unknown` |

### Authority Contact Status Values

| Value | Meaning |
|-------|---------|
| `configured` | Has active email, `is_active=true` ✅ |
| `inactive` | Authority exists but `is_active=false` ⚠️ |
| `missing` | No authority record OR email is NULL ❌ |
| `unknown` | No data available |

---

## Usage Examples

### 1. Get All District Analytics (Default Sorting)

```bash
curl -X GET "https://api.failstate.in/admin/analytics/districts" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

**Returns:** All districts sorted by `unresolved_count DESC` (most failing districts first)

---

### 2. Get Districts Sorted by High Severity Count

```bash
curl -X GET "https://api.failstate.in/admin/analytics/districts?sort_by=high_severity_count&sort_order=DESC" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

**Use case:** Identify districts with the most critical infrastructure failures

---

### 3. Get Analytics for Last 30 Days

```bash
curl -X GET "https://api.failstate.in/admin/analytics/districts?from_date=2026-01-01&to_date=2026-01-31" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

**Use case:** Monthly performance review

---

### 4. Get Districts with Most Total Issues

```bash
curl -X GET "https://api.failstate.in/admin/analytics/districts?sort_by=total_issues&sort_order=DESC" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

**Use case:** Find districts with highest reporting activity

---

### 5. Get Districts Alphabetically

```bash
curl -X GET "https://api.failstate.in/admin/analytics/districts?sort_by=district_name&sort_order=ASC" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

**Use case:** Browse districts systematically

---

## Analytics Logic

### "Unresolved" Definition

An issue is considered **unresolved** if ALL of the following are true:
- `status` NOT IN (`'resolved'`, `'closed'`, `'completed'`)
- `resolved_at` IS NULL

This captures issues that are:
- Pending verification
- Awaiting authority contact
- In progress but not completed

### Severity Counts

Severity counts are derived from the **`issues_verified`** table:
- Only AI-verified issues have severity ratings
- Severity is AI-assessed, not user-reported
- Values: `low`, `moderate`, `high`

### Districts with Zero Issues

Districts with **no reported issues** still appear in results with:
- All counts = 0
- `oldest_unresolved_issue_age_days` = NULL
- `last_issue_reported_at` = NULL
- `percentage_unresolved` = 0.00

This is intentional for comprehensive monitoring.

---

## Performance

### Query Optimization

- **Execution time:** 100-500ms for ~750 districts
- **Strategy:** SQL aggregation with CTEs and LEFT JOINs
- **No N+1 queries:** Single RPC call to database function
- **Indexed columns:** `district_id`, `status`, `reported_at`, `severity`

### Critical Indexes

These indexes are auto-created by the SQL setup script:

```sql
-- Core indexes
idx_issues_district_id
idx_issues_status
idx_issues_reported_at
idx_issues_verified_district_id

-- Analytics composite index
idx_issues_analytics (district_id, status, reported_at DESC)
```

---

## Database Setup

### 1. Run the SQL Function

Execute the SQL function that powers this endpoint:

```bash
psql -d your_database -f sql/admin/district_analytics_function.sql
```

Or in **Supabase SQL Editor:**
1. Open SQL Editor
2. Copy contents of `sql/admin/district_analytics_function.sql`
3. Execute

### 2. Verify Function Exists

```sql
SELECT routine_name 
FROM information_schema.routines 
WHERE routine_name = 'get_district_analytics';
```

Should return: `get_district_analytics`

### 3. Test Function Directly

```sql
SELECT * FROM get_district_analytics(NULL, NOW(), 'unresolved_count', 'DESC');
```

---

## Frontend Integration Recommendations

### District Heatmap

```javascript
// Fetch districts sorted by unresolved count
const response = await fetch('/admin/analytics/districts?sort_by=unresolved_count&sort_order=DESC');
const { districts } = await response.json();

// Color districts by unresolved percentage
districts.forEach(district => {
  const color = district.percentage_unresolved > 75 ? 'red' :
                district.percentage_unresolved > 50 ? 'orange' :
                district.percentage_unresolved > 25 ? 'yellow' : 'green';
  
  // Apply color to map polygon
  mapLayer.setFillColor(district.district_id, color);
});
```

### Failure Rankings Table

```javascript
// Get top 50 failing districts
const response = await fetch('/admin/analytics/districts?sort_by=unresolved_count&sort_order=DESC');
const { districts } = await response.json();

// Display top 50
const top50 = districts.slice(0, 50);
renderTable(top50);
```

### Escalation Priority Queue

```javascript
// Get districts with high severity issues and missing authority contacts
const response = await fetch('/admin/analytics/districts?sort_by=high_severity_count&sort_order=DESC');
const { districts } = await response.json();

// Filter for escalation
const needsEscalation = districts.filter(d => 
  d.high_severity_count > 0 && 
  d.authority_contact_status === 'missing'
);

renderEscalationQueue(needsEscalation);
```

---

## Error Handling

### 400 Bad Request

**Invalid date format:**
```json
{
  "detail": "Invalid from_date format. Use ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ"
}
```

**Invalid sort field:**
```json
{
  "detail": "Invalid sort_by. Must be one of: unresolved_count, high_severity_count, total_issues, district_name"
}
```

### 401 Unauthorized

```json
{
  "detail": "Invalid or expired admin token"
}
```

### 500 Internal Server Error

```json
{
  "detail": "Failed to retrieve district analytics: [error details]"
}
```

---

## System Requirements

### Database Function

**Required:** `get_district_analytics()` function must exist in database  
**Source:** `sql/admin/district_analytics_function.sql`

### Tables Required

1. `district_boundaries` - District geometry and metadata
2. `district_authorities` - Authority contact information
3. `issues` - All reported issues (with district mapping)
4. `issues_verified` - AI-verified issues (with severity)

### Indexes Required

All critical indexes are auto-created by setup scripts.

---

## Testing

### 1. Test Endpoint Availability

```bash
curl -X GET "https://api.failstate.in/admin/analytics/districts" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -w "\nHTTP Status: %{http_code}\n"
```

**Expected:** HTTP 200 with JSON response

### 2. Test Date Filtering

```bash
curl -X GET "https://api.failstate.in/admin/analytics/districts?from_date=2026-01-01&to_date=2026-01-31" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Expected:** Only issues within date range

### 3. Test Sorting

```bash
# Sort by unresolved DESC
curl -X GET "https://api.failstate.in/admin/analytics/districts?sort_by=unresolved_count&sort_order=DESC" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Verify first district has highest unresolved count
```

### 4. Test Empty Districts

```bash
# Get all districts
curl -X GET "https://api.failstate.in/admin/analytics/districts" \
  -H "Authorization: Bearer YOUR_TOKEN" | jq '.districts[] | select(.total_issues == 0)'
```

**Expected:** Districts with all counts = 0 still appear

---

## Monitoring & Observability

### Key Metrics to Track

1. **Response time:** Should be < 500ms for 750 districts
2. **Districts with missing authorities:** Monitor `.summary.districts_with_missing_authority`
3. **Unresolved rate:** Track `.summary.total_unresolved_all_districts / total_issues`
4. **Date range usage:** Log which date ranges are most queried

### Database Query Performance

```sql
-- Check query execution time
EXPLAIN ANALYZE 
SELECT * FROM get_district_analytics(NULL, NOW(), 'unresolved_count', 'DESC');
```

**Target:** < 300ms execution time

---

## Changelog

**2026-01-23:** Initial implementation
- Added `GET /admin/analytics/districts` endpoint
- Created `get_district_analytics()` SQL function
- Added composite indexes for performance
- Supports date filtering and dynamic sorting

---

## Support

For issues or questions:
- **Endpoint errors:** Check admin logs in Render
- **SQL function errors:** Check Supabase logs
- **Performance issues:** Run `EXPLAIN ANALYZE` on SQL function

---

**Built for systems-level operational analytics** 📊
