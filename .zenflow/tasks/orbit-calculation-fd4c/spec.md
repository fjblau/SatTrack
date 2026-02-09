# Technical Specification: Orbit Calculation

## Task Summary
Implement orbit propagation functionality to calculate satellite positions for one complete orbit at 1-minute intervals given a TLE (Two-Line Element set).

## Complexity Assessment
**Medium**

### Reasoning
- Requires integration of a new Python library for SGP4 orbit propagation
- Need to create new API endpoints and service methods
- Integration with existing TLE service infrastructure
- Moderate testing requirements (unit tests for service, integration tests for API)
- The mathematical complexity is abstracted by well-established libraries
- Edge cases include: invalid TLEs, decayed satellites, different orbital periods

## Technical Context

### Language & Framework
- **Language**: Python 3.11
- **Framework**: FastAPI
- **Existing Dependencies**: pandas, numpy, requests, fastapi, uvicorn

### New Dependencies Required
**Primary Choice**: `sgp4` library (v2.23 or later)
- Official implementation of SGP4/SDP4 orbit propagation models
- Maintained by Brandon Rhodes
- Lightweight, fast, well-tested
- Compatible with TLE format used by the application

**Alternative**: `skyfield` library
- Higher-level API, easier to use
- Includes built-in SGP4 propagation
- Better for astronomical calculations
- Slightly heavier dependency

**Recommendation**: Use `sgp4` for this implementation due to its simplicity, performance, and direct alignment with TLE-based propagation.

### Current Architecture
The application already has:
- **TLE Service** ([./api/services/tle_service.py](./api/services/tle_service.py:117)): Fetches TLE data by NORAD ID with caching
- **Orbital Service** ([./api/services/orbital_service.py](./api/services/orbital_service.py:7)): Calculates orbital parameters (apogee, perigee, period, etc.)
- **TLE Router** ([./api/routers/tle.py](./api/routers/tle.py:9)): Provides `/v2/tle/{norad_id}` endpoint
- **Cache Service**: 1-hour TTL for TLE data
- **Database**: ArangoDB for satellite registry data

## Implementation Approach

### 1. Library Integration
Add `sgp4>=2.23` to [./requirements.txt](./requirements.txt:1)

### 2. Service Layer Extension

**Create new service**: `api/services/propagation_service.py`

The service will:
- Accept TLE data (line1, line2) and optional start time
- Initialize SGP4 satellite object
- Calculate orbital period from mean motion
- Generate position predictions at 1-minute intervals for one complete orbit
- Return position data in multiple formats:
  - **ECI coordinates** (Earth-Centered Inertial): X, Y, Z in kilometers
  - **Geodetic coordinates**: Latitude, Longitude, Altitude
  - **Timestamp** for each position

**Key Methods**:
```python
def propagate_orbit(tle_line1: str, tle_line2: str, 
                    start_time: Optional[datetime] = None,
                    interval_minutes: int = 1) -> Dict[str, Any]
```

Returns:
```json
{
  "orbital_period_minutes": 90.5,
  "num_positions": 91,
  "start_time": "2026-02-09T12:00:00Z",
  "positions": [
    {
      "time": "2026-02-09T12:00:00Z",
      "eci": {"x": 6800.0, "y": 1200.0, "z": 300.0},
      "geodetic": {"lat": 45.2, "lon": -122.5, "alt": 420.0}
    },
    ...
  ]
}
```

### 3. API Layer

**Add new endpoint to** `api/routers/tle.py`:

```python
@router.get("/tle/{norad_id}/orbit")
def calculate_orbit(norad_id: str, 
                   start_time: Optional[str] = None,
                   interval_minutes: int = 1)
```

This endpoint will:
1. Fetch TLE data using existing `fetch_tle_by_norad_id()` from `tle_service`
2. Call propagation service to calculate orbit
3. Return propagated positions with metadata
4. Handle errors (TLE not found, propagation errors, invalid satellites)

**Query Parameters**:
- `start_time` (optional): ISO 8601 timestamp (default: current UTC time)
- `interval_minutes` (optional): Time step in minutes (default: 1, max: 10)

**Response Format**:
```json
{
  "norad_id": "25544",
  "satellite_name": "ISS (ZARYA)",
  "tle_epoch": "2026-02-08T12:34:56Z",
  "calculation": {
    "orbital_period_minutes": 90.5,
    "num_positions": 91,
    "start_time": "2026-02-09T12:00:00Z",
    "interval_minutes": 1,
    "positions": [...]
  },
  "timestamp": "2026-02-09T12:03:45Z"
}
```

### 4. Frontend Implementation

**Add UI components for displaying orbit calculations in the React application.**

#### 4.1. Orbit Calculation Button

