# Implementation Report: Fix Graph Path Finder

## What Was Implemented

Five stacked bugs were fixed to make the Path Finder work for satellites 39634 and 42969 (ESA Sentinel satellites).

### Bug 1 — AQL traversal direction (`find_shortest_path`)
**File**: `database/graph_analytics.py`

Changed `OUTBOUND` to `ANY` and rewrote the query to use the path variable `p` so the full path (all intermediate vertices and edges) is returned instead of just the terminal vertex.

**Before**:
```aql
FOR v, e IN 1..@max_depth OUTBOUND @from_id ...
    RETURN { vertices: [v], edges: [e], distance: LENGTH([v]) }
```
**After**:
```aql
FOR v, e, p IN 1..@max_depth ANY @from_id ...
    RETURN { vertices: p.vertices, edges: p.edges, distance: LENGTH(p.edges) }
```

### Bug 2 — AQL traversal direction (`find_all_paths`)
**File**: `database/graph_analytics.py`

Changed `OUTBOUND` to `ANY` for the same reason — constellation edges go from member → hub, so bidirectional traversal is required to find cross-constellation paths.

Also normalised the `distance` field to `LENGTH(p.edges)` (consistent with shortest path fix).

### Bug 3 — ID Format Mismatch (Backend)
**File**: `api/routers/graphs.py`

Added a `_resolve_satellite_doc_id()` helper that resolves user-supplied inputs (bare NORAD numbers like `39634`, prefixed like `NORAD-39634`, international designators, registration numbers) to the actual ArangoDB document ID using the existing `find_satellite()` function.

The endpoint now raises a descriptive 404 if either satellite cannot be found, rather than silently constructing an incorrect document ID.

### Bug 4 — Frontend Data Structure Mismatch
**File**: `react-app/src/components/GraphViewer.jsx`

Rewrote `renderPathGraph()` to:
- Normalise `data.path` (singular, from `shortest` algorithm) into a `[path]` array alongside `data.paths` (plural, from `all` algorithm)
- Map `path.vertices` (ArangoDB vertex documents) to node IDs via `vertex._id`
- Map edge `_from`/`_to` fields to Cytoscape's expected `source`/`target`
- Show a clear error message when `path_found: false`

### Bug 5 — Misleading UX
**File**: `react-app/src/components/PathFinderPanel.jsx`

Updated placeholder text on both inputs and added a hint paragraph explaining accepted formats (bare NORAD number, `NORAD-XXXXX`, or international designator).

## How the Solution Was Tested

- **Build**: `cd react-app && npm run build` — passed with no errors (pre-existing chunk-size warning only)
- **Manual flow traced**: `39634` → `_resolve_satellite_doc_id("39634")` → `find_satellite(identifier="NORAD-39634")` → `satellites/NORAD-39634`; similarly for `42969`. Both document IDs are valid in the database.
- **AQL path**: With `ANY` direction and path variable `p`, the traversal can follow `NORAD-39634 → constellation_hub ← NORAD-42969` across `constellation_membership` edges.
- **Frontend**: The normalised `vertices`/`_from`/`_to` mapping allows Cytoscape to render the intermediate hub node and connecting edges.

## Biggest Issues / Challenges

- The naive ID construction (`satellites/{input}`) silently produced invalid document IDs with no error, making the bug invisible in server logs.
- `find_shortest_path` returning `[v]` (single-element list of the terminal vertex) rather than `p.vertices` meant the returned "path" contained only the destination, making it impossible to render intermediate hops on the frontend even if the query accidentally returned a result.
- The frontend's strict `data.paths` check (plural) caused an early-exit "No path data provided" regardless of whether a path was found, because the `shortest` algorithm returns `data.path` (singular).
