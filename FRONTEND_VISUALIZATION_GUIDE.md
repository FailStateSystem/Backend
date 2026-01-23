# District Analytics - Frontend Visualization Guide

## Overview

This guide explains **how to use** the district analytics data for building visualizations in the admin console. No code provided - just data structure explanation and visualization patterns.

---

## API Call

**Endpoint:** `GET /admin/analytics/districts`

**Authentication:** Include admin token in Authorization header

**Query Parameters:**
- `from_date` - Start date (optional, ISO format)
- `to_date` - End date (default: now)
- `sort_by` - Field to sort by (default: `unresolved_count`)
- `sort_order` - ASC or DESC (default: DESC)

---

## Response Structure

The API returns 3 main sections:

### 1. **districts** (array)
The actual district data - one object per district

### 2. **metadata** (object)
Info about the query: total count, date range, sorting

### 3. **summary** (object)
Aggregate statistics across all districts

---

## Understanding the District Object

Each district in the `districts` array has these fields:

### Identity Fields
```
district_id: "a1b2c3d4-..." (UUID)
district_name: "Mumbai"
state_name: "Maharashtra"
```

**Use for:** Labels, unique identifiers for map polygons

---

### Issue Count Fields
```
total_issues: 150              (All issues ever reported)
verified_issues: 140           (Issues that passed AI check)
unresolved_issues: 75          (Issues NOT marked resolved)
```

**Key insight:** 
- `total_issues` = everything reported in this district
- `verified_issues` = subset that passed AI verification
- `unresolved_issues` = subset that needs action

**Use for:**
- Total issue volume (are they reporting a lot?)
- Verification success rate (how many pass AI?)
- Action backlog (how many need resolution?)

---

### Severity Fields
```
high_severity_count: 20        (Critical infrastructure failures)
moderate_severity_count: 35    (Medium priority issues)
low_severity_count: 20         (Minor issues)
```

**Important:** These counts are **only from verified issues** with AI-assessed severity

**Use for:**
- Prioritization (high severity = urgent)
- Risk assessment (many high severity = dangerous)
- Resource allocation (focus on high severity districts)

**Note:** Total of severity counts may be less than `verified_issues` because some verified issues might not have severity assigned yet.

---

### Time Fields
```
oldest_unresolved_issue_age_days: 45
last_issue_reported_at: "2026-01-23T10:30:00Z"
```

**oldest_unresolved_issue_age_days:**
- How many days since the oldest unresolved issue was reported
- NULL if no unresolved issues
- Use for: Finding neglected districts (age > 90 days = very bad)

**last_issue_reported_at:**
- Timestamp of most recent issue
- NULL if no issues ever
- Use for: Finding active vs dormant districts

---

### Calculated Fields
```
percentage_unresolved: 50.00   (Decimal, 0.00 to 100.00)
```

**Formula:** (unresolved_issues / total_issues) * 100

**Use for:**
- Performance metric (higher % = worse performance)
- Heatmap coloring (>75% red, 50-75% orange, etc.)
- Comparing districts fairly (normalized by issue volume)

---

### Authority Field
```
authority_contact_status: "configured" | "inactive" | "missing" | "unknown"
```

**Meanings:**
- `configured` = Has active DM office email ✅
- `inactive` = Authority exists but is_active=false ⚠️
- `missing` = No authority OR no email ❌
- `unknown` = No data

**Use for:**
- Escalation readiness (can we contact them?)
- Configuration gaps (which districts need setup?)
- Filtering (show only "missing" to fix)

---

## Metadata Section

```json
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
}
```

**Use for:**
- Displaying query context to user
- Showing "X of Y districts have issues"
- Confirming date filter was applied correctly

---

## Summary Section

```json
"summary": {
  "total_issues_all_districts": 12500,
  "total_unresolved_all_districts": 6200,
  "districts_with_configured_authority": 450,
  "districts_with_missing_authority": 300
}
```

**Use for:**
- Dashboard KPIs (big numbers at top)
- National-level statistics
- Progress tracking (authority configuration progress)

**Derived calculations:**
- Overall unresolved rate: `total_unresolved / total_issues * 100`
- Authority coverage: `configured / total_districts * 100`

---

## Visualization Patterns

### 1. DISTRICT HEATMAP (Geographic Visualization)