**Location**: [./react-app/src/components/DetailPanel.jsx](./react-app/src/components/DetailPanel.jsx:204)

Add new button next to the existing "MQTT Feed" button (around line 199-206):

```jsx
{currentTle && !currentTle._notFound && (currentTle.line1 || currentTle.line2) && (
  <>
    <button 
      className="mqtt-feed-button"
      onClick={() => setShowMqttConfig(true)}
    >
      MQTT Feed
    </button>
    <button 
      className="orbit-calculation-button"
      onClick={() => setShowOrbitCalculation(true)}
    >
      Calculate Orbit
    </button>
  </>
)}
```

**State Management**:
- Add `const [showOrbitCalculation, setShowOrbitCalculation] = useState(false)`
- Add `const [orbitData, setOrbitData] = useState(null)`
- Add `const [orbitLoading, setOrbitLoading] = useState(false)`

#### 4.2. Orbit Calculation Modal Component

**Create new component**: `react-app/src/components/OrbitCalculationModal.jsx`

**Component Features**:
- Modal dialog overlaying the current page
- Fetches orbit data from `/v2/tle/{norad_id}/orbit` endpoint
- Displays loading state while calculating
- Shows orbit positions in a scrollable table
- Includes interval selector (1 min, 2 min, 5 min)
- Close button to dismiss modal

**Table Columns**:
1. **Time** - Timestamp (formatted: HH:MM:SS UTC)
2. **Latitude** - Decimal degrees (-90 to 90)
3. **Longitude** - Decimal degrees (-180 to 180)
4. **Altitude** - Kilometers above Earth surface
5. **ECI X** - Earth-Centered Inertial X (km) - optional, collapsible
6. **ECI Y** - Earth-Centered Inertial Y (km) - optional, collapsible
7. **ECI Z** - Earth-Centered Inertial Z (km) - optional, collapsible

**Modal Header**:
- Satellite name
- NORAD ID
- Orbital period (e.g., "90.5 minutes")
- Number of positions (e.g., "91 positions")
- TLE epoch date

**Table Features**:
- Fixed header with scrollable body
- Zebra striping for readability
- Numeric values right-aligned
- Precision: Lat/Lon (2 decimals), Alt (1 decimal), ECI (1 decimal)
- Row highlighting on hover

**Styling**: `react-app/src/components/OrbitCalculationModal.css`
- Consistent with existing modal styles (reference: MqttConfigModal.css)
- Responsive design for different screen sizes
- Table width optimized for readability

#### 4.3. API Integration

**Endpoint Call**:
```javascript
const fetchOrbitData = async (noradId, intervalMinutes = 1) => {
  setOrbitLoading(true)
  try {
    const response = await fetch(
      `/api/v2/tle/${noradId}/orbit?interval_minutes=${intervalMinutes}`
    )
    const data = await response.json()
    setOrbitData(data)
  } catch (error) {
    console.error('Error fetching orbit data:', error)
    // Show error message to user
  } finally {
    setOrbitLoading(false)
  }
}
```

**Error Handling**:
- Display user-friendly error messages for:
  - TLE not found (404)
  - Propagation errors (400)
  - Network errors
- Allow retry on failure

#### 4.4. User Workflow

1. User selects satellite in Table View
2. DetailPanel shows satellite details with TLE data
3. User clicks "Calculate Orbit" button (next to "MQTT Feed")
4. Modal opens showing loading spinner
5. Backend calculates orbit positions (1-2 seconds)
6. Table populates with position data
7. User can scroll through positions
8. User can change interval and recalculate
9. User clicks "Close" or clicks outside modal to dismiss

### 5. Error Handling

**Common Error Scenarios**:
- **TLE not found**: Return 404 with helpful message
- **Invalid TLE format**: Return 400 with validation error
- **Satellite decayed**: Propagation may fail for satellites that have re-entered
- **Invalid time range**: Start time too far from TLE epoch may produce inaccurate results
- **Propagation errors**: SGP4 can fail for certain edge cases (very eccentric orbits, etc.)

**Error Response Format**:
```json
{
  "error": "Propagation failed: satellite has decayed",
  "norad_id": "12345",
  "timestamp": "2026-02-09T12:03:45Z"
}
```

### 6. Performance Considerations

- **Caching**: Leverage existing TLE cache (1-hour TTL)
- **Computation**: Propagating 90 positions should complete in <100ms
- **Memory**: Minimal overhead (~10KB per orbit calculation)
- **Rate Limiting**: Consider adding rate limits if endpoint becomes popular
- **Frontend**: Render table with virtualization if >500 positions (not needed for 1-minute intervals)

## Source Code Changes

### Backend Files to Create
1. `api/services/propagation_service.py` - New service for orbit propagation

