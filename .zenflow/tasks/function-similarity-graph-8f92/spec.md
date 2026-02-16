# Technical Specification: Function Similarity Graph Enhancement

## Task Difficulty Assessment
**Difficulty**: Medium

**Rationale**: The task requires modifying an existing graph endpoint to create synthetic similarity edges, updating the frontend visualization, and ensuring proper edge styling. While not architecturally complex, it involves coordinating changes across backend API, database queries, and frontend rendering logic.

## Problem Analysis

### Current Behavior
The Function Similarity Graph endpoint ([`/v2/graphs/function-similarity`](./api/routers/graphs.py:1091)) currently:
1. Categorizes satellites by function (Communications, Earth Observation, Scientific Research, etc.)
2. Returns nodes (satellites) grouped by function categories
3. Attempts to show edges between satellites **only if they have existing constellation/registration/proximity relationships**

### Root Cause
The query at [./api/routers/graphs.py:1155-1193](./api/routers/graphs.py:1155) filters edges where both `_from` and `_to` are in the satellite list:
```aql
LET constellation_edges = (
    FOR edge IN {EDGE_COLLECTION_CONSTELLATION}
        FILTER edge._from IN satellite_ids AND edge._to IN satellite_ids
        RETURN {...}
)
```

**Issue**: Satellites grouped by function alone rarely share edges. Database analysis shows:
- 100 satellites with same function: **0 proximity edges, 0 constellation edges**
- Single-dimension clustering (function only) produces empty graphs

### Data Analysis Results

**Function + Orbital Band clusters have real edges**:
- Communications + LEO-Polar: 617 satellites, **5,188 proximity edges**, 556 constellation edges
- Navigation + MEO: 33 satellites, **74 proximity edges**, 28 constellation edges
- Earth Observation + LEO-Polar: 93 satellites, **71 proximity edges**

**Function + Country clusters also have real edges**:
- Communications + United Kingdom: 569 satellites, **5,123 proximity edges** (OneWeb/Starlink)
- Navigation + Russian Federation: 22 satellites, **66 proximity edges** (GLONASS)
- Communications + Germany: 17 satellites, **32 proximity edges**

### Expected Behavior
A useful "Function Similarity Graph" should:
1. **Initial display**: Show top multi-dimensional clusters pre-computed with real edges (Option B)
2. **Interactive filtering**: Allow users to select combinations of function + orbital band + country (Option C)
3. **Only show real edges**: No synthetic edges; display actual proximity/constellation relationships
4. **Meaningful clusters**: Show clusters where satellites actually have orbital/organizational connections

## Technical Context

### Languages & Frameworks
- **Backend**: Python 3.11, FastAPI, ArangoDB (AQL queries)
- **Frontend**: React 19.2.3, Cytoscape.js for graph visualization
- **Build Tool**: Vite 7.2.7

### Key Files to Modify
1. **Backend**:
   - [`./api/routers/graphs.py`](./api/routers/graphs.py) - Function similarity endpoint (lines 1091-1230)

2. **Frontend**:
   - [`./react-app/src/components/GraphViewer.jsx`](./react-app/src/components/GraphViewer.jsx) - Graph rendering (lines 614-688, function similarity logic)

### Dependencies
- **Cytoscape.js**: Already included, supports all required edge styling
- **cytoscape-cola**: Already included for force-directed layout
- **ArangoDB**: No schema changes needed; synthetic edges created in query response only

## Implementation Approach

### Strategy: Multi-Dimensional Clustering with Real Edges

Show clusters based on **function + orbital band** and/or **function + country** combinations, displaying only real proximity and constellation edges that exist in the data.

#### Phase 1: Initial Display (Option B)
Pre-compute and display top clusters sorted by edge density:

**Backend Changes** ([`./api/routers/graphs.py:1091`](./api/routers/graphs.py:1091)):
1. Group satellites by (function_category, orbital_band)
2. Count real edges (proximity + constellation) within each cluster
3. Filter clusters with:
   - Minimum 5 satellites
   - Minimum 10 edges
4. Sort by edge count DESC
5. Return top 10-15 clusters as default view
6. Include cluster metadata:
   - `cluster_id`: "Communications-LEO-Polar"
   - `satellite_count`: 617
   - `edge_count`: 5744
   - `density`: edges / max_possible_edges

