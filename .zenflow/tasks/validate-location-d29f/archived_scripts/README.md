# Archived Validation Scripts

This directory contains scripts used during the development and validation of the coordinate transformation accuracy improvements.

These scripts are archived for reference but are no longer needed for normal operation.

## Scripts

### compare_coordinates.py
Comparison script to validate coordinate transformation accuracy between the old simplified method, Skyfield library, and N2YO reference data. Tests multiple satellite types (PRETTY, ISS, GOES-16).

**Status**: Archived - validation complete, integration tests now serve this purpose

### verify_skyfield.py  
Simple verification script to test Skyfield installation and basic functionality.

**Status**: Archived - Skyfield is installed and tested via unit tests

### manual_validation.py
Real-time manual validation script for comparing calculated positions with N2YO. Generates N2YO comparison links for manual spot-checking.

**Status**: Archived - automated integration tests now provide continuous validation

## Current Testing

All validation is now handled by the automated test suite:

- **Unit Tests**: `tests/test_propagation_service.py` (27 tests)
- **Integration Tests**: `tests/integration/test_n2yo_validation.py` (7 tests)

Run tests with:
```bash
pytest tests/ -v
```

## Archive Date
2024-02-09
