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
