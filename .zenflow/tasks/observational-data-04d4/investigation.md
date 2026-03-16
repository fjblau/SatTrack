# Investigation: Observational Data Feature

## Summary

Add a new `satellite_observations` collection to ArangoDB for real-time observational data (multiple observations per satellite, keyed by NORAD ID). Surface this data from the Satellite detail page via a new "Observations" button next to the MQTT button.

## Existing Architecture

### Database (ArangoDB `kessler` DB)
- **Existing collections**: satellites, constellation_membership, registration_documents, orbital_proximity, collision_risk_edges, satellite_lineage, registration_links, mqtt_configurations
- **Satellite document structure**: envelope with `identifier`, `canonical`, `sources`, `metadata`
- **Canonical fields include**: `norad_cat_id` (the shared key for cross-collection queries), `name`, `status`, `orbit`, `tle`, etc.
- **PRETTY satellite (NORAD 58023)**: Exists in DB. `norad_cat_id` is an integer in some records, string in others.

### Backend (FastAPI)
- `api/main.py`: includes routers for satellites, metadata, graphs, documents, tle, mqtt, admin
- `api/routers/satellites.py`: satellite detail at `GET /v2/satellite/{identifier}` returns `canonical`, `sources`, `metadata`
- `database/connection.py`: ArangoDB connection management, collection/graph name constants
- `database/__init__.py`: exports all DB functions

### Frontend (React)
- `react-app/src/config/constants.js`: API_ENDPOINTS constants (needs new entry)
- `react-app/src/components/DetailPanel.jsx`: satellite detail view
  - Header buttons area (lines 232-267): "Show Data Record", "Track on N2YO", "MQTT Feed", "Calculate Orbit"
  - **MQTT Feed button** is at line 252-258 (shown when TLE data available)
  - New "Observations" button goes next to MQTT button

## Proposed Solution

### 1. New ArangoDB Collection: `satellite_observations`
- Collection name: `satellite_observations`
- Documents indexed on `norad_id` (integer, shared key with satellites collection)
- Each document = one observation record (multiple per satellite)
- Fields from the sample data:
  - `norad_id`, `observation_epoch`, `source`, `object_name`, `object_type`, `origin_country`
  - `estimated_mass_kg`, `spin_rate_rpm`
  - Nested: `attitude` (roll_deg, pitch_deg, yaw_deg, stability_flag)
  - Nested: `thermal` (surface_temp_K, temp_variance_30d, anomaly_flag)
  - Nested: `material_signature` (reflectivity_index, inferred_material, confidence)
  - Nested: `proximity_state` (range_km, relative_velocity_ms)
  - `derived_health_score`
  - Nested: `maneuver_indicator` (delta_v_residual_ms, confidence, flag)
  - Nested: `orbital_decay_indicator` (perigee_drift_km_per_day, estimated_perigee_km)

### 2. Satellite Canonical: Add Observational Data Node
Add `observational_data` field to satellite `canonical` when observations exist:
```json
{
  "observational_data": {
    "has_observations": true,
    "observation_count": 2,
    "last_observation_epoch": "2026-03-01T00:48:51Z",
    "sources": ["kestrel_proxy_v1"]
  }
}
```

### 3. Import Sample Data
Import the 2 PRETTY (NORAD 58023) observation records from the task description into `satellite_observations`. Also update the satellite canonical with the observational data metadata.

### 4. Backend API: New Router `observations.py`
- `GET /v2/observations/{norad_id}` - returns paginated list of observations for a NORAD ID
- `POST /v2/observations` - insert new observation(s) (optional for future)
- Register in `api/main.py`

### 5. Frontend: New ObservationsModal Component
- New file: `react-app/src/components/ObservationsModal.jsx`
- New file: `react-app/src/components/ObservationsModal.css`
- Flattened table view of all observations (flatten nested JSON to dotted-key columns)
- Sort by `observation_epoch` descending
- Button added in `DetailPanel.jsx` header buttons section, next to MQTT button
- Conditional: show button only if `fullDocument?.canonical?.observational_data?.has_observations`
- Update `constants.js`: add `OBSERVATIONS: '/v2/observations'` to `API_ENDPOINTS`

## Affected Components

1. `database/connection.py` - add `COLLECTION_OBSERVATIONS = 'satellite_observations'` constant
2. `database/__init__.py` - export the new constant  
3. `api/routers/observations.py` - new router (create)
4. `api/main.py` - register new router
5. `react-app/src/config/constants.js` - add OBSERVATIONS endpoint
6. `react-app/src/components/DetailPanel.jsx` - add Observations button
7. `react-app/src/components/ObservationsModal.jsx` - new component (create)
8. `react-app/src/components/ObservationsModal.css` - new styles (create)
9. Import script or one-time script - import sample data and update canonical

## Implementation Notes

- `norad_id` in satellite_observations should be stored as integer (matching `canonical.norad_cat_id`)
- The flattened table should convert nested objects like `attitude.roll_deg`, `thermal.surface_temp_K`, etc.
- The button should only appear when the satellite has a NORAD ID and has observations
- Follow the same modal pattern as `MqttConfigModal.jsx` and `OrbitCalculationModal.jsx`
- Add persistent index on `norad_id` field in the new collection for query performance
