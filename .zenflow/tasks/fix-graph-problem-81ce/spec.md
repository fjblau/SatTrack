# Technical Specification: Fix Graph Path Finder

## Difficulty Assessment
**Medium** — Multiple layered bugs across backend (AQL query logic, ID resolution) and frontend (data structure mismatch). Each fix is self-contained but all must be addressed together for the feature to work.

---

## Technical Context

- **Backend**: Python FastAPI, ArangoDB (python-arango)
- **Frontend**: React 19, Cytoscape.js
- **Key files**: `database/graph_analytics.py`, `api/routers/graphs.py`, `react-app/src/components/GraphViewer.jsx`, `react-app/src/components/PathFinderPanel.jsx`
- **Graph DB**: ArangoDB with named graph `satellite_relationships`
- **Edge collections**: `constellation_membership`, `registration_links`, `orbital_proximity`, `collision_risk_edges`, `satellite_lineage`
- **Satellite _key format**: e.g. `NORAD-39634` (identifier matches), not just `39634`

---

## Root Cause Analysis

Running satellite IDs `39634` and `42969` through the path finder shows "No Path data provided". There are **four stacked bugs**:

### Bug 1 — ID Format Mismatch (Backend)
**File**: `api/routers/graphs.py` — `get_path_between_satellites()`

The endpoint blindly constructs `satellites/{from_id}` (e.g. `satellites/39634`), but satellite documents use `_key` like `NORAD-39634`. Users naturally enter bare NORAD numbers.

**Fix**: Before calling path-find functions, resolve the input identifier to the actual document ID by querying the satellite collection (like `find_satellite()` already does — by `identifier`, `norad_cat_id`, `registration_number`).

### Bug 2 — Graph Traversal Direction (Backend)
**File**: `database/graph_analytics.py` — `find_shortest_path()` and `find_all_paths()`

Both functions use `OUTBOUND` traversal only. In `constellation_membership`, all edges point from a member satellite **to** a hub satellite (`member_to_hub`). So the path `NORAD-39634 → hub ← NORAD-42969` requires traversing edges in reverse for the second leg. `OUTBOUND` can never discover this; `ANY` is required.

**Fix**: Change `OUTBOUND` to `ANY` in both AQL traversal queries.

### Bug 3 — Broken `find_shortest_path` AQL (Backend)
**File**: `database/graph_analytics.py` — `find_shortest_path()`

The current query is a simple graph traversal with FILTER, not a proper shortest-path query:
```aql
FOR v, e IN 1..@max_depth OUTBOUND @from_id ...
    FILTER v._id == @to_id
    RETURN { vertices: [v], edges: [e], distance: LENGTH([v]) }
```
This is wrong in two ways:
1. It iterates ALL vertices at ALL depths and filters. It does not accumulate path; it only returns the final vertex `[v]` — not intermediate hops.
2. The returned structure is `{ vertices: [v], edges: [e] }` — just the endpoint, not the full path.

**Fix**: Rewrite using the path variable `p` (as `find_all_paths` already does correctly):
```aql
FOR v, e, p IN 1..@max_depth ANY @from_id ...
    FILTER v._id == @to_id
    LIMIT 1
    RETURN { vertices: p.vertices, edges: p.edges, distance: LENGTH(p.edges) }
```

### Bug 4 — Frontend Data Structure Mismatch (Frontend)
**File**: `react-app/src/components/GraphViewer.jsx` — `renderPathGraph()`

The frontend always checks `data.paths` (plural array), but the backend returns:
- For `shortest` algorithm: `{ path_found, path: {...} }` — singular `path`, not `paths`
- For `all` algorithm: `{ path_found, paths: [...] }` — correct

Additionally, the frontend expects each path entry to have:
- `path.nodes` — but backend returns `path.vertices`
- `edge.source` / `edge.target` — but ArangoDB edges use `_from` / `_to`

**Fix**: Normalize the response in `renderPathGraph` to handle both `data.path` and `data.paths`, and map `vertices` → node IDs and `_from`/`_to` → `source`/`target`.

