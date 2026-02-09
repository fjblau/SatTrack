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

---

## Workflow Steps

### [x] Step: Technical Specification
<!-- chat-id: 527daa6f-dcf9-4268-812d-69911d3fc6f5 -->

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

### [x] Step: Add SGP4 Dependency
<!-- chat-id: 165ff26d-2830-4f02-a4a4-461ca85eaabe -->

Add the `sgp4` library to project dependencies and verify installation.

**Tasks**:
- Add `sgp4>=2.23` to `requirements.txt`
- Install the library: `pip install sgp4`
- Verify import works: `python -c "from sgp4.api import Satrec, jday; print('SGP4 installed successfully')"`

**Verification**:
- Library installs without errors
- Import statement succeeds
- No conflicts with existing dependencies

---

### [x] Step: Implement Propagation Service
<!-- chat-id: a226bf16-83bc-45ef-a806-a5906919c5e5 -->

Create `api/services/propagation_service.py` to handle orbit propagation logic.

**Implementation Details**:
- Create `PropagationService` class with `propagate_orbit()` method
- Accept TLE lines (line1, line2), optional start time (defaults to current UTC), and interval
- Use SGP4 to initialize satellite object from TLE
- Extract TLE epoch from line 1
- Calculate **TLE epoch position** (position at TLE epoch time)
- Calculate **current position** (position at start_time, typically "now")
- Calculate orbital period from mean motion in TLE
- Generate **future positions** starting from start_time at specified intervals for one complete orbit
- Return both ECI (Earth-Centered Inertial) and geodetic (lat/lon/alt) coordinates for all positions
- Return structure: `{tle_epoch_position, current_position, future_positions, orbital_period_minutes, ...}`
- Handle propagation errors (decayed satellites, invalid TLEs, etc.)

**Unit Tests** (`tests/unit/test_propagation_service.py`):
- Test with ISS TLE (NORAD 25544) - known stable orbit
- Verify TLE epoch position is calculated correctly
- Verify current position (at start_time) is calculated correctly
- Verify correct number of future positions calculated (period / interval)
- Validate position data structure (ECI and geodetic coordinates) for all three position types
- Test that future_positions start from start_time, not TLE epoch
- Test error handling: invalid TLE format, propagation failures
- Test different intervals (1 min, 5 min, 10 min)
- Test custom start times

**Verification**:
- Run unit tests: `pytest tests/unit/test_propagation_service.py -v`
- All tests pass
- Code coverage >80% for new service

---

### [ ] Step: Add Orbit Calculation API Endpoint

Add new endpoint to `api/routers/tle.py` for orbit calculation.

**Implementation Details**:
- Add `GET /v2/tle/{norad_id}/orbit` endpoint
- Query parameters:
  - `start_time` (optional): ISO 8601 timestamp
  - `interval_minutes` (optional, default=1, max=10)
- Integrate with existing `tle_service.fetch_tle_by_norad_id()`
- Call `propagation_service.propagate_orbit()`
- Return formatted JSON response with satellite info and positions
- Handle errors: TLE not found (404), propagation errors (400/500)

**Integration Tests** (`tests/integration/test_tle_orbit_endpoint.py`):
- Test successful orbit calculation with ISS (NORAD 25544)
- Test with different NORAD IDs
- Test query parameters (start_time, interval_minutes)
- Test error cases: invalid NORAD ID, TLE not found
- Verify response format matches specification
- Test caching behavior (leverages existing TLE cache)

**Verification**:
- Run integration tests: `pytest tests/integration/test_tle_orbit_endpoint.py -v`
- All tests pass
- Manual API test: `curl http://localhost:8000/v2/tle/25544/orbit`
- Response matches expected format

---

### [ ] Step: Create Orbit Calculation Modal Component

Create the React modal component to display orbit calculation results in a table.

**Implementation Details**:
- Create `react-app/src/components/OrbitCalculationModal.jsx`
- Create `react-app/src/components/OrbitCalculationModal.css`
- Modal features:
  - **Header section**:
    - Satellite name and NORAD ID
    - TLE epoch date/time
    - **Last TLE Position** (tle_epoch_position): Display time, lat, lon, alt with note "Position at TLE epoch"
    - **Estimated Current Position** (current_position): Display time, lat, lon, alt with note "Estimated position now"
    - Orbital period
  - Interval selector dropdown (1, 2, 5 minutes)
  - Loading spinner during API call
  - **Future positions table** with scrollable body and fixed header:
    - Title: "Future Orbit Positions (starting from current time)"
    - Columns: Time, Latitude, Longitude, Altitude, ECI X/Y/Z (collapsible)
    - Displays `future_positions` array from API response
  - Close button and click-outside-to-close behavior
  - Error message display
