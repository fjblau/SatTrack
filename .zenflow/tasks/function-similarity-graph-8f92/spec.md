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

**Issue**: Satellites with similar functions often don't share constellation membership, registration documents, or orbital proximity. This results in graphs with nodes but **no edges**, making the visualization useless.

### Expected Behavior
A "Function Similarity Graph" should create **synthetic similarity edges** between satellites that share the same function category, independent of existing graph relationships. This would:
- Show clear clusters of satellites by function
- Enable users to understand functional groupings
- Provide meaningful visual structure to the graph

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

### Strategy 1: Synthetic Similarity Edges (Recommended)
Create synthetic edges between satellites that share the same function category. This directly addresses the "similarity" aspect of the graph.

**Backend Changes** ([`./api/routers/graphs.py:1091`](./api/routers/graphs.py:1091)):
1. After categorizing satellites, generate edges between all satellites in the same category
2. Add edge properties:
   - `relationship_type`: `"function_similarity"`
   - `function_category`: The shared category
   - `similarity_score`: 1.0 (perfect similarity within category)
3. **Optimization**: For large categories, limit edges using strategies:
   - **Option A**: Sample pairs (e.g., max 500 edges per category)
   - **Option B**: Create hub-spoke topology (all satellites connect to category hub)
   - **Option C**: Create edges only within subclusters (e.g., by orbital band + function)

