# Implementation Plan: Kessler Code Review and Refactoring

**Task Complexity**: HARD  
**Estimated Duration**: 5-8 days

---

## Overview

This plan breaks down the refactoring work into concrete, testable milestones. Each phase is designed to be independently verifiable and can be rolled back if issues arise.

**Key Principles:**
- Maintain 100% backward compatibility
- Test thoroughly after each phase
- Keep main branch deployable at all times
- Document changes as they happen

---

## Workflow Steps

### [x] Step: Technical Specification
<!-- chat-id: 73ca0c44-e297-4620-857a-e319d97d3d22 -->
Create comprehensive technical specification analyzing the codebase and proposing refactoring strategy.
- [x] Analyze codebase structure and metrics
- [x] Identify code duplications and inefficiencies
- [x] Document issues by severity
- [x] Propose refactoring strategy with phases
- [x] Define success criteria and deliverables

### [x] Step: Phase 1 - Foundation and Configuration

**Goal**: Set up new structure and configuration without breaking existing code.

**Tasks:**
- [x] Create directory structure for new modules
  - `api/` with subdirectories: `routers/`, `services/`, `utils/`
  - `database/` with subdirectories: `data/`, `utils/`
  - `scripts/` with subdirectories: `import/`, `verification/`, `population/`, `maintenance/`
  - `tests/` with subdirectories: `unit/`, `integration/`, `e2e/`

- [x] Create `config.py` with centralized configuration
  - Database settings
  - Cache settings
  - API settings
  - External service URLs
  - Load from environment variables

- [x] Implement `CacheService` class in `api/services/cache_service.py`
  - TTL management
  - Size limits with LRU eviction
  - Statistics tracking (hits/misses)
  - `get()`, `set()`, `get_or_fetch()` methods
  - Write unit tests

- [x] Implement `OrbitalService` class in `api/services/orbital_service.py`
  - Unified orbital calculations
  - Extract common logic from api.py and mqtt_publisher.py
  - Constants: GM, EARTH_RADIUS_KM
  - Methods: `calculate_orbital_parameters()`, `get_orbital_period()`, `get_semi_major_axis()`
  - Write unit tests with known TLE data

- [x] Extract country codes to `database/data/country_codes.json`
  - Copy country mapping from db.py
  - Format as clean JSON

- [x] Create `CountryNormalizer` in `database/utils/normalization.py`
  - Load country codes from JSON
  - `normalize()` method
  - Write unit tests

- [x] Run baseline tests
  - Execute all existing tests
  - Document passing tests
  - Capture API response samples for comparison

**Verification:**
- [x] All existing tests still pass
- [x] New services have >80% test coverage
- [x] No changes to existing functionality
- [x] Config loads correctly from environment

---

### [x] Step: Phase 2 - Database Module Decomposition
<!-- chat-id: 64a7b24f-2d91-4f7c-a4e1-ccd7aa7dac05 -->

**Goal**: Split db.py into focused, maintainable modules.

**Tasks:**
- [x] Create `database/connection.py`
  - Move connection logic: `connect_mongodb()`, `disconnect_mongodb()`, `get_satellites_collection()`
  - Rename functions to `connect_arangodb()`, `disconnect_arangodb()` (keep old names as deprecated aliases)
  - Update module-level variables

- [x] Create `database/operations.py`
  - Move CRUD operations: `find_satellite()`, `search_satellites()`, `count_satellites()`, `create_satellite_document()`
  - Move filter operations: `get_all_countries()`, `get_all_statuses()`, `get_all_orbital_bands()`, `get_all_congestion_risks()`

- [x] Create `database/transformations.py`
  - Move `update_canonical()` function
  - Move `record_transformation()` function
  - Move canonicalization logic

- [x] Create `database/queries.py`
  - Move complex search/filter logic if applicable
  - Keep focused on read operations
  - Note: Merged into operations.py for simplicity

- [x] Create `database/graph_operations.py`
  - Move graph-related database operations
  - Edge collection operations

- [x] Create `database/mqtt_config.py`
  - Move MQTT configuration storage functions
  - `get_mqtt_configurations_collection()`, `save_mqtt_configuration()`, etc.

- [x] Create `database/utils/field_utils.py`
  - Move `get_nested_field()`, `set_nested_field()`

- [x] Update `database/__init__.py` to export all functions
  - Maintain backward compatibility with old imports

- [x] Update all import statements
  - api.py
  - mqtt_publisher.py
  - mqtt_scheduler.py
  - All utility scripts

- [x] Replace `normalize_country()` with `CountryNormalizer.normalize()`
  - Update all usages in database modules
  - Backward compatibility wrapper added to database/__init__.py

- [x] Delete original db.py (after verifying all migrations)
  - Moved to db.py.backup for safety

