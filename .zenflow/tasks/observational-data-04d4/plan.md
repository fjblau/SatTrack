# Observational Data Feature

## Configuration
- **Artifacts Path**: `.zenflow/tasks/observational-data-04d4`

---

## Workflow Steps

### [x] Step: Investigation and Planning
<!-- chat-id: 826c77c4-1640-4704-a277-cc011db1f91e -->

Investigated codebase, ArangoDB structure, and existing satellite detail page.

Findings saved to `.zenflow/tasks/observational-data-04d4/investigation.md`.

Key findings:
- ArangoDB `kessler` DB has satellites collection with `canonical.norad_cat_id` as shared key
- PRETTY satellite (NORAD 58023) exists in DB
- DetailPanel.jsx has header buttons area (MQTT Feed button is the target neighbor)
- Need: new `satellite_observations` collection, backend router, frontend ObservationsModal component

### [ ] Step: Implementation

Read `.zenflow/tasks/observational-data-04d4/investigation.md` for full details.

1. Create `observations` collection in ArangoDB (add constant `COLLECTION_OBSERVATIONS = 'observations'` in `database/connection.py`)
2. Import sample observational data for PRETTY (NORAD 58023) and update satellite canonical with metadata
3. Create `api/routers/observations.py` with `GET /v2/observations/{norad_id}` endpoint
4. Register observations router in `api/main.py`
5. Add `OBSERVATIONS` to `API_ENDPOINTS` in `react-app/src/config/constants.js`
6. Create `react-app/src/components/ObservationsModal.jsx` (flattened table of observations)
7. Create `react-app/src/components/ObservationsModal.css`
8. Add "Observations" button in `DetailPanel.jsx` header buttons section (next to MQTT button)
