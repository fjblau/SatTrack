# Technical Specification: MQTT Feed

## Task Overview
Add MQTT publishing capability to the satellite tracking application, allowing users to configure and subscribe to periodic TLE data updates via MQTT.

## Difficulty Assessment
**Medium Complexity**

**Rationale**:
- Requires frontend UI changes (new button, modal/form)
- Backend MQTT integration with new Python library
- Data persistence for MQTT configurations
- Background task scheduling for periodic publishing
- Security considerations for credential storage
- Data transformation (TLE to JSON)

## Technical Context

### Language & Runtime
- **Frontend**: JavaScript/JSX (React 19.2.3, Vite 7.2.7)
- **Backend**: Python 3.11, FastAPI, uvicorn
- **Database**: ArangoDB

### Current Dependencies
**Frontend**:
- react: 19.2.3
- react-dom: 19.2.3
- vite: 7.2.7
- @vitejs/plugin-react: 5.1.2
- cytoscape: 3.33.1
- cytoscape-cola: 2.5.1

**Backend**:
- fastapi: 0.115.0
- uvicorn[standard]: 0.32.0
- python-arango: >=7.8.0
- pandas: >=2.2.2
- numpy: >=2.1.0
- requests: >=2.32.3
- beautifulsoup4: 4.12.0
- pdfplumber: 0.11.0
- python-dotenv: 1.0.0

### New Dependencies Required
**Backend**:
- `paho-mqtt`: MQTT client library for Python
- `apscheduler`: Advanced Python Scheduler for periodic task execution

## Implementation Approach

### 1. Frontend Changes

#### 1.1 DetailPanel Component Enhancement
**File**: [`./react-app/src/components/DetailPanel.jsx`](./react-app/src/components/DetailPanel.jsx)

Add "MQTT Feed" button next to "Track on N2YO" button in the header section (after line 185-194).

**Button Behavior**:
- Visible when satellite has TLE data available (`currentTle` is not null and not `_notFound`)
- Opens MQTT configuration modal when clicked

#### 1.2 New Component: MqttConfigModal
**File**: `./react-app/src/components/MqttConfigModal.jsx` (new)

**Purpose**: Configuration modal/dialog for MQTT publishing settings

**Features**:
- Form fields:
  - MQTT Broker Host (text input, required)
  - MQTT Broker Port (number input, default: 1883, required)
  - Username (text input, optional)
  - Password (password input, optional)
  - Topic (text input, default: `satellites/{norad_id}/tle`, required)
  - Publish Frequency (dropdown: "8 hours" or "24 hours", default: "24 hours")
  - Enable/Disable toggle (checkbox)
- Actions:
  - Save Configuration button
  - Cancel button
  - Test Connection button (optional, nice-to-have)
  - Delete Configuration button (if one exists)

**State Management**:
- Load existing configuration for the satellite (if any)
- Validate form inputs
- Submit configuration to backend API
- Display success/error messages

#### 1.3 New Component: MqttConfigModal.css
**File**: `./react-app/src/components/MqttConfigModal.css` (new)

Styling for the MQTT configuration modal, following existing CSS patterns in the project.

### 2. Backend Changes

#### 2.1 Database Schema
**Collection**: `mqtt_configurations` (new ArangoDB collection)

**Document Structure**:
```json
{
  "_key": "string",
  "satellite_id": "string",
  "norad_id": "string",
  "mqtt_broker": {
    "host": "string",
    "port": "number",
    "username": "string|null",
    "password": "string|null"
  },
  "topic": "string",
  "frequency_hours": "number",
  "enabled": "boolean",
  "last_published": "ISO8601 timestamp|null",
  "next_publish": "ISO8601 timestamp",
  "created_at": "ISO8601 timestamp",
  "updated_at": "ISO8601 timestamp"
}
```

**Indexes**:
- `satellite_id` (persistent index)
- `norad_id` (persistent index)
- `enabled` (persistent index)
- `next_publish` (persistent index) - for efficient scheduler queries

#### 2.2 Database Module Extensions
**File**: [`./db.py`](./db.py)

Add new functions:
- `get_mqtt_configurations_collection()` - Get or create MQTT configurations collection
- `save_mqtt_configuration(config: Dict)` - Upsert MQTT configuration
- `get_mqtt_configuration(satellite_id: str)` - Retrieve configuration for a satellite
- `delete_mqtt_configuration(satellite_id: str)` - Remove configuration
- `get_enabled_mqtt_configurations()` - Get all enabled configurations
- `update_last_published(config_id: str, timestamp: datetime)` - Update last published timestamp

#### 2.3 MQTT Publishing Module
**File**: `mqtt_publisher.py` (new)

**Purpose**: Handle MQTT connection and publishing