**Response Format**:
```json
{
  "data": {
    "clusters": [
      {
        "cluster_id": "Communications-LEO-Polar",
        "function": "Communications",
        "orbital_band": "LEO-Polar",
        "satellite_count": 617,
        "edge_count": 5744,
        "density": 0.031
      },
      ...
    ],
    "nodes": [...],  // Satellites from top clusters
    "edges": [...]   // Real proximity/constellation edges only
  }
}
```

#### Phase 2: Interactive Filtering (Option C)
Allow users to filter by multiple dimensions:

**Frontend Changes** ([`./react-app/src/components/GraphExplorer.jsx`](./react-app/src/components/GraphExplorer.jsx)):
1. Add multi-select controls:
   - Function categories (checkboxes)
   - Orbital bands (checkboxes)
   - Countries (checkboxes)
2. On selection change, request filtered data from backend
3. Backend re-computes clusters matching selected criteria
4. Show only real edges within filtered clusters

**User Flow**:
1. Initial load: See "Communications + LEO-Polar" (5,744 edges)
2. Click "Navigation": Add "Navigation + MEO" cluster (102 edges)
3. Filter by country "Russian Federation": Show Russian navigation satellites
4. Always see real edges, never synthetic/fake connections

## Source Code Structure Changes

### Backend: [`./api/routers/graphs.py`](./api/routers/graphs.py)

**Modified Function**: `get_function_similarity_graph` (lines 1092-1230)

**New Query Structure**:
```aql
LET satellites_with_function = (
    FOR doc IN satellites
        FILTER doc.canonical.function != null
        FILTER doc.canonical.orbital_band != null
        LET func_lower = LOWER(doc.canonical.function)
        LET category = (...)  # Existing categorization
        RETURN {
            _id: doc._id,
            function_category: category,
            orbital_band: doc.canonical.orbital_band,
            country: doc.canonical.country_of_origin,
            ...
        }
)

# Compute clusters with real edge counts
LET clusters = (
    FOR sat IN satellites_with_function
        COLLECT 
            category = sat.function_category, 
            band = sat.orbital_band 
        INTO group
        
        LET cluster_sats = group[*].sat
        LET sat_ids = cluster_sats[*]._id
        
        # Count REAL edges only
        LET proximity_edges = (
            FOR edge IN orbital_proximity
                FILTER edge._from IN sat_ids AND edge._to IN sat_ids
                RETURN edge
        )
        
        LET constellation_edges = (
            FOR edge IN constellation_membership
                FILTER edge._from IN sat_ids AND edge._to IN sat_ids
                RETURN edge
        )
        
        LET total_edges = LENGTH(proximity_edges) + LENGTH(constellation_edges)
        
        # Filter: minimum satellites and edges
        FILTER LENGTH(cluster_sats) >= 5
        FILTER total_edges >= 10
        
        SORT total_edges DESC
        LIMIT 15
        
        RETURN {
            cluster_id: CONCAT(category, "-", band),
            function: category,
            orbital_band: band,
            satellite_count: LENGTH(cluster_sats),
            proximity_edge_count: LENGTH(proximity_edges),
            constellation_edge_count: LENGTH(constellation_edges),
            edge_count: total_edges,
            satellites: cluster_sats,
            proximity_edges: proximity_edges,
            constellation_edges: constellation_edges
        }
)

# Extract nodes and edges from top clusters
LET nodes = FLATTEN(clusters[*].satellites)
LET edges = UNION(
    FLATTEN(clusters[*].proximity_edges),
    FLATTEN(clusters[*].constellation_edges)
)

RETURN {
    clusters: clusters,  // Metadata for display
    nodes: nodes,
    edges: edges,
    stats: {
        total_clusters: LENGTH(clusters),
        total_satellites: LENGTH(nodes),
        total_edges: LENGTH(edges)
    }
}
```

### Frontend: [`./react-app/src/components/GraphExplorer.jsx`](./react-app/src/components/GraphExplorer.jsx)

**New UI Controls** (add to Function Similarity section):
1. **Cluster Display**: Show top clusters as clickable cards/pills:
   ```jsx
   <div className="cluster-list">
     {clusters.map(cluster => (
       <ClusterCard
         key={cluster.cluster_id}
         label={`${cluster.function} (${cluster.orbital_band})`}
         satellites={cluster.satellite_count}
         edges={cluster.edge_count}
         selected={selectedClusters.includes(cluster.cluster_id)}
         onClick={() => toggleCluster(cluster.cluster_id)}
       />
     ))}
   </div>
   ```

