# Bug Investigation: Orbit Calculations not displaying

## Bug Summary
The Orbit Calculation modal displays but shows "N/A" for all "Future Orbit Positions" data instead of the calculated orbital positions.

## Root Cause Analysis

### Issue
The frontend component ([`OrbitCalculationModal.jsx`](./react-app/src/components/OrbitCalculationModal.jsx)) is accessing fields from the API response using an **incorrect data structure**.

### API Response Structure (Actual)
The backend endpoint `/v2/tle/{norad_id}/orbit` returns data in the following format:

```json
{
  "satellite": {
    "norad_id": "25544",
    "name": "ISS (ZARYA)"
  },
  "tle": {
    "source": "tle-api",
    "date": "2024-02-07",
    "epoch": "2024-02-07T13:05:38.808864+00:00"
  },
  "orbital_parameters": {
    "period_minutes": 92.5,
    "interval_minutes": 1,
    "num_positions": 93
  },
  "tle_epoch_position": {
    "timestamp": "2024-02-07T13:05:38.808864+00:00",
    "eci": {
      "x_km": 1234.56,
      "y_km": -2345.67,
      "z_km": 3456.78
    },
    "geodetic": {
      "latitude": 45.123456,
      "longitude": -123.456789,
      "altitude_km": 408.5
    }
  },
  "current_position": { /* same structure as tle_epoch_position */ },
  "future_positions": [ /* array of same structure */ ]
}
```

**Source:** [`api/routers/tle.py:82-101`](./api/routers/tle.py), [`api/services/propagation_service.py:193-201`](./api/services/propagation_service.py)

### Frontend Data Access (Incorrect)
The frontend attempts to access fields using a **flat structure**:

**Lines 101-109** (header info):
```javascript
orbitData.norad_id              // ❌ Should be: orbitData.satellite.norad_id
orbitData.tle_epoch             // ❌ Should be: orbitData.tle.epoch
orbitData.orbital_period_minutes // ❌ Should be: orbitData.orbital_parameters.period_minutes
```

**Lines 134-146** (TLE epoch position):
```javascript
orbitData.tle_epoch_position.latitude    // ❌ Should be: .geodetic.latitude
orbitData.tle_epoch_position.longitude   // ❌ Should be: .geodetic.longitude
orbitData.tle_epoch_position.altitude_km // ❌ Should be: .geodetic.altitude_km
```

**Lines 209-222** (future positions):
```javascript
pos.latitude       // ❌ Should be: pos.geodetic.latitude
pos.longitude      // ❌ Should be: pos.geodetic.longitude
pos.altitude_km    // ❌ Should be: pos.geodetic.altitude_km
pos.eci_x_km       // ❌ Should be: pos.eci.x_km
pos.eci_y_km       // ❌ Should be: pos.eci.y_km
pos.eci_z_km       // ❌ Should be: pos.eci.z_km
```

**Result:** Since these fields don't exist at the specified paths, JavaScript returns `undefined`, which gets formatted as "N/A" by the `formatCoordinate()` and `formatDateTime()` functions.

## Affected Components

1. **Frontend:** [`react-app/src/components/OrbitCalculationModal.jsx`](./react-app/src/components/OrbitCalculationModal.jsx)
   - Lines 101-109: Header orbital parameters
   - Lines 127-150: TLE epoch position display
   - Lines 152-175: Current position display
   - Lines 209-222: Future positions table

2. **Backend:** [`api/routers/tle.py`](./api/routers/tle.py) and [`api/services/propagation_service.py`](./api/services/propagation_service.py)
   - ✅ Working correctly, returns properly structured data
   - No backend changes needed

## Proposed Solution

**Update the frontend component** to correctly access nested fields from the API response:

### Changes Required in `OrbitCalculationModal.jsx`:

1. **NORAD ID** (line 101):
   ```javascript
   - <span className="info-value">{orbitData.norad_id}</span>
   + <span className="info-value">{orbitData.satellite?.norad_id}</span>
   ```

2. **TLE Epoch** (line 105):
   ```javascript
   - <span className="info-value">{formatDateTime(orbitData.tle_epoch)}</span>
   + <span className="info-value">{formatDateTime(orbitData.tle?.epoch)}</span>
   ```

3. **Orbital Period** (line 109):
   ```javascript
   - <span className="info-value">{formatCoordinate(orbitData.orbital_period_minutes, 2)} min</span>
   + <span className="info-value">{formatCoordinate(orbitData.orbital_parameters?.period_minutes, 2)} min</span>
   ```