**Functions**:
- `convert_tle_to_json(satellite_data: Dict, tle_data: Dict) -> str`
  - Convert TLE data and satellite metadata to JSON format
  - Include: satellite name, NORAD ID, international designator, TLE lines, timestamp, orbital parameters
  
- `publish_tle_to_mqtt(config: Dict, tle_data: Dict, satellite_data: Dict) -> bool`
  - Connect to MQTT broker using configuration
  - Publish JSON payload to specified topic
  - Handle connection errors and return success status
  
- `test_mqtt_connection(config: Dict) -> bool`
  - Test MQTT broker connectivity
  - Used for connection validation

**Error Handling**:
- Connection timeouts
- Authentication failures
- Network errors
- Invalid credentials

#### 2.4 Background Scheduler Module
**File**: `mqtt_scheduler.py` (new)

**Purpose**: Manage periodic TLE publishing using APScheduler

**Functions**:
- `initialize_scheduler()` - Start APScheduler background scheduler
- `schedule_mqtt_publish(config: Dict)` - Add/update scheduled job for a configuration
- `remove_scheduled_job(config_id: str)` - Remove scheduled job
- `publish_tle_job(config_id: str)` - Job function executed by scheduler
  - Fetch current TLE data
  - Fetch satellite data
  - Publish to MQTT
  - Update `last_published` timestamp
  - Calculate and update `next_publish` timestamp

**Scheduler Configuration**:
- Use `BackgroundScheduler` from APScheduler
- Job store: in-memory (or persistent if needed)
- Jobs execute independently, with error handling per job

#### 2.5 API Endpoints
**File**: [`./api.py`](./api.py)

Add new endpoints:

**1. GET `/v2/mqtt/config/{satellite_id}`**
- Retrieve MQTT configuration for a satellite
- Response: configuration object or 404 if not found

**2. POST `/v2/mqtt/config`**
- Create or update MQTT configuration
- Request body: configuration object (without `_key`, `created_at`, `updated_at`)
- Validates required fields
- Saves to database
- Schedules/updates background job
- Response: saved configuration with generated fields

**3. DELETE `/v2/mqtt/config/{satellite_id}`**
- Delete MQTT configuration
- Removes scheduled job
- Response: success confirmation or 404

**4. POST `/v2/mqtt/test-connection`**
- Test MQTT broker connection
- Request body: broker configuration (host, port, username, password)
- Response: success/failure with error details

**5. POST `/v2/mqtt/publish-now/{satellite_id}`**
- Immediately publish TLE data for a satellite (manual trigger)
- Response: success/failure with published payload

#### 2.6 Application Lifecycle Integration
**File**: [`./api.py`](./api.py)

Update the `lifespan` context manager:
- On startup: Initialize MQTT scheduler and load enabled configurations
- On shutdown: Stop scheduler gracefully

### 3. Data Model & API Contracts

#### 3.1 TLE JSON Format (Published Payload)

```json
{
  "satellite": {
    "norad_id": "string",
    "name": "string",
    "international_designator": "string",
    "country_of_origin": "string"
  },
  "tle": {
    "line1": "string",
    "line2": "string",
    "epoch": "ISO8601 timestamp",
    "classification": "string"
  },
  "orbital_parameters": {
    "apogee_km": "number",
    "perigee_km": "number",
    "inclination_degrees": "number",
    "period_minutes": "number",
    "semi_major_axis_km": "number",
    "eccentricity": "number",
    "mean_motion_rev_day": "number"
  },
  "metadata": {
    "published_at": "ISO8601 timestamp",
    "data_source": "CelesTrak",
    "publisher": "Kessler MQTT Feed"
  }
}
```

#### 3.2 Frontend-Backend API Contracts

**POST `/v2/mqtt/config` Request**:
```json
{
  "satellite_id": "satellites/12345",
  "norad_id": "25544",
  "mqtt_broker": {
    "host": "mqtt.example.com",
    "port": 1883,
    "username": "user",
    "password": "pass"
  },
  "topic": "satellites/25544/tle",
  "frequency_hours": 24,
  "enabled": true
}
```

**POST `/v2/mqtt/config` Response**:
```json
{
  "_key": "generated_key",
  "satellite_id": "satellites/12345",
  "norad_id": "25544",
  "mqtt_broker": {
    "host": "mqtt.example.com",
    "port": 1883,
    "username": "user",
    "password": "[REDACTED]"
  },
  "topic": "satellites/25544/tle",
  "frequency_hours": 24,
  "enabled": true,
  "last_published": null,
  "next_publish": "2026-02-06T06:36:00Z",
  "created_at": "2026-02-05T06:36:00Z",
  "updated_at": "2026-02-05T06:36:00Z"
}
```

**GET `/v2/mqtt/config/{satellite_id}` Response**:
- Same as POST response, or `{"detail": "MQTT configuration not found"}` with 404 status

