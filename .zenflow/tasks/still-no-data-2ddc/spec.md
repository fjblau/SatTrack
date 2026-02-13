# Technical Specification: Graph Data Not Displaying

## Problem Statement

Multiple graph views in the application are not displaying any data. The affected views are:
- **Centrality Analysis**
- **Collision Risks**  
- **Satellite Lineage**
- **Communities**
- **Graph Evolution**

The screenshot shows these views as menu items in the "Path Finder" panel, but clicking them results in blank/empty graphs with no visualization.

## Complexity Assessment

**Difficulty:** Medium

This is a data integration and rendering issue involving:
- Multiple graph visualization components
- Frontend-backend data contract mismatches
- Missing prop passing between components
- Potential API response handling issues

## Technical Context

### Language & Framework
- **Frontend:** React 19.2.3 with Cytoscape.js for graph visualization
- **Backend:** Python FastAPI with ArangoDB graph database
- **Build Tool:** Vite 7.2.7

### Key Components
- [`GraphExplorer.jsx`](./react-app/src/components/GraphExplorer.jsx) - Main container managing graph type selection
- [`GraphViewer.jsx`](./react-app/src/components/GraphViewer.jsx) - Cytoscape.js graph rendering engine
- [`CentralityView.jsx`](./react-app/src/components/CentralityView.jsx) - Centrality analysis control panel
- [`CollisionRiskView.jsx`](./react-app/src/components/CollisionRiskView.jsx) - Collision risk control panel
- [`EvolutionTimelineView.jsx`](./react-app/src/components/EvolutionTimelineView.jsx) - Graph evolution timeline (has its own rendering)
- [`api/routers/graphs.py`](./api/routers/graphs.py) - Backend API endpoints

### API Endpoints
All endpoints are under `/v2/graphs/`:
- `GET /analytics/centrality` - Returns centrality metrics
- `GET /collision-risks/network/graph` - Returns collision risk network
- `GET /collision-risks/clusters` - Returns collision risk clusters
- `GET /lineage/{satellite_id}` - Returns satellite lineage tree
- `GET /communities` - Returns detected communities
- `GET /evolution/timeline` - Returns temporal graph evolution data

## Root Cause Analysis

### Issue 1: Communities Graph - Data Structure Mismatch

**Location:** [`GraphViewer.jsx:865-923`](./react-app/src/components/GraphViewer.jsx:865-923)

**Problem:** The frontend expects `data.data.communities` to be an array of community objects with a `members` array, but the actual structure may differ.

**Backend Response Structure (from `graphs.py:2259-2268`):**
```json
{
  "data": {
    "communities": [
      {
        "community_id": "string",
        "size": 10,
        "members": [
          {
            "satellite_id": "satellites/12345",
            "satellite_name": "GPS-III-01",
            "identifier": "...",
            "orbital_band": "MEO",
            "country": "USA"
          }
        ]
      }
    ],
    "algorithm": "label_propagation",
    "stats": { ... }
  }
}
```

**Frontend Expectation (GraphViewer.jsx:873-900):**
The code properly expects this structure but may fail if:
- API returns empty communities array
- Members array is missing or malformed
- API endpoint returns an error that's not caught

### Issue 2: Lineage Graph - Missing Satellite Selection

**Location:** [`GraphExplorer.jsx:321-329`](./react-app/src/components/GraphExplorer.jsx:321-329), [`GraphViewer.jsx:292-299`](./react-app/src/components/GraphViewer.jsx:292-299)

**Problem:** The Lineage view requires a `selectedSatellite` prop to load data, but GraphExplorer never provides this prop.

**Current Flow:**
1. User clicks "Satellite Lineage" button → `graphType` set to `'lineage'`
2. GraphExplorer renders GraphViewer with `graphType='lineage'` but NO `selectedSatellite` prop
3. GraphViewer shows message: "Select a satellite from the data table to view its lineage"
4. User has no way to select a satellite from the graph view interface

**Expected Flow:**
Lineage should either:
- Allow satellite selection from within the graph view panel
- Auto-load a default satellite
- Show a proper UI to search/select a satellite

### Issue 3: Centrality & Collision Risk - User Interaction Required

**Location:** [`CentralityView.jsx`](./react-app/src/components/CentralityView.jsx), [`CollisionRiskView.jsx`](./react-app/src/components/CollisionRiskView.jsx)

**Problem:** These views require the user to click a button to load data, but may not be providing clear feedback or handling errors properly.

