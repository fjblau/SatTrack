# Technical Specification: Rethink Function Similarity Graph

## Task Difficulty: **Medium**

The task requires architectural analysis and UX redesign rather than complex algorithmic work, but involves multiple components (backend API, frontend visualization, data analysis) and requires careful consideration of trade-offs.

---

## 1. Current Implementation Analysis

### 1.1 Backend Implementation
**File**: [`./api/routers/graphs.py:1091-1280`](./api/routers/graphs.py:1091:1280)

**Endpoint**: `GET /v2/graphs/function-similarity`

**Algorithm**:
1. Categorizes satellites by pattern-matching their `function` field into 7 categories:
   - Communications, Earth Observation, Scientific Research, Navigation, Military-Defense, Space Station, Technology-Testing
2. Creates clusters grouped by `(function_category, orbital_band)` pairs
3. Filters clusters to only include those with:
   - ≥ 5 satellites AND
   - ≥ 10 edges (constellation membership or orbital proximity)
4. Ranks clusters by edge count and returns top N (default: 15)
5. Returns all individual satellites and edges within selected clusters

### 1.2 Frontend Implementation
**Files**: 
- [`./react-app/src/components/GraphViewer.jsx:645-828`](./react-app/src/components/GraphViewer.jsx:645:828) (loadAllFunctionCategories)
- [`./react-app/src/components/GraphExplorer.jsx:320-410`](./react-app/src/components/GraphExplorer.jsx:320:410) (UI controls)

**Visualization**:
- Uses Cytoscape.js with Cola force-directed layout
- Displays individual satellites as nodes (colored by cluster)
- Shows actual edges between satellites
- Labels hidden by default, visible on hover
- Allows filtering by function categories and orbital bands
- Currently requests `top_n=5` clusters from the API

### 1.3 Identified Problems

#### Problem 1: Too Many Nodes
Even with `top_n=5` clusters, each cluster contains 5-100+ satellites, resulting in hundreds of nodes on screen simultaneously.

#### Problem 2: Many Disconnected Nodes
- Clusters are defined by shared attributes (function + orbital band), not by connectivity
- Satellites within a cluster may have few or no edges to other satellites in that cluster
- Results in many isolated nodes or small disconnected components

#### Problem 3: Unclear Labeling
- Node labels (satellite names) hidden by default to reduce clutter
- Only visible on hover, making it hard to identify specific satellites
- No clear indication of what each cluster represents at a glance

#### Problem 4: Poor Visualization
- Cola layout struggles with large, sparse graphs
- Many overlapping nodes and crossing edges
- No visual hierarchy or grouping by cluster
- Difficult to identify patterns or insights

#### Problem 5: Questionable Value Proposition
The fundamental question: **Does "function similarity" as a graph visualization provide meaningful insights?**

Current approach groups satellites by function+orbital_band but doesn't show:
- How satellites with similar functions actually interact or relate
- Whether there are meaningful patterns in the network structure
- Clear actionable insights for users

---

## 2. Root Cause Analysis

### 2.1 Conceptual Mismatch
The current implementation conflates two different concepts:
1. **Attribute-based clustering**: Grouping satellites by shared properties (function, orbital band)
2. **Network-based analysis**: Analyzing connectivity patterns between satellites

These don't necessarily align:
- Satellites with the same function may never interact (different orbits, different countries)
- High connectivity within a cluster is not guaranteed

### 2.2 Sparse Graph Problem
The satellite network is inherently sparse for function-based views:
- Constellation edges only connect satellites within the same constellation (often different functions)
- Proximity edges only connect satellites in similar orbits (may or may not have similar functions)
- Registration edges connect satellites to documents (not satellite-to-satellite)

Result: Function-based clustering produces many small, disconnected components.

### 2.3 Scale Problem
Showing individual satellites doesn't scale:
- 5 clusters × 50 satellites/cluster = 250+ nodes
- Cola layout becomes unreadable at this scale
- Users can't identify patterns or navigate effectively

---

## 3. Proposed Solutions

