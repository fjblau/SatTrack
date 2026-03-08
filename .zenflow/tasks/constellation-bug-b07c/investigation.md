# Bug Investigation: Constellation Load Error

## Bug Summary

When selecting the **OneWeb** constellation in the Graphs → Constellations view, the graph fails to render and shows:

> Error: Failed to load constellation: Can not create edge `_to_hub` with unspecified source

## Root Cause Analysis

The error originates in Cytoscape.js when it tries to add an edge with a `null`/`undefined` source.

### Data Flow

1. Frontend calls `/v2/graphs/constellation/OneWeb?limit=100`
2. `api/routers/graphs.py` executes an AQL query:
   - First finds the **hub** satellite: `hub = FIRST(FOR edge IN constellation_membership ... RETURN edge._to)`
   - Then finds **members** using an INBOUND graph traversal from the hub
   - Builds **edges** from members to hub

### The Bug

In the AQL query (`api/routers/graphs.py`, lines 116–132), the INBOUND traversal:

```aql
LET members = (
    FOR v, e IN 1..1 INBOUND hub
    constellation_membership
    FILTER e.constellation_name == @constellation_name
    RETURN {
        id: v._id,
        ...
    }
)
```

If any `constellation_membership` edge references a `_from` satellite that **no longer exists** in the `satellites` collection (i.e., a dangling edge), the ArangoDB traversal returns `v = null` for that vertex. This causes `id: v._id` → `id: null` in the returned member object.

The edges are then built as:

```aql
LET edges = (
    FOR v IN members
        RETURN {
            id: CONCAT(v.id, "_to_hub"),
            source: v.id,   -- null when member was a dangling reference
            target: hub,
            ...
        }
)
```

An edge with `source: null` is returned to the frontend, which passes it directly to `cyRef.current.add(elements)`. Cytoscape.js throws:

> Can not create edge `_to_hub` with unspecified source

This error is caught and displayed as "Failed to load constellation: Can not create edge `_to_hub` with unspecified source".

OneWeb (1,207 satellites) has a high chance of containing dangling references because it is a very large constellation; some satellite records may have been deleted or not yet imported while the membership edges still exist.

## Affected Components

The same root cause (dangling edge references → null vertex → null id/source/target) affects **four** graph endpoints:

| Endpoint | File | Lines | Vulnerable via |
|---|---|---|---|
| `GET /constellation/{name}` | `api/routers/graphs.py` | 116–156 | `source: v.id` where `v` can be null |
| `GET /registration-document/{key}` | `api/routers/graphs.py` | 395–428 | `source: sat.id` where `sat.id = v._id`, `v` can be null |
| `GET /satellite/{id}/neighborhood` | `api/routers/graphs.py` | 255–325 | `id: n.vertex._id` where `n.vertex` can be null (nodes break Cytoscape) |
| `GET /lineage/{id}` | `api/services/lineage_service.py` | 297–316 | `_id: v._id` where `v` can be null; frontend uses `sat._id` as node id and in edges |

**Frontend** (`react-app/src/components/GraphViewer.jsx`):
- Lines 552–559: constellation edges passed to Cytoscape without null guard
- Lines 1596–1626: neighborhood nodes/edges without null guard
- Lines 1893–1944: lineage nodes/edges built directly from `sat._id` without null guard

## Proposed Solution

### Backend Fix — add `FILTER v != null` to every AQL traversal

**`api/routers/graphs.py` — constellation endpoint (~line 119)**
```aql
LET members = (
    FOR v, e IN 1..1 INBOUND hub
    constellation_membership
    FILTER e.constellation_name == @constellation_name
    FILTER v != null
    {limit clause}
    RETURN { id: v._id, ... }
)
```

**`api/routers/graphs.py` — registration-document endpoint (~line 397)**
```aql
LET satellites = reg_doc ? (
    FOR v, e IN 1..1 INBOUND @doc_id
    registration_links
    FILTER v != null
    {limit clause}
    RETURN { id: v._id, ... }
) : []
```

**`api/routers/graphs.py` — neighborhood endpoint (~line 259)**
```aql
LET neighbors = (
    FOR v, e, p IN 1..@depth ANY @source_id {edge_clause}
        OPTIONS {uniqueVertices: "global", bfs: true}
        FILTER v != null
        LIMIT @limit
        RETURN { vertex: v, edge: e, path_length: LENGTH(p.edges) }
)
```

**`api/services/lineage_service.py` — lineage traversal (~line 297)**
```aql
FOR v, e, p IN 1..@max_depth {direction} @start_id
    satellite_lineage
    FILTER v != null
    RETURN { satellite: { _id: v._id, ... }, ... }
```

### Frontend Fix — defense-in-depth null guards

For each `cyRef.current.add(elements)` call, filter out any node with `id == null` and any edge where `source` or `target` is null/undefined before adding to Cytoscape.

## Edge Cases / Side Effects

- `FILTER v != null` placed **before** `LIMIT` means the limit applies to valid vertices only — correct behavior.
- Null-filtering slightly reduces reported counts in `stats` fields, but those stats are computed from the same filtered `members`/`neighbors` LET, so they remain accurate.
- The neighborhood endpoint uses raw `n.edge._from`/`n.edge._to` for edge source/target (not vertex fields), so its **edges** are already safe; only its **nodes** need the null filter.
- The lineage endpoint is lower risk (lineage edges are rarer and manually curated) but should still be fixed for consistency.