2. **Multi-Select Filters**:
   - Function categories (existing, keep)
   - Orbital bands (new): LEO-Polar, LEO-Inclined, MEO, GEO
   - Countries (new): Top 10 countries by satellite count

3. **Filter Logic**:
   - When filters change, request new data from backend
   - Backend returns clusters matching selected criteria
   - Graph updates with real edges from matching clusters

### Frontend: [`./react-app/src/components/GraphViewer.jsx`](./react-app/src/components/GraphViewer.jsx)

**Modified Function**: `loadAllFunctionCategories` (lines 614-688)

**Changes**:
1. Parse cluster metadata from API response
2. Store cluster info in state for display
3. Render edges with existing relationship_type styling:
   - `orbital_proximity`: Use existing proximity styling (color by proximity_score)
   - `constellation_membership`: Use existing constellation styling (blue, solid)
4. Color nodes by function_category (existing logic can be reused)

**No new edge styling needed**: Real edges already have proper styling in lines 147-225

## Data Model / API Changes

### API Response Format Changes

**Before** (empty edges):
```json
{
    "data": {
        "nodes": [...],  // 350 satellites
        "edges": [],     // EMPTY - no edges between functional satellites
        "categories": [...],
        "stats": {
            "nodes_shown": 350,
            "edges_shown": 0  // Problem!
        }
    }
}
```

**After** (multi-dimensional clusters with real edges):
```json
{
    "data": {
        "clusters": [
            {
                "cluster_id": "Communications-LEO-Polar",
                "function": "Communications",
                "orbital_band": "LEO-Polar",
                "satellite_count": 617,
                "proximity_edge_count": 5188,
                "constellation_edge_count": 556,
                "edge_count": 5744,
                "density": 0.031
            },
            {
                "cluster_id": "Navigation-MEO",
                "function": "Navigation",
                "orbital_band": "MEO",
                "satellite_count": 33,
                "proximity_edge_count": 74,
                "constellation_edge_count": 28,
                "edge_count": 102,
                "density": 0.192
            }
        ],
        "nodes": [
            {
                "_id": "satellites/2025-180",
                "identifier": "2025-180",
                "function_category": "Communications",
                "orbital_band": "LEO-Polar",
                "country": "United Kingdom",
                "cluster_id": "Communications-LEO-Polar",
                ...
            }
        ],
        "edges": [
            {
                "id": "proximity_12345",
                "source": "satellites/2025-180",
                "target": "satellites/2025-181",
                "relationship_type": "orbital_proximity",
                "proximity_score": 0.05,
                "orbital_band": "LEO-Polar"
            },
            {
                "id": "constellation_67890",
                "source": "satellites/2025-180",
                "target": "satellites/constellation_hub",
                "relationship_type": "constellation_membership",
                "constellation_name": "OneWeb"
            }
        ],
        "categories": [...],  // Keep for UI
        "stats": {
            "total_clusters": 10,
            "total_satellites": 850,
            "total_edges": 8500,      // Real edges only!
            "avg_cluster_size": 85,
            "avg_edge_count": 850
        }
    }
}
```

### New Query Parameters

Add optional filtering parameters:
```
GET /v2/graphs/function-similarity?
    functions=Communications,Navigation&
    orbital_bands=LEO-Polar,MEO&
    countries=United%20Kingdom,Russian%20Federation&
    limit=50
```

## Edge Management Strategy

### Real Edges Only
All edges come from existing database collections:
- `orbital_proximity`: Physical orbital proximity (apogee/perigee/inclination similarity)
- `constellation_membership`: Organizational relationships

**No synthetic edges are created**. Edge counts reflect actual relationships in the data.

### Cluster Selection Strategy

**Default (Option B)**: Show top 10-15 clusters by edge count
- Displays most connected satellite groups
- Guarantees non-empty, meaningful graphs
- Example: "Communications-LEO-Polar" with 5,744 real edges

**Filtered (Option C)**: Show clusters matching user selections
- User selects: Functions=[Communications], Bands=[LEO-Polar, MEO]
- Backend returns: All clusters matching criteria
- Edges: Only real proximity/constellation edges within those clusters

### Performance Optimization

**Backend**:
- Pre-filter satellites with `function != null AND orbital_band != null`
- Use COLLECT to group efficiently
- Count edges per cluster before loading satellite details
- Return only top N clusters by edge count

**Frontend**:
- Limit initial display to 10-15 clusters (500-1000 satellites)
- Use existing Cytoscape pagination/limiting
- Allow users to expand by selecting more clusters

## Verification Approach

