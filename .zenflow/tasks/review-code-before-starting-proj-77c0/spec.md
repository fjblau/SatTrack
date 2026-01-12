# Technical Specification: Kessler Satellite Registry Codebase Review

## Difficulty Assessment: **MEDIUM**

This is a moderately complex full-stack application with:
- Multi-source data integration (UNOOSA, CelesTrak, Space-Track, Kaggle)
- MongoDB document database with sophisticated data merging logic
- External API integrations with caching strategies
- PDF processing and web scraping capabilities
- Established architecture patterns

## Technical Context

### Stack Overview
- **Backend**: Python 3.11, FastAPI, uvicorn
- **Database**: MongoDB 7.0 (Docker, port 27018)
- **Frontend**: React 19.2.3, Vite 7.2.7, JavaScript (no TypeScript)
- **Deployment**: Shell script orchestration (start.sh)

### Dependencies

**Python (Backend)**:
```
fastapi          # Web framework
uvicorn          # ASGI server
pymongo>=4.0.0   # MongoDB driver
pandas           # Data manipulation
numpy            # Numerical operations
requests         # HTTP client
beautifulsoup4   # Web scraping
pdfplumber       # PDF extraction
python-dotenv    # Environment variables (optional)
```

**JavaScript (Frontend)**:
```json
{
  "react": "^19.2.3",
  "react-dom": "^19.2.3",
  "vite": "^7.2.7",
  "@vitejs/plugin-react": "^5.1.2"
}
```

### Repository Structure
```
/
├── api.py                    # FastAPI backend (632 LOC)
├── db.py                     # MongoDB abstraction (381 LOC)
├── start.sh                  # Startup orchestration
├── docker-compose.yml        # MongoDB container
├── .env.example              # Environment template
├── requirements-mongodb.txt  # Minimal Python deps
│
├── react-app/               # Frontend application
│   ├── src/
│   │   ├── App.jsx          # Main app component
│   │   ├── components/      # React components
│   │   │   ├── Filters.jsx
│   │   │   ├── DataTable.jsx
│   │   │   ├── DetailPanel.jsx
│   │   │   └── DataRecordModal.jsx
│   │   └── *.css            # Component styles
│   ├── vite.config.js       # Vite configuration
│   └── package.json
│
├── data/                    # CSV registry data
│   ├── unoosa_registry.csv (1.19 MB)
│   └── *.csv
│
├── scripts/                 # Utility scripts
│   ├── mongodb.sh
│   └── migrate_data.sh
│
├── import_*.py              # Data import scripts
├── promote_attributes.py    # Field promotion (692 LOC)
├── test_*.py                # Test files
└── docs/                    # Documentation
```

## Architecture Analysis

### 1. Data Layer (MongoDB)

**Envelope Pattern** (`db.py`):
```python
{
  "identifier": "2024-001A",           # Unique ID
  "canonical": {                        # Merged best-available data
    "name": "...",
    "country_of_origin": "...",
    "orbit": { ... },
    "tle": { ... }
  },
  "sources": {                          # Source-specific data
    "unoosa": { ... },
    "celestrak": { ... },
    "kaggle": { ... }
  },
  "metadata": {
    "sources_available": ["unoosa", "celestrak"],
    "source_priority": ["unoosa", "celestrak", "spacetrack", "kaggle"],
    "transformations": [ ... ]
  }
}
```

**Key Functions**:
- `create_satellite_document()` - Create/update with envelope structure
- `update_canonical()` - Merge sources by priority
- `search_satellites()` - MongoDB queries with filters
- `get_nested_field()` / `set_nested_field()` - Dot-notation field access

**Indexes**:
- `canonical.international_designator` (non-unique)
- `canonical.registration_number` (non-unique)
- `identifier` (unique)

### 2. API Layer (FastAPI)

**api.py** - Two API versions:
- Legacy endpoints: `/api/documents/*` (document resolution, metadata extraction)
- V2 endpoints: `/v2/*` (MongoDB-backed satellite search)

**Key Endpoints**:
- `GET /v2/search` - Search with filters (country, status, orbital_band, congestion_risk)
- `GET /v2/satellite/{identifier}` - Detailed satellite view
- `GET /v2/countries|statuses|orbital-bands|congestion-risks` - Filter options
- `GET /v2/tle/{norad_id}` - Current TLE from Space-Track
- `GET /api/documents/resolve` - Resolve UNOOSA document links
- `GET /api/documents/metadata` - Extract PDF metadata

**Caching Strategy**:
- TLE data: 1-hour TTL (3600s) in-memory dict
- Document links: 1-hour TTL
- PDF metadata: 1-hour TTL

**External Integrations**:
- CelesTrak (TLE data): `https://celestrak.org/NORAD/elements/*.txt`
- Space-Track (authenticated): `https://www.space-track.org/` (requires credentials)
- UNOOSA (document scraping): `https://www.unoosa.org/`

### 3. Frontend (React)

