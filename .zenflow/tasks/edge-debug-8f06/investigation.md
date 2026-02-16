# Bug Investigation: Detached Nodes in Satellite Neighborhood View

## Bug Summary

When viewing the PRETTY satellite in the Satellite Neighborhood view and reducing the "Max Proximity Score" filter, nodes appear detached from the main PRETTY satellite node. These detached nodes should not be visible if they don't meet the proximity score threshold.

## Root Cause Analysis

### Location
**File**: [`./react-app/src/components/SatelliteNeighborhood.jsx`](./react-app/src/components/SatelliteNeighborhood.jsx)  
**Function**: `applyFilters` (lines 73-121)

### The Problem

The bug occurs in the edge filtering logic at line 82:

```javascript
if (edge.type !== 'orbital_proximity') return true
```

This line keeps **ALL** non-orbital_proximity edges (constellation_membership, registration_links) regardless of whether their connected nodes passed the proximity filter.

### Current Filter Flow (Broken)

1. Filter `orbital_proximity` edges based on proximity score threshold
2. **Keep ALL non-orbital_proximity edges unconditionally** ← Bug here
3. Build a set of `connectedNodeIds` from ALL remaining edges (including non-proximity edges)
4. Keep nodes that are either `is_source` OR have their ID in `connectedNodeIds`

### Why Detached Nodes Appear

When a user reduces the Max Proximity Score:
- Satellite A's `orbital_proximity` edge to PRETTY gets filtered out (doesn't meet threshold)
- But Satellite A's `constellation_membership` edge to PRETTY remains
- Satellite A appears in `connectedNodeIds` and is displayed
- **Result**: Satellite A appears "detached" because its visual proximity edge was filtered out, but it's still connected via constellation membership

### Example Scenario

```
PRETTY ----[orbital_proximity: score=3.0]---- Satellite A
       ----[constellation_membership]--------
```

When user sets `maxProximityScore = 2.0`:
- Orbital proximity edge filtered out (score 3.0 > 2.0)
- Constellation edge remains
- Satellite A still rendered but appears detached (no visible orbital proximity line)

## Affected Components

- **Primary**: [`SatelliteNeighborhood.jsx`](./react-app/src/components/SatelliteNeighborhood.jsx:73-121) - `applyFilters` function
- **Data Flow**: Affects graph visualization when proximity filters are applied with multiple edge types present

## Proposed Solution

### Option 1: Filter Nodes First, Then Edges (Recommended)

The filtering should work in two passes:

1. **First Pass**: Identify valid nodes based on orbital proximity edges
   - Start with source satellite
   - Add nodes connected via orbital_proximity edges that meet all filter criteria
   
2. **Second Pass**: Include edges
   - Keep orbital_proximity edges that meet filter criteria
   - Keep non-orbital_proximity edges ONLY if both endpoints are valid nodes from Pass 1

### Implementation Strategy

```javascript
const applyFilters = (data, filters = null) => {
  const activeFilters = filters || proximityFilters
  
  // Pass 1: Identify valid nodes via orbital proximity
  const validNodeIds = new Set()
  const sourceNode = data.nodes.find(n => n.is_source)
  if (sourceNode) {
    validNodeIds.add(sourceNode.id || sourceNode._id)
  }
  
  // Add nodes connected by valid orbital_proximity edges
  data.edges.forEach(edge => {
    if (edge.type === 'orbital_proximity') {
      // Check proximity filters
      if (meetsProximityFilters(edge, activeFilters)) {
        validNodeIds.add(edge.source || edge._from)
        validNodeIds.add(edge.target || edge._to)
      }
    }
  })
  
  // Pass 2: Filter edges - keep only if both endpoints are valid
  const filteredEdges = data.edges.filter(edge => {
    const source = edge.source || edge._from
    const target = edge.target || edge._to
    
    // Both endpoints must be valid nodes
    if (!validNodeIds.has(source) || !validNodeIds.has(target)) {
      return false
    }
    
    // For orbital_proximity edges, also check filter criteria
    if (edge.type === 'orbital_proximity') {
      return meetsProximityFilters(edge, activeFilters)
    }
    
    return true
  })
  
  // Filter nodes to only valid ones
  const filteredNodes = data.nodes.filter(node => 
    validNodeIds.has(node.id || node._id)
  )
  
  const filteredData = {
    ...data,
    nodes: filteredNodes,
    edges: filteredEdges
  }
  
  setNeighborhoodData(filteredData)
  if (onNeighborhoodLoad) {
    onNeighborhoodLoad(filteredData, selectedSatellite)
  }
}
```

### Edge Cases Considered

1. **Source satellite always visible**: Source node should always be included regardless of filters
2. **Isolated source node**: If all proximity edges are filtered out, only source node should remain
3. **Multi-hop paths**: Nodes reachable via valid proximity edges at any depth should be included
4. **Missing edge properties**: Handle null/undefined values in edge properties gracefully
5. **Multiple edge types between same nodes**: Keep non-proximity edges only if proximity edge is also valid

## Expected Behavior After Fix

- When Max Proximity Score is reduced, only satellites with orbital proximity edges meeting the threshold remain visible
- Non-orbital_proximity edges (constellation, registration) are only shown between satellites that are already visible via valid orbital proximity connections
- No "floating" or "detached" nodes appear in the visualization
- Source satellite (PRETTY) always remains visible

## Testing Recommendations

1. Load PRETTY satellite neighborhood view
2. Verify all nodes have visible connections at maximum filter values
3. Gradually reduce Max Proximity Score
4. Confirm no detached nodes appear at any filter value
5. Test with different edge type combinations enabled/disabled
6. Verify source satellite always remains visible