- [x] Run tests
  - All database operation tests
  - All API tests that use database
  - Verify same behavior
  - Verified Python syntax for all modules

**Verification:**
- [x] All tests pass
- [x] Database operations work identically
- [x] No import errors
- [x] Original db.py can be deleted safely
- [x] Code review: Each new file <300 lines

---

### [ ] Step: Phase 3 - API Module Decomposition

**Goal**: Split api.py into focused routers and services.

**Tasks:**
- [ ] Create `api/services/tle_service.py`
  - Move `fetch_tle_data()`, `fetch_tle_by_norad_id()`
  - Move `convert_to_norad_format()`
  - Integrate with `CacheService` for TLE caching
  - Remove manual cache dictionaries

- [ ] Create `api/services/document_service.py`
  - Move `extract_document_metadata()`, `fetch_english_doc_link()`, `convert_un_doc_to_pdf_url()`
  - Integrate with `CacheService` for document caching

- [ ] Create `api/routers/satellites.py`
  - Move `/v2/search`, `/v2/satellite/{identifier}` endpoints
  - Import from services as needed

- [ ] Create `api/routers/metadata.py`
  - Move `/v2/countries`, `/v2/statuses`, `/v2/orbital-bands`, `/v2/congestion-risks`, `/v2/stats`

- [ ] Create `api/routers/graphs.py`
  - Move all `/v2/graphs/*` endpoints
  - `/v2/graphs/constellation/{constellation_name}`
  - `/v2/graphs/registration-document/{doc_key}`
  - `/v2/graphs/stats`
  - And other graph endpoints

- [ ] Create `api/routers/documents.py`
  - Move `/api/documents/resolve`, `/api/documents/metadata`

- [ ] Create `api/routers/tle.py`
  - Move `/v2/tle/{norad_id}`

- [ ] Create `api/routers/mqtt.py`
  - Move all `/v2/mqtt/*` endpoints

- [ ] Create `api/utils/converters.py`
  - Helper functions for format conversions

- [ ] Update `api/main.py` (simplified entry point)
  - FastAPI app initialization
  - Lifespan context manager
  - CORS middleware setup
  - Include all routers
  - Keep minimal (<100 lines)

- [ ] Update imports throughout codebase
  - mqtt_scheduler.py imports from api
  - Any utility scripts

- [ ] Delete original api.py (after verifying migrations)

- [ ] Run tests
  - All API endpoint tests
  - Test each router independently
  - Test full API integration

**Verification:**
- [ ] All 41+ endpoints respond identically
- [ ] Response bodies match exactly
- [ ] No import errors
- [ ] Original api.py can be deleted safely
- [ ] Code review: Each router file <400 lines
- [ ] OpenAPI docs still generate correctly

---

### [ ] Step: Phase 4 - Eliminate Code Duplications

**Goal**: Replace duplicate logic with shared services.

**Tasks:**
- [ ] Update `api/routers/` to use `OrbitalService`
  - Replace `calculate_orbital_state()` calls
  - Remove old orbital calculation function

- [ ] Update `mqtt_publisher.py` to use `OrbitalService`
  - Replace `calculate_orbital_parameters()` calls
  - Remove duplicate function
  - Update imports

- [ ] Update all modules to use `CacheService`
  - Replace TLE manual caching in tle_service.py
  - Replace document caching in document_service.py
  - Remove all manual cache dictionaries and time tracking
  - Update cache access patterns

- [ ] Verify orbital calculations produce identical results
  - Compare old vs new with test TLE data
  - Ensure floating point differences <0.001%

- [ ] Run full test suite
  - Unit tests for all services
  - Integration tests for API
  - MQTT publishing test (if configured)

**Verification:**
- [ ] No code duplication remains
- [ ] Orbital calculations match exactly
- [ ] Cache hit rates are healthy (>80% for TLE)
- [ ] All tests pass
- [ ] Memory usage is acceptable

---

### [ ] Step: Phase 5 - Utility Script Organization

**Goal**: Organize 40+ scripts into logical directories.

**Tasks:**
- [ ] Move import scripts to `scripts/import/`
  - import_arangodb_data.py
  - import_kaggle_catalog.py
  - import_tle_api.py
  - import_spacetrack_tle.py
  - import_from_27018.py
  - import_to_railway.py

- [ ] Move verification scripts to `scripts/verification/`
  - verify_constellation_network.py
  - verify_graph_structure.py
  - verify_registration_network.py
  - verify_update.py

- [ ] Move population scripts to `scripts/population/`
  - populate_constellation_network.py
  - populate_orbital_proximity.py
  - populate_registration_network.py

- [ ] Move maintenance scripts to `scripts/maintenance/`
  - promote_attributes.py
  - promote_kaggle_orbital.py
  - promote_launch_site.py
  - enrich_launch_data.py
  - add_graph_indexes.py