**Component Hierarchy**:
```
App (state management)
├── Filters (search + filter UI)
├── DataTable (results grid + pagination)
└── DetailPanel (selected satellite details)
    └── DataRecordModal (raw MongoDB document viewer)
```

**Data Flow**:
1. `App.jsx` fetches filter options on mount
2. User changes filters → `Filters.jsx` → `App.handleFilterChange()`
3. `App.fetchObjects()` → `/v2/search?params`
4. Results → `DataTable` (50 per page)
5. Row click → `DetailPanel` → `/v2/satellite/{id}` + `/v2/tle/{norad}`

**API Calls**:
- `/v2/countries|statuses|orbital-bands|congestion-risks` (filter dropdowns)
- `/v2/search` (with pagination: skip, limit)
- `/v2/satellite/{identifier}` (detail view)
- `/v2/tle/{norad_id}` (current TLE)
- `/api/documents/resolve` (registration doc links)
- `/api/documents/metadata` (PDF extraction)

### 4. Data Import Scripts

**Pattern** (used by all import scripts):
```python
1. Load CSV/external data
2. Connect to MongoDB
3. For each record:
   - Normalize values
   - Find identifier (NORAD ID, intl designator, etc.)
   - Call create_satellite_document(identifier, source, data)
4. update_canonical() merges sources by priority
```

**Scripts**:
- `import_kaggle_catalog.py` - Kaggle current_catalog.csv → "kaggle" source
- `import_spacetrack_tle.py` - Space-Track TLE data → "spacetrack" source
- `promote_attributes.py` - Batch field promotion with safety checks (692 LOC)

## Code Quality Assessment

### Strengths ✅

1. **Clean Architecture**:
   - Clear separation: DB layer (`db.py`) → API layer (`api.py`) → Frontend
   - Envelope pattern enables multi-source data without conflicts
   - Component-based React with CSS modules

2. **Database Design**:
   - Flexible schema (MongoDB documents)
   - Source priority system (UNOOSA > CelesTrak > Space-Track > Kaggle)
   - Transformation history tracking

3. **Error Handling**:
   - Try-except blocks in data fetching
   - Graceful fallbacks (e.g., docLink not found → show message)
   - MongoDB connection checks on startup

4. **Modern Stack**:
   - React 19 with hooks
   - Vite for fast builds
   - FastAPI with async support

5. **Documentation**:
   - Comprehensive `docs/` folder with setup guides
   - Docstrings in Python functions
   - `.env.example` for configuration

### Issues & Technical Debt ⚠️

#### **High Priority**

1. **Missing Complete Requirements File**:
   ```
   Issue: Only requirements-mongodb.txt exists (1 package)
   Impact: Missing fastapi, uvicorn, pandas, numpy, requests, bs4, pdfplumber
   Fix: Create requirements.txt with all dependencies + versions
   ```

2. **Hardcoded Python Path**:
   ```bash
   # start.sh:57
   /usr/local/Cellar/python@3.11/3.11.13/Frameworks/Python.framework/Versions/3.11/Resources/Python.app/Contents/MacOS/Python -m uvicorn api:app
   
   Issue: Machine-specific absolute path
   Impact: Script fails on other machines
   Fix: Use `python3` or virtualenv
   ```

3. **Open CORS Policy**:
   ```python
   # api.py:37-38
   allow_origins=["*"]
   
   Issue: Security risk in production
   Impact: Any origin can make requests
   Fix: Restrict to specific origins via environment variable
   ```

4. **No Type Safety on Frontend**:
   ```
   Issue: JavaScript without TypeScript
   Impact: Runtime errors, poor IDE support
   Fix: Consider TypeScript migration or PropTypes validation
   ```

#### **Medium Priority**

5. **Inconsistent Error Handling in API**:
   ```python
   # api.py:518
   return {"error": "Satellite not found"}, 404
   
   Issue: Mixing dict and tuple returns
   Impact: Unclear response format
   Fix: Use FastAPI HTTPException consistently
   ```

6. **No Frontend State Management**:
   ```javascript
   // App.jsx has 14 useState calls
   Issue: State management in single component
   Impact: Difficult to scale, prop drilling
   Fix: Consider Context API or Zustand for shared state
   ```

7. **Limited Test Coverage**:
   ```
   Files: test_*.py exist (7 files)
   Issue: No CI/CD integration, unclear coverage
   Impact: Manual testing, regression risks
   Fix: Add pytest configuration, coverage reports
   ```

8. **Cache Invalidation Logic**:
   ```python
   # api.py:56 - TLE cache check
   if tle_cache and all(current_time - tle_cache_time.get(cat, 0) < CACHE_TTL for cat in tle_cache):
   
   Issue: Checks ALL categories even if one is stale
   Impact: Unnecessary cache hits/misses
   Fix: Per-category TTL checks
   ```

9. **No API Rate Limiting**:
   ```
   Issue: No rate limits on /v2/search or external API calls
   Impact: Potential abuse, CelesTrak/Space-Track blocking
   Fix: Add slowapi or similar middleware
   ```

#### **Low Priority**

