# Bug Investigation: Sorting Not Working on Full Dataset

## Bug Summary

Sorting functionality only works on the current page of data (e.g., 50 satellites) rather than the entire dataset. When clicking "Date of Launch" in descending order, it shows 1964-05-18 at the top, but satellites launched after that exist in the database.

## Root Cause Analysis

### Current Architecture Flow

1. **Backend** ([./database/operations.py:132-185](./database/operations.py:132-185))
   - The `search_satellites()` function has a **hardcoded sort** on line 179: `SORT doc.identifier ASC`
   - No support for dynamic sorting based on user input
   - Always returns results sorted by identifier regardless of user preferences

2. **API Endpoint** ([./api/routers/satellites.py:12-60](./api/routers/satellites.py:12-60))
   - The `/v2/search` endpoint accepts filters (`q`, `country`, `status`, etc.) and pagination (`limit`, `skip`)
   - **Does NOT accept any sort parameters** (`sort_by`, `sort_order`)
   - Cannot pass sort preferences to the backend

3. **Frontend** ([./react-app/src/App.jsx:164-185](./react-app/src/App.jsx:164-185))
   - Implements **client-side sorting** on the `objects` array
   - The `objects` state only contains the current page's data (50 satellites out of ~18,000+)
   - Sorting only reorders these 50 items, not the entire dataset
   - Pagination controls fetch new pages without considering sort state

### Why It Fails

```
User clicks "Date of Launch ▼"
    ↓
Frontend sorts current 50 satellites client-side
    ↓
Shows oldest date among those 50 satellites (e.g., 1964-05-18)
    ↓
User navigates to next page
    ↓
Backend returns next 50 satellites sorted by identifier (ignoring date)
    ↓
Frontend sorts those 50 satellites client-side again
    ↓
Shows oldest date among these new 50 satellites
```

The backend never knows about the user's sort preference, so pagination breaks sorting completely.

## Affected Components

1. **Backend**: `database/operations.py` - `search_satellites()` function
2. **API**: `api/routers/satellites.py` - `/v2/search` endpoint
3. **Frontend**: `react-app/src/App.jsx` - `fetchObjects()`, `handleSort()`, and sorting logic

## Proposed Solution

### 1. Backend Changes (`database/operations.py`)

Modify the `search_satellites()` function to:
- Accept `sort_by` (field name) and `sort_order` ('ASC' or 'DESC') parameters
- Map frontend column names to backend field paths (e.g., "Date of Launch" → "doc.canonical.launch_date")
- Build dynamic AQL SORT clause
- Default to current behavior (`doc.identifier ASC`) if no sort provided

**Example mapping needed**:
```python
SORT_FIELD_MAPPING = {
    'Identifier': 'doc.identifier',
    'Object Name': 'doc.canonical.object_name',
    'Country of Origin': 'doc.canonical.country_of_origin',
    'Date of Launch': 'doc.canonical.launch_date',
    'Status': 'doc.canonical.status',
    'Orbital Band': 'doc.canonical.orbital_band',
    'Congestion Risk': 'doc.canonical.congestion_risk',
    'Apogee (km)': 'doc.canonical.orbit.apogee_km',
    'Perigee (km)': 'doc.canonical.orbit.perigee_km',
    'Inclination (degrees)': 'doc.canonical.orbit.inclination_degrees',
    'Period (minutes)': 'doc.canonical.orbit.period_minutes'
}
```

### 2. API Changes (`api/routers/satellites.py`)

Update the `/v2/search` endpoint to:
- Add `sort_by: Optional[str]` and `sort_order: Optional[str]` query parameters
- Pass these to the `search_satellites()` function
- Document the new parameters in the endpoint docstring

### 3. Frontend Changes (`react-app/src/App.jsx`)

Modify to:
- Send `sort_by` and `sort_order` as URL parameters when calling `/v2/search`
- Reset to page 0 when sort changes (similar to filter changes on line 33)
- Remove or keep client-side sorting as defensive fallback
- Trigger data fetch when `sortConfig` changes

**Key change in `fetchObjects()`**:
```javascript
// Add sort parameters to URL
if (sortConfig.length > 0) {
  const primarySort = sortConfig[0]; // Use primary sort for backend
  params.append('sort_by', primarySort.column);
  params.append('sort_order', primarySort.direction.toUpperCase());
}
```

**Add useEffect to refetch on sort change**:
```javascript
useEffect(() => {
  fetchObjects(0);
}, [sortConfig]);
```

## Edge Cases and Considerations

1. **Multiple column sorting**: Frontend supports multi-column sorting, but for initial fix, only send primary sort to backend. Can be enhanced later.

2. **Null/empty values**: Backend needs to handle null values in sorting (e.g., satellites without launch dates should appear at the end or beginning consistently)

3. **Case sensitivity**: Use case-insensitive sorting for text fields in AQL

4. **Performance**: Sorting + pagination with large datasets might benefit from database indexes on frequently sorted fields (launch_date, country, status, etc.)

5. **Backward compatibility**: Default sort behavior should remain `identifier ASC` if no sort parameters provided

## Testing Approach

1. Test sorting by each column (11 columns total)
2. Test both ascending and descending order
3. Test sorting with pagination (navigate between pages and verify sort persists)
4. Test sorting combined with filters
5. Test sorting with empty/null values in the sort field
6. Verify performance with full dataset (~18,000+ satellites)

## Implementation Order

1. ✅ Complete investigation and create this document
2. ⏳ Update `database/operations.py` - add sort parameters and dynamic sorting
3. ⏳ Update `api/routers/satellites.py` - add sort query parameters
4. ⏳ Update `react-app/src/App.jsx` - send sort to backend and refetch on sort change
5. ⏳ Test all sorting scenarios
6. ⏳ Verify with user that "Date of Launch" descending shows recent launches

## Expected Result

After the fix:
- Clicking "Date of Launch ▼" (descending) should show the most recent satellite launches at the top across ALL pages
- Pagination should maintain the sort order
- All 18,000+ satellites should be sorted correctly by the database, not just the current page