- [ ] Move test scripts to `tests/`
  - Organize by type: unit/, integration/, e2e/
  - test_comprehensive.py
  - test_graph_db.py
  - test_mqtt_config.py
  - test_mqtt_endpoint.py
  - test_batch_processing.py
  - etc.

- [ ] Update script imports for new module structure
  - Change `import db` to `from database import ...`
  - Change `import api` to `from api import ...`

- [ ] Test that scripts still run correctly
  - Test at least one script from each category
  - Verify they can import from new module structure

**Verification:**
- [ ] All scripts are in appropriate directories
- [ ] Scripts execute without import errors
- [ ] No scripts left in root directory
- [ ] Documentation updated if scripts are referenced

---

### [ ] Step: Phase 6 - Frontend Improvements (Optional)

**Goal**: Minor frontend improvements for consistency.

**Tasks:**
- [ ] Create `react-app/src/config/constants.js`
  - Extract hardcoded pagination limits
  - Extract API endpoint paths
  - Extract configuration values

- [ ] Update components to use constants
  - App.jsx
  - DataTable.jsx
  - Filters.jsx

- [ ] (Optional) Create custom hooks
  - `useSatellites()` for data fetching
  - `useFilters()` for filter management

- [ ] Test frontend
  - Verify all views load correctly
  - Test search and filtering
  - Test pagination
  - Test graph visualizations

**Verification:**
- [ ] Frontend works identically
- [ ] No console errors
- [ ] All user interactions work
- [ ] No hardcoded values in components

---

### [ ] Step: Documentation and Finalization

**Goal**: Document changes and create migration guide.

**Tasks:**
- [ ] Create architecture diagram
  - Before/after comparison
  - Module dependencies
  - Data flow

- [ ] Write migration guide
  - How imports changed
  - Where to find specific functionality
  - How to use new services

- [ ] Update API documentation
  - Reflect new module structure
  - Update code examples

- [ ] Create developer guide
  - How to add new endpoints
  - How to use OrbitalService
  - How to use CacheService
  - Testing guidelines

- [ ] Update README
  - New project structure
  - New development setup
  - Testing instructions

- [ ] Create metrics comparison report
  - LOC before/after
  - File count before/after
  - Complexity metrics
  - Code duplication metrics

- [ ] Clean up deprecated code
  - Remove commented-out code
  - Remove unused imports
  - Remove temporary compatibility aliases

- [ ] Final code review
  - Check for TODOs/FIXMEs
  - Verify consistent code style
  - Verify test coverage

**Verification:**
- [ ] Documentation is complete and accurate
- [ ] All metrics show improvement
- [ ] No deprecated code remains
- [ ] Code passes linting/style checks

---

### [ ] Step: Comprehensive Testing and Verification

**Goal**: Verify entire refactoring maintains functionality.

**Tasks:**
- [ ] Run full test suite
  - All unit tests
  - All integration tests
  - All end-to-end tests

- [ ] API endpoint verification
  - Test all 41+ endpoints
  - Compare responses with baseline
  - Verify identical behavior

- [ ] Performance benchmarking
  - API response times (compare with baseline)
  - Database query performance
  - Cache performance (hit rates)
  - Memory usage

- [ ] Manual verification
  - Start application locally
  - Test satellite search
  - Test graph visualizations
  - Test timeline view
  - Test MQTT configuration (if available)
  - Test document metadata extraction

- [ ] Create verification report
  - Test results summary
  - Performance comparison
  - Metrics comparison
  - Known issues (if any)

**Verification:**
- [ ] All automated tests pass
- [ ] All endpoints return identical responses
- [ ] Performance within acceptable range (<10% regression)
- [ ] Manual testing confirms all features work
- [ ] Verification report complete

---

## Success Criteria

The refactoring is complete when:

- [x] Technical specification created
- [ ] All 6 implementation phases completed
- [ ] All tests pass (existing + new)
- [ ] All API endpoints verified identical
- [ ] Performance benchmarks acceptable
- [ ] Documentation complete
- [ ] Code metrics show significant improvement:
  - api.py reduced from 2,241 to <400 lines (via decomposition)
  - db.py reduced from 1,274 to <300 lines (via decomposition)
  - Zero code duplication
  - Unified caching system
  - Organized script structure

---

## Rollback Plan

If critical issues are discovered:

1. **Per-Phase Rollback**:
   - Each phase is in its own Git branch
   - Can revert individual phase if needed
   - Tags mark stable points

2. **Full Rollback**:
   - Keep original `api.py` and `db.py` in `backup/` directory until final verification
   - Can restore from backup if catastrophic issue
   - Database schema unchanged, so no data migration needed

---

## Notes

- Each phase should be completed and verified before moving to next
- Keep main branch deployable - use feature branches
- Document any issues or deviations from plan
- Update this plan if scope changes
- Test coverage should increase, not decrease
