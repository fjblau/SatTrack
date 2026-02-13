# Bug Investigation: API Data Loading Failures

## Bug Summary
Three graph visualization features are failing to load data:
1. **Communities** - Returns 422 (Unprocessable Entity)
2. **Graph Evolution Timeline** - Returns 500 (Internal Server Error)  
3. **Centrality Analysis** - Returns no satellites in data

## Root Cause Analysis

### Issue 1: Communities Endpoint - Algorithm Mismatch

**Location**: 
- Frontend: [./react-app/src/components/GraphExplorer.jsx:502-505](./react-app/src/components/GraphExplorer.jsx:502:505)
- Backend: [./api/routers/graphs.py:2246-2251](./api/routers/graphs.py:2246:2251)

**Problem**: Frontend and backend have mismatched algorithm options.

**Frontend** (GraphExplorer.jsx) offers 3 algorithms:
```jsx
<option value="label_propagation">Label Propagation</option>
<option value="louvain">Louvain</option>
<option value="greedy_modularity">Greedy Modularity</option>
```

**Backend** (graphs.py) only accepts 2 algorithms:
```python
valid_algorithms = ["connected_components", "label_propagation"]
if algorithm not in valid_algorithms:
    raise HTTPException(
        status_code=400,  # Note: actual error shows 422
        detail=f"Invalid algorithm. Must be one of: {', '.join(valid_algorithms)}"
    )
```

**Result**: When user selects "louvain" or "greedy_modularity", the API returns 422 with error message: "Invalid algorithm. Must be one of: connected_components, label_propagation"

---

### Issue 2: Centrality Analysis - Parameter and Response Mismatch

**Location**:
- Frontend: [./react-app/src/components/CentralityView.jsx:38-45](./react-app/src/components/CentralityView.jsx:38:45)
- Backend: [./api/routers/graphs.py:1444-1448](./api/routers/graphs.py:1444:1448)

**Problem 1**: Parameter name mismatch

**Frontend** sends:
```javascript
const params = new URLSearchParams({
    metric: metricType,
    top_n: topN  // ❌ Wrong parameter name
})
```

**Backend** expects:
```python
limit: int = Query(
    default=50,
    description="Maximum number of results to return",
    ge=1,
    le=200
)
```

**Problem 2**: Response structure mismatch

**Frontend** expects (line 60):
```javascript
if (data.data.nodes && data.data.nodes.length === 0) {
    // ❌ Looking for 'nodes' property
}
```

**Backend** returns (line 1527):
```python
response_data = {
    "metric": metric,
    "satellites": results,  # ✅ Returns 'satellites', not 'nodes'
    "count": len(results),
    ...
}
```

**Result**: Frontend sends `top_n` parameter which backend ignores (defaults to 50), and then looks for `data.data.nodes` which doesn't exist in the response, causing "No satellites found in centrality data" error.

---

### Issue 3: Graph Evolution Timeline - 500 Internal Server Error

**Location**: 
- Frontend: [./react-app/src/components/EvolutionTimelineView.jsx:74-84](./react-app/src/components/EvolutionTimelineView.jsx:74:84)
- Backend: [./api/routers/graphs.py:2287-2347](./api/routers/graphs.py:2287:2347)

**Problem**: Need to investigate backend function `calculate_graph_evolution_timeline` for potential:
- Database query errors
- Data processing exceptions
- Missing required fields in database
- Edge case handling issues

The error is a 500 (Internal Server Error), indicating an unhandled exception in the backend code. The endpoint calls `calculate_graph_evolution_timeline()` from `database.graph_analytics` which may be throwing an exception.

---

## Affected Components

### Communities
- [./react-app/src/components/GraphExplorer.jsx:481-535](./react-app/src/components/GraphExplorer.jsx:481:535) - UI controls
- [./react-app/src/components/GraphViewer.jsx:1051-1204](./react-app/src/components/GraphViewer.jsx:1051:1204) - Data loading
- [./api/routers/graphs.py:2192-2284](./api/routers/graphs.py:2192:2284) - API endpoint

### Centrality Analysis  
- [./react-app/src/components/CentralityView.jsx:1-177](./react-app/src/components/CentralityView.jsx:1:177) - Full component
- [./api/routers/graphs.py:1434-1552](./api/routers/graphs.py:1434:1552) - API endpoint

### Graph Evolution Timeline
- [./react-app/src/components/EvolutionTimelineView.jsx:1-429](./react-app/src/components/EvolutionTimelineView.jsx:1:429) - Full component  
- [./api/routers/graphs.py:2287-2407](./api/routers/graphs.py:2287:2407) - API endpoint
- Database analytics function (needs investigation)

---

## Proposed Solution

### Fix 1: Communities Algorithm Options
**Option A** (Recommended): Update frontend to match backend
- Remove "louvain" and "greedy_modularity" from dropdown
- Add "connected_components" option
- Ensures immediate fix without backend changes

**Option B**: Implement missing algorithms in backend
- Add louvain and greedy_modularity algorithms to `database.graph_analytics`
- Update valid_algorithms list in API
- More work but provides better UX

### Fix 2: Centrality Analysis
**Changes needed**:
1. Update frontend parameter from `top_n` to `limit`
2. Update frontend to look for `data.data.satellites` instead of `data.data.nodes`

### Fix 3: Graph Evolution Timeline
**Investigation needed**:
1. Check backend logs for specific error
2. Review `calculate_graph_evolution_timeline()` implementation
3. Add error handling for edge cases
4. Validate database has required fields

---

## Edge Cases and Side Effects

### Communities
- Users who previously selected "louvain" or "greedy_modularity" will need to reselect
- Default algorithm should be set to "label_propagation" (already is)

### Centrality
- Current code ignores user's `top_n` selection (defaults to 50)
- After fix, users get their requested limit
- Should validate limit is within backend's accepted range (1-200)

### Evolution Timeline  
- Unknown until backend error is investigated
- May affect cached results if caching is involved