**DELETE `/v2/mqtt/config/{satellite_id}` Response**:
```json
{
  "success": true,
  "message": "MQTT configuration deleted"
}
```

**POST `/v2/mqtt/test-connection` Request**:
```json
{
  "host": "mqtt.example.com",
  "port": 1883,
  "username": "user",
  "password": "pass"
}
```

**POST `/v2/mqtt/test-connection` Response**:
```json
{
  "success": true,
  "message": "Connection successful"
}
```
or
```json
{
  "success": false,
  "error": "Connection timeout",
  "details": "Failed to connect to mqtt.example.com:1883"
}
```

## Source Code Structure Changes

### New Files
1. **Frontend**:
   - `./react-app/src/components/MqttConfigModal.jsx`
   - `./react-app/src/components/MqttConfigModal.css`

2. **Backend**:
   - `./mqtt_publisher.py`
   - `./mqtt_scheduler.py`

### Modified Files
1. **Frontend**:
   - `./react-app/src/components/DetailPanel.jsx` - Add MQTT Feed button and modal integration

2. **Backend**:
   - `./api.py` - Add MQTT endpoints and scheduler initialization
   - `./db.py` - Add MQTT configuration collection and CRUD functions
   - `./requirements.txt` - Add paho-mqtt and apscheduler dependencies

## Security Considerations

### 1. Credential Storage
- MQTT passwords stored in database (consider encryption at rest)
- Passwords redacted in API responses (show as `[REDACTED]`)
- Environment variables for sensitive defaults (if applicable)

### 2. Input Validation
- Validate MQTT broker host format
- Validate port range (1-65535)
- Sanitize topic strings (prevent MQTT injection)
- Validate frequency values (only 8 or 24 hours)

### 3. Rate Limiting
- Consider adding rate limits to prevent MQTT broker abuse
- Limit number of configurations per satellite to 1

### 4. Error Handling
- Don't expose internal error details to frontend
- Log MQTT connection errors securely on backend
- Handle scheduler failures gracefully

## Verification Approach

### 1. Unit Tests
- Test TLE to JSON conversion
- Test MQTT connection logic
- Test configuration CRUD operations
- Test scheduler job execution

### 2. Integration Tests
- Test full flow: save config → schedule job → publish to MQTT
- Test configuration updates and job rescheduling
- Test delete configuration and job removal

### 3. Manual Verification
1. **Frontend**:
   - Open satellite detail view with TLE data
   - Click "MQTT Feed" button
   - Fill out configuration form
   - Save configuration
   - Verify configuration persists after page reload
   - Test disabling/enabling feed
   - Test deleting configuration

2. **Backend**:
   - Set up local MQTT broker (e.g., Mosquitto)
   - Configure MQTT feed for a test satellite
   - Subscribe to the topic using MQTT client
   - Verify JSON payload is received
   - Wait for scheduled publish and verify timing
   - Test "Publish Now" functionality
   - Check scheduler logs for errors

3. **Error Cases**:
   - Test with invalid MQTT credentials
   - Test with unreachable broker
   - Test with missing TLE data
   - Verify error messages are user-friendly

### 4. Test Commands
After implementation, run:
```bash
# Backend tests (if test framework is available)
pytest test_mqtt_*.py

# Frontend tests (if test framework is available)
npm run test

# Lint and typecheck
npm run lint  # (check if available in package.json)
python -m flake8 mqtt_*.py  # (check if flake8 is available)
```

## Implementation Notes

### Phased Approach
1. **Phase 1: Database & Backend Core**
   - Add database collection and CRUD functions
   - Implement MQTT publisher module
   - Add API endpoints (without scheduler)

2. **Phase 2: Scheduler Integration**
   - Implement scheduler module
   - Integrate scheduler with application lifecycle
   - Add "Publish Now" functionality

3. **Phase 3: Frontend UI**
   - Create MQTT config modal component
   - Add button to DetailPanel
   - Integrate with backend API
   - Handle user feedback (success/error states)

4. **Phase 4: Testing & Refinement**
   - Write unit tests
   - Perform manual verification
   - Handle edge cases
   - Add error handling and user feedback

### Edge Cases to Handle
- Satellite with no TLE data
- TLE data becomes unavailable after configuration
- MQTT broker goes offline
- Database connection issues during scheduled publish
- Scheduler restart (jobs should be reloaded from database)
- Duplicate configuration attempts
- Concurrent updates to same configuration

### Nice-to-Have Features (Future Enhancements)
- Multiple MQTT configurations per satellite
- Custom JSON payload templates
- Publish history log
- Retry mechanism for failed publishes
- Email notifications on publish failures
- QoS (Quality of Service) level selection
- MQTT over TLS/SSL support
- Retained message option
- Wildcard subscriptions for multiple satellites
