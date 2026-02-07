# Migration Guide: Kessler Refactoring

This guide helps developers migrate from the old monolithic structure to the new modular architecture.

---

## Table of Contents

1. [Overview](#overview)
2. [Import Changes](#import-changes)
3. [API Changes](#api-changes)
4. [Database Changes](#database-changes)
5. [Service Usage](#service-usage)
6. [Script Location Changes](#script-location-changes)
7. [Configuration Changes](#configuration-changes)
8. [Testing Changes](#testing-changes)
9. [Troubleshooting](#troubleshooting)

---

## Overview

### What Changed?

- **api.py** (2,241 lines) → Split into **api/** module (main.py + routers + services)
- **db.py** (1,274 lines) → Split into **database/** module (connection + operations + transformations)
- **40+ utility scripts** → Organized into **scripts/** subdirectories
- **Manual caching** → Unified **CacheService**
- **Duplicate orbital calculations** → Unified **OrbitalService**

### What Stayed the Same?

- ✅ All API endpoints (same URLs, same responses)
- ✅ Database schema (no migrations needed)
- ✅ Frontend components (no React changes needed)
- ✅ Environment variables (same names)
- ✅ Docker/deployment configuration

---

## Import Changes

### Database Module

#### Before (Old Imports)
```python
# Old imports from db.py
from db import connect_mongodb, disconnect_mongodb
from db import get_satellites_collection
from db import find_satellite, search_satellites
from db import get_all_countries, get_all_statuses
from db import normalize_country
from db import update_canonical, record_transformation
```

#### After (New Imports)
```python
# New imports from database module
from database.connection import connect_arangodb, disconnect_arangodb
from database.connection import get_satellites_collection
from database.operations import find_satellite, search_satellites
from database.operations import get_all_countries, get_all_statuses
from database.utils.normalization import normalize_country
from database.transformations import update_canonical, record_transformation
```

#### Backward Compatibility (Temporary)

For backward compatibility during migration, you can still use:

```python
# These imports work but are deprecated
from database import connect_mongodb, find_satellite, normalize_country
# Will show deprecation warning in logs
```

**Recommendation**: Update to new imports as soon as possible.

---

### API Module

#### Before (Old Imports)
```python
# Old imports from api.py
from api import app
from api import fetch_tle_data, fetch_tle_by_norad_id
from api import extract_document_metadata
from api import calculate_orbital_state
```

#### After (New Imports)
```python
# New imports from api module
from api.main import app
from api.services.tle_service import TLEService
from api.services.document_service import DocumentService
from api.services.orbital_service import OrbitalService

# Usage
tle_service = TLEService()
tle_data = tle_service.fetch_tle_by_norad_id(25544)

orbital_service = OrbitalService()
orbital_state = orbital_service.calculate_orbital_state(tle_line1, tle_line2)
```

---

### Configuration

#### Before (Old Config)
```python
# Hardcoded values scattered across files
TLE_CACHE_TTL = 3600
DOCUMENT_CACHE_TTL = 86400
DATABASE_HOST = "localhost"
```

#### After (New Config)
```python
# Centralized configuration
from config import DatabaseConfig, CacheConfig, APIConfig

db_config = DatabaseConfig()
print(db_config.host)  # From environment or default

cache_config = CacheConfig()
print(cache_config.tle_cache_ttl)  # From environment or default
```

---

## API Changes

### Endpoint URLs

**No changes!** All endpoints remain the same:

| Endpoint | Status |
|----------|--------|
| `GET /v2/search` | ✅ Unchanged |
| `GET /v2/satellite/{identifier}` | ✅ Unchanged |
| `GET /v2/countries` | ✅ Unchanged |
| `GET /v2/tle/{norad_id}` | ✅ Unchanged |
| `GET /v2/graphs/constellation/{name}` | ✅ Unchanged |
| `POST /v2/mqtt/configurations` | ✅ Unchanged |

### Response Format

**No changes!** All responses have identical structure and fields.

### Internal Changes

If you're working on the API codebase:

#### Before (Monolithic api.py)
```python
# api.py - everything in one file
@app.get("/v2/tle/{norad_id}")
async def get_tle(norad_id: int):
    # TLE fetching logic inline
    # Caching logic inline
    # Parsing logic inline
    return response
```

#### After (Modular Structure)
```python
# api/routers/tle.py - focused router
from api.services.tle_service import TLEService

@router.get("/{norad_id}")
async def get_tle(norad_id: int, tle_service: TLEService = Depends()):
    tle_data = tle_service.fetch_tle_by_norad_id(norad_id)
    return tle_data

# api/services/tle_service.py - reusable service
class TLEService:
    def __init__(self):
        self.cache = CacheService.get_cache("tle_cache")
    
    def fetch_tle_by_norad_id(self, norad_id: int):
        return self.cache.get_or_fetch(
            key=str(norad_id),
            fetch_func=lambda: self._fetch_from_celestrak(norad_id)
        )
```

---

## Database Changes

### Connection Management

#### Before
```python
from db import connect_mongodb, disconnect_mongodb

# Connect
await connect_mongodb()

# Use
collection = await get_satellites_collection()

# Disconnect
await disconnect_mongodb()
```

#### After
```python
from database.connection import connect_arangodb, disconnect_arangodb

# Connect (renamed for clarity)
await connect_arangodb()

# Use (same)
collection = await get_satellites_collection()

# Disconnect
await disconnect_arangodb()

# Note: connect_mongodb() still works as alias (deprecated)
```

### CRUD Operations

#### Before
```python
from db import find_satellite, search_satellites

# Find by ID
satellite = await find_satellite(norad_id="25544")

# Search with filters
results = await search_satellites(
    country="USA",
    status="operational"
)
```

#### After
```python
from database.operations import find_satellite, search_satellites

# Exact same usage!
satellite = await find_satellite(norad_id="25544")

results = await search_satellites(
    country="USA",
    status="operational"
)
```

### Graph Operations

#### Before
```python
from db import get_constellation_graph, get_registration_graph

# Graph queries
graph_data = await get_constellation_graph("Starlink")
```

#### After
```python
from database.graph_operations import get_constellation_graph, get_registration_graph

# Exact same usage!
graph_data = await get_constellation_graph("Starlink")
```

---

## Service Usage

### CacheService

Replaces all manual caching logic.

#### Before (Manual Caching)
```python
# Manual cache dictionary
tle_cache = {}
tle_cache_time = {}

def get_tle_cached(norad_id):
    # Check if cached
    if norad_id in tle_cache:
        cache_time = tle_cache_time[norad_id]
        if time.time() - cache_time < 3600:  # 1 hour TTL
            return tle_cache[norad_id]
    
    # Fetch and cache
    tle_data = fetch_tle_from_celestrak(norad_id)
    tle_cache[norad_id] = tle_data
    tle_cache_time[norad_id] = time.time()
    return tle_data
```

#### After (CacheService)
```python
from api.services.cache_service import CacheService

# Get cache instance
cache = CacheService.get_cache("tle_cache", ttl=3600, max_size=10000)

# Simple get/set
cache.set(norad_id, tle_data)
tle_data = cache.get(norad_id)

# Or use get_or_fetch (recommended)
tle_data = cache.get_or_fetch(
    key=norad_id,
    fetch_func=lambda: fetch_tle_from_celestrak(norad_id)
)

# Check statistics
stats = cache.get_statistics()
print(f"Hit rate: {stats['hit_rate']:.2%}")
print(f"Total hits: {stats['hits']}, misses: {stats['misses']}")
```

---

### OrbitalService

Replaces all duplicate orbital calculation logic.

#### Before (Duplicate Calculations)
```python
# api.py version
def calculate_orbital_state(tle_line1, tle_line2):
    GM = 398600.4418
    mean_motion = float(tle_line2[52:63])
    n = mean_motion * 2 * math.pi / 1440
    a = (GM / (n**2)) ** (1/3)
    # ... more calculations ...

# mqtt_publisher.py version (duplicate!)
def calculate_orbital_parameters(tle_line1, tle_line2):
    GM = 398600.4418
    mean_motion = float(tle_line2[52:63])
    # ... slightly different implementation ...
```

#### After (Unified Service)
```python
from api.services.orbital_service import OrbitalService

service = OrbitalService()

# Calculate full orbital parameters
params = service.calculate_orbital_parameters(tle_line1, tle_line2)
# Returns: {
#   "mean_motion": 15.54,
#   "eccentricity": 0.0001,
#   "inclination": 51.6,
#   "semi_major_axis_km": 6793.0,
#   "orbital_period_minutes": 92.7,
#   "apogee_km": 422.0,
#   "perigee_km": 416.0,
#   "orbital_band": "LEO"
# }

# Or get specific values
period = service.get_orbital_period(mean_motion=15.54)
sma = service.get_semi_major_axis(mean_motion=15.54)
band = service.classify_orbital_band(altitude_km=500)
```

---

## Script Location Changes

All utility scripts have been organized into subdirectories.

### Import Scripts

| Before | After |
|--------|-------|
| `./import_arangodb_data.py` | `scripts/import/import_arangodb_data.py` |
| `./import_kaggle_catalog.py` | `scripts/import/import_kaggle_catalog.py` |
| `./import_tle_api.py` | `scripts/import/import_tle_api.py` |
| `./export_arangodb.py` | `scripts/import/export_arangodb.py` |

### Verification Scripts

| Before | After |
|--------|-------|
| `./verify_constellation_network.py` | `scripts/verification/verify_constellation_network.py` |
| `./verify_graph_structure.py` | `scripts/verification/verify_graph_structure.py` |
| `./check_tle_status.py` | `scripts/verification/check_tle_status.py` |
| `./benchmark_performance.py` | `scripts/verification/benchmark_performance.py` |

### Population Scripts

| Before | After |
|--------|-------|
| `./populate_constellation_network.py` | `scripts/population/populate_constellation_network.py` |
| `./populate_orbital_proximity.py` | `scripts/population/populate_orbital_proximity.py` |

### Maintenance Scripts

| Before | After |
|--------|-------|
| `./promote_attributes.py` | `scripts/maintenance/promote_attributes.py` |
| `./enrich_launch_data.py` | `scripts/maintenance/enrich_launch_data.py` |
| `./add_graph_indexes.py` | `scripts/maintenance/add_graph_indexes.py` |

### Running Scripts

#### Before
```bash
python verify_constellation_network.py
python import_kaggle_catalog.py
```

#### After
```bash
python scripts/verification/verify_constellation_network.py
python scripts/import/import_kaggle_catalog.py

# Or from project root (scripts handle paths)
cd /path/to/kessler
python scripts/verification/verify_constellation_network.py
```

---

## Configuration Changes

### Environment Variables

**No changes!** All environment variables remain the same:

```bash
# Database
ARANGO_HOST=localhost
ARANGO_PORT=8529
ARANGO_DATABASE=kessler
ARANGO_USER=root
ARANGO_PASSWORD=

# API
API_HOST=127.0.0.1
API_PORT=8000
LOG_LEVEL=info
CORS_ORIGINS=*

# Caching
TLE_CACHE_TTL=3600
DOCUMENT_CACHE_TTL=86400
MAX_CACHE_SIZE=10000
```

### Configuration Access

#### Before
```python
import os

database_host = os.getenv("ARANGO_HOST", "localhost")
tle_cache_ttl = int(os.getenv("TLE_CACHE_TTL", "3600"))
```

#### After
```python
from config import DatabaseConfig, CacheConfig

db_config = DatabaseConfig()
print(db_config.host)  # Automatically loads from env

cache_config = CacheConfig()
print(cache_config.tle_cache_ttl)  # Automatically loads from env
```

---

## Testing Changes

### Test Location

| Before | After |
|--------|-------|
| `./test_comprehensive.py` | `tests/unit/test_comprehensive.py` |
| `./test_graph_db.py` | `tests/integration/test_graph_db.py` |
| `./test_mqtt_endpoint.py` | `tests/integration/test_mqtt_endpoint.py` |

### Running Tests

#### Before
```bash
pytest test_comprehensive.py
pytest test_graph_db.py
```

#### After
```bash
# Run all tests
pytest tests/

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/

# Run specific test file
pytest tests/unit/test_cache_service.py

# Run with coverage
pytest tests/ --cov=api --cov=database --cov-report=html
```

### Test Imports

#### Before
```python
# test_comprehensive.py
from api import app
from db import connect_mongodb
```

#### After
```python
# tests/unit/test_cache_service.py
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.main import app
from database.connection import connect_arangodb
```

---

## Troubleshooting

### Common Issues

#### Issue 1: ImportError for old imports

**Error:**
```python
ImportError: cannot import name 'find_satellite' from 'db'
```

**Solution:**
```python
# Old (broken)
from db import find_satellite

# New (works)
from database.operations import find_satellite
```

---

#### Issue 2: Scripts can't find modules

**Error:**
```
ModuleNotFoundError: No module named 'api'
```

**Solution:**
Update script to add project root to Python path:

```python
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Now imports work
from api.services.tle_service import TLEService
```

---

#### Issue 3: Cache not working

**Error:**
```
Cache hit rate is 0%
```

**Solution:**
Ensure you're using the same cache instance:

```python
# Wrong - creates new cache each time
def get_tle(norad_id):
    cache = CacheService.get_cache("tle")  # New instance!
    return cache.get_or_fetch(...)

# Right - reuse singleton
cache = CacheService.get_cache("tle_cache")  # At module level

def get_tle(norad_id):
    return cache.get_or_fetch(...)
```

---

#### Issue 4: Orbital calculations differ

**Error:**
```
AssertionError: Orbital period differs by 0.5 minutes
```

**Solution:**
Check TLE format - ensure line1 and line2 are passed correctly:

```python
# Wrong - reversed lines
params = orbital_service.calculate_orbital_parameters(line2, line1)

# Right - line1 first, line2 second
params = orbital_service.calculate_orbital_parameters(line1, line2)
```

---

### Migration Checklist

Use this checklist when migrating your code:

- [ ] Update all `from db import` to `from database.*`
- [ ] Update all `from api import` to `from api.*`
- [ ] Replace manual caching with `CacheService`
- [ ] Replace duplicate orbital calculations with `OrbitalService`
- [ ] Move scripts to appropriate subdirectories
- [ ] Update script imports to add project root to path
- [ ] Update test imports and paths
- [ ] Run tests to verify functionality
- [ ] Check cache statistics to ensure caching works
- [ ] Verify orbital calculations match expected values

---

## Gradual Migration Strategy

You don't have to migrate everything at once! Here's a recommended approach:

### Phase 1: Update Imports (Low Risk)
1. Update `from db import` to `from database.*`
2. Update `from api import` to `from api.*`
3. Run tests to verify

### Phase 2: Adopt Services (Medium Risk)
1. Replace manual caching with `CacheService` in one module
2. Test thoroughly
3. Replace orbital calculations with `OrbitalService` in one module
4. Test thoroughly
5. Repeat for other modules

### Phase 3: Reorganize Scripts (Low Risk)
1. Move scripts to new directories
2. Update any CI/CD pipelines that reference script paths
3. Update documentation

### Phase 4: Clean Up (Low Risk)
1. Remove old backup files (api.py.backup, db.py.backup)
2. Remove deprecated import aliases
3. Remove old manual cache dictionaries

---

## Getting Help

### Resources

- **Architecture Documentation**: See `ARCHITECTURE.md` for module structure
- **Developer Guide**: See `DEVELOPER_GUIDE.md` for coding patterns
- **API Documentation**: `http://localhost:8000/docs` (FastAPI Swagger UI)
- **Test Examples**: Check `tests/unit/` for usage examples

### Support

If you encounter issues not covered in this guide:

1. Check the test files for usage examples
2. Review the original implementation in `api.py.backup` or `db.py.backup`
3. Check git commit history for migration examples
4. Open an issue on the project repository

---

## Summary

### Key Takeaways

✅ **API endpoints unchanged** - all URLs and responses identical  
✅ **Database schema unchanged** - no data migration needed  
✅ **Environment variables unchanged** - same config names  
✅ **Gradual migration supported** - migrate module by module  
✅ **Backward compatibility** - deprecated imports still work temporarily  

### Benefits After Migration

- 🚀 **Faster development** - small, focused files easier to work with
- 🧪 **Better testing** - services can be tested in isolation
- 📦 **Code reuse** - services used across multiple routers
- 🐛 **Easier debugging** - clear separation of concerns
- 📈 **Better performance** - unified caching with LRU eviction

---

**Last Updated**: February 6, 2026  
**Version**: 2.0.0 (Post-refactoring)
