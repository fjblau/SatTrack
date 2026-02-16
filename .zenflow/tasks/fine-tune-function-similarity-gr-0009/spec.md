# Technical Specification: Function Similarity Graph Visualization Improvements

## Complexity Assessment

**Difficulty: Medium**

The task requires improving the visual presentation of the function similarity graph. While the data structure and backend are working correctly, the frontend visualization needs significant refinement to make the graph readable and useful. This involves:
- Adjusting layout algorithms and parameters
- Refining visual styling (node sizes, colors, labels)
- Improving cluster visualization
- Adding interactive features for better navigation

## Problem Analysis

Based on the provided screenshot and codebase review, the function similarity graph has several critical usability issues:

### Current Issues

1. **Too Many Nodes Displayed Initially**: Graph loads with all 15 top clusters simultaneously, showing 100-500+ nodes at once, making it overwhelming and unreadable
2. **Poor Layout Quality**: The cola force-directed layout produces overlapping nodes and unclear cluster separation
3. **Visual Clutter**: All node labels are visible simultaneously, causing severe text overlap
4. **Inadequate Node Sizing**: Fixed 20px nodes are too small for the graph density
5. **Weak Cluster Differentiation**: While nodes are colored by cluster, the spatial layout doesn't respect cluster boundaries
6. **Suboptimal Layout Parameters**: Current settings (nodeSpacing: 50, edgeLength: 100) don't account for the multi-cluster nature of the data
7. **No Default Filtering**: The graph view starts with everything loaded rather than a manageable subset

### Data Structure (from API)

The backend API ([./api/routers/graphs.py:1091-1280](./api/routers/graphs.py:1091-1280)) returns:
- **Clusters**: Grouped by `(function_category, orbital_band)` with metadata
- **Nodes**: Satellites with `cluster_id`, `function_category`, `orbital_band`
- **Edges**: Constellation membership and orbital proximity relationships within clusters
- **Top N**: Only top 15 clusters by edge count are returned

## Technical Context

### Technologies
- **Frontend**: React 19.2.3, Vite 7.2.7
- **Graph Library**: Cytoscape.js 3.33.1
- **Layout Engine**: cytoscape-cola 2.5.1

### Key Files
- **Graph Component**: [./react-app/src/components/GraphViewer.jsx](./react-app/src/components/GraphViewer.jsx)
- **Graph Controls**: [./react-app/src/components/GraphExplorer.jsx](./react-app/src/components/GraphExplorer.jsx)
- **Styles**: [./react-app/src/components/GraphViewer.css](./react-app/src/components/GraphViewer.css)
- **Backend API**: [./api/routers/graphs.py:1091-1280](./api/routers/graphs.py:1091-1280)

### Current Implementation

**Load Function**: [`loadAllFunctionCategories`](./react-app/src/components/GraphViewer.jsx:618-718)
- Fetches data from `/v2/graphs/function-similarity?top_n=15`
- Maps clusters to colors (15 distinct colors)
- Creates cytoscape elements with cluster-based coloring
- Applies default cola layout

**Layout System**: [`applyLayout`](./react-app/src/components/GraphViewer.jsx:1689-1719)
- Supports: cola, circle, grid, concentric
- Cola parameters: `nodeSpacing: 50`, `edgeLength: 100`, `maxSimulationTime: 2000`

**Node Styling**: [./react-app/src/components/GraphViewer.jsx:24-310](./react-app/src/components/GraphViewer.jsx:24-310)
- Default node size: 30px
- Function graph nodes: 20px fixed size
- Labels always visible with outline

## Implementation Approach

### 0. Initial Data Filtering Strategy

**Problem**: Loading all 15 clusters (100-500+ nodes) at once creates an overwhelming, unreadable graph.

**Solution**: Start with a filtered, manageable view by default

**Default View Options** (pick one):

**Option A: Top Clusters Only**
- Load only top 3-5 clusters by default (instead of 15)
- Change `top_n` parameter from 15 to 3-5 initially
- Add "Load More Clusters" button to incrementally show additional clusters
- Show count of hidden clusters in UI

**Option B: Single Function Category**
- Auto-select first function category on initial load
- Show only satellites from one function (e.g., "Communications")
- User can add more categories via sidebar
- Clear visual indication that view is filtered

