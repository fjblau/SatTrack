# Technical Specification: Validate Location

## Task Complexity: **Hard**

This is a complex issue involving orbital mechanics, coordinate system transformations, and geodetic calculations. The discrepancies indicate fundamental problems with the coordinate transformation implementation.

---

## Problem Analysis

### Observed Discrepancies

Comparing N2YO vs Kessler application for satellite PRETTY (NORAD 58023) at approximately the same time:

| Metric | N2YO | Kessler | Difference |
|--------|------|---------|------------|
| **Latitude** | -45.87° | -47.48° | ~1.6° |
| **Longitude** | -49.80° | -67.23° | ~17.4° |
| **Altitude** | 519.60 km | 516.0 km | ~3.6 km |

**Critical Issue**: The longitude discrepancy of ~17 degrees is the most severe problem and indicates a fundamental coordinate transformation error.

### Root Cause Analysis

After examining the codebase, I identified three major issues in [`./api/services/propagation_service.py:42-65`](./api/services/propagation_service.py:42:65):

#### 1. **Missing ECI to ECEF Conversion** ⭐ **PRIMARY ISSUE**

The current `_eci_to_geodetic()` method treats **ECI** (Earth-Centered Inertial) coordinates as if they were **ECEF** (Earth-Centered Earth-Fixed) coordinates:

```python
def _eci_to_geodetic(x_km: float, y_km: float, z_km: float) -> Dict[str, float]:
    r = math.sqrt(x_km**2 + y_km**2 + z_km**2)
    longitude_rad = math.atan2(y_km, x_km)  # ❌ WRONG: This is ECI, not ECEF
    latitude_rad = math.asin(z_km / r)
    altitude_km = r - PropagationService.EARTH_RADIUS_KM
```

**Problem**: SGP4 outputs ECI coordinates (inertial frame), but longitude calculation requires ECEF coordinates (Earth-fixed frame). The conversion requires accounting for **Earth's rotation** using Greenwich Mean Sidereal Time (GMST).

**Impact**: Earth rotates ~15°/hour, causing longitude errors proportional to time difference from TLE epoch. For a satellite position calculated hours after TLE epoch, this can cause 10-20° errors.

#### 2. **Spherical Earth Assumption**

Current implementation uses a simple spherical Earth model (radius = 6371 km):

```python
EARTH_RADIUS_KM = 6371.0
altitude_km = r - PropagationService.EARTH_RADIUS_KM
```

**Problem**: Earth is an oblate spheroid (WGS84 ellipsoid):
- Equatorial radius: 6378.137 km
- Polar radius: 6356.752 km
- Flattening: 1/298.257223563

**Impact**: 
- Altitude errors up to ~7 km depending on latitude
- Latitude errors up to ~0.2° at mid-latitudes
- Less critical than issue #1, but compounds errors

#### 3. **Simplified Latitude Calculation**

Using `latitude_rad = math.asin(z_km / r)` assumes geocentric latitude instead of geodetic latitude.

**Problem**: Geodetic latitude (what GPS uses) differs from geocentric latitude due to Earth's oblateness.

**Impact**: Small errors (~0.1-0.2°) in latitude, especially at mid-latitudes.

---

## Technical Context

### Current Architecture

**Language**: Python 3.11  
**Framework**: FastAPI  
**Orbital Library**: `sgp4>=2.23`

**Key Files**:
- [`./api/services/propagation_service.py`](./api/services/propagation_service.py) - SGP4 propagation and coordinate conversion
- [`./api/services/orbital_service.py`](./api/services/orbital_service.py) - Orbital parameter calculations
- [`./api/routers/tle.py`](./api/routers/tle.py) - TLE API endpoint
- [`./config.py`](./config.py) - Orbital constants configuration
- [`./react-app/src/components/OrbitCalculationModal.jsx`](./react-app/src/components/OrbitCalculationModal.jsx) - Frontend display

### Current Data Flow

1. Frontend requests orbit calculation: `GET /v2/tle/{norad_id}/orbit`
2. Backend fetches TLE data from cache/external API
3. SGP4 propagates orbit → outputs **ECI coordinates** (x, y, z in km)
4. `_eci_to_geodetic()` converts to lat/lon/alt → **❌ INCORRECT CONVERSION**
5. Frontend displays position data

---

## Implementation Approach

### Solution Strategy