4. **TLE Epoch Position** (lines 138-146):
   ```javascript
   - <span className="position-value">{formatCoordinate(orbitData.tle_epoch_position.latitude, 2)}°</span>
   + <span className="position-value">{formatCoordinate(orbitData.tle_epoch_position?.geodetic?.latitude, 2)}°</span>
   
   - <span className="position-value">{formatCoordinate(orbitData.tle_epoch_position.longitude, 2)}°</span>
   + <span className="position-value">{formatCoordinate(orbitData.tle_epoch_position?.geodetic?.longitude, 2)}°</span>
   
   - <span className="position-value">{formatCoordinate(orbitData.tle_epoch_position.altitude_km, 1)} km</span>
   + <span className="position-value">{formatCoordinate(orbitData.tle_epoch_position?.geodetic?.altitude_km, 1)} km</span>
   ```

5. **Current Position** (lines 163-171): Same pattern as TLE epoch position

6. **Future Positions Table** (lines 212-218):
   ```javascript
   - <td className="numeric">{formatCoordinate(pos.latitude, 2)}</td>
   + <td className="numeric">{formatCoordinate(pos.geodetic?.latitude, 2)}</td>
   
   - <td className="numeric">{formatCoordinate(pos.longitude, 2)}</td>
   + <td className="numeric">{formatCoordinate(pos.geodetic?.longitude, 2)}</td>
   
   - <td className="numeric">{formatCoordinate(pos.altitude_km, 1)}</td>
   + <td className="numeric">{formatCoordinate(pos.geodetic?.altitude_km, 1)}</td>
   
   - <td className="numeric">{formatCoordinate(pos.eci_x_km, 2)}</td>
   + <td className="numeric">{formatCoordinate(pos.eci?.x_km, 2)}</td>
   
   - <td className="numeric">{formatCoordinate(pos.eci_y_km, 2)}</td>
   + <td className="numeric">{formatCoordinate(pos.eci?.y_km, 2)}</td>
   
   - <td className="numeric">{formatCoordinate(pos.eci_z_km, 2)}</td>
   + <td className="numeric">{formatCoordinate(pos.eci?.z_km, 2)}</td>
   ```

## Edge Cases and Side Effects

1. **Optional chaining (`?.`)** is used throughout to safely handle potentially missing nested properties
2. **Existing `formatCoordinate()` and `formatDateTime()` functions** already handle `null`/`undefined` values by returning "N/A"
3. **No changes needed** to error handling, loading states, or API calls
4. **Backend compatibility:** The fix aligns with the actual API response structure confirmed by integration tests ([`tests/integration/test_tle_orbit_endpoint.py`](./tests/integration/test_tle_orbit_endpoint.py))

## Testing Recommendations

1. **Manual testing:**
   - Select a satellite with TLE data
   - Click "Calculate Orbit" button
   - Verify all fields display numeric values instead of "N/A"
   - Test with different interval values (1, 2, 5 minutes)
   - Toggle "Show ECI coordinates" checkbox

2. **Verify data accuracy:**
   - Check that latitude is between -90° and 90°
   - Check that longitude is between -180° and 180°
   - Check that altitude is positive (> 0 km)
   - Verify timestamps increment by the selected interval

3. **Error cases:**
   - Test with satellites without TLE data (should show error message)
   - Test with invalid NORAD IDs (should show 404 error)

## Implementation

### Changes Made

All proposed changes to `OrbitCalculationModal.jsx` have been implemented:

1. ✅ **Header Info (lines 101, 105, 109)**: Updated to use `satellite?.norad_id`, `tle?.epoch`, and `orbital_parameters?.period_minutes`

2. ✅ **TLE Epoch Position (lines 138, 142, 146)**: Updated to access `tle_epoch_position?.geodetic?.latitude`, `longitude`, and `altitude_km`

3. ✅ **Current Position (lines 163, 167, 171)**: Updated to access `current_position?.geodetic?.latitude`, `longitude`, and `altitude_km`

4. ✅ **Future Positions Table (lines 212-219)**: Updated to access:
   - `pos.geodetic?.latitude`, `longitude`, `altitude_km` for geographic coordinates
   - `pos.eci?.x_km`, `y_km`, `z_km` for ECI coordinates

### Implementation Notes

- All field accessors now use optional chaining (`?.`) for safe navigation through nested objects
- No changes to existing logic, error handling, or component structure
- The fix aligns the frontend with the actual API response structure from the backend
- Backward compatible: existing `formatCoordinate()` and `formatDateTime()` functions handle undefined values gracefully

### Testing Status

⚠️ **Manual testing pending**: Node.js environment not available in current workspace to run React dev server. However:

- ✅ API server is running successfully on http://127.0.0.1:8000
- ✅ Code changes match the exact API response structure documented in backend integration tests
- ✅ All field paths verified against actual API response format

## References

- **Backend API:** [`api/routers/tle.py`](./api/routers/tle.py:30-117)
- **Propagation Service:** [`api/services/propagation_service.py`](./api/services/propagation_service.py:108-201)
- **Integration Tests:** [`tests/integration/test_tle_orbit_endpoint.py`](./tests/integration/test_tle_orbit_endpoint.py:90-120)
- **Frontend Modal:** [`react-app/src/components/OrbitCalculationModal.jsx`](./react-app/src/components/OrbitCalculationModal.jsx)
