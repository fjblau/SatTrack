# Technical Specification: TLE Persistence & Parsing

## Difficulty Assessment
**Medium** — Multi-layer change touching database, API, and frontend. Logic is clear, but requires careful integration across three layers and correct use of sgp4's parsed fields.

---

## Technical Context

### Language & Runtime
- **Backend**: Python 3.11, FastAPI, ArangoDB (python-arango)
- **Frontend**: React 19, Vite, JSX

### Relevant Dependencies (already installed)
- `sgp4>=2.23` — TLE parsing via `sgp4.api.Satrec`
- `skyfield>=1.46` — already used in `propagation_service.py`
- `python-arango>=7.8.0` — ArangoDB client

### Current Behavior
1. User clicks a satellite row → `DetailPanel.jsx` calls `/v2/satellite/{identifier}` to load the full document, then calls `/v2/tle/{norad_id}` to fetch the current TLE.
2. The TLE is displayed in the UI but **never persisted** to ArangoDB.
3. `canonical.tle` in the satellite document only stores `line1` and `line2` (set during bulk import, never live-updated).

---

## Implementation Approach

### 1. Backend: TLE Parsing Utility (`api/services/tle_service.py`)
Add a function `parse_tle_fields(name, line1, line2)` that uses `sgp4.api.Satrec.twoline2rv` to extract:
- `line1`, `line2` — raw TLE strings
- `name` — satellite name from TLE header
- `epoch_year`, `epoch_day` — TLE epoch
- `bstar` — drag coefficient
- `inclination_deg` — inclination (radians → degrees)
- `raan_deg` — right ascension of ascending node (radians → degrees)
- `eccentricity` — orbital eccentricity
- `arg_of_perigee_deg` — argument of perigee (radians → degrees)
- `mean_anomaly_deg` — mean anomaly (radians → degrees)
- `mean_motion_rev_per_day` — mean motion converted from rad/min to rev/day
- `rev_number` — revolution number at epoch
- `ndot` — first derivative of mean motion
- `nddot` — second derivative of mean motion
- `fetched_at` — ISO 8601 timestamp of when TLE was fetched

### 2. Backend: DB Update Function (`database/operations.py`)
Add `update_satellite_tle(identifier, norad_id, tle_data)`:
- Finds the satellite document by `identifier`
- Merges parsed TLE data into `sources["tleapi"]` (following existing source structure)
- Updates `canonical.tle` with parsed fields (always overwrite with fresh data)
- Updates `metadata.last_updated_at`
- Returns updated doc or `None` if satellite not found

### 3. Backend: API Endpoint (`api/routers/tle.py`)
Add `POST /v2/tle/{norad_id}/persist`:
- Request body: `{ "identifier": str }` (the satellite's ArangoDB identifier)
- Fetches TLE via existing `fetch_tle_by_norad_id(norad_id)`
- Parses TLE using new `parse_tle_fields()`
- Calls `update_satellite_tle()` to persist
- Returns the persisted TLE fields and update timestamp
- Returns 404 if TLE not found from API, 404 if satellite not in DB

### 4. Frontend: Persist TLE on Click (`react-app/src/components/DetailPanel.jsx`)
In `fetchCurrentTle` (the `useEffect` that fetches TLE after satellite load):
- After successfully fetching TLE (`data.data` is set), call `POST /v2/tle/{norad_id}/persist` with `{ identifier }` in the background (fire-and-forget, no UI blocking, log errors to console only)

### 5. Frontend: Add Endpoint Constant (`react-app/src/config/constants.js`)
Add `TLE_PERSIST: '/v2/tle'` (used as `/v2/tle/{norad_id}/persist`) under `API_ENDPOINTS`.

---

## Data Model Changes

### `canonical.tle` — extended from `{ line1, line2 }` to:
```json
{
  "line1": "...",
  "line2": "...",
  "name": "...",
  "epoch_year": 25,
  "epoch_day": 65.123456,
  "bstar": 0.000123,
  "inclination_deg": 51.6,
  "raan_deg": 201.3,
  "eccentricity": 0.0006703,
  "arg_of_perigee_deg": 130.5,
  "mean_anomaly_deg": 325.0,
  "mean_motion_rev_per_day": 15.49,
  "rev_number": 42000,
  "ndot": 0.00001,
  "nddot": 0.0,
  "fetched_at": "2026-03-09T20:00:00Z"
}
```

### `sources.tleapi` — stores raw + parsed data:
```json
{
  "line1": "...",
  "line2": "...",
  "name": "...",
  "norad_id": "25544",
  "fetched_at": "...",
  "updated_at": "...",
  "parsed": { ... }
}
```

---

## Source Code Files Modified

| File | Change |
|------|--------|
| `api/services/tle_service.py` | Add `parse_tle_fields()` function |
| `database/operations.py` | Add `update_satellite_tle()` function |
| `database/__init__.py` | Export `update_satellite_tle` |
| `api/routers/tle.py` | Add `POST /v2/tle/{norad_id}/persist` endpoint |
| `react-app/src/components/DetailPanel.jsx` | Call persist endpoint after TLE fetch |
| `react-app/src/config/constants.js` | Add `TLE_PERSIST` endpoint constant |

---

## Verification Approach

### Manual
1. Start both services (`./start.sh`)
2. Open the React app, click any satellite with a NORAD ID
3. Observe in network tab: `POST /v2/tle/{norad_id}/persist` is called
4. Query ArangoDB directly or use `/v2/satellite/{identifier}` to confirm `canonical.tle` now contains parsed fields

### Automated
- No existing test framework is set up for unit tests on these code paths (test files exist under `tests/` but focus on integration)
- Run linting manually if a linter is configured