**Frontend Changes** ([`./react-app/src/components/GraphViewer.jsx`](./react-app/src/components/GraphViewer.jsx)):
1. Add CSS styling for `function_similarity` edge type (lines 24-304)
2. Style edges by function category with distinct colors:
   - Communications: Blue (#3498db)
   - Earth Observation: Green (#27ae60)
   - Scientific Research: Purple (#9b59b6)
   - Navigation: Orange (#e67e22)
   - Military-Defense: Red (#c0392b)
   - Space Station: Teal (#16a085)
   - Technology-Testing: Yellow (#f39c12)
   - Other: Gray (#95a5a6)

### Strategy 2: Enhanced Existing Edges (Alternative)
Keep existing edges but supplement with cross-category proximity edges and improve visualization.

**Trade-offs**: Less clear representation of functional similarity, still relies on existing graph structure.

### Recommended: Strategy 1 with Option C Subclustering
Create synthetic edges within function + orbital band subclusters. This provides:
- Clear functional groupings
- Manageable edge count (avoids O(n²) explosion)
- Additional dimension of similarity (orbital band)

## Source Code Structure Changes

### Backend: [`./api/routers/graphs.py`](./api/routers/graphs.py)

**Modified Function**: `get_function_similarity_graph` (lines 1092-1230)

**New Query Structure**:
```aql
LET satellites_with_function = (...)  # Existing categorization logic

LET category_stats = (...)  # Existing stats logic

LET limited_satellites = (...)  # Existing limiting logic

# NEW: Generate synthetic similarity edges
LET similarity_edges = FLATTEN(
    FOR sat IN limited_satellites
        COLLECT category = sat.function_category, band = sat.orbital_band INTO group
        LET satellites_in_subcluster = group[*].sat
        
        # Create edges between all pairs in this subcluster
        FOR i IN 0..LENGTH(satellites_in_subcluster)-2
            FOR j IN i+1..LENGTH(satellites_in_subcluster)-1
                RETURN {
                    id: CONCAT(satellites_in_subcluster[i]._id, "_", satellites_in_subcluster[j]._id),
                    source: satellites_in_subcluster[i]._id,
                    target: satellites_in_subcluster[j]._id,
                    relationship_type: 'function_similarity',
                    function_category: category,
                    orbital_band: band,
                    similarity_score: 1.0
                }
)

# OPTIONAL: Keep existing edges for additional context (constellation, registration)
LET constellation_edges = (...)  # Keep existing
LET registration_edges = (...)  # Keep existing
# REMOVE proximity_edges to reduce noise

LET edges = UNION(similarity_edges, constellation_edges, registration_edges)

RETURN {
    nodes: limited_satellites,
    edges: edges,
    categories: category_stats,
    stats: {...}
}
```

### Frontend: [`./react-app/src/components/GraphViewer.jsx`](./react-app/src/components/GraphViewer.jsx)

**Modified Function**: `loadAllFunctionCategories` (lines 614-688)

**Changes**:
1. No structural changes needed; edge styling is declarative
2. Ensure edges are properly passed to Cytoscape (already implemented)

**Modified Styling** (lines 24-304, add new selector):
```javascript
{
    selector: 'edge[relationship_type="function_similarity"]',
    style: {
        'line-color': 'data(category_color)',  // Color by function category
        'width': 2,
        'line-style': 'solid',
        'opacity': 0.6
    }
}
```

**Add Category Color Mapping** (new function):
```javascript
const getCategoryColor = (category) => {
    const colors = {
        'Communications': '#3498db',
        'Earth Observation': '#27ae60',
        'Scientific Research': '#9b59b6',
        'Navigation': '#e67e22',
        'Military-Defense': '#c0392b',
        'Space Station': '#16a085',
        'Technology-Testing': '#f39c12',
        'Other': '#95a5a6'
    }
    return colors[category] || '#95a5a6'
}
```

## Data Model / API Changes

### API Response Format (No Breaking Changes)
The response format remains the same; only edge content changes:

**Before**:
```json
{
    "data": {
        "nodes": [...],
        "edges": [
            // Only constellation/registration/proximity edges (often empty)
        ],
        "categories": [...],
        "stats": {...}
    }
}
```

**After**:
```json
{
    "data": {
        "nodes": [...],
        "edges": [
            {
                "id": "satellites/X_satellites/Y",
                "source": "satellites/X",
                "target": "satellites/Y",
                "relationship_type": "function_similarity",
                "function_category": "Communications",
                "orbital_band": "LEO",
                "similarity_score": 1.0
            },
            // Plus optional constellation/registration edges
        ],
        "categories": [...],
        "stats": {
            "total_with_function": 5000,
            "nodes_shown": 350,
            "edges_shown": 1200,  // Now non-zero!
            "categories_count": 7,
            "similarity_edges": 1000,  // New stat
            "existing_edges": 200       // New stat
        }
    }
}
```

## Edge Count Optimization

### Problem: Quadratic Edge Growth
Creating edges between all pairs in a category results in O(n²) edges:
- Category with 100 satellites → 4,950 edges
- Category with 200 satellites → 19,900 edges

### Solution: Subclustering by Orbital Band
Group satellites by (function_category, orbital_band) before creating edges:
- Communications + LEO: 50 satellites → 1,225 edges
- Communications + MEO: 30 satellites → 435 edges
- Communications + GEO: 20 satellites → 190 edges
- **Total**: 1,850 edges instead of 4,950

### Additional Optimization: Edge Sampling
If subclusters are still large, apply max edges per subcluster:
```aql
# Limit to 500 edges per subcluster
FOR i IN 0..MIN(LENGTH(satellites_in_subcluster)-2, 31)  # √(500*2) ≈ 31
    FOR j IN i+1..LENGTH(satellites_in_subcluster)-1
        LIMIT 500
        RETURN {...}
```

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

### 1. **Hub-Spoke Topology**
Create category hub nodes; all satellites connect to their category hub.
- **Pros**: O(n) edges, very efficient
- **Cons**: Less visually informative, artificial hub nodes

### 2. **Proximity-Only Edges**
Show only orbital proximity edges, color by function.
- **Pros**: Uses real physical relationships
- **Cons**: Doesn't solve "no edges" problem; proximity is unrelated to function

### 3. **Full Mesh Per Category**
Create edges between all pairs in a category (no subclustering).
- **Pros**: Shows all functional relationships
- **Cons**: O(n²) edges, performance issues for large categories

**Decision**: Use subclustering (Strategy 1, Option C) for best balance of informativeness and performance.

## Success Criteria

1. ✅ Function Similarity Graph displays visible edges between satellites
2. ✅ Edges connect satellites within the same function category
3. ✅ Graph shows clear visual clusters for each function
4. ✅ Edge count is non-zero in stats display
5. ✅ Graph renders without performance degradation
6. ✅ Filtering by category works correctly
7. ✅ Edge styling clearly distinguishes function categories

## Risk Assessment

**Low Risk**: Changes are isolated to one endpoint and its frontend rendering logic. No database schema changes. No breaking API changes. Existing functionality unaffected.

**Rollback Plan**: If issues arise, the original query logic can be restored by reverting the single file changes.
