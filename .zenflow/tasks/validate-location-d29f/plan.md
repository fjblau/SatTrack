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
<!-- chat-id: ecee3ca3-cddc-4c89-90a1-70c03a17aa62 -->

**Completed**: Created comprehensive technical specification in `.zenflow/tasks/validate-location-d29f/spec.md`

**Complexity Assessment**: **Hard** - Complex orbital mechanics, coordinate transformations, and geodetic calculations

**Root Cause**: ECI to ECEF conversion missing GMST calculation, causing ~17° longitude errors

**Approach**: Use Skyfield library for proper coordinate transformations with WGS84 ellipsoid model

---

### [ ] Step: Setup and Investigation

Install Skyfield library and create comparison tools to validate the fix:

- [ ] Add `skyfield>=1.46` to `requirements.txt`
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Create test script to compare current implementation vs Skyfield vs N2YO for PRETTY satellite
- [ ] Document exact discrepancies with multiple test cases (at least 3 satellites)
- [ ] Verify Skyfield installation and basic functionality

**Verification**: Test script runs successfully and shows current errors match spec analysis

---

### [ ] Step: Implement Accurate Coordinate Conversion

Replace simplified ECI-to-geodetic conversion with Skyfield-based accurate transformation:

**Changes in `api/services/propagation_service.py`**:
- [ ] Import Skyfield dependencies (`from skyfield.api import wgs84, load`)
- [ ] Create new `_eci_to_geodetic_accurate()` method using Skyfield and WGS84 ellipsoid
- [ ] Update `_calculate_position()` to use new accurate conversion method
- [ ] Keep old method as `_eci_to_geodetic_simple()` for comparison/debugging
- [ ] Write unit tests for coordinate conversion accuracy
- [ ] Test against known satellite positions

**Verification**: 
- Unit tests pass with < 0.1° lat/lon error, < 1 km altitude error
- Run tests: `pytest tests/unit/test_propagation_service.py -v`

---

### [ ] Step: Update Configuration Constants

Update Earth model constants to WGS84 standard:

**Changes in `config.py`**:
- [ ] Add WGS84 constants (equatorial radius, polar radius, flattening)
- [ ] Keep old `EARTH_RADIUS_KM` for backward compatibility with deprecation comment
- [ ] Update `OrbitalService` to use new constants where appropriate

**Changes in `api/services/orbital_service.py`**:
- [ ] Update references to use WGS84 constants
- [ ] Ensure backward compatibility for existing calculations

**Verification**: All existing tests still pass

---

### [ ] Step: Integration Testing and Validation

Verify the fix resolves discrepancies with external reference data:

- [ ] Test with PRETTY (NORAD 58023) - compare with N2YO
- [ ] Test with ISS (NORAD 25544) - compare with N2YO
- [ ] Test with a GEO satellite - compare with N2YO
- [ ] Create integration test suite comparing with N2YO API (if accessible)
- [ ] Performance benchmark: ensure overhead < 5ms per calculation
- [ ] Run full test suite to ensure no regressions

**Verification**:
- Latitude error < 0.1° vs N2YO
- Longitude error < 0.1° vs N2YO  
- Altitude error < 1 km vs N2YO
- All tests pass
- Performance acceptable

---

### [ ] Step: Documentation and Cleanup

Document changes and clean up code:

- [ ] Update API documentation for `/v2/tle/{norad_id}/orbit` endpoint
- [ ] Add code comments explaining coordinate transformation
- [ ] Write report to `.zenflow/tasks/validate-location-d29f/report.md`:
  - What was implemented
  - How the solution was tested
  - Accuracy improvements achieved
  - Any issues or limitations encountered
- [ ] Remove or archive old comparison scripts
- [ ] Final code review and cleanup

**Verification**: Documentation is clear and complete