**Option C: Cluster-by-Cluster Browsing**
- Don't auto-load any graph data initially
- Show prominent message: "Select a cluster to view its satellites"
- User clicks a cluster in sidebar to load just that cluster
- Can select multiple clusters to compare

**Recommendation**: **Option B** - Auto-select first function category
- Provides immediate, useful visualization (not empty)
- Typically 50-150 nodes - manageable for layout algorithm
- Natural extension via existing filter controls
- User can easily add/remove categories

**Implementation Changes for Option B**:
1. Modify `GraphExplorer.jsx`:
   - After loading function categories, auto-select the first category
   - Set `selectedFunctionCategories` to `[functionCategories[0].category]` 
   - Add visual indicator showing active filter (already exists with highlight)

2. Modify `GraphViewer.jsx`:
   - `loadAllFunctionCategories` already respects `selectedFunctionCategories` filter
   - No changes needed - existing logic will handle filtered load

3. Add UI indicator:
   - Show banner/badge: "Showing: Communications only - Select more categories to expand"
   - Add "Clear Filters" button to show all clusters

**Alternative Enhancements** (can combine with above):
- Add "Top N Clusters" dropdown in controls (3, 5, 10, 15, 25)
- Add "Max Satellites" slider to cap total nodes shown
- Implement pagination: "Show Next 5 Clusters"

### 1. Layout Improvements

**Optimize Cola Layout for Clusters**
- Increase `nodeSpacing` to 80-120 for better separation
- Increase `edgeLength` to 150-200 to prevent overlap
- Add cluster-aware `alignment` and `flowLayoutSettings`
- Consider implementing component-based layout (separate clusters first, then internal layout)

**Alternative: Compound Nodes**
- Investigate using Cytoscape compound nodes to represent clusters
- Each cluster becomes a parent node containing satellite child nodes
- Enables better spatial organization and visual hierarchy

### 2. Visual Enhancements

**Node Sizing Strategy**
- Base size: 25-30px (larger than current 20px)
- Scale by edge count: nodes with more connections should be larger
- Formula: `nodeSize = Math.min(40, 25 + (edgeCount * 0.5))`

**Label Management**
- **Hide labels by default** to reduce clutter
- **Show on hover**: Display label when mouse enters node
- **Show on selection**: Keep label visible for selected nodes
- **Configurable toggle**: Add UI control to show/hide all labels

**Cluster Visual Separation**
- Add subtle cluster background (if using compound nodes)
- Increase color saturation/brightness for better distinction
- Add cluster legend showing function-orbital_band combinations

**Edge Styling**
- Reduce edge opacity to 0.3-0.5 to minimize visual noise
- Differentiate constellation vs proximity edges (already exists but may need tuning)
- Consider edge bundling for high-density areas

### 3. Interactive Features

**Hover Interactions**
- Show node label on hover
- Highlight connected nodes
- Display quick info tooltip (function, orbital band, country)

**Click Interactions**
- Select node to keep label visible
- Highlight neighborhood (connected nodes and edges)
- Show detailed panel (already exists via context menu)

**Cluster Interactions**
- Click cluster name in sidebar to highlight all nodes in that cluster
- Add "Focus on Cluster" button to zoom and center on selected cluster

### 4. Performance Considerations

**Graph Rendering**
- Current node count: typically 100-500 nodes (15 clusters)
- Edge count: varies, can be 500-2000+
- Cytoscape can handle this well, but layout computation may be slow
- Consider adding loading indicator during layout calculation

**Layout Caching**
- Consider caching computed positions when switching between graph types
- Store positions in state when user manually arranges nodes

## Source Code Structure Changes

### Files to Modify

1. **[./react-app/src/components/GraphViewer.jsx](./react-app/src/components/GraphViewer.jsx)**
   - Update `loadAllFunctionCategories` function:
     - Modify node size calculation (line 684)
     - Remove default label visibility
     - Add edge count to node data
   - Update `applyLayout` function:
     - Add function-graph-specific layout parameters
     - Implement cluster-aware layout settings
   - Add event handlers:
     - `mouseenter`/`mouseleave` for hover labels
     - `tap` for selection and highlighting
   - Update Cytoscape styles:
     - Hide labels by default for function graph
     - Show labels on `:selected` and new `:hover` class
     - Reduce edge opacity