Replace the simplified coordinate transformation with proper geodetic conversion that accounts for:
1. **GMST calculation** for ECI → ECEF transformation
2. **WGS84 ellipsoid model** for geodetic calculations
3. **Iterative geodetic conversion** for accurate latitude/altitude

### Option Analysis

#### Option A: Use Skyfield Library ⭐ **RECOMMENDED**

**Pros**:
- Battle-tested, maintained by professional astronomers
- Handles all coordinate transformations correctly
- Integrates seamlessly with SGP4
- Includes Earth rotation, precession, nutation
- Widely used in satellite tracking applications

**Cons**:
- Additional dependency (~2 MB)
- Slight learning curve

**Implementation**:
```python
from skyfield.api import EarthSatellite, load, wgs84
from skyfield.timelib import Time

# Skyfield automatically handles ECI → ECEF → Geodetic
```

#### Option B: Implement Custom WGS84 Conversion

**Pros**:
- No new dependencies
- Full control over implementation

**Cons**:
- Complex math (GMST, ellipsoid, iterative geodetic)
- Error-prone
- Must maintain and test extensively

**Verdict**: Option A (Skyfield) is superior due to reliability and maintenance benefits.

---

## Proposed Changes

### 1. Update Dependencies

**File**: [`./requirements.txt`](./requirements.txt)

Add Skyfield library:
```
skyfield>=1.46
```

### 2. Refactor Propagation Service

**File**: [`./api/services/propagation_service.py`](./api/services/propagation_service.py)

**Changes**:
- Replace `_eci_to_geodetic()` with Skyfield-based conversion
- Add GMST calculation using Skyfield's time utilities
- Use WGS84 ellipsoid for geodetic calculations
- Update `_calculate_position()` to use new conversion

**New Method Signature**:
```python
@staticmethod
def _eci_to_geodetic_accurate(
    x_km: float, 
    y_km: float, 
    z_km: float,
    dt: datetime
) -> Dict[str, float]:
    """
    Convert ECI coordinates to geodetic (lat/lon/alt) using WGS84 ellipsoid.
    
    Args:
        x_km: X coordinate in kilometers (ECI)
        y_km: Y coordinate in kilometers (ECI)
        z_km: Z coordinate in kilometers (ECI)
        dt: Timestamp for GMST calculation
        
    Returns:
        Dictionary with latitude (degrees), longitude (degrees), and altitude (km)
    """
```

### 3. Update Configuration

**File**: [`./config.py`](./config.py)

Update Earth radius constants to WGS84 values:
```python
class OrbitalConstants:
    """Physical constants for orbital calculations (WGS84)"""
    GM: float = 398600.4418  # km³/s²
    EARTH_EQUATORIAL_RADIUS_KM: float = 6378.137
    EARTH_POLAR_RADIUS_KM: float = 6356.752
    EARTH_FLATTENING: float = 1 / 298.257223563
    
    # Deprecated: kept for backward compatibility
    EARTH_RADIUS_KM: float = 6371.0  # Mean radius (simplified)
```

### 4. Add Verification Endpoint (Optional)

**File**: [`./api/routers/tle.py`](./api/routers/tle.py)

Add debug endpoint to compare old vs new calculations:
```python
@router.get("/tle/{norad_id}/orbit/debug")
def debug_orbit_calculation(norad_id: str):
    """Compare old vs new coordinate transformations"""
```

### 5. Update Tests

