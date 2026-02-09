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

### [x] Step: Setup and Investigation
<!-- chat-id: cf26fb63-118f-4ec9-9612-8887a4b4272a -->

**Completed**: Successfully installed Skyfield and validated coordinate transformation errors

Install Skyfield library and create comparison tools to validate the fix:

- [x] Add `skyfield>=1.46` to `requirements.txt`
- [x] Install dependencies: `pip install -r requirements.txt`
- [x] Create test script to compare current implementation vs Skyfield vs N2YO for PRETTY satellite
- [x] Document exact discrepancies with multiple test cases (at least 3 satellites)
- [x] Verify Skyfield installation and basic functionality

**Results**:
- Confirmed **~15° longitude error** across all satellites (LEO, ISS, GEO)
- Confirmed **6-13 km altitude error** due to spherical Earth assumption
- Skyfield installation verified and fully functional
- Created comparison scripts: `compare_coordinates.py` and `verify_skyfield.py`
- Detailed investigation report: `.zenflow/tasks/validate-location-d29f/investigation_report.md`

**Verification**: ✅ Test script runs successfully and confirms spec analysis

---

### [x] Step: Implement Accurate Coordinate Conversion
<!-- chat-id: afd2f9c7-b076-4715-adb1-cad6e6e1018f -->

**Completed**: Successfully implemented accurate coordinate conversion using Skyfield and WGS84 ellipsoid model

Replace simplified ECI-to-geodetic conversion with Skyfield-based accurate transformation:

**Changes in `api/services/propagation_service.py`**:
- [x] Import Skyfield dependencies (`from skyfield.api import wgs84, load`)
- [x] Create new `_eci_to_geodetic_accurate()` method using Skyfield and WGS84 ellipsoid
- [x] Update `_calculate_position()` to use new accurate conversion method
- [x] Keep old method as `_eci_to_geodetic_simple()` for comparison/debugging
- [x] Write unit tests for coordinate conversion accuracy
- [x] Test against known satellite positions

**Verification**: 
- ✅ All 27 unit tests pass
- ✅ Accurate conversion properly accounts for GMST (Earth rotation)
- ✅ WGS84 ellipsoid model used for altitude calculation
- ✅ Comparison test confirms significant improvement over simple method (>5° longitude, >1 km altitude)

---

### [x] Step: Update Configuration Constants
<!-- chat-id: 17c69417-3682-4b9a-ac10-a10b16aa122e -->

**Completed**: Successfully updated configuration with WGS84 constants while maintaining backward compatibility

Update Earth model constants to WGS84 standard:

**Changes in `config.py`**:
- [x] Add WGS84 constants (equatorial radius, polar radius, flattening)
- [x] Keep old `EARTH_RADIUS_KM` for backward compatibility with deprecation comment
- [x] Update `OrbitalService` to use new constants where appropriate

**Changes in `api/services/orbital_service.py`**:
- [x] Update references to use WGS84 constants
- [x] Ensure backward compatibility for existing calculations

**Verification**: ✅ All 22 orbital service tests pass, all 27 propagation service tests pass

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
