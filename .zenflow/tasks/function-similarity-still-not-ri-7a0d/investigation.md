# Function Similarity Visualization Bug Investigation

## Bug Summary
The Function Similarity graph visualization has poor usability:
- Thick grey/translucent edges create visual clutter and make the graph unreadable
- No labels on nodes (just blue circles)
- No labels on edges to explain relationships
- Styling is inconsistent with the working Satellite Neighborhood visualization

## Root Cause Analysis

### Current Implementation Issues

**Location**: [./react-app/src/components/GraphViewer.jsx:620-718](./react-app/src/components/GraphViewer.jsx:620:718)

The `loadAllFunctionCategories()` function renders the Function Similarity graph but has several critical issues:

1. **Missing Edge Styling** (lines 688-700):
   - Edges are created without `edge_color` or `edge_width` properties
   - This causes edges to use the default style (line 127-138) which has thick grey lines
   - No edge coloring based on relationship type or proximity score

2. **Missing Edge Labels** (lines 688-700):
   - No `edge_label` property is set on edges
   - Users cannot see what the edges represent (constellation membership, registration links, etc.)

3. **Missing Node Labels** (lines 674-687):
   - While `label` property is set, nodes appear as just blue circles in the screenshot
   - The label property references `node.name || node.identifier` which may not exist in the API response

4. **No Edge Type Differentiation**:
   - The code sets `edge_type: edge.relationship_type` but doesn't use it for visual styling
   - Compare with Satellite Neighborhood which uses different colors for different edge types

### Working Reference: Satellite Neighborhood

**Location**: [./react-app/src/components/GraphViewer.jsx:1247-1349](./react-app/src/components/GraphViewer.jsx:1247:1349)

The `renderNeighborhoodGraph()` function demonstrates proper edge styling:

1. **Edge Color Calculation** (lines 1275-1286):
   - `getProximityColor()` function assigns colors based on proximity percentiles
   - Red for closest/dangerous, green for farthest/safest

2. **Edge Labels** (lines 1288-1316):
   - `getEdgeLabel()` generates meaningful labels based on edge type
   - Orbital proximity shows distance in km
   - Constellation edges show constellation name
   - Registration edges show "Registration"

3. **Proper Edge Properties** (lines 1317-1349):
   - Sets `edge_color`, `edge_width`, `edge_label`, `edge_type` for each edge
   - Differentiates edge types visually

## Affected Components

### Primary Files
- [./react-app/src/components/GraphViewer.jsx](./react-app/src/components/GraphViewer.jsx) - `loadAllFunctionCategories()` function

### Related Styles
Cytoscape style definitions (lines 24-310) need to be reviewed to ensure edge styling rules exist for function similarity edges.

## Proposed Solution

### 1. Add Edge Styling Logic
Similar to `renderNeighborhoodGraph()`, create helper functions:
- `getEdgeColorByType()` - assign colors based on relationship_type
- `getEdgeLabelByType()` - create meaningful labels for each edge type
- `getEdgeWidth()` - vary width based on edge importance/weight

### 2. Update Edge Data Mapping
Modify the edge mapping in `loadAllFunctionCategories()` to include:
```javascript
edges: data.data.edges.map(edge => ({
  data: {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    edge_type: edge.relationship_type,
    edge_color: getEdgeColorByType(edge.relationship_type),
    edge_width: getEdgeWidth(edge),
    edge_label: getEdgeLabelByType(edge),
    // ... other properties
  }
}))
```

### 3. Add Cytoscape Style Selectors
Ensure style definitions exist for:
- `edge[edge_type="constellation_membership"]`
- `edge[edge_type="registration_link"]`
- `edge[edge_type="orbital_proximity"]`
- Custom selectors for function similarity edge types

### 4. Fix Node Labels
Verify that the API response includes proper `name` or `identifier` fields. If not, adjust the label mapping or add fallback logic.

## Edge Cases & Considerations

1. **Multiple Edge Types**: Function similarity may have different edge types than neighborhood (e.g., "same function", "same orbital band")
2. **Performance**: Large graphs with many edges may need opacity/alpha on edges to prevent visual clutter
3. **Color Palette**: Ensure colors are distinct from node colors and accessible (colorblind-friendly)
4. **Legend**: May need to update the legend to match new edge styling

## Expected Outcome

After implementing the solution:
- Edges should have distinct colors based on relationship type
- Edge labels should clearly indicate what each connection represents
- Node labels should be visible on all satellites
- Visual style should match Satellite Neighborhood for consistency
- Overall graph should be readable with clear visual hierarchy

---

## Implementation Notes

### Changes Made

**File**: [./react-app/src/components/GraphViewer.jsx](./react-app/src/components/GraphViewer.jsx)

Modified the `loadAllFunctionCategories()` function (lines 662-746) to add edge styling logic matching the Satellite Neighborhood pattern:

1. **Added Edge Color Logic** (lines 673-686):
   - Calculate percentiles for orbital proximity edges (p25, p50, p75)
   - `getProximityColor()` function assigns colors based on proximity score:
     - Red (#e74c3c) for closest satellites (score ≤ p25)
     - Orange (#e67e22) for moderately close (p25 < score ≤ p50)
     - Light green (#2ecc71) for moderately far (p50 < score ≤ p75)
     - Dark green (#27ae60) for farthest satellites (score > p75)

2. **Added Edge Label Logic** (lines 688-699):
   - `getEdgeLabel()` function creates meaningful labels:
     - Orbital proximity: displays proximity score (e.g., "0.85")
     - Constellation membership: displays constellation name
     - Registration links: displays "Registration"

3. **Added Edge Width Logic** (lines 701-707):
   - `getEdgeWidth()` function varies width based on proximity:
     - Closer satellites (lower scores) get thicker lines (2-6px)
     - Default width of 2.5px for other edge types

4. **Updated Edge Data Mapping** (lines 724-745):
   - Added `edge_width` property to all edges
   - Added `edge_label` property when label exists
   - Added `edge_color` property for orbital proximity edges
   - Existing Cytoscape styles (lines 209-230) already support these properties

### Test Results

- Dev server started successfully without errors
- Changes follow the same pattern as the working Satellite Neighborhood visualization
- Cytoscape style definitions already exist for `edge[edge_type="orbital_proximity"]`, `edge[edge_type="constellation_membership"]`, and `edge[edge_type="registration_links"]`

### Manual Testing Required

User should verify:
1. Function Similarity graph now shows colored edges instead of grey
2. Edge labels are visible (proximity scores, constellation names, "Registration")
3. Node labels are visible on all satellites
4. Visual style matches Satellite Neighborhood
5. Graph is readable with proper visual hierarchy
