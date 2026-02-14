# Fix bug

## Configuration
- **Artifacts Path**: {@artifacts_path} → `.zenflow/tasks/{task_id}`

---

## Workflow Steps

### [x] Step: Investigation and Planning
<!-- chat-id: 249aaf3e-244b-456d-b8c3-99a5799415c8 -->

Analyze the bug report and design a solution.

1. Review the bug description, error messages, and logs
2. Clarify reproduction steps with the user if unclear
3. Check existing tests for clues about expected behavior
4. Locate relevant code sections and identify root cause
5. Propose a fix based on the investigation
6. Consider edge cases and potential side effects

Save findings to `{@artifacts_path}/investigation.md` with:
- Bug summary
- Root cause analysis
- Affected components
- Proposed solution

### [x] Step: Implementation
<!-- chat-id: 59835b75-19ee-49c4-9144-66acc94c14c9 -->
Read `{@artifacts_path}/investigation.md`
Implement the bug fix.

1. Add/adjust regression test(s) that fail before the fix and pass after
2. Implement the fix
3. Run relevant tests
4. Update `{@artifacts_path}/investigation.md` with implementation notes and test results

**Implementation Completed**:
- Created `/v2/graphs/satellite/{id}/neighborhood` endpoint
- Fixed SatelliteNeighborhood component (search endpoint & response mapping)
- Fixed ConstellationBrowser component (removed invalid depth parameter)
- Fixed Cytoscape node_size console warnings
- Fixed database connection bugs in collision_service.py, lineage_service.py, graph_operations.py
- Fixed populate_collision_risks.py script (status filter, field names, database connection)
- Populated production database with 191,000 collision risk edges
- Fixed collision risk score display precision (2→4 decimal places)
- Wired Constellation Browser and Satellite Neighborhood to GraphViewer component
- Added renderConstellationBrowserGraph() and renderNeighborhoodGraph() functions
- Added styling for source nodes in neighborhood view (green with border)
- Updated GraphExplorer state management to pass data to GraphViewer
- Fixed populate_satellite_lineage.py script (import order, database connection)
- Populated 52 satellite lineage edges (GLONASS family with generations)
- Fixed collision risk duplicate edges (678k → 179k unique edges)
- Improved collision risk query to show connected hubs instead of isolated pairs
- Made collision risk colors relative (percentile-based) instead of absolute thresholds
- Updated legend to reflect relative coloring (Top 25%, 50-75%, 25-50%, Bottom 25%)
- Added risk distribution stats (min, max, p25, median, p75) to graph metadata
- Added edge type differentiation to Satellite Neighborhood view:
  * Orange solid lines for orbital proximity (width varies by distance, labels show km)
  * Blue solid lines for constellation membership (labels show constellation name)
  * Purple dashed lines for registration document links
  * Added legend explaining edge types and node types
  * Edge stats show breakdown by type
- Fixed edge labels to use proximity field data (apogee_diff_km, perigee_diff_km)
- Updated backend endpoint to return proximity_score, apogee_diff_km, perigee_diff_km, inclination_diff_degrees
- Frontend now calculates and displays average separation in km for orbital proximity edges
- Edge width now based on proximity_score (closer satellites = thicker lines)
- Fixed filter button text color (white text on white background issue)
- Fixed edge type naming mismatch (constellation_membership, registration_links vs constellation_edges, registration_edges)
- Added relative color coding for orbital proximity edges in neighborhood view:
  * Dark green = closest 25% (lowest proximity scores)
  * Green = 25-50%
  * Orange = 50-75%
  * Red = farthest 25% (highest proximity scores)
  * Updated legend to show color gradient
  * Added proximity distribution stats to metadata
- Added right-click context menus to graph visualization:
  * Right-click on satellite nodes → "Show Satellite Details" option
  * Right-click on registration document nodes → "Show Registration Document" option
  * Context menu fetches full data from API and displays in modal panel
  * Fixed context menu detection: registration documents now properly identified by type field
  * Fixed hub satellite detection:
    - Backend: explicitly set is_hub=false for member nodes, is_hub=true for hub node
    - Frontend: use strict equality (===) instead of truthy checks, preserve is_hub from backend via spread operator
    - Frontend: removed is_hub transformation that was causing property loss
  * Hub nodes now correctly show "⭐ Show Hub Details" in context menu
  * Modal shows raw JSON data (same format as Table View's "Show Data Record")
  * Added "Copy to Clipboard" button to copy JSON data
  * Styled JSON display with monospace font, syntax highlighting background, scrollable container
  * Fixed spread operator ordering in renderNeighborhoodGraph to preserve node properties
  * Fixed API endpoint typo: changed /v2/satellites/{id} to /v2/satellite/{id} (singular)
  * Removed all debug logging statements
  * Fixed satellite detail lookup for Kaggle-only satellites:
    - Added identifier parameter to find_satellite() database function
    - Updated API endpoint to search by identifier field first (before international_designator or registration_number)
    - Fixes issue where 73% of satellites (Kaggle-only) couldn't be found by their identifier
    - Satellites like BRO-18 (NORAD-64550) now show their data in detail panel
- Pushed to main and deployed to production
- All graph features now functional with data and proper visualizations

If blocked or uncertain, ask the user for direction.