### Bug 5 — Misleading UX (Minor)
**File**: `react-app/src/components/PathFinderPanel.jsx`

Input placeholder says "Enter satellite ID or identifier" — unclear. Users may not know to enter `NORAD-39634`.

**Fix**: Update placeholder to `"e.g. NORAD-39634"` and add helper text explaining accepted formats.

---

## Implementation Approach

### Step 1 — Backend: ID Resolution in path endpoint
In `get_path_between_satellites()` in `api/routers/graphs.py`:
- After receiving `from_id` and `to_id`, attempt to find the actual satellite document using AQL (query by `identifier`, `canonical.norad_cat_id` as int and string, `canonical.registration_number`)
- If found, use `doc._id` as the actual document ID for path traversal
- If not found, return a clear 404 with guidance

### Step 2 — Backend: Fix AQL traversal direction and path structure
In `database/graph_analytics.py`:
- Change `OUTBOUND` → `ANY` in both `find_shortest_path` and `find_all_paths`
- Rewrite `find_shortest_path` AQL to use path variable `p` so it returns full path

### Step 3 — Frontend: Fix `renderPathGraph` data normalization
In `react-app/src/components/GraphViewer.jsx`:
- Normalize `data.path` (singular) into `[data.path]` array if `data.paths` is absent
- Map `path.vertices` → list of node IDs
- Map edge `_from`/`_to` → `source`/`target`
- Handle `path_found: false` case cleanly

### Step 4 — Frontend: Improve PathFinderPanel UX
In `react-app/src/components/PathFinderPanel.jsx`:
- Update placeholder text and add a note about ID formats
- Optionally show the resolved satellite name after entry (stretch goal)

---

## Source Code Changes

| File | Change |
|------|--------|
| `api/routers/graphs.py` | Add ID resolution logic before calling `find_shortest_path`/`find_all_paths` |
| `database/graph_analytics.py` | Fix AQL in `find_shortest_path` (path variable, ANY direction); change `find_all_paths` to ANY |
| `react-app/src/components/GraphViewer.jsx` | Fix `renderPathGraph` to normalize `path`/`paths`, map vertex/edge fields |
| `react-app/src/components/PathFinderPanel.jsx` | Update placeholder text |

---

## Data Flow (After Fix)

```
User enters: "39634", "42969"
    ↓
PathFinderPanel → GET /v2/graphs/paths/39634/42969?algorithm=shortest
    ↓
Backend resolves IDs:
  "39634" → query by norad_cat_id → satellites/NORAD-39634
  "42969" → query by norad_cat_id → satellites/NORAD-42969
    ↓
find_shortest_path(from="satellites/NORAD-39634", to="satellites/NORAD-42969")
  AQL: FOR v, e, p IN 1..10 ANY "satellites/NORAD-39634"
         constellation_membership, registration_links, orbital_proximity
       FILTER v._id == "satellites/NORAD-42969"
       LIMIT 1
       RETURN { vertices: p.vertices, edges: p.edges, distance: LENGTH(p.edges) }
    ↓
Path found: NORAD-39634 → 1983-058B → NORAD-42969 (via constellation hub)
    ↓
Backend response: { data: { path_found: true, path: { vertices: [...], edges: [...] } } }
    ↓
Frontend normalizes: treats as paths=[path]
  nodes: ["satellites/NORAD-39634", "satellites/1983-058B", "satellites/NORAD-42969"]
  edges: [{ source: "satellites/NORAD-39634", target: "satellites/1983-058B" }, ...]
    ↓
Cytoscape renders the graph
```

---

## Verification Approach

1. **Manual test**: Start backend and frontend with `./start.sh`, enter `39634` and `42969` in Path Finder, verify graph renders with the constellation hub as intermediate node
2. **Manual test**: Try `NORAD-39634` and `NORAD-42969` explicitly — same result
3. **Manual test**: Try non-existent IDs — verify clean 404 error message
4. **Manual test**: Try `algorithm=all` — verify multiple paths shown if available
5. **Lint**: Run `cd react-app && npm run build` to check for JSX/JS errors
