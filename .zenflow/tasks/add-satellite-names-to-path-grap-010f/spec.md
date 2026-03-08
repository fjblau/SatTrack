# Technical Specification: Add Satellite Names to Path Graph

## Difficulty Assessment
**Easy** — Localized change in a single render function. No API changes required. The vertex data returned by the backend already includes `canonical.name` (via the full ArangoDB document), so the name is available in the frontend payload. The fix is purely in the label-construction logic inside `renderPathGraph`.

---

## Technical Context

- **Language**: JavaScript/JSX (React 19, Vite)
- **Graph Library**: [Cytoscape.js](https://js.cytoscape.org/) with `cytoscape-cola` layout
- **Relevant file**: `react-app/src/components/GraphViewer.jsx`

### How vertices reach the frontend

The backend `find_shortest_path` / `find_all_paths` functions (in `database/graph_analytics.py`) return full ArangoDB satellite documents as `vertices` — **not** a projected subset. Each vertex therefore contains:

```json
{
  "_id": "satellites/NORAD-39634",
  "identifier": "NORAD-39634",
  "canonical": {
    "name": "COSMOS 2251 DEB",
    ...
  }
}
```

`vertex.canonical?.name` is already accessed in the existing label expression (line 1207 of `GraphViewer.jsx`), but only as a **fallback** when `vertex.identifier` is absent. The current logic shows only the identifier (NORAD ID) because `identifier` is almost always present and takes precedence.

---

## Implementation Approach

### Change: Update the node label in `renderPathGraph`

**File**: `react-app/src/components/GraphViewer.jsx`  
**Location**: `renderPathGraph` function, inside the `vertices.forEach` block (~line 1207)

**Current code**:
```js
label: vertex.identifier || vertex.canonical?.name || (nodeId.split('/')[1]) || nodeId,
```

**New code** — show NORAD ID on the first line and the satellite name (in parentheses) on the second line, using a `\n` newline which Cytoscape supports when `text-wrap: wrap` is set on the node style:
```js
const identifier = vertex.identifier || nodeId.split('/')[1] || nodeId
const satName = vertex.canonical?.name
label: satName ? `${identifier}\n(${satName})` : identifier,
```

To make Cytoscape render the newline, `text-wrap: wrap` must be added to the node style. This should be scoped to the `node[is_path_node]` selector (or the global `node` selector — preferably scoped to avoid affecting all graph views).

### Cytoscape style addition

Add `text-wrap: wrap` to the `node[is_path_node]` selector (and `node[node_role="source"]`, `node[node_role="destination"]`, `node[node_role="intermediate"]`, `node[node_role="hub"]` for completeness), or more cleanly, add a dedicated selector for the path view.

The simplest approach is to add it to the **global** `node` selector since other graph views don't use multi-line labels (they all use short labels). This avoids duplicating style rules. The fallback for non-path nodes is that their labels stay on one line because they don't contain `\n`.

---

## Source Code Structure Changes

| File | Change |
|------|--------|
| `react-app/src/components/GraphViewer.jsx` | 1. Add `text-wrap: 'wrap'` to global node style. 2. Update label construction in `renderPathGraph` `vertices.forEach` to include satellite name. |

No new files. No API changes.

---

## Data Model / API / Interface Changes

**None.** The API already returns full satellite documents whose `canonical.name` field is available in the frontend. No backend changes needed.

---

## Verification Approach

1. Start the dev server (`npm run dev` in `react-app/`).
2. Navigate to the Path Finder graph view.
3. Enter two NORAD IDs and find a path.
4. Verify that each satellite node in the graph shows the NORAD identifier on one line and the satellite name (in parentheses) on the second line.
5. Verify other graph views (constellation, orbital band, etc.) are unaffected.
6. Run lint: `cd react-app && npm run lint` (if configured).
