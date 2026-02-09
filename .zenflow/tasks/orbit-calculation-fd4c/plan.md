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

### [ ] Step: Add SGP4 Dependency

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

### [ ] Step: Implement Propagation Service

Create `api/services/propagation_service.py` to handle orbit propagation logic.

**Implementation Details**:
- Create `PropagationService` class with `propagate_orbit()` method
- Accept TLE lines (line1, line2), optional start time, and interval
- Use SGP4 to initialize satellite object from TLE
- Calculate orbital period from mean motion in TLE
- Generate positions at specified intervals for one complete orbit
- Return both ECI (Earth-Centered Inertial) and geodetic (lat/lon/alt) coordinates
- Handle propagation errors (decayed satellites, invalid TLEs, etc.)

**Unit Tests** (`tests/unit/test_propagation_service.py`):
- Test with ISS TLE (NORAD 25544) - known stable orbit
- Verify correct number of positions calculated (period / interval)
- Validate position data structure (ECI and geodetic coordinates)
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

### [ ] Step: Manual Verification and Documentation

Perform end-to-end manual testing and create completion report.

**Manual Testing**:
- Test with ISS (NORAD 25544): verify ~90-minute orbital period
- Test with geostationary satellite: verify ~24-hour period
- Test with MEO satellite (GPS): verify ~12-hour period
- Compare first/last positions to ensure orbit closes correctly
- Verify geodetic coordinates make sense (lat: -90 to 90, lon: -180 to 180)
- Test edge cases: very old TLE, recently launched satellite

**Documentation**:
- Update API documentation with new endpoint details
- Create report at `{@artifacts_path}/report.md` with:
  - Summary of implementation
  - Test results and coverage
  - Manual verification outcomes
  - Known limitations (TLE age, accuracy degradation)
  - Example API calls and responses
  - Any challenges encountered

**Final Verification**:
- Run full test suite: `pytest tests/ -v`
- Check for any lint/type errors
- Ensure all workflow steps are completed
