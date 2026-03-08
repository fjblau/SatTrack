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

- **`api/routers/graphs.py`** (lines 116–156): The AQL query returns null members and null-source edges
- **`react-app/src/components/GraphViewer.jsx`** (lines 552–559): Passes edges to Cytoscape without null-checking

## Proposed Solution

### Primary Fix – AQL query (backend)

Add `FILTER v != null` to skip dangling edge references in the traversal:

```aql
LET members = (
    FOR v, e IN 1..1 INBOUND hub
    constellation_membership
    FILTER e.constellation_name == @constellation_name
    FILTER v != null        -- skip dangling edges
    {limit clause}
    RETURN {
        id: v._id,
        ...
    }
)
```

### Secondary Fix – Frontend (defense in depth)

Filter out edges with null/undefined source or target before adding to Cytoscape:

```javascript
edges: data.data.edges
  .filter(edge => edge.source != null && edge.target != null)
  .map(edge => ({
    data: {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      ...edge
    }
  }))
```

## Edge Cases / Side Effects

- Filtering null vertices reduces the member count slightly; `stats.members` returned by the API would still be accurate because it counts `LENGTH(members)` which would now exclude nulls.
- The `LIMIT` clause is applied after the null filter, which is correct behavior — we still get up to `limit` valid members.
- No other graph endpoints use the same traversal pattern, so the fix is isolated.
