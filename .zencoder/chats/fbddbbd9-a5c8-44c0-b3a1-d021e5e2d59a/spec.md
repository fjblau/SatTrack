# Technical Specification: Observation Graph Database and AQL Editor

## Technical Context
- **Language**: Python (FastAPI), JavaScript (React)
- **Database**: ArangoDB
- **Frontend Patterns**: React functional components, `GraphViewer.jsx` (Cytoscape.js for graph visualization), SVG for charts.
- **Authentication**: Token-based, with `is_demo` flag in session storage.

## Implementation Approach

### 1. Backend: Observation Graph and AQL Endpoint
Modify `api/routers/graphs.py` to add the graph neighborhood endpoint:
- **`GET /v2/graphs/observations/neighborhood`**:
  - Parameters: `norad_id` (required).
  - Fetches the satellite node.
  - Fetches all observations for the satellite from the `observations` collection.
  - Extracts unique `source` strings from those observations to create source nodes.
  - Returns a graph structure:
    - **Nodes**:
      - Satellite (center): `{ id, name, type: "satellite", is_source: true }`
      - Observations: `{ id, epoch, type: "observation", is_source: false }`
      - Sources: `{ id: "source/<name>", name, type: "source", is_source: false }`
    - **Edges**:
      - `satellite` -> `observation` (type: "has_observation")
      - `observation` -> `source` (type: "recorded_by")

Modify `api/routers/observations.py` to add analytics and AQL endpoints:
- **`GET /v2/observations/analytics/health-over-time`**: 
  - Groups observations by date and returns `{ date, average_health_score }`.
- **`GET /v2/observations/analytics/anomaly-distribution`**:
  - Groups observations where `thermal.anomaly_flag == true` by `source` or `object_type`.
- **`GET /v2/observations/analytics/source-distribution`**:
  - Groups all observations by `source`.
- **`POST /v2/observations/aql`**:
  - Executes a raw AQL query and returns JSON results.

### 2. Frontend: Observation Graphs Page
- **Navigation**: Update `react-app/src/App.jsx` to include an "Observation Graphs" button in the header (admin-only).
- **New Component `ObservationGraphs.jsx`**:
  - Sidebar for selecting:
    - **Observation Network (Graph View)**: Uses `GraphViewer.jsx` to visualize the relationship between satellites, observations, and ground sources.
    - **Health Trends (Line Chart)**: SVG chart for health scores over time.
    - **Anomaly Analysis (Bar Chart)**: SVG chart for anomaly distribution.
    - **Source Statistics (Bar Chart)**: SVG chart for observation counts.
    - **AQL Editor**: Text area and results panel for running manual queries.
  - **Graph View**:
    - Provides a search/select for `norad_id` to center the graph.
    - Passes fetched data to `GraphViewer` with `graphType="neighborhood"`.

### 3. Configuration
- Update `react-app/src/config/constants.js` to include the new API endpoints.

## Source Code Structure Changes

### New Files:
- `react-app/src/components/ObservationGraphs.jsx`
- `react-app/src/components/ObservationGraphs.css`

### Modified Files:
- `react-app/src/App.jsx`: Add new tab and routing.
- `react-app/src/config/constants.js`: Add API endpoints.
- `api/routers/observations.py`: Add analytics and AQL routes.
- `api/routers/graphs.py`: Add `/v2/graphs/observations/neighborhood` route.

## Data Model / API / Interface Changes

### API Endpoints
- `GET /v2/observations/analytics/health-over-time`
- `GET /v2/observations/analytics/anomaly-distribution?by=source|object_type`
- `GET /v2/observations/analytics/source-distribution`
- `POST /v2/observations/aql`
  - Body: `{ "query": "string" }`
- `GET /v2/graphs/observations/neighborhood?norad_id=12345`
  - Response: `{ "nodes": [...], "edges": [...] }`

## Verification Approach

### Automated Testing
- Unit tests for the new backend endpoints.
- Verify `POST /v2/observations/aql` returns expected data.

### Manual Verification
1. Log in as admin.
2. Verify "Observation Graphs" appears.
3. Select "Observation Network" and search for a satellite to see its connections.
4. Verify the AQL Editor can query the `observations` and `satellites` collections.
5. Verify charts render correctly.
6. Verify access is restricted for demo users.
