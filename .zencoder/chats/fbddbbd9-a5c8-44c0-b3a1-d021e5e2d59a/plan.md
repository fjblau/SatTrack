# Implementation Plan: Observation Graph and AQL Editor

## Workflow Steps

### [x] 1. Backend: Analytics and AQL Endpoints
Implement new analytics and AQL execution routes in `api/routers/observations.py`.
- Implement `GET /v2/observations/analytics/health-over-time`.
- Implement `GET /v2/observations/analytics/anomaly-distribution`.
- Implement `GET /v2/observations/analytics/source-distribution`.
- Implement `POST /v2/observations/aql`.
- **Verification**: Use `curl` or Postman to verify endpoints return valid JSON.

### [x] 2. Backend: Observation Graph Endpoint
Implement the observation neighborhood graph endpoint in `api/routers/graphs.py`.
- Implement `GET /v2/graphs/observations/neighborhood?norad_id=...`.
- Ensure it returns a structure compatible with `GraphViewer.jsx` (nodes/edges).
- **Verification**: Verify the graph structure contains the satellite, observations, and source nodes.

### [x] 3. Frontend: Configuration and Navigation
Update constants and navigation.
- Add new endpoints to `react-app/src/config/constants.js`.
- Modify `react-app/src/App.jsx` to add "Observation Graphs" tab (admin-only).
- **Verification**: Login as admin and verify the new tab is visible.

### [x] 4. Frontend: ObservationGraphs Component
Create the main component with sidebar navigation.
- Create `react-app/src/components/ObservationGraphs.jsx` and `.css`.
- Implement the sidebar to switch between different views.
- **Verification**: Verify sidebar navigation works and switches components.

### [x] 5. Frontend: Observation Network (Graph View)
Implement the graph visualization using `GraphViewer`.
- Integrate `GraphViewer` with `graphType="neighborhood"`.
- Implement a search bar to select a satellite by `norad_id`.
- **Verification**: Searching for a satellite should render its observation network.

### [x] 6. Frontend: Analytics Charts
Implement the SVG-based charts.
- Implement Health Trends (line chart).
- Implement Anomaly Analysis and Source Statistics (bar charts).
- **Verification**: Verify charts render correctly with real data from the backend.

### [x] 7. Frontend: AQL Editor
Implement the AQL editor functionality.
- Add text area for query input and a result display area.
- Handle success and error states (e.g., syntax errors).
- **Verification**: Execute `FOR o IN observations LIMIT 5 RETURN o` and verify results.

### [x] 8. Final Review
- Manual verification of all features.
- Run `npm run lint` and backend tests.