10. **Magic Numbers**:
    ```python
    # api.py:138-144
    GM = 398600.4418  # No comment explaining constant
    earth_radius = 6378.137
    
    Fix: Add comments or constants file
    ```

11. **Repeated Code Patterns**:
    ```python
    # db.py has similar loops in update_canonical()
    # for canonical_fields vs orbital_fields vs tle_fields
    
    Fix: Extract to helper function
    ```

12. **CSS Not Scoped**:
    ```
    Issue: CSS files loaded globally (potential conflicts)
    Fix: Use CSS Modules (*.module.css) or styled-components
    ```

13. **No Logging Framework**:
    ```python
    # api.py uses print() statements
    print(f"Error fetching {tle_url}: {e}")
    
    Fix: Use Python logging module with levels
    ```

## Security Considerations

1. **Credentials Management**: Space-Track credentials via `.env` (good), but no validation
2. **PDF Processing**: `pdfplumber` on untrusted PDFs (potential security risk)
3. **Web Scraping**: BeautifulSoup on external content (XSS risks if rendered)
4. **MongoDB Injection**: Using `$regex` with user input (potential injection)
   - Current: `{"canonical.name": {"$regex": query, "$options": "i"}}`
   - Fix: Escape regex special characters

## Performance Notes

1. **Pagination**: Frontend uses 50 items/page (reasonable)
2. **Database Indexes**: Present on key fields (good)
3. **Caching**: 1-hour TTL on external data (appropriate for orbital data)
4. **React Rendering**: No memo/useMemo optimizations (minor issue with current dataset size)

## Deployment Considerations

1. **Environment Variables**:
   - `MONGO_URI` (required)
   - `SPACE_TRACK_USER`, `SPACE_TRACK_PASS` (optional)
   - Missing: `CORS_ORIGINS`, `API_URL`, `LOG_LEVEL`

2. **Docker Compose**: MongoDB only (no backend/frontend containers)
   - Recommendation: Add `api` and `web` services

3. **Port Conflicts**: Uses 8000 (API), 3000 (web), 27018 (MongoDB)
   - Handled by `start.sh` cleanup

4. **Data Persistence**: MongoDB volume mounted correctly

## Recommendations for Future Development

### Immediate (Before Adding Features)

1. **Create `requirements.txt`**:
   ```
   fastapi==0.115.0
   uvicorn[standard]==0.32.0
   pymongo>=4.0.0
   pandas==2.2.0
   numpy==2.0.0
   requests==2.32.0
   beautifulsoup4==4.12.0
   pdfplumber==0.11.0
   python-dotenv==1.0.0
   ```

2. **Fix `start.sh` Python path**:
   ```bash
   # Replace line 57 with:
   python3 -m uvicorn api:app --host 127.0.0.1 --port 8000 &
   ```

3. **Add CORS configuration**:
   ```python
   # api.py
   CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
   allow_origins=CORS_ORIGINS
   ```

### Short-term (Quality Improvements)

4. **Add input validation** (Pydantic models):
   ```python
   from pydantic import BaseModel
   
   class SearchParams(BaseModel):
       q: Optional[str] = None
       country: Optional[str] = None
       # ...
   ```

5. **Use FastAPI dependency injection** for DB connection:
   ```python
   from fastapi import Depends
   
   def get_db():
       if satellites_collection is None:
           raise HTTPException(503, "Database not connected")
       return satellites_collection
   ```

6. **Add logging**:
   ```python
   import logging
   logging.basicConfig(level=logging.INFO)
   logger = logging.getLogger(__name__)
   ```

7. **Add PropTypes or TypeScript** on frontend

8. **Set up pytest** with coverage reporting

### Long-term (Architecture Evolution)

9. **Consider state management library** (Zustand/Redux) if UI grows
10. **Add background tasks** (FastAPI BackgroundTasks) for slow PDF processing
11. **Implement Redis caching** instead of in-memory dicts (for multi-process deployments)
12. **Add OpenAPI tags** for better documentation organization
13. **Containerize all services** (Docker Compose with api + web services)

## Implementation Approach (If Starting New Project on This)

Given this is a **review** task, no implementation needed. However, if building on this codebase:

1. **Fix Critical Issues First**: requirements.txt, start.sh path, CORS
2. **Understand Data Flow**: Read `db.py` → `api.py` → React components
3. **Review Existing Patterns**: Use envelope pattern for new sources, follow component structure
4. **Test Integration Points**: TLE fetching, MongoDB queries, document resolution
5. **Respect Source Priority**: UNOOSA is authoritative → preserve in canonical merging

## Summary

**Kessler** is a well-architected satellite registry application with:
- ✅ Solid MongoDB envelope pattern for multi-source data
- ✅ Clean separation between backend and frontend
- ✅ Good foundation for extension
- ⚠️ Missing production-ready configuration (requirements.txt, CORS, logging)
- ⚠️ Some technical debt in caching, error handling, and type safety

**Recommendation**: This codebase is suitable for building upon. Address high-priority issues (requirements.txt, hardcoded paths, CORS) before adding new features. The architecture is sound and follows good separation of concerns.
