# Investigation: Add Object Type

## Task Summary

Add "Object Type" as:
1. A column in the Main Table View (`DataTable.jsx`)
2. A filter in the left-side filter pane (`Filters.jsx`)

## Affected Components

### Backend
- `database/operations.py` — DB query functions
- `database/__init__.py` — module exports
- `api/routers/metadata.py` — metadata endpoints
- `api/routers/satellites.py` — search endpoint

### Frontend
- `react-app/src/config/constants.js` — API endpoints & labels
- `react-app/src/App.jsx` — data fetching, filter state, object mapping
- `react-app/src/components/Filters.jsx` — filter UI
- `react-app/src/components/DataTable.jsx` — table columns & rows

## Current State

- The satellite documents have a `canonical.object_type` field (populated by GCAT import scripts)
- No API endpoint exists for listing distinct object types
- `search_satellites()` and `count_satellites()` do not accept an `object_type` filter
- The frontend does not fetch, display, or filter by object_type
- Existing pattern for analogous field: `congestion_risk` (full-stack reference)

## Proposed Solution

### Step 1: Backend — Database layer (`database/operations.py`)

Add `get_all_object_types()` following the same pattern as `get_all_congestion_risks()`:
```python
def get_all_object_types() -> List[str]:
    aql = """
    RETURN UNIQUE(
        FOR doc IN @@collection
            FILTER doc.canonical.object_type != null
            RETURN doc.canonical.object_type
    )
    """
    cursor = db_conn.db.aql.execute(aql, bind_vars={'@collection': COLLECTION_NAME})
    result = list(cursor)
    return result[0] if result else []
```

Add `object_type` filter parameter to `search_satellites()` and `count_satellites()`.

### Step 2: Backend — Exports (`database/__init__.py`)

Export `get_all_object_types` from the module.

### Step 3: Backend — Metadata endpoint (`api/routers/metadata.py`)

Add `/object-types` endpoint following the same pattern as `/congestion-risks`.

### Step 4: Backend — Search endpoint (`api/routers/satellites.py`)

Add `object_type: Optional[str]` query parameter and pass it through to `search_satellites()` / `count_satellites()`.

### Step 5: Frontend — Constants (`react-app/src/config/constants.js`)

- Add `OBJECT_TYPES: '/v2/object-types'` to `API_ENDPOINTS`
- Add `ALL_OBJECT_TYPES: 'All Object Types'` to `FILTER_LABELS`

### Step 6: Frontend — App (`react-app/src/App.jsx`)

- Fetch object types in `fetchFilterOptions()` alongside other filter options
- Include `object_types` in `filterOptions` state
- Map `'Object Type': canonical.object_type || ''` in object mapping
- Send `object_type` filter param to API when set

### Step 7: Frontend — Filters (`react-app/src/components/Filters.jsx`)

Add `<select>` for object_type following the same pattern as congestion_risk.

### Step 8: Frontend — DataTable (`react-app/src/components/DataTable.jsx`)

- Add `{ key: 'Object Type', label: 'Object Type' }` to the columns array
- Add `<td>{obj['Object Type'] || '—'}</td>` to the row render
- Add `'Object Type': 'doc.canonical.object_type'` to `SORT_FIELD_MAPPING` in `operations.py`

## Edge Cases

- Object type values may be null/empty — handled with `|| '—'` in the table cell
- The `UNIQUE()` AQL query may return null — filtered via `if t and t.strip()` in the API endpoint
- Sort mapping must be added in `operations.py` for the new column to be sortable