**Current Flow:**
1. User selects "Centrality Analysis" or "Collision Risks"
2. Control panel appears with configuration options
3. User must click "Calculate Centrality" or "Load Collision Risks" button
4. Data loads and passes to GraphViewer via callback

**Potential Issues:**
- Button clicks may not trigger properly
- API errors may not display clearly
- Loading states may not show feedback
- Empty results may render as blank canvas

### Issue 4: Graph Evolution - Self-Contained Rendering

**Location:** [`EvolutionTimelineView.jsx`](./react-app/src/components/EvolutionTimelineView.jsx), [`GraphExplorer.jsx:354-356`](./react-app/src/components/GraphExplorer.jsx:354-356)

**Problem:** Evolution timeline auto-loads on mount but may fail silently if API returns no data.

**Current Behavior:**
- Component renders own SVG chart (not using GraphViewer)
- Auto-fetches data on mount via `useEffect` (line 14-16)
- If `timeline` array is empty, shows "No timeline data available"

**Potential Issues:**
- API might be returning empty `timeline` array
- Date range might be invalid
- Chart may fail to render if data exists but has invalid values

## Implementation Approach

The fix will address each issue systematically:

### 1. Add Error Handling & Logging
Add comprehensive error logging to identify which specific API calls are failing and why.

### 2. Fix Lineage Satellite Selection
Implement a satellite search/selection UI within the lineage panel to allow users to select satellites.

### 3. Improve User Feedback
Ensure all graph views show:
- Clear loading states
- Explicit error messages when API calls fail
- "No data" messages when queries return empty results
- Instructions for required user actions

### 4. Validate API Responses
Add response validation to ensure data contracts match between frontend and backend.

### 5. Add Default/Sample Data Loading
For views that support it, auto-load sample data on first render to demonstrate functionality.

## Files to Modify

### Frontend Components
1. **`react-app/src/components/GraphViewer.jsx`**
   - Add error logging to all `loadXxxGraph` functions
   - Add proper null/empty checks for API responses
   - Display user-friendly error messages in graph container

2. **`react-app/src/components/GraphExplorer.jsx`**
   - Add satellite selection state for lineage view
   - Pass `selectedSatellite` prop to GraphViewer
   - Add satellite search/autocomplete input for lineage panel

3. **`react-app/src/components/CentralityView.jsx`**
   - Improve error message display
   - Add more detailed loading feedback
   - Show validation errors inline

4. **`react-app/src/components/CollisionRiskView.jsx`**
   - Improve error message display
   - Add more detailed loading feedback
   - Show validation errors inline

5. **`react-app/src/components/EvolutionTimelineView.jsx`**
   - Add error boundary
   - Show detailed error messages
   - Add console logging for debugging

### CSS Updates (if needed)
6. **`react-app/src/components/GraphViewer.css`**
   - Add styles for error states
   - Add styles for empty states
   - Add styles for loading states

## Data Model / API Contract

### Centrality Response
```typescript
{
  data: {
    satellites: Array<{
      _id: string;
      name?: string;
      identifier?: string;
      degree?: number;
      betweenness?: number;
      closeness?: number;
    }>;
    metric: string;
    edge_types: string[];
  };
  cached: boolean;
  timestamp: string;
}
```

### Collision Risk Response
```typescript
{
  data: {
    nodes: Array<{
      id: string;
      name?: string;
      identifier?: string;
      congestion_risk?: string;
    }>;
    edges: Array<{
      id?: string;
      source: string;
      target: string;
      risk_score?: number;
      proximity_score?: number;
    }>;
    stats?: object;
  };
  cached: boolean;
  timestamp: string;
}
```

### Communities Response
```typescript
{
  data: {
    communities: Array<{
      community_id: string;
      size: number;
      members: Array<{
        satellite_id: string;
        satellite_name?: string;
        identifier?: string;
        orbital_band?: string;
        country?: string;
      }>;
    }>;
    algorithm: string;
    stats: {
      total_communities: number;
      total_satellites: number;
      min_community_size: number;
      edge_types: string[];
    };
  };
  cached: boolean;
  timestamp: string;
}
```

### Lineage Response
```typescript
{
  data: {
    root: {
      _id: string;
      name?: string;
      identifier: string;
      family?: string;
      generation?: number;
    };
    ancestors?: Array<{
      satellite: {
        _id: string;
        name?: string;
        identifier: string;
      };
      generation: number;
      edge?: {
        relationship_type: string;
      };
    }>;
    descendants?: Array<{
      satellite: {
        _id: string;
        name?: string;
        identifier: string;
      };
      generation: number;
      edge?: {
        relationship_type: string;
      };
    }>;
  };
  cached: boolean;
  timestamp: string;
}
```

