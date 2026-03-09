# Spec and build

## Configuration
- **Artifacts Path**: {@artifacts_path} → `.zenflow/tasks/{task_id}`

---

## Agent Instructions

Ask the user questions when anything is unclear or needs their input. This includes:
- Ambiguous or incomplete requirements
- Technical decisions that affect architecture or user experience
- Trade-offs that require business context

Do not make assumptions on important decisions — get clarification first.

If you are blocked and need user clarification, mark the current step with `[!]` in plan.md before stopping.

---

## Workflow Steps

### [x] Step: Technical Specification
<!-- chat-id: 0d033743-0b77-4d8c-bd0a-31f91cf98466 -->

Assess the task's difficulty, as underestimating it leads to poor outcomes.
- easy: Straightforward implementation, trivial bug fix or feature
- medium: Moderate complexity, some edge cases or caveats to consider
- hard: Complex logic, many caveats, architectural considerations, or high-risk changes

Create a technical specification for the task that is appropriate for the complexity level:
- Review the existing codebase architecture and identify reusable components.
- Define the implementation approach based on established patterns in the project.
- Identify all source code files that will be created or modified.
- Define any necessary data model, API, or interface changes.
- Describe verification steps using the project's test and lint commands.

Save the output to `{@artifacts_path}/spec.md` with:
- Technical context (language, dependencies)
- Implementation approach
- Source code structure changes
- Data model / API / interface changes
- Verification approach

If the task is complex enough, create a detailed implementation plan based on `{@artifacts_path}/spec.md`:
- Break down the work into concrete tasks (incrementable, testable milestones)
- Each task should reference relevant contracts and include verification steps
- Replace the Implementation step below with the planned tasks

Rule of thumb for step size: each step should represent a coherent unit of work (e.g., implement a component, add an API endpoint, write tests for a module). Avoid steps that are too granular (single function).

Important: unit tests must be part of each implementation task, not separate tasks. Each task should implement the code and its tests together, if relevant.

Save to `{@artifacts_path}/plan.md`. If the feature is trivial and doesn't warrant this breakdown, keep the Implementation step below as is.

---

### [x] Step: Backend - TLE Parsing & DB Persistence
<!-- chat-id: 50216d2d-cb8f-4567-82b4-07fa918ef98d -->

Implement the backend changes for TLE persistence:
- Add `parse_tle_fields(name, line1, line2)` in `api/services/tle_service.py` using `sgp4.api.Satrec` to extract all individual TLE parameters (inclination, eccentricity, RAAN, arg of perigee, mean anomaly, mean motion, BSTAR, epoch, etc.) converting radians to degrees where appropriate.
- Add `update_satellite_tle(identifier, norad_id, tle_data)` in `database/operations.py` that finds the satellite document, merges raw+parsed TLE into `sources["tleapi"]`, and always overwrites `canonical.tle` with the fresh parsed data.
- Export `update_satellite_tle` from `database/__init__.py`.
- Verify: unit-test `parse_tle_fields` with a known TLE string and assert correct field values.

---

### [x] Step: Backend - Persist TLE API Endpoint
<!-- chat-id: c7fe7d89-e3e0-43ed-9e3e-2b4eb9afc0b5 -->

Add the API endpoint to wire TLE fetch + parse + persist together:
- Add `POST /v2/tle/{norad_id}/persist` in `api/routers/tle.py`.
- Request body: `{ "identifier": str }`.
- Internally: fetch TLE via `fetch_tle_by_norad_id`, parse with `parse_tle_fields`, call `update_satellite_tle`.
- Return persisted TLE fields + timestamp on success; 404 if TLE not found or satellite not in DB.
- Verify: manually call the endpoint (via FastAPI docs or curl) with a known NORAD ID and confirm the DB document is updated.

---

### [x] Step: Frontend - Call Persist Endpoint on Satellite Click
<!-- chat-id: ad420b06-6ec3-4ce8-94fa-04fd02ca76c6 -->

Update the React frontend to persist TLE when a satellite is selected:
- Add `TLE_PERSIST: '/v2/tle'` to `API_ENDPOINTS` in `react-app/src/config/constants.js`.
- In `DetailPanel.jsx`, inside `fetchCurrentTle` after a successful TLE response, fire-and-forget `POST /v2/tle/{norad_id}/persist` with `{ identifier }` — no UI blocking, errors logged to console only.
- Verify: open the app, click a satellite with a NORAD ID, confirm the persist request appears in the network tab and the ArangoDB document's `canonical.tle` is populated with parsed fields.

---
