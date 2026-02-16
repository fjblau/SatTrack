# Spec and build

## Configuration
- **Artifacts Path**: {@artifacts_path} → `.zenflow/tasks/{task_id}`

---

## Agent Instructions

Ask the user questions when anything is unclear or needs their input. This includes:
- Ambiguous or incomplete requirements
- Technical decisions that affect architecture or user experience
- Trade-offs that require business context

Do not make assumptions on important decisions — get clarification first.

---

## Workflow Steps

### [x] Step: Technical Specification
<!-- chat-id: 7ddd772e-bbcd-431f-91bd-000ac07c5fab -->

**Completed**: Technical specification created at `.zenflow/tasks/function-similarity-graph-8f92/spec.md`

**Difficulty Assessment**: Medium

**Root Cause Identified**: The Function Similarity Graph shows satellites grouped by function alone, but function-only grouping produces **0 real edges** (proven via database analysis). Satellites need multi-dimensional clustering (function + orbital band) to have real proximity/constellation edges.

**Data Analysis Results**:
- Communications + LEO-Polar: 617 satellites, **5,188 real proximity edges**
- Navigation + MEO: 33 satellites, **74 real proximity edges**
- Single function dimension: 100 satellites, **0 edges**

**Solution**: Multi-dimensional clustering (function + orbital band + country) showing only real edges:
- **Option B**: Pre-compute top 10-15 clusters by edge count (initial display)
- **Option C**: Multi-select filtering (function, orbital band, country)
- **No synthetic edges**: All edges from existing database relationships

---

### [x] Step: Backend - Multi-Dimensional Cluster Query
<!-- chat-id: c7ff7b84-c19a-4397-a165-6ac014d01ae8 -->

Modify the `/v2/graphs/function-similarity` endpoint to compute and return multi-dimensional clusters with real edges.

**Files to modify**:
- `./api/routers/graphs.py` (lines 1091-1230, function `get_function_similarity_graph`)

**Implementation details**:
1. Pre-filter satellites: `function != null AND orbital_band != null`
2. Group by (function_category, orbital_band) using COLLECT
3. For each cluster, count real edges:
   - Query `orbital_proximity` edges where both endpoints in cluster
   - Query `constellation_membership` edges where both endpoints in cluster
4. Filter clusters: `satellite_count >= 5 AND edge_count >= 10`
5. Sort by edge_count DESC, return top 15 clusters
6. Return cluster metadata + all nodes/edges from selected clusters
7. Add query parameters for filtering:
   - `functions`: comma-separated function categories
   - `orbital_bands`: comma-separated orbital bands  
   - `countries`: comma-separated countries

**Response structure**:
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
      }
    ],
    "nodes": [...],  // Satellites from clusters
    "edges": [...],  // Real proximity/constellation edges
    "stats": {...}
  }
}
```

**Verification**:
- Test endpoint: `curl "http://127.0.0.1:8000/v2/graphs/function-similarity"`
- Verify clusters array has 10-15 entries
- Verify edges array is non-empty (expect 5000-10000 edges)
- Verify each cluster has edge_count >= 10
- Test with filters: `?functions=Communications&orbital_bands=LEO-Polar`

---

### [x] Step: Frontend - Cluster Display and Multi-Select Filtering
<!-- chat-id: 6b5afaa1-1d87-48f6-b197-a869e72ef6b9 -->

Update the UI to display cluster metadata and allow multi-dimensional filtering.

**Files to modify**:
- `./react-app/src/components/GraphExplorer.jsx` (function similarity section)
- `./react-app/src/components/GraphViewer.jsx` (loadAllFunctionCategories function)

**Implementation details**:

**GraphExplorer.jsx**:
1. Add state for orbital bands and cluster selections
2. Add UI controls above graph:
   - Cluster pills/cards showing "Communications (LEO-Polar) - 617 sats, 5744 edges"
   - Orbital band checkboxes: LEO-Polar, LEO-Inclined, MEO, GEO
   - Keep existing function category checkboxes
   - Optional: Add country multi-select
3. On filter change, call API with selected dimensions
4. Pass cluster data to GraphViewer

**GraphViewer.jsx**:
1. Parse `clusters` array from API response
2. Store cluster metadata in component state
3. Render nodes with `cluster_id` property for coloring
4. Edges already styled correctly (orbital_proximity, constellation_membership)
5. Update stats display to show cluster count

**Verification**:
- Start application: `./start.sh`
- Navigate to Function Similarity tab
- Verify cluster pills/cards display with satellite/edge counts
- Click cluster pill → graph updates with that cluster
- Select orbital band filter → clusters update
- Select multiple function categories → see combined clusters
- Check stats show correct cluster/edge counts

---

### [x] Step: Manual Testing and Verification
<!-- chat-id: fc521ee0-40a5-4868-a23b-2629384282a6 -->

Perform end-to-end testing of the multi-dimensional clustering feature.

**Test scenarios**:

1. **Initial Load (Option B)**:
   - Graph shows top 10-15 clusters automatically
   - Cluster metadata displays: "Communications (LEO-Polar) - 617 satellites, 5744 edges"
   - Graph has visible nodes and edges (non-empty)
   - Stats show: "10 clusters, 850 satellites, 8500 edges"

2. **Cluster Selection**:
   - Click cluster pill to highlight/select
   - Graph focuses on that cluster
   - Edge count matches cluster metadata
   - Multiple cluster selection shows union

3. **Multi-Dimensional Filtering (Option C)**:
   - Select function: Communications
   - Select orbital bands: LEO-Polar, MEO
   - Graph shows only matching clusters
   - Unselect filters → return to top clusters view

4. **Real Edges Validation**:
   - Verify edges are orbital_proximity (colored by proximity score) or constellation_membership (blue)
   - NO synthetic/fake edges present
   - Edge count matches database query results

5. **Performance**:
   - Graph renders within 2 seconds
   - 500-1000 satellites render smoothly
   - Filtering updates within 1 second
   - No browser console errors

**Verification checklist**:
- [ ] Top clusters display on initial load
- [ ] Cluster metadata shows satellite/edge counts
- [ ] Graph has non-zero real edges
- [ ] Multi-select filtering works (function + orbital band)
- [ ] No synthetic edges present
- [ ] Stats accurate (cluster count, edge count)
- [ ] Performance acceptable (<2s render)
- [ ] No console errors

**Report creation**:
- Document findings in `.zenflow/tasks/function-similarity-graph-8f92/report.md`
- Include cluster statistics from testing
- Note most connected clusters found
- List any edge cases or future improvements