### Evolution Timeline Response
```typescript
{
  data: {
    timeline: Array<{
      period: string;
      node_count: number;
      edge_count: number;
      density: number;
      avg_degree: number;
      node_growth: number;
      edge_growth: number;
    }>;
    parameters: {
      start_date: string;
      end_date: string;
      granularity: string;
      edge_types: string[];
    };
    stats: {
      total_periods: number;
      total_growth: { nodes: number; edges: number };
      final_state: {
        node_count: number;
        edge_count: number;
        density: number;
        avg_degree: number;
      };
      peak_growth_period: string;
      avg_density: number;
    };
  };
  cached: boolean;
  timestamp: string;
}
```

## Verification Approach

### Manual Testing
1. **Communities:**
   - Navigate to Graphs → Communities
   - Verify communities load automatically
   - Check console for errors
   - Verify nodes are colored by community
   - Verify stats display correctly

2. **Centrality:**
   - Navigate to Graphs → Centrality Analysis
   - Select metric type (degree/betweenness/closeness)
   - Select edge types
   - Click "Calculate Centrality"
   - Verify nodes render with size based on centrality score
   - Verify stats display

3. **Collision Risks:**
   - Navigate to Graphs → Collision Risks
   - Select view type (network/clusters)
   - Select orbital band
   - Click "Load Collision Risks"
   - Verify graph renders with colored edges
   - Verify risk legend displays

4. **Satellite Lineage:**
   - Navigate to Graphs → Satellite Lineage
   - Search/select a satellite (e.g., "GPS-III")
   - Verify lineage tree renders with ancestors/descendants
   - Verify nodes are colored by type (root/ancestor/descendant)

5. **Graph Evolution:**
   - Navigate to Graphs → Graph Evolution
   - Verify timeline chart loads
   - Adjust date range and granularity
   - Verify chart updates
   - Verify metrics can be switched (node count/edge count/density)

### Automated Testing
Run existing test suite after changes:
```bash
cd react-app
npm run test  # If tests exist
npm run lint
npm run typecheck  # If TypeScript is used
```

### API Testing
Test API endpoints directly:
```bash
# Test communities endpoint
curl http://localhost:8000/v2/graphs/communities?algorithm=label_propagation&min_size=3

# Test centrality endpoint  
curl "http://localhost:8000/v2/graphs/analytics/centrality?metric=degree&edge_types=constellation&top_n=20"

# Test collision risks endpoint
curl "http://localhost:8000/v2/graphs/collision-risks/network/graph?risk_threshold=0.5"

# Test evolution timeline endpoint
curl "http://localhost:8000/v2/graphs/evolution/timeline?start_date=2000&end_date=2024&granularity=year"
```

### Browser DevTools
1. Open browser console (F12)
2. Navigate to Network tab
3. Click each graph view
4. Check for:
   - Failed API requests (4xx/5xx status codes)
   - Empty response bodies
   - JavaScript errors in console
   - React component errors

## Success Criteria

1. ✅ Communities graph displays colored nodes grouped by community
2. ✅ Centrality analysis shows nodes sized by centrality metric
3. ✅ Collision risks display network with risk-colored edges
4. ✅ Satellite lineage provides UI to select satellites and displays family trees
5. ✅ Graph evolution timeline renders chart with selectable metrics
6. ✅ All error states display helpful messages
7. ✅ All loading states show clear feedback
8. ✅ Browser console shows no errors during normal operation

## Notes

- The screenshot shows these as items in a "Path Finder" panel, but they are actually separate graph types in the GraphExplorer sidebar
- Some views (Centrality, Collision Risks) require user interaction to load data - this is expected behavior
- Lineage view is fundamentally broken due to missing satellite selection mechanism
- Evolution timeline is a special case that doesn't use GraphViewer

## References

- [GraphExplorer.jsx:111-181](./react-app/src/components/GraphExplorer.jsx:111-181) - Graph type selector buttons
- [GraphViewer.jsx:269-300](./react-app/src/components/GraphViewer.jsx:269-300) - Graph loading logic
- [graphs.py:2192-2284](./api/routers/graphs.py:2192-2284) - Communities endpoint
- [graphs.py:2287-2416](./api/routers/graphs.py:2287-2416) - Evolution timeline endpoint
