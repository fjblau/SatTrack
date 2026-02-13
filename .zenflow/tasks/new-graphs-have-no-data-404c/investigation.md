# Bug Investigation: New Graphs Have No Data

## Summary

The "new graphs" feature introduced in the last task (expand-graph-scope) has multiple data structure mismatches between the frontend and backend APIs. Three graph types are affected: **Communities**, **Centrality Analysis**, and **Lineage**.

## Root Cause Analysis

### 1. Communities Graph - Parameter and Data Structure Mismatch

**Location**: [`react-app/src/components/GraphViewer.jsx:861`](./react-app/src/components/GraphViewer.jsx:861)

**Issues**:
- **Parameter Name Mismatch**: Frontend sends `min_community_size=3`, but backend expects `min_size`
- **Data Structure Mismatch**: Frontend expects graph structure with `nodes` and `edges`, but backend returns list of `communities`

**Frontend Code** (line 861):
```javascript
const response = await fetch('/v2/graphs/communities?algorithm=label_propagation&min_community_size=3')
// ...
if (data.data && data.data.nodes) {  // ❌ Expects nodes array
```

**Backend Response** ([`api/routers/graphs.py:2259-2268`](./api/routers/graphs.py:2259)):
```python
result = {
    "communities": communities,  # ✓ Returns communities array, not nodes/edges
    "algorithm": algorithm,
    "stats": {...}
}
```

**Impact**: No data displayed because `data.data.nodes` is undefined (backend doesn't return `nodes`).

---

### 2. Centrality Analysis - Field Name and Missing Data Mismatch

**Location**: [`react-app/src/components/GraphViewer.jsx:752-798`](./react-app/src/components/GraphViewer.jsx:752)

**Issues**:
- **Field Name Mismatch**: Frontend expects `centrality_scores`, but backend returns `satellites`
- **Missing Edges**: Frontend expects `edges` array, but backend doesn't return edges for centrality

**Frontend Code** (lines 757-774):
```javascript
const maxScore = Math.max(...(data.centrality_scores?.map(s => s.score) || [1]))  // ❌ Expects centrality_scores

const elements = {
  nodes: (data.centrality_scores || []).map(item => { ... }),  // ❌ Expects centrality_scores
  edges: (data.edges || []).map(edge => { ... })  // ❌ Expects edges (not returned by API)
}
```

**Backend Response** ([`api/routers/graphs.py:1525-1533`](./api/routers/graphs.py:1525)):
```python
response_data = {
    "metric": metric,
    "satellites": results,  # ✓ Returns satellites, not centrality_scores
    "count": len(results),
    "parameters": {...}
    # ❌ No edges field returned
}
```

**Impact**: No data displayed because:
1. `data.centrality_scores` is undefined (should be `data.satellites`)
2. No edges are provided by the backend for graph visualization

---

### 3. Lineage Graph - Not Implemented in Frontend

**Location**: [`react-app/src/components/GraphViewer.jsx:292-293`](./react-app/src/components/GraphViewer.jsx:292)

**Issue**: Frontend only shows a message, doesn't fetch or render lineage data

**Frontend Code**:
```javascript
} else if (graphType === 'lineage') {
  setStats({ message: 'Select a satellite from the data table to view its lineage' })
}
```

**Backend**: API endpoint exists at `/v2/graphs/lineage/{satellite_id}` ([`api/routers/graphs.py:2054`](./api/routers/graphs.py:2054))

**Impact**: No data displayed because frontend never calls the API endpoint.

---

## Graphs Working Correctly

### ✓ Evolution Timeline
- Uses separate component: [`EvolutionTimelineView.jsx`](./react-app/src/components/EvolutionTimelineView.jsx)
- Correctly fetches from `/v2/graphs/evolution/timeline`
- Data structure matches expected format

### ✓ Collision Risk Network
- Correctly expects `data.nodes` and `data.edges`
- API returns matching structure via `collision_service.get_collision_risk_network()`

---

## Affected Components

1. **Communities** ([`GraphViewer.jsx:856-914`](./react-app/src/components/GraphViewer.jsx:856))
2. **Centrality Analysis** ([`GraphViewer.jsx:752-798`](./react-app/src/components/GraphViewer.jsx:752))
3. **Lineage** ([`GraphViewer.jsx:292-293`](./react-app/src/components/GraphViewer.jsx:292))

---

## Proposed Solution

### Option 1: Fix Frontend (Recommended)
Adapt frontend to match existing backend data structures:

1. **Communities**: 
   - Change parameter name to `min_size`
   - Convert `communities` array to graph structure with nodes/edges

2. **Centrality**: 
   - Rename `centrality_scores` to `satellites`
   - Build edges from existing graph data or remove edge rendering

3. **Lineage**:
   - Implement API call to `/v2/graphs/lineage/{satellite_id}`
   - Add graph rendering logic

### Option 2: Fix Backend
Modify backend to return graph-ready data structures (nodes/edges) for all endpoints.

**Recommendation**: Option 1 (fix frontend) is preferred because:
- Backend data structures are semantically correct
- Multiple API consumers may already depend on current structure
- Frontend can transform data for visualization needs

---

## Edge Cases & Side Effects

- **Caching**: Communities and evolution endpoints use caching (12-24 hours). Cache keys must match parameter names.
- **Error Handling**: Frontend doesn't show error messages when data structure mismatches occur
- **Lineage Integration**: Requires satellite selection from data table (not yet wired up)

---

## Test Verification

To verify the bug:
1. Navigate to Graph Explorer
2. Select "Communities" → No graph appears
3. Select "Centrality Analysis" → Click "Calculate Centrality" → No graph appears
4. Select "Satellite Lineage" → Only shows instruction message

Expected browser console errors:
- "Cannot read property 'map' of undefined" (accessing undefined arrays)
- No data logged for communities/centrality responses
