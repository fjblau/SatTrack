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
<!-- chat-id: d6cd8e56-8a9b-4ec4-8d13-36866474c149 -->

**Completed**: Technical specification created at `.zenflow/tasks/arrangodb-migration-186b/spec.md`

**Complexity Assessment**: MEDIUM
- Database layer is well-abstracted but requires query translation from MongoDB to AQL
- Testing required to ensure query behavior equivalence
- No UI changes required (per task requirements)

---

## Implementation Steps

### [x] Step 1: Infrastructure Setup - Docker & Configuration

Update Docker and configuration files for ArangoDB:
1. Update `docker-compose.yml`: Replace MongoDB service with ArangoDB Enterprise 3.12.7.1 (`arangodb/enterprise:3.12.7.1`)
2. Update `.env.example`: Replace MONGO_URI with ARANGO_HOST, ARANGO_USER, ARANGO_PASSWORD
3. Create `.env` file with local credentials
4. Test: `docker-compose up -d` and verify ArangoDB Web UI accessible at http://localhost:8529

**Verification**:
- ArangoDB container starts successfully
- Can access Web UI with credentials
- No errors in container logs

---

### [x] Step 2: Install ArangoDB Python Driver

Update Python dependencies:
1. Update `requirements.txt`: Remove `pymongo`, add `python-arango>=7.8.0`
2. Install new dependencies: `pip install -r requirements.txt`

**Verification**:
- `pip list` shows `python-arango` installed
- No import errors when running `python -c "from arango import ArangoClient"`

---

### [x] Step 3: Database Connection & Initialization

Rewrite database connection functions in `db.py`:
1. Replace `pymongo` imports with `python-arango`
2. Implement `connect_arangodb()` function (replaces `connect_mongodb()`)
3. Implement `disconnect_arangodb()` function
4. Update `get_satellites_collection()` for ArangoDB
5. Create database and collection if they don't exist
6. Create indexes: unique on `identifier`, persistent on `canonical.international_designator` and `canonical.registration_number`

**Verification**:
- Run `test_startup.py` and verify connection succeeds
- Check ArangoDB Web UI: database `kessler` and collection `satellites` exist
- Verify indexes are created

---

### [x] Step 4: Query Functions - Find Operations

Translate find operations to AQL:
1. Rewrite `find_satellite()` using AQL queries
2. Handle search by: international_designator, registration_number, name (case-insensitive)
3. Return `None` if not found (maintain existing behavior)

**Verification**:
- Unit test: Insert test document, retrieve by each identifier type
- Verify case-insensitive name search works

---

### [x] Step 5: Query Functions - Search & Filter

Translate complex search with filters to AQL:
1. Rewrite `search_satellites()` function
2. Implement text search with LIKE patterns for query string
3. Implement filters: country, status, orbital_band, congestion_risk
4. Support pagination with skip/limit
5. Handle combined filters with AND logic

**Verification**:
- Run `test_query_filtering.py` and verify all filter combinations work
- Test edge cases: empty query, no filters, all filters combined

---

### [x] Step 6: Query Functions - Count & Aggregations

Translate aggregation operations to AQL:
1. Rewrite `count_satellites()` with filter support
2. Rewrite `get_all_countries()` using AQL UNIQUE
3. Rewrite `get_all_statuses()` using AQL UNIQUE
4. Rewrite `get_all_orbital_bands()` using AQL UNIQUE
5. Rewrite `get_all_congestion_risks()` using AQL UNIQUE

**Verification**:
- Test count matches expected results
- Verify distinct values are correct (no duplicates)
- Compare results with MongoDB (if available for reference)

---

### [x] Step 7: Document Operations - Create & Update

Translate document manipulation operations to AQL:
1. Rewrite `create_satellite_document()` function
2. Handle upsert logic: insert new or update existing by `identifier`
3. Maintain `update_canonical()` logic (no database-specific code)
4. Handle ArangoDB `_key` field (maps to `identifier`)
5. Update `clear_collection()` for ArangoDB

**Verification**:
- Test document creation with new identifier
- Test document update with existing identifier
- Verify canonical section is updated correctly
- Run `test_comprehensive.py` and verify all document operations work

---

### [x] Step 8: Update API Layer

Minimal updates to `api.py`:
1. Update `lifespan` function: Replace `connect_mongodb()` → `connect_arangodb()`
2. Update error messages to reference ArangoDB
3. Verify all database operations still work through abstracted `db.py` functions

**Verification**:
- Start API: `python -m uvicorn api:app --reload`
- Access `/docs` endpoint and verify API documentation loads
- Check health endpoint: `curl http://localhost:8000/v2/health`

---

### [x] Step 9: Integration Testing - API Endpoints

Test all API endpoints with ArangoDB backend:
1. Import sample satellite data using existing import scripts
2. Test `/v2/search` endpoint with various queries and filters
3. Test `/v2/satellite/{identifier}` endpoint
4. Test `/v2/countries`, `/v2/statuses`, `/v2/orbital-bands`, `/v2/congestion-risks`
5. Test `/v2/stats` endpoint
6. Verify response formats match MongoDB implementation (no breaking changes)

**Verification**:
- All API endpoints return HTTP 200 for valid requests
- Response JSON structure unchanged
- Search results match expected data
- No errors in API logs

---

### [x] Step 10: Frontend Verification

Verify React frontend works without modifications:
1. Start React dev server: `cd react-app && npm run dev`
2. Access UI at http://localhost:3000
3. Test search functionality
4. Test filter dropdowns (country, status, orbital band, congestion risk)
5. Test detail panel when clicking a satellite
6. Verify no JavaScript console errors

**Verification**:
- UI loads successfully
- Search returns results
- Filters work correctly
- Detail view displays satellite information
- No UI changes introduced (as per requirements)

---

### [x] Step 11: Run Full Test Suite

Execute all existing tests with ArangoDB:
1. Run `test_comprehensive.py`
2. Run `test_query_filtering.py`
3. Run `test_startup.py`
4. Fix any test failures related to ArangoDB differences
5. Verify all tests pass

**Verification**:
- All test scripts execute without errors
- Test assertions pass
- No regressions in functionality

---

### [x] Step 12: Documentation & Reporting

Create implementation report:
1. Document any query behavior differences found
2. List all modified files
3. Describe testing performed
4. Note any challenges encountered
5. Save report to `.zenflow/tasks/arrangodb-migration-186b/report.md`

**Verification**:
- Report.md exists and is complete
- All steps in plan.md marked as complete
