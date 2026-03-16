# Investigation: Make Observations Top Level

## Summary

Add a top-level "Observations" navigation tab next to "Table View" that shows a full-page observations browser with sidebar filters and a paginated table using the same two-line header layout as `ObservationsModal`.

## Affected Components

### Frontend
- **`react-app/src/App.jsx`** — Add `observations` tab button in nav; render `<ObservationsView>` when active
- **`react-app/src/App.css`** — Add CSS for `observations-view-container` and associated layout (mirror `.app-container` / `.sidebar` / `.main-content`)
- **`react-app/src/components/ObservationsView.jsx`** — NEW component: full-page observations browser
- **`react-app/src/components/ObservationsView.css`** — NEW CSS for the view
- **`react-app/src/components/ObservationsFilters.jsx`** — NEW sidebar filter component specific to observations
- **`react-app/src/components/ObservationsFilters.css`** — NEW CSS (can share `.filters` styles or reuse Filters.css)

### Backend
- **`api/routers/observations.py`** — Add `GET /v2/observations` endpoint (without norad_id, with query filters + pagination)

## Current State

### Navigation (App.jsx)
Current tabs: `table`, `graphs`, `timeline`, `analytics`, `admin`.  
Need to add `observations` between `table` and `graphs`.

### ObservationsModal (existing)
- Fetches `/v2/observations/{norad_id}` (per-satellite)
- Two-line header: `<h2>Observational Data</h2>` + subtitle paragraph
- Table with two header rows:
  - Row 1: TOP_LEVEL_COLUMNS (rowSpan=2) + section headers (colSpan)
  - Row 2: section sub-columns
- Styled with dark header (`#1a1a2e`), section headers `#2d2d5e`, sub-headers `#3d3d8e`

### Current API (observations.py)
- Only endpoint: `GET /v2/observations/{norad_id}` — requires a specific NORAD ID
- **Missing**: A global endpoint to list all observations with filters

## Proposed Solution

### 1. New API Endpoint (`api/routers/observations.py`)
Add `GET /v2/observations` supporting:
- `source` — filter by source
- `object_type` — filter by object type  
- `origin_country` — filter by country
- `search` — partial match on object_name
- `has_anomaly` — boolean filter on `thermal.anomaly_flag`
- `health_score_min` / `health_score_max` — range on `derived_health_score`
- `epoch_from` / `epoch_to` — date range on `observation_epoch`
- `skip` / `limit` — pagination (default limit=50)
- `sort_by` / `sort_order` — sorting

### 2. New ObservationsView Component
**Layout**: Mirror Table View layout:
- Left sidebar (280px) with `ObservationsFilters` component
- Main content area with paginated table + header count (like `{total} observations`)

**Header**: Two-line like modal:
```
Observational Data
{total} observations
```
(These go in the page header area or a content header, styled like the modal header but adapted for full-page view)

**Table**: Reuse the exact same two-line header structure from ObservationsModal (`TOP_LEVEL_COLUMNS` with rowSpan + `SECTION_COLUMNS` with section/sub headers). Same CSS classes.

**Pagination**: Same pattern as Table View.

### 3. ObservationsFilters Component
Sidebar filters relevant to observational data:
- **Search** (object name text input)
- **Source** (select dropdown)
- **Object Type** (select dropdown)
- **Country** (select dropdown)
- **Health Score Range** (min/max number inputs)
- **Epoch Date Range** (from/to date inputs)
- **Has Anomaly** (checkbox/toggle)
- **Reset** button

Styled to match existing `Filters.css` pattern (same 280px width sidebar with `.filter-group` pattern).

### 4. App.jsx Changes
- Add `observations` tab button in `<nav>` between "Table View" and "Graphs"
- Add state for observations tab: `obsFilters`, `obsPage`, `obsObjects`, `obsTotal`, `obsLoading`
- Fetch from new `/v2/observations` endpoint
- Render `<ObservationsView>` when `activeTab === 'observations'`
- Show `{total} observations` count in header when on observations tab

## Key Design Decisions

1. **Font/style consistency**: Use same `.observations-table` CSS classes from ObservationsModal — share or duplicate styles in ObservationsView.css
2. **Two-line header**: Page-level header shows "Observational Data" as h2 + subtitle line (count + active filters summary), matching modal pattern
3. **Sidebar width**: 280px, same as Table View sidebar
4. **Table reuse**: Extract `TOP_LEVEL_COLUMNS`, `SECTION_COLUMNS`, `SECTION_FIELD_KEYS`, `formatCell` into a shared module (`components/observationsConfig.js`) or duplicate in the new component

## Implementation Notes

- The API endpoint needs an AQL query that filters across the `observations` collection without a required norad_id
- Available filter fields from the data model (from ObservationsModal): `source`, `object_name`, `object_type`, `origin_country`, `derived_health_score`, `observation_epoch`, `thermal.anomaly_flag`
- For the `sources` and `object_types` dropdowns, either hardcode reasonable values or add dedicated `/v2/observations/filter-options` endpoint
