# Technical Specification: ArangoDB Migration

## Task Complexity: **MEDIUM**

**Rationale**: While the database layer is well-encapsulated in `db.py`, this migration involves:
- Translating MongoDB query patterns to AQL (ArangoDB Query Language)
- Adapting connection management and driver APIs
- Testing query behavior equivalence
- Ensuring no data loss during migration
- Maintaining backward compatibility with existing data import scripts

However, the scope is contained within the database layer with no UI changes required.

---

## 1. Technical Context

### Current Stack
- **Database**: MongoDB 7.0
- **Driver**: `pymongo >= 4.0.0`
- **Connection**: `mongodb://localhost:27019`
- **Database Name**: `kessler`
- **Collection**: `satellites`

### Target Stack
- **Database**: ArangoDB Community Edition (latest stable: 3.11+)
- **Driver**: `python-arango` (Python driver for ArangoDB)
- **Connection**: `http://localhost:8529` (ArangoDB default)
- **Database Name**: `kessler`
- **Collection**: `satellites` (document collection)

### Document Structure
```json
{
  "_key": "generated-by-arango",
  "identifier": "2024-001A",
  "canonical": {
    "name": "Satellite Name",
    "country_of_origin": "USA",
    "international_designator": "2024-001A",
    "registration_number": "REG-001",
    "norad_cat_id": "12345",
    "status": "In Orbit",
    "orbital_band": "LEO",
    "congestion_risk": "Low",
    "orbit": {
      "apogee_km": 550.0,
      "perigee_km": 530.0,
      "inclination_degrees": 97.5,
      "period_minutes": 95.2
    },
    "tle": {
      "line1": "...",
      "line2": "..."
    }
  },
  "sources": {
    "unoosa": { ... },
    "celestrak": { ... }
  },
  "metadata": {
    "created_at": "2024-01-01T00:00:00Z",
    "last_updated_at": "2024-01-01T00:00:00Z",
    "sources_available": ["unoosa", "celestrak"],
    "transformations": []
  }
}
```

---

## 2. Implementation Approach

### 2.1 Database Layer Abstraction
**Modify**: `db.py`

Replace MongoDB-specific operations with ArangoDB equivalents:

| MongoDB Operation | ArangoDB Equivalent |
|------------------|---------------------|
| `MongoClient()` | `ArangoClient()` |
| `client[db_name]` | `client.db(db_name)` |
| `db[collection]` | `db.collection(collection)` |
| `collection.find_one(filter)` | AQL: `FOR doc IN satellites FILTER ... LIMIT 1 RETURN doc` |
| `collection.find(filter)` | AQL: `FOR doc IN satellites FILTER ... RETURN doc` |
| `collection.insert_one(doc)` | `collection.insert(doc)` |
| `collection.replace_one(filter, doc)` | `collection.replace(doc)` |
| `collection.count_documents(filter)` | AQL: `RETURN COUNT(FOR doc IN satellites FILTER ... RETURN 1)` |
| `collection.distinct(field)` | AQL: `RETURN UNIQUE(FOR doc IN satellites RETURN doc.field)` |
| `collection.create_index(field)` | `collection.add_persistent_index(fields=[field])` |
| `{"$regex": pattern, "$options": "i"}` | AQL: `LIKE(doc.field, pattern, true)` or `REGEX_TEST(doc.field, pattern, true)` |
| `{"$or": [...]}` | AQL: `(condition1 OR condition2)` |

### 2.2 Query Translation Strategy

**Text Search with Regex**:
MongoDB:
```python
{"canonical.name": {"$regex": query, "$options": "i"}}
```

ArangoDB AQL:
```aql
FILTER LIKE(doc.canonical.name, CONCAT('%', @query, '%'), true)
```

**Complex Filters**:
MongoDB:
```python
filters = {
    "$or": [
        {"canonical.name": {"$regex": query, "$options": "i"}},
        {"canonical.international_designator": {"$regex": query, "$options": "i"}}
    ],
    "canonical.country": country,
    "canonical.status": status
}
```

ArangoDB AQL:
```aql
FOR doc IN satellites
  FILTER (
    LIKE(doc.canonical.name, @query_pattern, true) OR
    LIKE(doc.canonical.international_designator, @query_pattern, true)
  )
  AND doc.canonical.country == @country
  AND doc.canonical.status == @status
  RETURN doc
```