- Follow existing modal patterns from `MqttConfigModal.jsx`
- Responsive design

**API Integration**:
- Fetch from `/api/v2/tle/{norad_id}/orbit?interval_minutes={interval}`
- Handle loading states
- Handle errors (404, 400, network errors)
- Display user-friendly error messages

**Styling**:
- Consistent with existing modal styles
- Table formatting: zebra striping, hover effects
- Number formatting: lat/lon (2 decimals), alt (1 decimal)
- Right-align numeric columns

**Verification**:
- Component renders correctly
- Modal opens/closes properly
- Header displays Last TLE Position and Estimated Current Position correctly
- Table displays future positions starting from current time
- Table shows correct number of rows (orbital period / interval)
- Interval selector works and triggers recalculation
- Position formatting is correct (lat/lon: 2 decimals, alt: 1 decimal)
- Error states display properly
- Responsive on different screen sizes

---

### [ ] Step: Integrate Orbit Button in DetailPanel

Add "Calculate Orbit" button to the DetailPanel component next to "MQTT Feed" button.

**Implementation Details**:
- Modify `react-app/src/components/DetailPanel.jsx`
- Add button next to MQTT Feed button (line ~199-206)
- Add state variables:
  - `showOrbitCalculation`
  - `orbitData`
  - `orbitLoading`
- Import and render `OrbitCalculationModal` component
- Pass necessary props: NORAD ID, satellite name, TLE data
- Button only shows when valid TLE data exists (same condition as MQTT button)

**Button Styling**:
- Add CSS for `orbit-calculation-button` class
- Match styling of adjacent MQTT Feed button
- Ensure proper spacing between buttons

**Verification**:
- Button appears next to MQTT Feed button
- Button only shows for satellites with TLE data
- Clicking button opens modal
- Modal receives correct satellite data
- Test with multiple satellites (ISS, geostationary, MEO)

---

### [ ] Step: Manual Verification and Documentation

Perform end-to-end manual testing and create completion report.

**Backend Testing**:
- Test with ISS (NORAD 25544): verify ~90-minute orbital period
- Test with geostationary satellite: verify ~24-hour period
- Test with MEO satellite (GPS): verify ~12-hour period
- Compare first/last positions to ensure orbit closes correctly
- Verify geodetic coordinates make sense (lat: -90 to 90, lon: -180 to 180)
- Test edge cases: very old TLE, recently launched satellite

**Frontend Testing**:
- Complete user workflow: select satellite → click button → view orbit data
- **Verify header positions**:
  - Last TLE Position timestamp matches TLE epoch
  - Estimated Current Position timestamp is current time
  - Positions differ appropriately based on time elapsed since TLE epoch
  - Both positions show reasonable lat/lon/alt values
- **Verify future positions table**:
  - First row starts at current time (matches Estimated Current Position timestamp)
  - Subsequent rows increment by the selected interval
  - Positions complete one full orbit (period matches expected value)
- Test with different satellites and orbital periods (LEO ~90 min, GEO ~24 hours)
- Test interval selector (1, 2, 5 minutes) and verify recalculation
- Verify table scrolling with long datasets
- Test modal close behavior (button, outside click, escape key)
- Test error scenarios: invalid NORAD ID, network error, TLE not found
- Cross-browser testing (Chrome, Firefox, Safari)
- Responsive design testing (desktop, tablet, mobile)

**Documentation**:
- Update API documentation with new endpoint details
- Create report at `{@artifacts_path}/report.md` with:
  - Summary of implementation
  - Test results and coverage
  - Manual verification outcomes
  - Known limitations (TLE age, accuracy degradation)
  - Example API calls and responses
  - Screenshots of UI (optional)
  - Any challenges encountered

**Final Verification**:
- Run full backend test suite: `pytest tests/ -v`
- Run frontend build: `cd react-app && npm run build`
- Check for any lint/type errors
- Ensure all workflow steps are completed
- Test deployed application (if applicable)