### Option 1: Aggregate Cluster View (Recommended)
**Concept**: Show clusters as single aggregate nodes instead of individual satellites

**Implementation**:
- Display each cluster as one node (size = satellite count, color = function category)
- Show inter-cluster edges (count of satellites with connections between clusters)
- Allow drill-down: clicking a cluster shows satellites within that cluster
- Two-level navigation: overview → detail

**Pros**:
- ✅ Scales well (15 cluster nodes vs 500+ satellite nodes)
- ✅ Clear hierarchy and organization
- ✅ Easy to identify patterns in function relationships
- ✅ Maintains ability to drill into details
- ✅ Familiar pattern (used by GitHub network graphs, Gephi, etc.)

**Cons**:
- ⚠️ Requires new API endpoint or modified response format
- ⚠️ Two-step interaction to see individual satellites

**Effort**: Medium (2-3 days)

---

### Option 2: Matrix/Heatmap View
**Concept**: Replace graph with an interactive matrix showing function category relationships

**Implementation**:
- Rows/columns: function categories
- Cell color: connection strength (edge count, density, proximity score)
- Click cell to show details of satellites connecting those functions
- Include orbital band as third dimension (filters or small multiples)

**Pros**:
- ✅ Excellent for dense relationship data
- ✅ No overlapping nodes/edges
- ✅ Easy to compare all pairs of functions
- ✅ Works well with sparse data (empty cells are informative)

**Cons**:
- ⚠️ Different mental model (not a network graph)
- ⚠️ Requires new component (d3.js or similar)
- ⚠️ Less intuitive for exploring network structure

**Effort**: Medium (3-4 days)

---

### Option 3: Statistical Summary View
**Concept**: Replace graph with tables, charts, and statistics

**Implementation**:
- Show function category statistics (satellite counts, density, top countries)
- Bar charts showing connections between functions
- Top clusters ranked by various metrics (density, satellite count, edge count)
- Filterable table of satellites with their function categories

**Pros**:
- ✅ Fast to implement (reuse existing table components)
- ✅ Clear, actionable information
- ✅ No visualization scalability issues
- ✅ Easy to export/analyze data

