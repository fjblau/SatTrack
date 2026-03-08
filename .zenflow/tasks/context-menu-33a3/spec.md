# Technical Specification: Path Finder Context Menu Fix

## Difficulty
**Easy** — A straightforward data mapping bug. The fix is a single-line change in one function.

## Technical Context
- **Language**: JavaScript/JSX (React 19)
- **Component**: `react-app/src/components/GraphViewer.jsx`
- **Graph Library**: Cytoscape.js

## Root Cause

In `renderPathGraph` (~line 1206), path nodes are constructed without an `identifier` field:

```js
pathNodes.set(nodeId, {
  id: nodeId,
  label: ...,
  is_path_node: true,
  node_role: nodeRole,
  node_size: ...
  // ← no `identifier` field
})
```

The context menu JSX at line 2443 gates the "Show Details" menu item behind `contextMenu.node.identifier`:

```jsx
{contextMenu.node.identifier && contextMenu.node.type !== 'registration_document' && (
  <div className="context-menu-item" ...>
    📊 Show Satellite Details
  </div>
)}
```

Since path nodes lack `identifier`, neither condition in the context menu is truthy, so the menu renders as an empty `<div className="graph-context-menu">` — a bordered empty box that appears as "just a line".

`handleShowSatelliteDetails` already handles the fallback correctly:
```js
const satelliteId = nodeData.identifier || nodeData.key || nodeData.id?.split('/')[1]
```
So if `identifier` is present, the fetch will succeed.

## Implementation Approach

Add `identifier` to the path node data object in `renderPathGraph`. The identifier string is already being computed inline for the label — extract it and store it as a named field too.

The label computation:
```js
const identifier = vertex.identifier || nodeId.split('/')[1] || nodeId
```

Store it on the node:
```js
pathNodes.set(nodeId, {
  id: nodeId,
  identifier: vertex.identifier || nodeId.split('/')[1] || nodeId,
  label: ...,
  is_path_node: true,
  node_role: nodeRole,
  node_size: ...
})
```

## Files Modified
- `react-app/src/components/GraphViewer.jsx` — add `identifier` field to path node data objects in `renderPathGraph`

## Data Model / API Changes
None — this is a frontend-only fix with no backend or API changes.

## Verification
1. Start the app (`./start.sh`)
2. Navigate to Path Finder graph
3. Find a path between two satellites
4. Right-click a node — confirm "Show Satellite Details" appears in context menu
5. Click the menu item — confirm the detail panel opens with data
6. Right-click a registration document node (supplementary) — confirm "Show Registration Document" still works
7. Confirm empty-context-menu "line" no longer renders on nodes without matching type
