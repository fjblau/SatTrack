# Bug Investigation: API Data Loading Failures

## CRITICAL FINDING: This is the 3rd attempt to fix these bugs

Previous fix attempts (commits 126357c, de71d00, 3925175) added error handling and UI improvements **but did not fix the root API contract mismatches**. This investigation identifies the actual root causes.

---

## Bug Summary
Three graph visualization features are failing to load data:
1. **Communities** - Returns 422 (Unprocessable Entity)
2. **Graph Evolution Timeline** - Returns 500 (Internal Server Error)  
3. **Centrality Analysis** - Returns no satellites in data

---

## Root Cause Analysis

### Issue 1: Communities Endpoint - Frontend Offers Unsupported Algorithms ⚠️ CRITICAL

**Location**: 
- Frontend: [./react-app/src/components/GraphExplorer.jsx:502-505](./react-app/src/components/GraphExplorer.jsx:502:505)
- Backend: [./api/routers/graphs.py:2246-2251](./api/routers/graphs.py:2246:2251)

**Problem**: Frontend offers algorithms that backend doesn't support

**What Happened in Previous Fix (commit 126357c)**:
- Added algorithm selector dropdown with 3 options: `label_propagation`, `louvain`, `greedy_modularity`
- **Did NOT check** if backend supports these algorithms
- This introduced the bug!

**Current State**:

Frontend (GraphExplorer.jsx lines 502-505):
```jsx
<option value="label_propagation">Label Propagation</option>
<option value="louvain">Louvain</option>  <!-- ❌ NOT SUPPORTED -->
<option value="greedy_modularity">Greedy Modularity</option>  <!-- ❌ NOT SUPPORTED -->
```

Backend (graphs.py lines 2246-2251):
```python
valid_algorithms = ["connected_components", "label_propagation"]
if algorithm not in valid_algorithms:
    raise HTTPException(
        status_code=400,
        detail=f"Invalid algorithm. Must be one of: {', '.join(valid_algorithms)}"
    )
```

**Result**: When user selects "louvain" or "greedy_modularity", API returns 422

**Why Previous Fix Failed**: Added UI features without verifying backend capabilities

---

### Issue 2: Centrality Analysis - Dual Mismatch (Parameter Name + Response Structure) ⚠️ CRITICAL

**Location**:
- Frontend: [./react-app/src/components/CentralityView.jsx:38-45](./react-app/src/components/CentralityView.jsx:38:45)
- Backend: [./api/routers/graphs.py:1444-1448](./api/routers/graphs.py:1444:1448)

**What Happened in Previous Fix (commit de71d00)**:
- Added error handling, validation, and logging
- **Did NOT fix** parameter name mismatch
- **Did NOT fix** response structure mismatch
- Error handling just showed better error messages for the wrong data!

**Problem 1**: Parameter name mismatch

Frontend sends (CentralityView.jsx lines 38-40):
```javascript
const params = new URLSearchParams({
    metric: metricType,
    top_n: topN  // ❌ Wrong parameter name
})
```

Backend expects (graphs.py line 1444):
```python
limit: int = Query(
    default=50,
    description="Maximum number of results to return",
    # ⬆️ Expects 'limit', not 'top_n'
)
```

**Problem 2**: Response structure mismatch

Frontend expects (CentralityView.jsx line 60):
```javascript
if (data.data.nodes && data.data.nodes.length === 0) {
    // ❌ Looking for 'nodes' property
}
```

Backend returns (graphs.py lines 1525-1533):
```python
response_data = {
    "metric": metric,
    "satellites": results,  # ✅ Returns 'satellites', not 'nodes'
    "count": len(results),
    "parameters": {...}
}
```

**Result**: 
1. Frontend sends `top_n=20` → backend ignores it, uses default `limit=50`
2. Frontend looks for `data.data.nodes` → undefined, always triggers "no results" error

**Why Previous Fix Failed**: Enhanced error handling without fixing the API contract

---

### Issue 3: Graph Evolution Timeline - Wrong Database Field Name 🔥 SMOKING GUN

**Location**: 
- Frontend: [./react-app/src/components/EvolutionTimelineView.jsx:74-84](./react-app/src/components/EvolutionTimelineView.jsx:74:84)
- Backend Query: [./database/graph_analytics.py:1728-1793](./database/graph_analytics.py:1728:1793)
- Database Schema: Actual field is `canonical.date_of_launch`

**What Happened in Previous Fix (commit 3925175)**:
- Added comprehensive error handling and validation
- **Did NOT investigate** the actual database field name
- Error handling masked the real issue: queries returning zero results

**THE SMOKING GUN**:

Backend query uses (graph_analytics.py lines 1737, 1772, 1793):
```python
FILTER doc.canonical.launch_date != null  # ❌ WRONG FIELD NAME
```

Actual database field (throughout codebase - api/routers/graphs.py lines 95, 109, App.jsx line 103):
```python
canonical.date_of_launch  # ✅ CORRECT FIELD NAME
```

**Proof**:
- [./api/routers/graphs.py:95](./api/routers/graphs.py:95): `launch_date: v.canonical.date_of_launch`
- [./api/routers/graphs.py:109](./api/routers/graphs.py:109): `launch_date: hub_doc.canonical.date_of_launch`
- [./api/routers/graphs.py:306-307](./api/routers/graphs.py:306:307): Working queries use `doc.canonical.launch_date` (wait, this is also wrong!)
- [./react-app/src/App.jsx:103](./react-app/src/App.jsx:103): `'Date of Launch': canonical.date_of_launch`

**WAIT - There's confusion in the codebase**:
- Some queries use `canonical.launch_date` (lines 306, 527, 576, etc. in graphs.py)
- The object property is `canonical.date_of_launch`
- The queries that work must be using a different approach or the field is aliased