**Goal:** Color districts on a map to show failure hotspots

**Best field to use:** `percentage_unresolved`

**Why:** Normalized metric that's fair for all district sizes

**Color scheme:**
- 0-25% unresolved → Green (good performance)
- 25-50% unresolved → Yellow (moderate issues)
- 50-75% unresolved → Orange (poor performance)
- 75-100% unresolved → Red (critical failure)

**Alternative coloring:**
- By `high_severity_count` (urgency-based)
- By `unresolved_issues` (absolute volume)

**Data prep:**
1. Fetch: `GET /admin/analytics/districts`
2. For each district in response:
   - Get `district_id` (match to your map polygon)
   - Get `percentage_unresolved`
   - Calculate color based on percentage
   - Apply color to polygon on map

**Districts with 0 issues:**
- Will have `percentage_unresolved = 0.00`
- Color them green or grey (your choice)

**Tooltip on hover:**
Show:
- District name
- Total issues
- Unresolved count
- Percentage unresolved
- High severity count
- Authority status

---

### 2. FAILURE RANKINGS TABLE

**Goal:** List worst-performing districts in a table

**Query:** `?sort_by=unresolved_count&sort_order=DESC`

**Columns to display:**

| Rank | District | State | Total Issues | Unresolved | High Severity | % Unresolved | Authority Status |
|------|----------|-------|--------------|------------|---------------|--------------|------------------|
| 1 | Mumbai | Maharashtra | 150 | 75 | 20 | 50.00% | configured |
| 2 | Delhi | NCR | 200 | 90 | 15 | 45.00% | missing |

**Data mapping:**
- Rank: Your array index + 1
- District: `district_name`
- State: `state_name`
- Total Issues: `total_issues`
- Unresolved: `unresolved_issues`
- High Severity: `high_severity_count`
- % Unresolved: `percentage_unresolved` (format with "%")
- Authority Status: `authority_contact_status` (use icon/badge)

**Visual indicators:**
- Red badge if `authority_contact_status = "missing"`
- Red text if `percentage_unresolved > 75`
- Orange text if `percentage_unresolved > 50`

**Pagination:**
- Show top 50 by default
- Allow user to see more (but response includes all 750)

**Sorting:**
User should be able to re-sort by clicking column headers:
- Unresolved: Make new API call with `?sort_by=unresolved_count`
- High Severity: `?sort_by=high_severity_count`
- District Name: `?sort_by=district_name&sort_order=ASC`

---

### 3. ESCALATION PRIORITY QUEUE

**Goal:** Show districts that need immediate attention

**Query:** `?sort_by=high_severity_count&sort_order=DESC`

**Filter logic (do in frontend after receiving data):**

Priority 1 (CRITICAL):
- `high_severity_count > 5` AND
- `authority_contact_status = "missing"`

Priority 2 (URGENT):
- `high_severity_count > 10` AND
- `authority_contact_status = "configured"`

Priority 3 (ATTENTION):
- `oldest_unresolved_issue_age_days > 90` AND
- `unresolved_issues > 20`

**Display format:**