### Backend Files to Modify
1. [./requirements.txt](./requirements.txt:1) - Add `sgp4>=2.23`
2. [./api/routers/tle.py](./api/routers/tle.py:1) - Add new `/tle/{norad_id}/orbit` endpoint

### Frontend Files to Create
1. `react-app/src/components/OrbitCalculationModal.jsx` - Modal component for displaying orbit table
2. `react-app/src/components/OrbitCalculationModal.css` - Styling for orbit modal

### Frontend Files to Modify
1. [./react-app/src/components/DetailPanel.jsx](./react-app/src/components/DetailPanel.jsx:1) - Add "Calculate Orbit" button and modal integration

### Test Files to Create
1. `tests/unit/test_propagation_service.py` - Unit tests for propagation logic
2. `tests/integration/test_tle_orbit_endpoint.py` - Integration tests for API endpoint

## Data Model Changes

**No database schema changes required.**

The feature operates entirely on:
- Input: TLE data (fetched from external APIs, cached in memory)
- Output: Calculated positions (returned as JSON, not persisted)

## Verification Approach

### 1. Unit Tests
- Test `propagation_service.propagate_orbit()` with known TLE
- Verify correct number of positions (orbital_period / interval)
- Validate position format (ECI and geodetic coordinates)
- Test edge cases: invalid TLE, zero eccentricity, high eccentricity

### 2. Integration Tests
- Test `/v2/tle/{norad_id}/orbit` endpoint with real NORAD ID
- Verify TLE fetching integration
- Test query parameters (start_time, interval_minutes)
- Test error responses (404, 400)

### 3. Manual Verification
- Test with ISS (NORAD 25544) - well-known, stable orbit
- Compare results with online orbit calculators (e.g., N2YO, Heavens-Above)
- Verify ground track makes sense (crosses equator for inclined orbit)
- Check orbital period matches expected value (~90 min for LEO)

### 4. Test Commands
Based on project structure, likely commands:
```bash
# Run unit tests
pytest tests/unit/test_propagation_service.py -v

# Run integration tests
pytest tests/integration/test_tle_orbit_endpoint.py -v

# Run all tests
pytest tests/ -v

# Type checking (if configured)
mypy api/services/propagation_service.py
```

**Note**: Need to verify actual test commands from [./README.md](./README.md:1) or project documentation.

## Implementation Estimates

### Backend
- **Service Layer** (`propagation_service.py`): 2-3 hours
  - SGP4 integration: 1 hour
  - Position formatting: 30 min
  - Error handling: 30 min
  - Unit tests: 1 hour

- **API Layer** (endpoint in `tle.py`): 1-2 hours
  - Endpoint implementation: 30 min
  - Query parameter handling: 30 min
  - Integration tests: 1 hour

### Frontend
- **Modal Component** (`OrbitCalculationModal.jsx`): 2-3 hours
  - Component structure: 30 min
  - API integration: 30 min
  - Table rendering: 1 hour
  - Styling: 1 hour

- **DetailPanel Integration**: 30 min
  - Add button: 15 min
  - State management: 15 min

### Testing & Documentation
- **Manual Testing**: 1 hour
  - End-to-end workflow testing
  - Cross-browser testing
  
- **Documentation**: 30 min
  - API documentation
  - Implementation report

**Total Estimate**: 7-10 hours

## Dependencies & Constraints

### Python Library: sgp4
- **Installation**: `pip install sgp4`
- **Size**: ~500KB
- **License**: MIT
- **Stability**: Mature (v2.x stable since 2020)

### TLE Data Quality
- Accuracy degrades as time from TLE epoch increases
- Typical accuracy: ±1-2 km for recent TLEs
- Recommend warning if start_time > 7 days from TLE epoch

### Orbital Period Variation
- LEO: ~90 minutes
- MEO: ~6-12 hours
- GEO: ~24 hours
- The endpoint should dynamically calculate based on mean motion

## Future Enhancements (Out of Scope)

1. **Ground Track Visualization**: Return GeoJSON for mapping
2. **Custom Time Ranges**: Allow arbitrary start/end times (multiple orbits)
3. **Velocity Vectors**: Include velocity at each position
4. **Multiple Satellites**: Batch calculation for constellation tracking
5. **Visibility Windows**: Calculate when satellite is visible from ground station
6. **Collision Detection**: Check proximity to other satellites

## References

- [SGP4 Library Documentation](https://pypi.org/project/sgp4/)
- [TLE Format Specification](https://celestrak.org/NORAD/documentation/tle-fmt.php)
- [SGP4 Theory](https://celestrak.org/publications/AIAA/2006-6753/)
- [Existing TLE Service](./api/services/tle_service.py:1)
- [Existing Orbital Service](./api/services/orbital_service.py:1)