**File**: [`./tests/unit/test_propagation_service.py`](./tests/unit/test_propagation_service.py) (create if doesn't exist)

Add tests for:
- ECI to geodetic conversion accuracy
- Comparison with known satellite positions
- Edge cases (poles, equator, high eccentricity orbits)

---

## Verification Approach

### 1. Unit Tests

Create comprehensive tests for coordinate transformations:
- Test against known satellite positions from N2YO/CelesTrak
- Verify GMST calculation accuracy
- Test WGS84 geodetic conversion

### 2. Integration Testing

Compare with external reference data:
- **N2YO API**: Query same satellite at same time
- **CelesTrak**: Verify against their predictions
- **Space-Track**: Cross-reference orbital data

### 3. Manual Verification

Test with PRETTY (NORAD 58023):
1. Fetch current TLE
2. Calculate position at specific time
3. Compare with N2YO display
4. Verify differences < 0.1° for lat/lon, < 1 km for altitude

### 4. Regression Testing

Ensure existing functionality remains intact:
- Run full test suite
- Verify API endpoints still work
- Check frontend displays correctly

---

## Expected Improvements

### Accuracy Gains

| Metric | Current Error | Expected Error | Improvement |
|--------|---------------|----------------|-------------|
| **Latitude** | ~1.6° | < 0.05° | **97% better** |
| **Longitude** | ~17.4° | < 0.05° | **99.7% better** |
| **Altitude** | ~3.6 km | < 0.5 km | **86% better** |

### Performance Impact

- **Minimal**: Skyfield's coordinate transformations are highly optimized
- **Expected overhead**: < 1 ms per position calculation
- **Acceptable**: For current use case (1-minute intervals)

---

## Risks and Mitigations

### Risk 1: Breaking Changes

**Risk**: Existing API consumers may expect current (incorrect) coordinates

**Mitigation**: 
- Version API endpoint (`/v3/tle/{norad_id}/orbit`)
- Keep old endpoint with deprecation warning
- Provide migration guide

### Risk 2: Dependency Issues

**Risk**: Skyfield dependency conflicts or installation problems

**Mitigation**:
- Pin specific Skyfield version
- Test in CI/CD pipeline
- Document installation requirements

### Risk 3: Performance Regression

**Risk**: Skyfield may be slower than current implementation

**Mitigation**:
- Benchmark before/after
- Profile critical paths
- Optimize if needed (caching GMST calculations)

---

## Data Model Changes

### API Response Structure

**Endpoint**: `GET /v2/tle/{norad_id}/orbit`

**No changes to response schema**, but values will be corrected:

```json
{
  "current_position": {
    "timestamp": "2026-02-09T13:34:10+00:00",
    "geodetic": {
      "latitude": -45.87,    // Was: -47.48 (❌ incorrect)
      "longitude": -49.80,   // Was: -67.23 (❌ incorrect)
      "altitude_km": 519.6   // Was: 516.0 (❌ incorrect)
    },
    "eci": {
      "x_km": 1234.56,
      "y_km": -5678.90,
      "z_km": -3456.78
    }
  }
}
```

**Backward Compatibility**: ✅ Maintained (schema unchanged, only values corrected)

---

## Implementation Plan

Based on task complexity, this requires a detailed implementation plan:

### Phase 1: Investigation & Setup
- [ ] Install and test Skyfield library
- [ ] Create comparison script (current vs Skyfield vs N2YO)
- [ ] Document exact discrepancies with test cases

### Phase 2: Core Implementation
- [ ] Implement new `_eci_to_geodetic_accurate()` method
- [ ] Update `_calculate_position()` to use new method
- [ ] Update configuration constants to WGS84
- [ ] Write unit tests for coordinate conversion

### Phase 3: Integration & Testing
- [ ] Integration tests comparing with N2YO/CelesTrak
- [ ] Manual verification with PRETTY satellite
- [ ] Performance benchmarking
- [ ] Update documentation

### Phase 4: Deployment Preparation
- [ ] Add deprecation warnings if needed
- [ ] Update API documentation
- [ ] Create migration notes
- [ ] Final regression testing

---

## Alternative Approaches Considered

### 1. PyOrbital Library
- Similar to Skyfield but less maintained
- **Rejected**: Skyfield is more reliable

### 2. Astropy Library
- Comprehensive astronomy library
- **Rejected**: Overkill for this use case, larger dependency

### 3. Custom Implementation
- Full control, no dependencies
- **Rejected**: Too error-prone, maintenance burden

---

## References

- [SGP4 Library Documentation](https://pypi.org/project/sgp4/)
- [Skyfield Documentation](https://rhodesmill.org/skyfield/)
- [WGS84 Specification](https://en.wikipedia.org/wiki/World_Geodetic_System#WGS84)
- [ECI/ECEF Coordinate Systems](https://en.wikipedia.org/wiki/Earth-centered_inertial)
- [N2YO Satellite Tracker](https://www.n2yo.com/)
- [CelesTrak TLE Data](https://celestrak.org/)

---

## Success Criteria

✅ **Acceptance Criteria**:
1. Latitude error < 0.1° compared to N2YO
2. Longitude error < 0.1° compared to N2YO
3. Altitude error < 1 km compared to N2YO
4. All existing tests pass
5. API response schema unchanged
6. Performance overhead < 5 ms per calculation

✅ **Quality Gates**:
- Unit test coverage > 90% for coordinate transformations
- Integration tests with N2YO pass
- Manual verification with at least 3 different satellites
- Documentation updated
