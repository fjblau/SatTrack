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
<!-- chat-id: b5c101dd-648d-4dcd-8323-e1d16feb4c6f -->

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

### [x] Step: Database and MQTT Publisher Core
<!-- chat-id: 02933789-ab17-4b5d-9ef5-bf3bf2419841 -->

Implement the database layer and MQTT publishing functionality.

**Tasks**:
- Add `paho-mqtt` and `apscheduler` to `requirements.txt`
- Create MQTT configurations collection in ArangoDB via `db.py`
  - Add `get_mqtt_configurations_collection()` function
  - Add `save_mqtt_configuration()`, `get_mqtt_configuration()`, `delete_mqtt_configuration()` functions
  - Add `get_enabled_mqtt_configurations()`, `update_last_published()` functions
  - Create indexes: `satellite_id`, `norad_id`, `enabled`, `next_publish`
- Create `mqtt_publisher.py` module
  - Implement `convert_tle_to_json()` - convert TLE data to JSON format (as per spec)
  - Implement `publish_tle_to_mqtt()` - connect to MQTT broker and publish
  - Implement `test_mqtt_connection()` - validate broker connectivity
  - Add error handling for connection issues

**Verification**:
- Manually test database functions in Python REPL or test script
- Test MQTT publisher against local Mosquitto broker (if available) or public test broker
- Verify JSON payload structure matches spec

---

### [x] Step: REST API Endpoints
<!-- chat-id: e96a9aaa-6400-4d87-94e0-bab4362a5bed -->

Add FastAPI endpoints for MQTT configuration management.

**Tasks**:
- Update `api.py` with new endpoints:
  - `GET /v2/mqtt/config/{satellite_id}` - retrieve configuration
  - `POST /v2/mqtt/config` - create/update configuration
  - `DELETE /v2/mqtt/config/{satellite_id}` - delete configuration
  - `POST /v2/mqtt/test-connection` - test broker connection
  - `POST /v2/mqtt/publish-now/{satellite_id}` - manual publish trigger
- Add input validation for all endpoints
- Implement password redaction in responses
- Add proper error responses (404, 400, 500)

**Verification**:
- Test each endpoint with `curl` or Postman/Insomnia
- Verify CRUD operations work correctly
- Test error cases (invalid inputs, missing data, etc.)
- Verify password redaction in GET responses

---

### [x] Step: Background Scheduler Integration
<!-- chat-id: aa655d66-b67a-4389-95d6-f2df9b14892f -->

Implement periodic TLE publishing using APScheduler.

**Tasks**:
- Create `mqtt_scheduler.py` module
  - Implement `initialize_scheduler()` - start BackgroundScheduler
  - Implement `schedule_mqtt_publish()` - add/update scheduled job
  - Implement `remove_scheduled_job()` - remove job
  - Implement `publish_tle_job()` - scheduled job function that fetches TLE, publishes to MQTT, updates timestamps
- Update `api.py` lifespan context manager
  - Initialize scheduler on startup
  - Load enabled configurations and schedule jobs
  - Gracefully stop scheduler on shutdown
- Update POST/DELETE config endpoints to schedule/remove jobs

**Verification**:
- Start the API server and verify scheduler initializes
- Create MQTT configuration and verify job is scheduled
- Monitor logs to confirm scheduled job executes at correct interval
- Verify MQTT messages are published (use MQTT client to subscribe)
- Test configuration updates reschedule jobs correctly
- Test delete configuration removes scheduled job

---

### [x] Step: Frontend MQTT Configuration UI
<!-- chat-id: 44b876bb-34b8-45eb-931e-ce254fdc80c4 -->

Create the React components for MQTT configuration.

**Tasks**:
- Create `MqttConfigModal.jsx` component
  - Modal dialog with form fields: broker host, port, username, password, topic, frequency
  - Load existing configuration from API on mount
  - Validate form inputs (required fields, port range, etc.)
  - Save configuration via POST `/v2/mqtt/config`
  - Delete configuration via DELETE endpoint
  - Display success/error messages
  - Optional: Test connection button
- Create `MqttConfigModal.css` following existing CSS patterns
- Update `DetailPanel.jsx`
  - Add "MQTT Feed" button next to "Track on N2YO" (visible when TLE data is available)
  - Add state for modal visibility
  - Import and render MqttConfigModal
  - Pass satellite data and TLE data to modal

**Verification**:
- Start frontend dev server (`npm run dev`)
- Navigate to satellite with TLE data
- Verify "MQTT Feed" button appears
- Click button and verify modal opens
- Fill form and save configuration
- Verify configuration persists (reload page, reopen modal)
- Test editing existing configuration
- Test deleting configuration
- Verify error handling for invalid inputs

---

### [x] Step: End-to-End Testing and Documentation
<!-- chat-id: 4f2e77a5-1026-4849-9d61-8720291cf45a -->

Perform comprehensive testing and create implementation report.

**Tasks**:
- **Manual E2E Testing**:
  - Set up local MQTT broker (Mosquitto or public test broker)
  - Configure MQTT feed for test satellite
  - Subscribe to topic and verify JSON payload format
  - Test both 8-hour and 24-hour frequencies
  - Test "Publish Now" functionality
  - Verify scheduler persistence across server restarts
  - Test error scenarios (invalid credentials, unreachable broker, missing TLE)
- **Code Quality**:
  - Run linters if available (check README/package.json for commands)
  - Check for console errors in browser
  - Review code for security issues (password handling, input validation)
- **Report Creation**:
  - Write `{@artifacts_path}/report.md` with:
    - Summary of implementation
    - Testing approach and results
    - Known issues or limitations
    - Suggestions for future enhancements

**Verification**:
- All manual test cases pass
- No console errors or warnings
- MQTT messages successfully published to broker
- Configuration UI is intuitive and error-free