### Manual Testing
1. **Start the application**:
   ```bash
   ./start.sh
   ```

2. **Navigate to Graph Explorer**:
   - Open http://localhost:3000
   - Click "Function Similarity" tab

3. **Verify visualization**:
   - ✅ Graph shows nodes (satellites)
   - ✅ Graph shows edges connecting satellites
   - ✅ Edges are colored by function category
   - ✅ Clear clusters visible for each function
   - ✅ Stats show non-zero edge count

4. **Test filtering**:
   - Click on individual function categories
   - Verify nodes and edges filter correctly
   - Check that stats update properly

### API Testing
```bash
# Test the endpoint directly
curl "http://127.0.0.1:8000/v2/graphs/function-similarity?limit=50" | python3 -m json.tool

# Verify response:
# - data.edges is non-empty
# - data.edges contains relationship_type: "function_similarity"
# - data.stats.edges_shown > 0
```

### Data Validation
1. Check edge count makes sense:
   - For 350 satellites across 7 categories
   - With subclustering by orbital band (3-4 bands per category)
   - Expected: 500-2000 edges

2. Verify edge properties:
   - All edges have `relationship_type`
   - Similarity edges have `function_category`
   - Source and target are both in nodes list

### Frontend Console Checks
Open browser DevTools console and verify:
```javascript
// After graph loads
console.log('[GraphViewer] Function data received:', {
    nodeCount: data.data?.nodes?.length || 0,
    edgeCount: data.data?.edges?.length || 0
})
// Should show edgeCount > 0
```

### No Automated Tests Required
This is a visualization feature without critical business logic. Manual verification is sufficient. The application doesn't appear to have existing graph endpoint tests based on codebase exploration.

## Performance Considerations

### Backend Query Performance
- **Subclustering**: O(n log n) for grouping by category + band
- **Edge generation**: O(k²) where k = avg subcluster size (< 100)
- **Expected query time**: < 500ms for 500 satellites, 2000 edges

### Frontend Rendering Performance
- **Cytoscape.js**: Handles 1000+ nodes and 5000+ edges smoothly
- **Current limit**: 50 satellites per category via API (max ~2000 edges)
- **Layout**: Cola force-directed layout is efficient for this scale

### Potential Issues
- If category has 500+ satellites in same orbital band, use edge sampling
- Monitor API response time; add index on `canonical.function` if needed

## Alternative Approaches Considered

### 1. **Synthetic Similarity Edges** (Rejected)
Create artificial edges between satellites with same function.
- **Pros**: Guaranteed non-empty graphs
- **Cons**: **Not real data** - user requirement to avoid fake edges

### 2. **Single-Dimension Clustering** (Rejected - Doesn't Work)
Show satellites grouped by function only.
- **Pros**: Simple conceptually
- **Cons**: Database analysis shows 0 real edges (proven empty graphs)

### 3. **Hierarchical Filtering Only** (Option A - Considered)
User selects function first, then orbital band/country.
- **Pros**: Clear step-by-step workflow
- **Cons**: Requires multiple clicks to see any graph; poor initial UX

### 4. **Multi-Dimensional Clusters with Real Edges** (Selected)
Show top clusters by (function + orbital_band), allow multi-select filtering.
- **Pros**: Immediate useful visualization, real edges only, flexible filtering
- **Cons**: Slightly more complex initial query
- **Decision**: Combines Option B (top clusters) + Option C (multi-select) for best UX

## Success Criteria

1. ✅ Function Similarity Graph displays visible edges between satellites (real edges only)
2. ✅ Initial display shows top 10-15 clusters pre-computed (e.g., "Communications-LEO-Polar")
3. ✅ Each cluster has non-zero edge count (minimum 10 edges per cluster)
4. ✅ Graph shows clear visual clusters by function + orbital band
5. ✅ Stats display shows actual edge counts (e.g., 5,744 edges for top cluster)
6. ✅ Users can filter by function, orbital band, and country (multi-select)
7. ✅ Filtering updates graph with real edges from selected clusters
8. ✅ Graph renders without performance degradation (<2s for 500-1000 satellites)
9. ✅ No synthetic/fake edges - all edges from database collections
10. ✅ Cluster metadata shows satellite count, edge count, and density

## Risk Assessment

**Low Risk**: Changes are isolated to one endpoint and its frontend rendering logic. No database schema changes. No breaking API changes. Existing functionality unaffected.

**Rollback Plan**: If issues arise, the original query logic can be restored by reverting the single file changes.
