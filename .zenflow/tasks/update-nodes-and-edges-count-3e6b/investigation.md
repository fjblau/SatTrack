# Investigation: Update Nodes and Edges Count

## Bug Summary
When filters change in the Graph Explorer (specifically for Function Similarity and Country Relations graphs), the "Nodes" and "Edges" count displayed in the upper right corner of the graph viewer disappears instead of updating to reflect the filtered graph.

## Root Cause Analysis

### Current Behavior
1. **Initial Graph Load**: When graphs are first loaded via `loadAllFunctionCategories()` or `loadCountryGraph()`, the stats are set from the API response:
   - [./react-app/src/components/GraphViewer.jsx:680](./react-app/src/components/GraphViewer.jsx:680): `setStats(data.data.stats)` 
   - [./react-app/src/components/GraphViewer.jsx:834](./react-app/src/components/GraphViewer.jsx:834): `setStats(data.data.stats)`

2. **Filter Applied**: When filters are applied:
   - `filterFunctionGraph()` ([lines 691-766](./react-app/src/components/GraphViewer.jsx:691)) sets stats to:
     ```javascript
     {
       satellites_shown: filteredNodes.length,
       edges_shown: filteredEdges.length
     }
     ```
   - `filterCountryGraph()` ([lines 845-917](./react-app/src/components/GraphViewer.jsx:845)) sets stats to:
     ```javascript
     {
       countries_shown: filteredNodes.length,
       relationships_found: filteredEdges.length
     }
     ```

3. **UI Display**: The UI renders Nodes and Edges count at [lines 1814-1815](./react-app/src/components/GraphViewer.jsx:1814):
   ```javascript
   {stats.total_nodes !== undefined && <span>Nodes: {stats.total_nodes}</span>}
   {stats.total_edges !== undefined && <span>Edges: {stats.total_edges}</span>}
   ```

### The Problem
The filter functions use different property names (`satellites_shown`, `edges_shown`, `countries_shown`, `relationships_found`) than what the UI looks for (`total_nodes`, `total_edges`). This causes the Nodes and Edges count to disappear when filters are applied.

## Affected Components
- [./react-app/src/components/GraphViewer.jsx](./react-app/src/components/GraphViewer.jsx)
  - `filterFunctionGraph()` function (lines 691-766)
  - `filterCountryGraph()` function (lines 845-917)
  - Stats display UI (lines 1814-1815)

## Proposed Solution
Update both `filterFunctionGraph()` and `filterCountryGraph()` functions to include `total_nodes` and `total_edges` in their stats objects when filtering, so the counts remain visible and accurate:

### For `filterFunctionGraph()`:
```javascript
const newStats = {
  satellites_shown: filteredNodes.length,
  edges_shown: filteredEdges.length,
  total_nodes: filteredNodes.length,  // Add this
  total_edges: filteredEdges.length   // Add this
}
```

### For `filterCountryGraph()`:
```javascript
const newStats = {
  countries_shown: filteredNodes.length,
  relationships_found: filteredEdges.length,
  total_nodes: filteredNodes.length,  // Add this
  total_edges: filteredEdges.length   // Add this
}
```

## Edge Cases Considered
- When filters are cleared (categories/countries = []), the full graph should be shown with accurate counts
- Multiple filter selections should show the count of nodes/edges in the filtered subgraph
- Stats should update in real-time as filters are toggled on/off

## Expected Behavior After Fix
1. When a user selects filter options in the Function Similarity or Country Relations views
2. The graph updates to show only filtered nodes and edges
3. The "Nodes: X" and "Edges: Y" count in the upper right updates to reflect the filtered graph
4. When filters are cleared, the counts update back to show the full graph