```
PRIORITY 1 (CRITICAL) - 15 districts
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
District: Mumbai, Maharashtra
High Severity: 25 issues
Problem: No authority contact configured
Action: Set up DM office email
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Action buttons:**
- "Configure Authority" (if missing)
- "View High Severity Issues" (link to issue list)
- "Contact DM Office" (if configured)

---

### 4. PERFORMANCE DASHBOARD (KPI Cards)

**Goal:** Show high-level system health

**Top cards (from `summary`):**

**Card 1: Total Issues**
- Number: `summary.total_issues_all_districts`
- Label: "Total Issues Nationwide"
- Subtext: "Across {metadata.districts_with_issues} districts"

**Card 2: Unresolved Issues**
- Number: `summary.total_unresolved_all_districts`
- Label: "Unresolved Issues"
- Calculate rate: `(unresolved / total) * 100`
- Subtext: "49.6% unresolved rate"
- Color: Red if >60%, Yellow if >40%, Green if <40%

**Card 3: Authority Coverage**
- Number: `summary.districts_with_configured_authority`
- Label: "Districts with Authority Contact"
- Calculate percentage: `(configured / metadata.total_districts) * 100`
- Subtext: "60% coverage"
- Progress bar showing percentage

**Card 4: Districts Needing Attention**
- Number: Count districts where `percentage_unresolved > 75`
- Label: "Critical Districts"
- Subtext: "Over 75% unresolved rate"

---

### 5. STATE-LEVEL AGGREGATION

**Goal:** Roll up district data to state level

**Data processing:**

1. Group districts by `state_name`
2. For each state, sum up:
   - Total issues
   - Unresolved issues
   - High/moderate/low severity counts
3. Calculate state-level percentage unresolved
4. Count districts per state

**Display as:**
- Bar chart (states on X-axis, unresolved count on Y-axis)
- Table with state rollup
- State dropdown filter

**Example state object you'd create:**
```
State: Maharashtra
Districts: 36
Total Issues: 1,250
Unresolved: 620
% Unresolved: 49.6%
High Severity: 180
```

---

### 6. SEVERITY BREAKDOWN PIE CHART

**Goal:** Show distribution of issue severity

**Data aggregation:**
Sum across all districts:
- High: Sum of all `high_severity_count`
- Moderate: Sum of all `moderate_severity_count`
- Low: Sum of all `low_severity_count`

**Pie chart segments:**
- Red slice: High severity (% of total verified)
- Orange slice: Moderate severity
- Yellow slice: Low severity

**Note:** This is for **verified issues only** - unverified issues don't have severity.

---

### 7. TIME TREND CHART

**Goal:** Show how unresolved issues change over time

**Approach:** Make multiple API calls with different date ranges

**Example queries:**
- Week 1: `?from_date=2026-01-01&to_date=2026-01-07`
- Week 2: `?from_date=2026-01-08&to_date=2026-01-14`
- Week 3: `?from_date=2026-01-15&to_date=2026-01-21`
- Week 4: `?from_date=2026-01-22&to_date=2026-01-28`

**For each week, extract:**
- `summary.total_issues_all_districts`
- `summary.total_unresolved_all_districts`

**Plot on line chart:**
- X-axis: Week
- Y-axis: Issue count
- Line 1: Total issues (blue)
- Line 2: Unresolved issues (red)

---

### 8. DISTRICT COMPARISON VIEW

**Goal:** Compare 2-5 districts side by side

**Query:** `?sort_by=district_name&sort_order=ASC` (get all, filter in frontend)

**Display format:** Side-by-side cards or table

**Metrics to compare:**
- Total issues
- Unresolved count and percentage
- Severity breakdown (stacked bar chart)
- Oldest unresolved age
- Authority status
- Last issue reported

**Use case:** Compare similar-sized cities or districts in same state

---

## Common Calculations

### 1. Verification Success Rate
```
(verified_issues / total_issues) * 100
```
Shows what % of reports pass AI verification. Lower rate = more spam/fake reports.

### 2. Resolution Rate
```
((total_issues - unresolved_issues) / total_issues) * 100
```
Shows what % of issues have been resolved. Higher is better.

### 3. Critical District Count
```
Count where: percentage_unresolved > 75 AND total_issues > 10
```
Districts in crisis (ignore districts with <10 issues to avoid false positives).

### 4. Average Age of Unresolved Issues
```
Sum of (oldest_unresolved_issue_age_days) / Count of districts with unresolved issues
```
System-wide metric: how long do issues sit unresolved?

### 5. Authority Configuration Gap
```
metadata.total_districts - summary.districts_with_configured_authority
```
How many districts still need authority setup?

---

## Filtering Strategies

### Filter 1: By Authority Status
```
Filter where: authority_contact_status = "missing"
```
**Use case:** Show which districts need configuration

### Filter 2: By Severity
```
Filter where: high_severity_count > threshold
```
**Use case:** Focus on critical districts

### Filter 3: By Performance
```
Filter where: percentage_unresolved > 60
```
**Use case:** Show poorly performing districts

### Filter 4: By Activity
```
Filter where: total_issues > 50
```
**Use case:** Focus on active districts, ignore low-activity ones

### Filter 5: By Neglect
```
Filter where: oldest_unresolved_issue_age_days > 90
```
**Use case:** Find districts with very old unresolved issues

### Filter 6: By State
```
Filter where: state_name = "Maharashtra"
```
**Use case:** State-level drilldown

---

## Sorting Strategies

### Sort 1: Most Failing (default)
```
?sort_by=unresolved_count&sort_order=DESC
```
Districts with most unresolved issues first

### Sort 2: Most Urgent
```
?sort_by=high_severity_count&sort_order=DESC
```
Districts with most critical issues first

### Sort 3: Highest Volume
```
?sort_by=total_issues&sort_order=DESC
```
Districts with most total reports (active users)

### Sort 4: Alphabetical
```
?sort_by=district_name&sort_order=ASC
```
Browse districts systematically

---

## Handling Edge Cases

### Districts with 0 Issues
- `total_issues = 0`
- `percentage_unresolved = 0.00`
- `oldest_unresolved_issue_age_days = null`
- `last_issue_reported_at = null`

**Display:** Show as "No issues reported" or grey out on map

### Districts with All Issues Resolved
- `unresolved_issues = 0`
- `percentage_unresolved = 0.00`
- `oldest_unresolved_issue_age_days = null`

**Display:** Show as "All resolved" with green badge

### Districts with No Authority
- `authority_contact_status = "missing"`

**Display:** Show warning badge, offer "Configure" action

### Very Old Unresolved Issues
- `oldest_unresolved_issue_age_days > 180`

**Display:** Show in red with "⚠️ Neglected" badge

---

## Date Range Usage

### All Time (default)
```
GET /admin/analytics/districts
```
No date params = all data since system launch

### Last 30 Days
```
?from_date=2026-01-01&to_date=2026-01-31
```
Filter to specific month

### Current Year
```
?from_date=2026-01-01&to_date=2026-12-31
```
Annual performance view

### Custom Range
Let user pick dates in UI, pass as query params

**Note:** Date filtering affects issue counts but NOT district list (all 750 districts still returned, just with counts = 0 if no issues in range).

---

## Performance Considerations

### 1. Data Freshness
- API query time: 100-500ms
- Refresh strategy: Cache for 5-10 minutes on frontend
- Don't query on every user interaction

### 2. Large Data Set
- Response includes all 750 districts (~200-500KB JSON)
- Consider pagination if showing in table
- Use virtual scrolling for large lists

### 3. Map Rendering
- Don't re-color map on every API call
- Only update when data changes
- Use requestAnimationFrame for smooth updates

### 4. Multiple Visualizations
- Fetch data once, reuse for all visualizations
- Don't make separate API calls for each chart

---

## Visualization Priority Recommendations

### Phase 1: Essential
1. **District heatmap** (primary visualization)
2. **Failure rankings table** (top 50)
3. **Performance dashboard** (KPI cards)

### Phase 2: Enhanced
4. **Escalation priority queue**
5. **State-level aggregation**
6. **Severity breakdown chart**

### Phase 3: Advanced
7. **Time trend analysis**
8. **District comparison view**

---

## Summary

### Key Data Points to Use

**For Heatmaps:** `percentage_unresolved`, `district_id`  
**For Rankings:** `unresolved_issues`, `high_severity_count`, `district_name`  
**For Escalation:** `high_severity_count`, `authority_contact_status`, `oldest_unresolved_issue_age_days`  
**For KPIs:** `summary.*` fields  
**For Filtering:** `state_name`, `authority_contact_status`, thresholds on numeric fields

### Most Important Fields

1. `district_id` - Unique identifier for map matching
2. `district_name` - User-friendly label
3. `unresolved_issues` - Action backlog (absolute)
4. `percentage_unresolved` - Performance metric (normalized)
5. `high_severity_count` - Urgency indicator
6. `authority_contact_status` - Escalation readiness

### Best Practices

✅ **DO:**
- Use percentage_unresolved for fair comparisons
- Filter out districts with <10 issues when calculating averages
- Show authority status prominently
- Refresh data periodically (not on every click)
- Cache the response for multiple visualizations

❌ **DON'T:**
- Don't compare districts by absolute counts only (unfair to small districts)
- Don't ignore districts with 0 issues (they exist in the data for completeness)
- Don't make separate API calls for each visualization
- Don't forget null checks (age_days, last_reported_at can be null)

---

**This data is built for operational analytics, not vanity metrics. Use it to identify problems, prioritize action, and track improvement.**
