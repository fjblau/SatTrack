# Technical Specification: Observation Graphs and AQL Editor

## Technical Context
- **Language**: Python (FastAPI), JavaScript (React)
- **Database**: ArangoDB
- **Frontend Patterns**: React functional components with `useState`, `useEffect`, and manual SVG rendering for charts (matching `TimelineChart.jsx`).
- **Authentication**: Token-based, with `is_demo` flag in session storage to differentiate between admin and demo users.

## Implementation Approach

### 1. Backend: Observation Analytics and AQL Endpoint
Modify `api/routers/observations.py` to add new endpoints:
- **`GET /v2/observations/analytics/health-over-time`**: 
  - Groups observations by date (daily or weekly).
  - Calculates the average `derived_health_score` for each group.
  - Returns a list of `{ date, average_health_score }`.
- **`GET /v2/observations/analytics/anomaly-distribution`**:
  - Groups observations where `thermal.anomaly_flag == true`.
  - Groups by `source` or `object_type`.
  - Returns counts for each group.
- **`GET /v2/observations/analytics/source-distribution`**:
  - Groups all observations by `source`.
  - Returns counts for each source.
- **`POST /v2/observations/aql`**:
  - Accepts a JSON body with a `query` string.
  - Executes the query using `db.aql.execute`.
  - Returns the results as a list.
  - **Security**: Since this is restricted to admins in the UI, we will rely on the existing `AuthMiddleware` which should already be protecting these routes if we ensure they are handled correctly. Note: `AuthMiddleware` currently allows all requests if a token is present, but we should verify if it distinguishes between demo and admin tokens. Looking at `api/routers/auth.py`, it seems it doesn't strictly forbid demo users from hitting certain endpoints yet, other than what's filtered in the frontend. 

### 2. Frontend: Observation Graphs Page
- **Navigation**: Update `react-app/src/App.jsx` to include an "Observation Graphs" button in the header, visible only when `!isDemo`.
- **New Component `ObservationGraphs.jsx`**:
  - Implements a sidebar similar to `GraphExplorer.jsx` for selecting different visualizations:
    - Health Trends
    - Anomaly Analysis
    - Source Statistics
    - AQL Editor
  - **Visualizations**:
    - **Health Trends**: A line chart (SVG) showing average health score over time.
    - **Anomaly Analysis**: A bar chart (SVG) or pie chart showing anomalies by source.
    - **Source Statistics**: A bar chart (SVG) showing observation counts per source.
  - **AQL Editor**:
    - A text area for writing AQL queries.
    - An "Execute" button.
    - A results panel that displays the returned JSON data in a formatted way (e.g., `<pre>` block or table).

### 3. Configuration
- Update `react-app/src/config/constants.js` to include the new API endpoints.

## Source Code Structure Changes

### New Files:
- `react-app/src/components/ObservationGraphs.jsx`
- `react-app/src/components/ObservationGraphs.css`

### Modified Files:
- `react-app/src/App.jsx`: Add new tab and routing logic.
- `react-app/src/config/constants.js`: Add new API endpoints to `API_ENDPOINTS`.
- `api/routers/observations.py`: Add new analytics and AQL routes.

## Data Model / API / Interface Changes

### API Endpoints
- `GET /v2/observations/analytics/health-over-time`
- `GET /v2/observations/analytics/anomaly-distribution?by=source|object_type`
- `GET /v2/observations/analytics/source-distribution`
- `POST /v2/observations/aql`
  - Body: `{ "query": "string" }`
  - Response: `{ "data": [...], "count": number }`

## Verification Approach

### Automated Testing
- Add unit tests in `tests/unit/test_observations_router.py` (if it exists, or create it) to test the new analytics endpoints.
- Ensure `POST /v2/observations/aql` returns expected results for a simple query.

### Manual Verification
1. Log in as admin (not demo).
2. Verify "Observation Graphs" button appears in the header.
3. Click "Observation Graphs" and verify the sidebar and initial graph load.
4. Switch between different visualizations in the sidebar.
5. Use the AQL Editor to run a simple query like `FOR obs IN observations LIMIT 5 RETURN obs` and verify the results are displayed.
6. Log in as demo user and verify "Observation Graphs" button is NOT visible.
7. Verify the AQL editor handles errors (e.g., syntax errors in AQL) gracefully.

### Linting & Type Checking
- Run `npm run lint` in `react-app`.
- Run `ruff` or `flake8` on the backend code.
