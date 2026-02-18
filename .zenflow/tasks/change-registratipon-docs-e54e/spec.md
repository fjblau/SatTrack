# Technical Specification: Registration Documents Analytics Page

## Task Difficulty
**Medium** - This involves multiple file changes across frontend components and requires creating a new analytics view, but follows established patterns in the codebase.

## Overview
Remove the "Registration Docs" graph visualization from the Graphs tab and create a new dedicated analytics page that displays registration document information in a table format with counts, dates, and other metadata.

## Technical Context

### Language & Stack
- **Frontend**: React 19.2.3 with Vite
- **Backend**: Python FastAPI with ArangoDB
- **Database Collection**: `registration_documents` (COLLECTION_REG_DOCS)

### Current Implementation
- Registration documents are shown as a graph visualization in [`./react-app/src/components/GraphExplorer.jsx`](./react-app/src/components/GraphExplorer.jsx)
- Currently displayed in the "Graphs" tab via a button (lines 196-201) and selector (lines 274-295)
- Data comes from `/v2/graphs/stats` endpoint returning `top_registration_documents` (top 10 documents)
- Registration document data structure:
  ```javascript
  {
    key: string,           // Document key (URL with special chars replaced)
    url: string,           // Original registration document URL
    satellite_count: number,
    countries: string[]    // Array of countries
  }
  ```

## Implementation Approach

### 1. Remove Registration Docs from Graphs Tab

**File**: [`./react-app/src/components/GraphExplorer.jsx`](./react-app/src/components/GraphExplorer.jsx)

**Changes**:
- Remove "Registration Docs" button from graph type selector (lines 196-201)
- Remove registration document selector section (lines 274-295)
- Remove `documents` state and related logic (lines 13, 51, 58-59)
- Remove `selectedDocument` state (line 18)
- Remove registration document props passed to GraphViewer (line 639)

### 2. Create Registration Documents Analytics Component

**New File**: [`./react-app/src/components/RegistrationDocumentAnalytics.jsx`](./react-app/src/components/RegistrationDocumentAnalytics.jsx)

**Features**:
- Fetch all registration documents (not just top 10)
- Display in sortable table format
- Columns:
  - **URL**: Registration document URL (with clickable link)
  - **Satellite Count**: Number of satellites linked to this document
  - **Countries**: List of countries associated
  - **Created At**: Document creation timestamp
- Sorting capability on all columns
- Search/filter functionality for URL
- Statistics summary cards showing:
  - Total registration documents
  - Total satellites with registration docs
  - Average satellites per document
  - Most common country

**Styling**: Create accompanying [`./react-app/src/components/RegistrationDocumentAnalytics.css`](./react-app/src/components/RegistrationDocumentAnalytics.css) following patterns from [`./react-app/src/components/FunctionAnalytics.css`](./react-app/src/components/FunctionAnalytics.css)

### 3. Create Backend API Endpoint

**File**: [`./api/routers/graphs.py`](./api/routers/graphs.py)

**New Endpoint**: `GET /v2/graphs/registration-documents-analytics`

**Query Parameters**:
- `sort_by` (optional): Field to sort by (url, satellite_count, created_at)
- `sort_order` (optional): ASC or DESC
- `search` (optional): Filter URLs containing search term

**Response**:
```json
{
  "data": {
    "documents": [
      {
        "key": "string",
        "url": "string",
        "satellite_count": number,
        "countries": ["string"],
        "created_at": "ISO timestamp"
      }
    ],
    "stats": {
      "total_documents": number,
      "total_satellites": number,
      "avg_satellites_per_doc": number,
      "top_country": "string"
    }
  },
  "timestamp": "ISO timestamp"
}
```

**AQL Query**:
```aql
LET all_docs = (
    FOR doc IN registration_documents
        FILTER @search == null OR CONTAINS(LOWER(doc.url), LOWER(@search))
        SORT doc[@sort_by] @sort_order
        RETURN {
            key: doc._key,
            url: doc.url,
            satellite_count: doc.satellite_count,
            countries: doc.countries,
            created_at: doc.created_at
        }
)

LET stats = {
    total_documents: LENGTH(all_docs),
    total_satellites: SUM(all_docs[*].satellite_count),
    avg_satellites_per_doc: AVG(all_docs[*].satellite_count),
    top_country: FIRST(
        FOR doc IN all_docs
            FOR country IN doc.countries
                COLLECT c = country WITH COUNT INTO cnt
                SORT cnt DESC
                LIMIT 1
                RETURN c
    )
}

RETURN {
    documents: all_docs,
    stats: stats
}
```