2. **[./react-app/src/components/GraphViewer.css](./react-app/src/components/GraphViewer.css)**
   - Add styles for cluster legend
   - Add styles for hover tooltips
   - Adjust control panel layout

3. **[./react-app/src/components/GraphExplorer.jsx](./react-app/src/components/GraphExplorer.jsx)**
   - **Auto-select first function category on load** in `loadFunctionCategories`
   - Add filter indicator banner showing active filters
   - Add "Clear Filters / Show All" button
   - Update cluster display to show more metadata
   - Add "Focus" button to cluster items
   - Optionally add label visibility toggle

### No New Files Required

All changes will be made to existing components.

## Data Model / API / Interface Changes

**No backend changes required**. The existing API endpoint provides all necessary data:
- Cluster metadata with `cluster_id`, `function`, `orbital_band`, `satellite_count`, `edge_count`, `density`
- Nodes with `cluster_id` for grouping
- Edges with relationship types

**Frontend State Changes**:
- Add `hoveredNode` state to track current hover
- Add `selectedNodes` state for multi-selection
- Add `showLabels` boolean state for label toggle

## Verification Approach

### Visual Verification
1. Load function similarity graph - **verify only one category is auto-selected**
2. **Verify initial node count is manageable** (50-150 nodes, not 500+)
3. **Verify filter indicator banner** shows active filter
4. Verify nodes are well-spaced with minimal overlap
5. Verify labels are hidden by default
6. Hover over nodes to confirm labels appear
7. Verify cluster colors are distinct and visible
8. Test different layout algorithms (cola, circle, grid)

### Functional Testing
1. **Initial load**: Confirm first function category is auto-selected
2. **Add categories**: Click additional categories, verify graph expands correctly
3. **Clear filters**: Click "Show All" button, verify all clusters load
4. **Filter indicator**: Verify banner accurately reflects active filters
5. Filter by orbital band - verify filtering works
6. Click on node - verify context menu and details panel
7. Test with different cluster counts (top_n parameter if added)
8. Verify performance with filtered view (< 3 seconds)
9. Verify performance with full view (all 15 clusters, may be slower)

### Browser Testing
- Test in Chrome/Edge (primary)
- Test in Firefox
- Test in Safari
- Verify hover/click interactions work consistently

### Accessibility
- Ensure sufficient color contrast for clusters
- Verify keyboard navigation works for controls
- Test with screen readers (basic functionality)

## Risk Assessment

**Low Risk Changes**:
- Node sizing adjustments
- Label visibility changes
- Edge opacity adjustments

**Medium Risk Changes**:
- Layout parameter tuning (may require iteration)
- Hover event handlers (performance consideration)

**High Risk Changes**:
- Compound nodes implementation (significant refactor, may not be needed)

## Success Criteria

1. **Initial view is manageable**: Graph loads with filtered subset (50-150 nodes), not overwhelming
2. **Graph is readable**: Nodes are well-separated with minimal overlap
3. **Clusters are distinguishable**: Clear visual grouping by color and spatial layout
4. **Labels are manageable**: No clutter, visible on hover/selection
5. **Performance is acceptable**: Graph renders and layouts in < 3 seconds
6. **Interactions are smooth**: Hover and click responses are immediate
7. **Filtering is discoverable**: Users understand they can add/remove categories to explore

## Implementation Priority

1. **Critical Priority (Must Have - Fixes Core Issue)**:
   - **Implement default filtering**: Auto-select first function category on load
   - Add filter indicator banner showing active filters
   - Add "Clear Filters / Show All" button

2. **High Priority (Must Have - Improves Readability)**:
   - Optimize cola layout parameters
   - Hide labels by default, show on hover
   - Increase node sizes with edge-based scaling
   - Reduce edge opacity

3. **Medium Priority (Should Have)**:
   - Add cluster highlighting on sidebar click
   - Add neighborhood highlighting on node click
   - Add quick info tooltip on hover
   - Add "Top N Clusters" control (3/5/10/15)

4. **Low Priority (Nice to Have)**:
   - Compound nodes for clusters
   - Label visibility toggle in UI
   - Layout position caching
   - Max satellites slider