**Cons**:
- ⚠️ Not a graph visualization (doesn't meet original intent)
- ⚠️ Less engaging visually
- ⚠️ Misses network topology insights (if they exist)

**Effort**: Low (1-2 days)

---

### Option 4: Improved Force-Directed Layout
**Concept**: Keep current approach but fix visualization issues

**Implementation**:
- Use compound nodes to group satellites by cluster visually
- Implement better layout (force-atlas2, d3-force with custom forces)
- Add cluster labels and boundaries
- Reduce default `top_n` to 2-3 clusters
- Only show satellites with ≥2 edges (remove disconnected nodes)
- Implement search/highlight functionality

**Pros**:
- ✅ Minimal API changes
- ✅ Preserves network visualization approach
- ✅ Incremental improvement

**Cons**:
- ⚠️ May still be cluttered with many nodes
- ⚠️ Doesn't solve fundamental sparse graph problem
- ⚠️ Limited scalability improvements

**Effort**: Medium (2-3 days)

---

### Option 5: Remove Feature
**Concept**: Remove Function Similarity graph if it doesn't provide value

**Implementation**:
- Remove "Function Similarity" tab from GraphExplorer
- Remove `/v2/graphs/function-similarity` endpoint
- Keep underlying data for potential future use

**Pros**:
- ✅ Simplifies codebase
- ✅ Removes confusing/non-useful feature
- ✅ Fastest solution

**Cons**:
- ⚠️ Removes potentially useful concept
- ⚠️ Doesn't explore alternatives
- ⚠️ May frustrate users who use the feature

**Effort**: Very Low (0.5 days)

---

## 4. Recommendation

### Primary Recommendation: **Option 1 (Aggregate Cluster View)**

**Reasoning**:
1. **Addresses root causes**: Solves scale problem while preserving network visualization concept
2. **Clear value proposition**: Users can see high-level function relationships, then drill down for details
3. **Scalable**: Works with any number of clusters
4. **Familiar pattern**: Similar to other successful network visualization tools
5. **Moderate effort**: Achievable in 2-3 days

### Alternative Recommendation: **Option 3 (Statistical Summary)**

If the user wants **faster delivery** or determines that network visualization doesn't fit the use case.

### Not Recommended: **Option 5 (Remove Feature)**

Should only be considered if:
- User confirms the feature has no usage/value
- Time constraints prevent proper solution
- After attempting Option 1 and determining insufficient data patterns exist

---

## 5. Detailed Design for Option 1 (Aggregate Cluster View)

### 5.1 API Changes

**New Query Parameter** for `/v2/graphs/function-similarity`:
- `view_mode`: `"aggregate"` (default) or `"detailed"`

**When `view_mode="aggregate"`**:
Return cluster-level graph:
```json
{
  "data": {
    "nodes": [
      {
        "id": "Communications-LEO-Polar",
        "type": "cluster",
        "function": "Communications",
        "orbital_band": "LEO-Polar",
        "satellite_count": 234,
        "edge_count": 456,
        "density": 0.023,
        "avg_congestion_risk": "medium",
        "top_countries": ["USA", "China"],
        "top_constellations": ["Starlink", "OneWeb"]
      }
    ],
    "edges": [
      {
        "id": "Communications-LEO-Polar_to_Earth-Observation-LEO-Polar",
        "source": "Communications-LEO-Polar",
        "target": "Earth-Observation-LEO-Polar",
        "connection_count": 45,
        "edge_types": ["orbital_proximity", "constellation_membership"],
        "avg_proximity_score": 0.8
      }
    ],
    "stats": { ... }
  }
}
```

**When `view_mode="detailed"` and `cluster_id` parameter provided**:
Return current detailed view for a single cluster.

### 5.2 Frontend Changes

**GraphViewer.jsx**:
1. Add new function `loadFunctionGraphAggregateView()`
2. Modify cluster node rendering with:
   - Larger node size (based on satellite count)
   - Tooltip showing cluster statistics
   - Double-click to drill down
3. Add back button when in drill-down mode

**GraphExplorer.jsx**:
1. Update UI to show cluster list instead of function category list
2. Add toggle for aggregate vs detailed view
3. Show cluster statistics in sidebar

### 5.3 Layout Strategy

For aggregate view:
- Use **Cola** or **Cose-Bilkent** layout (good for small graphs)
- Apply compound node positioning if grouping by function category

For detailed view (drill-down):
- Use current force-directed approach
- Show only satellites from selected cluster

---

## 6. Implementation Plan (for Option 1)

### Step 1: Backend - Aggregate API Response
- Modify `/v2/graphs/function-similarity` to support `view_mode` parameter
- Implement cluster-level aggregation logic
- Calculate inter-cluster connection counts
- Test with various filter combinations

### Step 2: Frontend - Aggregate Visualization  
- Implement `loadFunctionGraphAggregateView()` in GraphViewer
- Create cluster node rendering with enhanced tooltips
- Implement drill-down interaction (double-click)
- Add breadcrumb/back navigation

### Step 3: UI Enhancement
- Update GraphExplorer sidebar for cluster browsing
- Add view mode toggle (aggregate/detailed)
- Improve cluster statistics display
- Add legends for node colors and edge types

### Step 4: Testing & Refinement
- Manual testing across different filters
- Performance testing with large datasets
- UX refinement based on interaction patterns
- Documentation updates

---

## 7. Files to Modify

### Backend
- [`./api/routers/graphs.py`](./api/routers/graphs.py) (lines 1091-1280)

### Frontend
- [`./react-app/src/components/GraphViewer.jsx`](./react-app/src/components/GraphViewer.jsx)
  - Modify `loadAllFunctionCategories()` (lines 645-828)
  - Add new aggregate view function
- [`./react-app/src/components/GraphExplorer.jsx`](./react-app/src/components/GraphExplorer.jsx)
  - Update sidebar UI (lines 320-410)
  - Add view mode controls
- [`./react-app/src/config/constants.js`](./react-app/src/config/constants.js)
  - Add configuration for aggregate view

### Styling (if needed)
- `./react-app/src/components/GraphViewer.css`
- `./react-app/src/components/GraphExplorer.css`

---

## 8. Verification Approach

### Manual Testing
1. Load aggregate view and verify cluster nodes render correctly
2. Test drill-down interaction on each cluster
3. Test filtering by function categories and orbital bands
4. Verify statistics are accurate
5. Test edge cases (empty clusters, single-node clusters)

### Backend Testing
- Verify aggregate query returns correct cluster counts
- Test inter-cluster edge calculations
- Validate filter combinations

### Frontend Testing  
- Test interaction flows (aggregate → detail → back)
- Verify layout rendering at different screen sizes
- Test performance with maximum number of clusters

### Linting & Type Checking
```bash
# Frontend
cd react-app
npm run lint
npm run build

# Backend (if available)
ruff check api/routers/graphs.py
mypy api/routers/graphs.py
```

---

## 9. Open Questions for User

Before proceeding with implementation, please clarify:

1. **Which solution do you prefer?**
   - Option 1 (Aggregate Cluster View) - Recommended
   - Option 2 (Matrix/Heatmap View)
   - Option 3 (Statistical Summary)
   - Option 4 (Improved Current Layout)
   - Option 5 (Remove Feature)
   - Other approach?

2. **What insights are users hoping to gain from Function Similarity?**
   - Understanding which function categories co-occur?
   - Finding satellites with similar missions?
   - Analyzing orbital band usage by function?
   - Other use cases?

3. **Is there existing user feedback about this feature?**
   - Usage analytics?
   - Complaints or confusion?
   - Feature requests?

4. **What's the priority/timeline?**
   - Quick fix (Option 3 or 5)
   - Proper solution (Option 1 or 2)
   - Exploratory/research mode (try multiple approaches)

---

## 10. Alternative Approaches Considered

### Network-Based Clustering
Instead of attribute-based clustering, use community detection algorithms (Louvain, Label Propagation) to find naturally connected groups, then analyze their function composition.

**Issue**: This reverses the problem - shows communities first, functions second. May not answer "which functions are related" directly.

### Ego Network View
Show network from perspective of a selected satellite, highlighting function categories of neighbors.

**Issue**: Too specific, doesn't give overview of function relationships.

### Time-Series Animation
Show how function similarity evolves over time (by launch year).

**Issue**: Adds complexity without solving current visualization problems.

---

## 11. Success Metrics

After implementation, success can be measured by:
- **Clarity**: Can users understand the visualization within 30 seconds?
- **Performance**: Does it load and render smoothly (<2s)?
- **Scalability**: Does it work with 20+ clusters without degradation?
- **Insight**: Can users answer "which functions are related?" easily?
- **Engagement**: Do users interact with the feature more/less than before?

---

## 12. Technical Context

### Languages & Frameworks
- **Backend**: Python 3.11, FastAPI
- **Frontend**: React 19.2.3, Vite 7.2.7
- **Visualization**: Cytoscape.js 3.x with Cola layout
- **Database**: ArangoDB (graph database)

### Dependencies
- Backend: `database/connection.py`, `database/graph_analytics.py`
- Frontend: `cytoscape`, `cytoscape-cola`

### Data Model
- Nodes: Satellites (collection: `satellites`)
- Edges: 
  - `constellation_membership` (satellite → constellation hub)
  - `orbital_proximity` (satellite → satellite, based on orbit similarity)
  - `registration_links` (satellite → registration document)

---

## Summary

The Function Similarity graph suffers from fundamental scalability and clarity issues due to showing too many individual satellites in sparse, attribute-based clusters. **Option 1 (Aggregate Cluster View)** provides the best balance of clarity, scalability, and value by showing cluster-level relationships with drill-down capability. This requires moderate effort (2-3 days) and addresses all four identified problems while preserving the network visualization concept.