### 4. Add Constants

**File**: [`./react-app/src/config/constants.js`](./react-app/src/config/constants.js)

Add to `API_ENDPOINTS.GRAPHS`:
```javascript
REGISTRATION_DOCUMENTS_ANALYTICS: '/v2/graphs/registration-documents-analytics',
```

### 5. Update Main App Component

**File**: [`./react-app/src/components/App.jsx`](./react-app/src/components/App.jsx)

**Changes**:
- Import new `RegistrationDocumentAnalytics` component
- Add new tab button "Registration Docs" after "Analytics" tab (around line 225)
- Add conditional rendering for new tab (similar to analytics tab at lines 304-308)

**Tab Order**:
1. Table View
2. Graphs
3. Timeline
4. Analytics
5. **Registration Docs** (new)

### 6. Clean up GraphViewer Component

**File**: [`./react-app/src/components/GraphViewer.jsx`](./react-app/src/components/GraphViewer.jsx)

**Check and remove** any references to:
- `selectedDocument` prop
- Registration graph rendering logic
- Any imports or functions specific to registration document graphs

## Data Model / API Changes

### New API Endpoint
- Route: `/v2/graphs/registration-documents-analytics`
- Method: GET
- Collection accessed: `registration_documents`

### No Database Schema Changes
- Using existing `registration_documents` collection
- No new fields or indices required

## Verification Approach

### Manual Testing
1. **Verify Graphs tab**:
   - Start application: `./start.sh`
   - Navigate to Graphs tab
   - Confirm "Registration Docs" button is removed
   - Test remaining graph types work correctly

2. **Verify new Registration Docs tab**:
   - Navigate to new "Registration Docs" tab
   - Verify table displays all registration documents
   - Test sorting on each column
   - Test search/filter functionality
   - Verify summary statistics display correctly

3. **API Testing**:
   - Test endpoint: `http://localhost:8000/v2/graphs/registration-documents-analytics`
   - Test with sort parameters: `?sort_by=satellite_count&sort_order=DESC`
   - Test with search: `?search=ST/SG`
   - Verify response structure matches spec

### Automated Testing
- If project has test suite, run: Check `package.json` and root directory for test commands
- Backend: Check for pytest configuration and run API tests
- Frontend: Check for Vitest/Jest configuration

### Linting
- Backend: Check for `ruff`, `flake8`, or similar in requirements.txt
- Frontend: Run `npm run lint` in react-app directory (if configured)

## Files Modified

1. [`./react-app/src/components/GraphExplorer.jsx`](./react-app/src/components/GraphExplorer.jsx) - Remove registration docs tab
2. [`./react-app/src/components/GraphViewer.jsx`](./react-app/src/components/GraphViewer.jsx) - Remove registration graph logic
3. [`./react-app/src/components/App.jsx`](./react-app/src/components/App.jsx) - Add new tab
4. [`./react-app/src/config/constants.js`](./react-app/src/config/constants.js) - Add API endpoint constant
5. [`./api/routers/graphs.py`](./api/routers/graphs.py) - Add new analytics endpoint

## Files Created

1. [`./react-app/src/components/RegistrationDocumentAnalytics.jsx`](./react-app/src/components/RegistrationDocumentAnalytics.jsx) - New analytics component
2. [`./react-app/src/components/RegistrationDocumentAnalytics.css`](./react-app/src/components/RegistrationDocumentAnalytics.css) - Styles for analytics component

## Risks and Considerations

### Low Risk
- Established patterns exist for analytics pages (FunctionAnalytics component)
- Similar table/statistics patterns already in use
- No database schema changes required

### Edge Cases
- Empty state: No registration documents in database
- Large datasets: Consider pagination if >1000 documents (current: ~746 documents per population script)
- URL display: Very long URLs may need truncation with tooltip
- Missing data: Handle documents without `created_at` field gracefully

## Success Criteria

1. ✅ "Registration Docs" button removed from Graphs tab
2. ✅ New "Registration Docs" tab appears in main navigation
3. ✅ Table displays all registration documents with correct data
4. ✅ Sorting works on all columns
5. ✅ Summary statistics calculate correctly
6. ✅ Search/filter functionality works
7. ✅ No console errors in browser
8. ✅ Existing graph visualizations continue to work
9. ✅ API endpoint returns correct data structure
10. ✅ Application passes lint checks (if configured)