### 2.3 Index Strategy

ArangoDB indexes to create:
1. **Persistent index** on `identifier` (unique constraint)
2. **Persistent index** on `canonical.international_designator`
3. **Persistent index** on `canonical.registration_number`
4. **Fulltext index** on `canonical.name` (for faster text search)

### 2.4 Connection Management

**Current (MongoDB)**:
```python
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
client.admin.command('ping')
db = client[DB_NAME]
collection = db[COLLECTION_NAME]
```

**Target (ArangoDB)**:
```python
from arango import ArangoClient

client = ArangoClient(hosts=ARANGO_HOST)
sys_db = client.db('_system', username='root', password=ARANGO_PASSWORD)
if not sys_db.has_database(DB_NAME):
    sys_db.create_database(DB_NAME)
db = client.db(DB_NAME, username='root', password=ARANGO_PASSWORD)
if not db.has_collection(COLLECTION_NAME):
    db.create_collection(COLLECTION_NAME)
collection = db.collection(COLLECTION_NAME)
```

---

## 3. Source Code Structure Changes

### Files to Modify
1. **`db.py`** (major changes)
   - Replace `pymongo` imports with `python-arango`
   - Rewrite all query functions using AQL
   - Update connection/disconnection logic
   - Translate index creation syntax
   - Handle ArangoDB-specific `_key` field (maps to MongoDB's `_id`)

2. **`requirements.txt`**
   - Remove: `pymongo>=4.0.0`
   - Add: `python-arango>=7.8.0`

3. **`docker-compose.yml`**
   - Replace MongoDB service with ArangoDB
   - Update ports (27019 → 8529)
   - Update environment variables
   - Update healthcheck commands

4. **`.env.example`**
   - Replace `MONGO_URI` with `ARANGO_HOST`, `ARANGO_USER`, `ARANGO_PASSWORD`
   - Update documentation comments

5. **`api.py`** (minimal changes)
   - Update imports (if any direct MongoDB references)
   - Update lifespan function messages
   - All database operations are already abstracted through `db.py`

### Files to Create (Optional)
1. **`db_arango.py`** (alternative approach)
   - Create new ArangoDB implementation alongside MongoDB
   - Allow gradual migration with feature flag
   - Risk: More code to maintain during transition

**Recommendation**: Direct replacement in `db.py` is cleaner given the abstraction layer already exists.

---

## 4. Data Model / API / Interface Changes

### 4.1 No UI Changes Required
Per task requirements, React frontend remains unchanged. All API endpoints maintain same:
- Request parameters
- Response formats
- HTTP status codes

### 4.2 Internal Document Changes
- **MongoDB `_id`** becomes **ArangoDB `_key`**
- ArangoDB auto-generates `_id` (includes collection name: `satellites/xxx`)
- `_rev` field added by ArangoDB (revision tracking)
- No changes to `canonical`, `sources`, or `metadata` structure

### 4.3 Query Result Differences
ArangoDB cursor objects behave differently from MongoDB cursors:
- Need explicit list conversion: `list(cursor)` or iterate
- No in-place `.skip()` / `.limit()` chaining
- All filtering/pagination done in AQL query

---

## 5. Verification Approach

### 5.1 Unit Testing Strategy
Extend existing tests to verify ArangoDB equivalence:

**Test Files**:
- `test_comprehensive.py` - Run with ArangoDB connection
- `test_query_filtering.py` - Verify filter translation
- `test_startup.py` - Verify connection and indexes

**Test Cases**:
1. **Connection**: Verify `connect_mongodb()` → `connect_arangodb()` succeeds
2. **CRUD Operations**:
   - Create document with `create_satellite_document()`
   - Find by identifier, registration_number, name
   - Update canonical fields
   - Delete (via `clear_collection()`)
3. **Search & Filtering**:
   - Text search with query string
   - Filter by country, status, orbital_band, congestion_risk
   - Combined filters with pagination (skip/limit)
4. **Aggregations**:
   - `count_satellites()` with various filters
   - `get_all_countries()`, `get_all_statuses()`, etc.
5. **Indexes**:
   - Verify unique constraint on `identifier`
   - Verify query performance with indexes

### 5.2 Integration Testing
1. **Start ArangoDB**: `docker-compose up -d`
2. **Import Data**: Run existing import scripts
   - `import_unoosa_data.py`
   - `import_celestrak.py`
   - Verify document structure matches expected format
3. **API Testing**:
   - Start FastAPI: `python -m uvicorn api:app`
   - Test all `/v2/*` endpoints
   - Verify response formats unchanged
4. **React Frontend**:
   - Start dev server: `cd react-app && npm run dev`
   - Perform manual UI testing (search, filter, detail view)
   - Verify no JavaScript errors

### 5.3 Migration Testing
If migrating existing MongoDB data:
1. Export MongoDB data: `mongodump` or Python script
2. Transform `_id` → `_key` if needed
3. Import to ArangoDB: bulk insert via Python script
4. Verify document counts match
5. Spot-check random samples for data integrity

### 5.4 Performance Testing
Compare query performance:
- Search 10,000+ satellites
- Filter by multiple criteria
- Aggregate distinct values
- Expected: Similar or better performance (ArangoDB is optimized for complex queries)

---

## 6. Deployment Considerations

### 6.1 Development Environment
1. Update `docker-compose.yml` for ArangoDB
2. Update `start.sh` script to wait for ArangoDB readiness
3. Provide migration script for existing dev databases

### 6.2 Configuration
- ArangoDB requires authentication by default (username/password)
- Store credentials in `.env` file (not committed)
- Provide clear setup instructions in updated README

### 6.3 Backward Compatibility
- Import scripts will work with new `db.py` (abstracted interface)
- No changes to API contracts
- No changes to frontend

---

## 7. Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Query behavior differences | High | Comprehensive test suite, side-by-side comparison |
| Performance regression | Medium | Benchmark before/after, optimize indexes |
| Data loss during migration | High | Export backup before migration, verify counts |
| Auth configuration errors | Low | Clear documentation, validated .env.example |
| Missing ArangoDB features | Medium | Research feature parity before implementation |

---

## 8. Dependencies

### New Dependencies
- `python-arango>=7.8.0` - Official Python driver for ArangoDB
- ArangoDB Community Edition 3.11+ (Docker image: `arangodb:latest`)

### Removed Dependencies
- `pymongo>=4.0.0`
- `mongo:7.0` Docker image

### Unchanged Dependencies
All other requirements remain the same (FastAPI, pandas, requests, etc.)

---

## 9. Implementation Plan

Given the **medium complexity**, create a detailed step-by-step implementation plan:

### Phase 1: Infrastructure Setup
1. Update `docker-compose.yml` for ArangoDB service
2. Update `.env.example` with ArangoDB configuration
3. Verify ArangoDB starts correctly with Docker

### Phase 2: Database Layer Migration
4. Install `python-arango` and remove `pymongo`
5. Create new connection functions in `db.py`
6. Implement AQL-based query functions
7. Create indexes on ArangoDB collection

### Phase 3: Query Translation
8. Translate `find_satellite()` to AQL
9. Translate `search_satellites()` with filters to AQL
10. Translate `count_satellites()` to AQL
11. Translate aggregation functions (`get_all_*`) to AQL

### Phase 4: Testing & Validation
12. Run existing test suite, fix failures
13. Import sample data and verify structure
14. Test all API endpoints with Postman/curl
15. Manual frontend testing

### Phase 5: Documentation
16. Update plan.md with completion status
17. Create implementation report in `report.md`

---

## 10. Success Criteria

✅ ArangoDB starts successfully via Docker Compose  
✅ All existing tests pass with ArangoDB  
✅ API endpoints return identical responses  
✅ Frontend works without modifications  
✅ Data import scripts work with new database layer  
✅ Query performance is acceptable (no significant regression)  
✅ No UI changes introduced without confirmation  

---

## 11. Rollback Plan

If migration fails:
1. Revert `db.py` to MongoDB implementation
2. Revert `requirements.txt` and `docker-compose.yml`
3. Restart MongoDB service
4. No data loss (original MongoDB still has data)

---

## Estimated Effort

- **Setup & Infrastructure**: 1 hour
- **Database Layer Rewrite**: 3-4 hours
- **Testing & Debugging**: 2-3 hours
- **Documentation**: 30 minutes

**Total**: ~6-8 hours