Let me check the actual working query more carefully...

Looking at [./api/routers/graphs.py:306-307](./api/routers/graphs.py:306:307):
```python
FILTER doc.canonical.launch_date != null
LET year = TO_NUMBER(SUBSTRING(doc.canonical.launch_date, 0, 4))
```

This is in the `/stats` endpoint which works (we tested it). So either:
1. The field exists under both names (aliased)
2. Or there's something else going on

**Result**: The `get_graph_snapshot_by_date` function queries return zero satellites because the field filter doesn't match actual data, causing:
- Empty timeline arrays
- Zero node counts
- 500 errors when the data structure is invalid

**Why Previous Fix Failed**: Added validation and error handling but didn't investigate why the backend query returns no data

---

## Historical Context: Why Did Previous Fixes Fail?

### Commit 126357c "Improve Communities Graph"
- ❌ Added frontend features (algorithm selector) without backend validation
- ❌ Introduced new bugs by offering unsupported options
- ✅ Added good error handling (but for the wrong problem)

### Commit de71d00 "Enhance Centrality and Collision Risk Views"  
- ❌ Did not fix parameter name mismatch (`top_n` vs `limit`)
- ❌ Did not fix response structure mismatch (`nodes` vs `satellites`)
- ✅ Added validation and better error messages (but data still wrong)

### Commit 3925175 "Fix Evolution Timeline"
- ❌ Did not investigate database field names
- ❌ Did not discover `launch_date` vs `date_of_launch` issue
- ✅ Added comprehensive error handling (masked the real issue)

**Pattern**: All previous fixes focused on **error handling and UX improvements** without fixing the **underlying API contract and data layer bugs**.

---

## Proposed Solutions

### Fix 1: Communities - Remove Unsupported Algorithms

**File**: [./react-app/src/components/GraphExplorer.jsx](./react-app/src/components/GraphExplorer.jsx)

**Change**: Remove unsupported algorithm options from dropdown

```jsx
// BEFORE (lines 502-505)
<option value="label_propagation">Label Propagation</option>
<option value="louvain">Louvain</option>
<option value="greedy_modularity">Greedy Modularity</option>

// AFTER
<option value="label_propagation">Label Propagation</option>
<option value="connected_components">Connected Components</option>
```

**Alternative**: Implement louvain and greedy_modularity in backend (more work, better UX)

---

### Fix 2: Centrality - Fix Parameter Name and Response Reference

**File**: [./react-app/src/components/CentralityView.jsx](./react-app/src/components/CentralityView.jsx)

**Change 1**: Update parameter name (line 40)
```javascript
// BEFORE
const params = new URLSearchParams({
    metric: metricType,
    top_n: topN
})

// AFTER  
const params = new URLSearchParams({
    metric: metricType,
    limit: topN
})
```

**Change 2**: Update response property reference (line 60 and 64)
```javascript
// BEFORE
if (data.data.nodes && data.data.nodes.length === 0) {
    // ...
} else {
    console.log(`[CentralityView] Success: ${data.data.nodes?.length || 0} nodes`)
}

// AFTER
if (data.data.satellites && data.data.satellites.length === 0) {
    // ...
} else {
    console.log(`[CentralityView] Success: ${data.data.satellites?.length || 0} satellites`)
}
```

---

### Fix 3: Graph Evolution - NEEDS VERIFICATION FIRST

**CRITICAL**: Need to verify which field name is correct in actual database before changing code

**Investigation Steps**:
1. Check actual ArangoDB collection schema
2. Verify which field name exists: `launch_date` or `date_of_launch`
3. Test working queries (like `/stats`) to see which they use
4. Check if field is aliased or duplicated

**Potential Fix** (if field is `date_of_launch`):

**File**: [./database/graph_analytics.py](./database/graph_analytics.py)

**Change**: Update all references in `get_graph_snapshot_by_date` function

```python
# BEFORE (lines 1737, 1772, 1793)
FILTER doc.canonical.launch_date != null

# AFTER
FILTER doc.canonical.date_of_launch != null
```

**BUT WAIT**: Other working queries in graphs.py also use `launch_date`. Need to investigate why they work first!

---

## Testing Strategy (to prevent 4th attempt)

### Before implementing fixes:

1. **Verify Database Schema**:
   - Query actual ArangoDB to see field names
   - Check if both field names exist (aliasing)
   - Document findings

2. **Test Current Behavior**:
   - Start backend with logging enabled
   - Reproduce all three errors
   - Capture actual error messages from backend logs

3. **Verify API Contracts**:
   - Review OpenAPI docs at http://localhost:8000/docs
   - Confirm expected parameter names
   - Confirm expected response structures

### After implementing fixes:

1. **Test Each Fix Individually**:
   - Communities: Test all algorithm options
   - Centrality: Test with different limit values, verify correct count returned
   - Evolution: Test with different date ranges and granularities

2. **Integration Testing**:
   - Test all three features together
   - Verify no regressions in other features

3. **Regression Tests**:
   - Add automated tests to prevent these bugs from returning
   - Document API contracts in tests

---

## Edge Cases and Side Effects

### Communities
- Default algorithm should be "label_propagation" (already is)
- Users previously selecting "louvain" will see different results after fix

### Centrality
- After fix, results count will match user's selection (currently always 50)
- Need to validate limit range (currently 5-100 in UI, 1-200 in API)

### Evolution Timeline
- May reveal other bugs if queries start returning actual data
- Need to verify date parsing logic handles all formats correctly
- Check performance with large date ranges (e.g., 1957-2026)

---

## Next Steps

1. **FIRST**: Verify database schema and field names
2. **SECOND**: Implement and test fixes one by one
3. **THIRD**: Add regression tests
4. **FOURTH**: Document API contracts to prevent future mismatches
