# Kessler Architecture Documentation

## Overview

Kessler is a satellite tracking and orbital debris monitoring application with a Python FastAPI backend and React frontend. This document describes the architecture before and after the refactoring project.

---

## Architecture Comparison

### Before Refactoring

```
kessler/
├── api.py                      # 2,241 lines - monolithic API
│   ├── All endpoints
│   ├── TLE fetching & caching
│   ├── Document metadata extraction
│   ├── Orbital calculations
│   ├── Graph operations
│   └── MQTT configuration
│
├── db.py                       # 1,274 lines - monolithic database
│   ├── Connection management
│   ├── CRUD operations
│   ├── Graph operations
│   ├── MQTT config storage
│   ├── Country normalization
│   └── Data transformations
│
├── 40+ utility scripts          # Unorganized in root
├── react-app/                   # Frontend (organized)
└── tests/                       # Few tests, unorganized
```

**Issues:**
- ❌ **Massive files**: api.py (2,241 lines), db.py (1,274 lines)
- ❌ **Code duplication**: Orbital calculations in 3+ places
- ❌ **Manual caching**: Multiple cache dictionaries with inconsistent TTL
- ❌ **Mixed concerns**: Business logic, data access, and utilities mixed
- ❌ **Poor testability**: Hard to test individual components
- ❌ **Unorganized scripts**: 40+ scripts in root directory

---

### After Refactoring

```
kessler/
├── config.py                    # Centralized configuration (DatabaseConfig, CacheConfig,
│                                #   APIConfig, ExternalServicesConfig, AuthConfig, AgentConfig)
│
├── api/                         # API Layer
│   ├── main.py                  # FastAPI app entry point, lifespan, middleware
│   ├── middleware/
│   │   └── auth.py              # Bearer-token authentication middleware
│   ├── routers/                 # API endpoints by domain
│   │   ├── auth.py              # POST /v2/auth/login, POST /v2/auth/logout
│   │   ├── satellites.py        # Satellite search & retrieval (legacy /v2/satellite/* — deprecated, to be removed in Spec 3)
│   │   ├── objects.py           # Space object search & retrieval (/v2/objects/*)
│   │   ├── provenance.py        # Provenance graph traversal (/v2/provenance/*)
│   │   ├── inference.py         # ML inference stubs (/v2/inference/*; not yet implemented)
│   │   ├── metadata.py          # Countries, statuses, orbital bands, stats
│   │   ├── graphs.py            # Graph visualization & analytics endpoints
│   │   ├── documents.py         # UN document metadata
│   │   ├── tle.py               # TLE data endpoints & orbit propagation
│   │   ├── ephemeris.py         # Ephemeris generation (SGP4 + GMAT HIFI), CZML export
│   │   ├── mqtt.py              # MQTT configuration & publishing
│   │   ├── observations.py      # Observation import, analytics, graph data
│   │   ├── admin.py             # Admin script execution, run tracking, GMAT status
│   │   ├── agent.py             # POST /v2/ask, POST /v2/aql, GET /v2/ask/status (AI agents)
│   │   ├── kestrel.py           # POST /v2/kestrel/maneuver-plan, GET/DELETE /v2/kestrel/maneuver-plans
│   │   └── docs.py              # GET /v2/docs — HTML documentation viewer
│   ├── services/                # Business logic services
│   │   ├── cache_service.py     # Unified caching with LRU & TTL
│   │   ├── orbital_service.py   # Orbital calculations from TLE
│   │   ├── tle_service.py       # TLE fetching & parsing (CelesTrak / Space-Track)
│   │   ├── document_service.py  # UN document metadata extraction
│   │   ├── collision_service.py # Collision risk computation
│   │   ├── lineage_service.py   # Satellite family-tree traversal
│   │   ├── propagation_service.py # SGP4/Skyfield orbit propagation
│   │   ├── gmat_service.py      # GMAT high-fidelity propagation (RK89 + EGM96)
│   │   ├── gmat_maneuver_service.py # Kestrel Hohmann + GMAT rendezvous maneuver planning
│   │   ├── spacetrack_service.py  # Space-Track API integration
│   │   ├── discos_service.py    # ESA DISCOSweb v2 API client (objects, launches, fragmentations, entities)
│   │   ├── index_service.py     # ChromaDB RAG vector store build & load
│   │   ├── agent_service.py     # LangGraph general assistant (RAG + tools, /v2/ask)
│   │   ├── aql_agent_service.py # LangGraph AQL translation agent (/v2/aql)
│   │   └── kestrel_agent_service.py # LangGraph Kestrel mission planning agent
│   └── utils/
│       └── converters.py        # Format conversion utilities
│
├── database/                    # Data Layer
│   ├── connection.py            # ArangoDB connection, collection & graph init (all collections & named graphs)
│   ├── operations.py            # CRUD operations (objects collection)
│   ├── identifier_operations.py # Alias-based lookups (norad, cospar, discos, vimpel, kestrel)
│   ├── graph_operations.py      # Graph edge CRUD & index management
│   ├── graph_analytics.py       # AQL graph analytics (centrality, communities, etc.)
│   ├── observation_graph_ops.py # Observation edge creation & graph traversal
│   ├── ephemeris_ops.py         # Ephemeris envelope CRUD (ephemeris_envelopes collection)
│   ├── maneuver_plan_ops.py     # Kestrel maneuver plan CRUD (kestrel_maneuver_plans collection)
│   ├── transformations.py       # Data canonicalization & transformation
│   ├── mqtt_config.py           # MQTT configuration storage
│   ├── data/
│   │   └── country_codes.json   # ISO 3166-1 alpha-3 mappings
│   └── utils/
│       ├── normalization.py     # Country code normalization
│       └── field_utils.py       # Nested field manipulation utilities
│
├── gmat_scripts/                # GMAT script templates & output
│   ├── templates/
│   │   └── propagation.script   # Parameterized GMAT script (RK89 + EGM96)
│   └── output/                  # Ephemeris output files (transient)
│
├── scripts/                     # Organized utility scripts
│   ├── import/                  # Data import scripts
│   ├── verification/            # Data verification scripts
│   ├── population/              # Graph population scripts
│   └── maintenance/             # Data maintenance scripts
│
├── tests/                       # Comprehensive test suite
│   ├── unit/                    # Unit tests for services
│   ├── integration/             # API & database integration tests
│   └── e2e/                     # End-to-end tests
│
├── react-app/                   # React Frontend
│   └── src/
│       ├── config/
│       │   └── constants.js     # API endpoint constants
│       ├── utils/
│       │   ├── apiFetch.js      # Authenticated fetch wrapper
│       │   └── orbitUtils.js    # Client-side orbital calculation utilities
│       └── components/
│           ├── DataTable.jsx    # Satellite data grid
│           ├── DetailPanel.jsx  # Satellite detail view
│           ├── Filters.jsx      # Search filter sidebar
│           ├── GraphExplorer.jsx/GraphViewer.jsx  # Graph visualization
│           ├── TimelineChart.jsx  # Launch timeline
│           ├── ObservationsView.jsx/ObservationGraphs.jsx/ObservationDashboard.jsx
│           ├── EphemerisPage.jsx  # Ephemeris generation & CZML export
│           ├── KestrelMissionPage.jsx  # Rendezvous mission planner (Hohmann + GMAT)
│           ├── KestrelDataPage.jsx  # Kestrel satellite data dashboard
│           ├── KestrelCesiumViewer.jsx/KestrelDataGlobe.jsx/KestrelDataDials.jsx
│           ├── CesiumViewer.jsx  # General-purpose CesiumJS 3D viewer
│           ├── CentralityView.jsx/CollisionRiskView.jsx/ConstellationBrowser.jsx
│           ├── SatelliteNeighborhood.jsx/EvolutionTimelineView.jsx/PathFinderPanel.jsx
│           ├── AqlEditorPage.jsx  # Interactive AQL query editor
│           ├── HelpPage.jsx     # AI assistant chat interface
│           ├── AdminPage.jsx    # Admin script runner + Demo Contents checklist (controls demo-mode tab/subtab visibility; persisted to ArangoDB app_settings collection via GET/PUT /v2/admin/demo-config, shared across all users)
│           └── LoginPage.jsx    # Authentication
│
└── mqtt_publisher.py            # MQTT publishing service
    mqtt_scheduler.py            # MQTT scheduling service
```

**Improvements:**
- ✅ **Modular structure**: Small, focused files (<400 lines each)
- ✅ **Unified services**: Single source of truth for caching and orbital calculations
- ✅ **Clear separation**: Routers → Services → Database
- ✅ **Organized scripts**: Grouped by purpose (import, verification, population, maintenance)
- ✅ **Comprehensive tests**: 51+ unit tests, integration tests, E2E tests
- ✅ **Configuration management**: Centralized, environment-aware config

---

## Module Dependencies

### Layered Architecture

```
┌─────────────────────────────────────────────┐
│           External Clients                   │
│     (React App, MQTT Subscribers, etc.)      │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│              API Layer                       │
│  ┌──────────────────────────────────────┐   │
│  │  main.py (FastAPI app)               │   │
│  └────────────┬─────────────────────────┘   │
│               │                              │
│  ┌────────────▼─────────────────────────┐   │
│  │  Routers (endpoints)                 │   │
│  │  - auth, satellites, metadata        │   │
│  │  - graphs, documents, tle, mqtt      │   │
│  │  - observations, admin, agent        │   │
│  └────────────┬─────────────────────────┘   │
│               │                              │
│  ┌────────────▼─────────────────────────┐   │
│  │  Services (business logic)           │   │
│  │  - CacheService, OrbitalService      │   │
│  │  - TLEService, DocumentService       │   │
│  │  - CollisionService, LineageService  │   │
│  │  - PropagationService, GmatService   │   │
│  │  - SpaceTrackService, IndexService   │   │
│  │  - AgentService, AqlAgentService     │   │
│  └────────────┬─────────────────────────┘   │
└───────────────┼──────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────┐
│           Database Layer                     │
│  ┌──────────────────────────────────────┐   │
│  │  connection.py (ArangoDB)            │   │
│  └────────────┬─────────────────────────┘   │
│               │                              │
│  ┌────────────▼─────────────────────────┐   │
│  │  operations.py (CRUD)                │   │
│  │  graph_operations.py (Graph queries) │   │
│  │  transformations.py (Data transform) │   │
│  │  mqtt_config.py (MQTT storage)       │   │
│  └──────────────────────────────────────┘   │
└───────────────┼──────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────┐
│          External Services                   │
│  - ArangoDB (database)                       │
│  - CelesTrak (TLE data)                      │
│  - Space-Track (TLE data)                    │
│  - UN Documents (metadata)                   │
└─────────────────────────────────────────────┘
```

### Key Design Principles

1. **Separation of Concerns**
   - **Routers**: Handle HTTP requests/responses, validation
   - **Services**: Business logic, external API calls, caching
   - **Database**: Data persistence, queries, transformations

2. **Dependency Injection**
   - Services are passed to routers via dependency injection
   - Database connections managed via lifespan context
   - Easy to mock for testing

3. **Single Responsibility**
   - Each module has one clear purpose
   - Files are <400 lines (routers) or <300 lines (database)
   - Services are reusable across routers

4. **No Circular Dependencies**
   - API layer depends on Database layer
   - Database layer has no knowledge of API layer
   - Services can be used independently

---

## Data Flow

### Satellite Search Example

```
1. User Request
   └─→ GET /v2/search?country=USA&status=operational

2. API Router (satellites.py)
   └─→ Validate parameters
   └─→ Call database.operations.search_satellites()

3. Database Operations
   └─→ Build AQL query
   └─→ Execute against ArangoDB
   └─→ Return results

4. API Response
   └─→ Format as JSON
   └─→ Return to client
```

### TLE Data Fetching Example

```
1. User Request
   └─→ GET /v2/tle/25544 (ISS)

2. API Router (tle.py)
   └─→ Call TLEService.get_tle_by_norad_id(25544)

3. TLE Service
   └─→ Check CacheService for cached TLE
   └─→ If cache miss:
       └─→ Fetch from CelesTrak API
       └─→ Parse TLE data
       └─→ Store in CacheService (1 hour TTL)
   └─→ Return TLE data

4. Orbital Calculations (if requested)
   └─→ Call OrbitalService.calculate_orbital_parameters()
   └─→ Return orbital state

5. API Response
   └─→ Format as JSON with TLE + orbital data
   └─→ Return to client
```

---

## Service Details

### CacheService

**Purpose**: Unified caching with TTL and LRU eviction

**Features**:
- Time-to-live (TTL) management
- LRU (Least Recently Used) eviction when size limit reached
- Named cache instances (e.g., "tle_cache", "document_cache")
- Statistics tracking (hits, misses, evictions, hit rate)
- `get_or_fetch()` convenience method

**Usage**:
```python
from api.services.cache_service import CacheService

cache = CacheService.get_cache("tle_cache", ttl=3600, max_size=1000)

# Get or fetch with automatic caching
tle_data = cache.get_or_fetch(
    key=norad_id,
    fetch_func=lambda: fetch_from_celestrak(norad_id)
)

# Check statistics
stats = cache.get_statistics()
print(f"Hit rate: {stats['hit_rate']:.2%}")
```

---

### OrbitalService

**Purpose**: Unified orbital calculations from TLE data

**Features**:
- Parse TLE (Two-Line Element) format
- Calculate orbital parameters (semi-major axis, period, apogee, perigee)
- Classify orbital band (LEO, MEO, GEO, HEO)
- Extract epoch from TLE
- Handle scientific notation in TLE format

**Usage**:
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

# Classify orbital band
band = service.classify_orbital_band(altitude_km=500.0)
# Returns: "LEO"
```

---

## Database Schema

### ArangoDB Database: `kessler`

#### Vertex Collections

| Collection | Description | Key Indexes |
|-----------|-------------|-------------|
| `objects` | Primary space-object registry — all UNOOSA/NORAD records with canonical fields, `object_class`, and `identifier_aliases` | `identifier` (unique), `canonical.international_designator`, `canonical.registration_number`, `canonical.object_class`, `identifier_aliases.norad`, `identifier_aliases.cospar` |
| `registration_documents` | UN registration document metadata | — |
| `observations` | Observational data records (health, mass, thermal, spin) | `norad_id`, `source`, `observation_epoch` |
| `observation_sources` | Observation data source metadata | — |
| `ephemeris_envelopes` | Stored ephemeris envelopes (SGP4 or GMAT RK89) | `norad_id`, `generated_at`, `valid_from`, `valid_until` |
| `kestrel_maneuver_plans` | Kestrel rendezvous maneuver plans | `kestrel_norad_id`, `target_norad_id`, `created_at` |
| `mqtt_configurations` | MQTT broker configurations for TLE publishing | — |
| `fragmentation_events` | DISCOS fragmentation/breakup event records; canonical fields include `epoch`, `altitude`, `latitude`, `longitude`, `eventType`, `comment`; fragment count is computed dynamically from `caused_by` graph edges | — |
| `launch_events` | DISCOS launch event records | — |
| `launch_vehicles` | DISCOS launch vehicle records | — |
| `launch_sites` | DISCOS launch site records | — |
| `entities` | DISCOS operator/country entity records | — |

#### Object Document Structure

Each document in the `objects` collection follows a multi-source canonical model:

```json
{
  "identifier": "1998-067A",
  "canonical": {
    "norad_cat_id": 25544,
    "international_designator": "1998-067A",
    "name": "ISS (ZARYA)",
    "object_class": "Payload",
    "object_type": "PAYLOAD",
    "status": "operational",
    "country_of_origin": "USA",
    "launch_date": "1998-11-20",
    "orbital_band": "LEO"
  },
  "identifier_aliases": {
    "norad": "25544",
    "cospar": "1998-067A",
    "discos": "12345"
  },
  "sources": {
    "unoosa": { ... },
    "celestrak": { ... },
    "discos": { ... }
  },
  "metadata": {
    "sources_available": ["unoosa", "celestrak", "discos"],
    "transformations": [ ... ],
    "attribution_status": "attributed"
  }
}
```

**`object_class` enum values** (set by Spec 1 migration):

| Value | Description |
|-------|-------------|
| `Payload` | Active or inactive spacecraft |
| `Rocket Body` | Launch vehicle upper stages |
| `Mission-Related Object` | Fairings, adapter rings, deployment hardware |
| `Rocket Fragmentation Debris` | Debris attributed to a rocket body |
| `Payload Fragmentation Debris` | Debris attributed to a payload |
| `Unknown` | Unclassified or unattributed debris |

#### Edge Collections

| Collection | From | To | Description |
|-----------|------|----|-------------|
| `constellation_membership` | `objects` | `objects` | Maps a space object to its constellation hub |
| `registration_links` | `objects` | `registration_documents` | Space object ↔ UN registration document |
| `orbital_proximity` | `objects` | `objects` | Objects within ±50 km apogee/perigee, ±5° inclination |
| `collision_risk_edges` | `objects` | `objects` | Computed collision-risk pairs with risk score and min-distance |
| `satellite_lineage` | `objects` | `objects` | Predecessor/successor relationships between satellite generations |
| `observation_satellite_edges` | `observations` | `objects` | Links an observation to the object being tracked |
| `observation_source_edges` | `observations` | `observation_sources` | Links an observation to its reporting source |
| `observation_correlation_edges` | `observations` | `observations` | Correlates observations sharing characteristics (same source, band, etc.) |
| `observation_temporal_edges` | `observations` | `observations` | Sequential chain of observations over time for the same NORAD ID |
| `fragmented_from` | `objects` | `objects` | Fragment → parent object relationship (from DISCOS attributions) |
| `caused_by` | `objects` | `fragmentation_events` | Fragment → fragmentation event that produced it |
| `launched_by` | `objects` | `entities` | Object → operator/country entity |
| `launched_via` | `objects` | `launch_vehicles` | Object → launch vehicle used |
| `launched_from` | `objects` | `launch_sites` | Object → launch site |

#### Named Graphs

**`satellite_relationships`**
- Vertex collections: `objects`, `registration_documents`
- Edge collections: `constellation_membership`, `registration_links`, `orbital_proximity`, `collision_risk_edges`, `satellite_lineage`
- Used for: constellation browsing, registration document graphs, proximity analysis, collision risk network, lineage trees

**`observation_relationships`**
- Vertex collections: `observations`, `objects`, `observation_sources`
- Edge collections: `observation_satellite_edges`, `observation_source_edges`, `observation_correlation_edges`, `observation_temporal_edges`
- Used for: observation neighborhood graphs, source networks, temporal health chains, anomaly correlation

**`provenance_relationships`**
- Vertex collections: `objects`, `fragmentation_events`, `launch_events`, `launch_vehicles`, `launch_sites`, `entities`
- Edge collections: `fragmented_from`, `caused_by`, `launched_by`, `launched_via`, `launched_from`
- Used for: full provenance chain traversal (fragment → event → parent → launch vehicle → operator), sibling fragment discovery, launch event and entity lookups

---

## Configuration

### config.py Structure

```python
class DatabaseConfig:
    HOST: str        # ARANGO_HOST (default: http://localhost:8529)
    USER: str        # ARANGO_USER (default: root)
    PASSWORD: str    # ARANGO_PASSWORD
    DB_NAME: str = "kessler"
    # Collection & graph name constants ...

class CacheConfig:
    TLE_CACHE_TTL: int = 3600      # 1 hour
    DOCUMENT_CACHE_TTL: int = 3600
    MAX_CACHE_SIZE: int = 1000

class APIConfig:
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    CORS_ORIGINS: list              # CORS_ORIGINS (comma-separated)
    IS_SERVERLESS: bool             # Set by VERCEL=1

class ExternalServicesConfig:
    CELESTRAK_BASE_URL: str = "https://celestrak.org/NORAD/elements"
    CELESTRAK_TLE_FILES: list       # stations, resource, sarsat, dmc, weather, geo, iss
    SPACETRACK_BASE_URL: str        # SPACETRACK_USERNAME / SPACETRACK_PASSWORD
    DISCOS_BASE_URL: str            # DISCOS_BASE_URL (default: https://discosweb.esoc.esa.int/api)
    DISCOS_API_TOKEN: str           # DISCOS_API_TOKEN (Bearer token for ESA DISCOSweb v2)
    DISCOS_CACHE_TTL: int = 86400   # DISCOS_CACHE_TTL (default: 24 hours)
    DISCOS_REQUEST_TIMEOUT: int = 30 # DISCOS_REQUEST_TIMEOUT

class OrbitalConstants:
    GM: float = 398600.4418         # Earth gravitational parameter (km³/s²)
    WGS84_EQUATORIAL_RADIUS_KM: float = 6378.137
    EARTH_RADIUS_KM: float = 6371.0 # Legacy, kept for backward compatibility

class AuthConfig:
    USERNAME: str   # APP_USERNAME (default: admin)
    PASSWORD: str   # APP_PASSWORD (required)
    SHANTANU_USERNAME: str  # SHANTANU_USERNAME
    SHANTANU_PASSWORD: str  # SHANTANU_PASSWORD

class AgentConfig:
    OPENAI_API_KEY: str             # OPENAI_API_KEY (required for /v2/ask)
    MODEL: str = "gpt-4o-mini"      # AGENT_MODEL
    VECTOR_STORE_PATH: str = ".chroma"  # AGENT_VECTOR_STORE_PATH
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    RAG_CHUNK_SIZE: int = 1000
    RAG_CHUNK_OVERLAP: int = 200
    RAG_TOP_K: int = 5
    INDEX_SOURCES: list             # Markdown docs to index for RAG
```

### Environment Variables

```bash
# Database
ARANGO_HOST=http://localhost:8529
ARANGO_USER=root
ARANGO_PASSWORD=kessler_dev_password

# API
API_PORT=8000
CORS_ORIGINS=http://localhost:3000

# Authentication
APP_USERNAME=admin
APP_PASSWORD=changeme
SHANTANU_USERNAME=shantanu
SHANTANU_PASSWORD=changeme

# Space-Track (optional TLE fallback)
SPACETRACK_USERNAME=your_email@example.com
SPACETRACK_PASSWORD=your_password

# ESA DISCOSweb (optional — required for DISCOS provenance ingestion)
DISCOS_API_TOKEN=your_discos_bearer_token
DISCOS_BASE_URL=https://discosweb.esoc.esa.int/api
DISCOS_CACHE_TTL=86400
DISCOS_REQUEST_TIMEOUT=30

# LangGraph AI Agents (required for /v2/ask and /v2/aql)
OPENAI_API_KEY=sk-...
AGENT_MODEL=gpt-4o-mini
AGENT_VECTOR_STORE_PATH=.chroma
AGENT_EMBEDDING_MODEL=text-embedding-3-small

# GMAT high-fidelity propagation (optional — required for propagator: "HIFI")
GMAT_HOME=/opt/gmat   # Path to GMAT installation directory

# Caching
TLE_CACHE_TTL=3600
MAX_CACHE_SIZE=1000
```

---

## Testing Strategy

### Test Structure

```
tests/
├── unit/                              # Fast, isolated tests
│   ├── test_cache_service.py          # 14 tests
│   ├── test_orbital_service.py        # 22 tests
│   ├── test_country_normalizer.py     # 15 tests
│   ├── test_gmat_service.py           # GmatService unit tests (mocked subprocess)
│   └── ...
│
├── integration/                       # API + Database tests
│   ├── test_satellite_api.py          # Test /v2/search, /v2/satellite/*
│   ├── test_metadata_api.py           # Test /v2/countries, /v2/stats
│   ├── test_graph_api.py              # Test /v2/graphs/*
│   ├── test_gmat_integration.py       # GMAT ephemeris endpoint integration tests
│   └── ...
│
└── e2e/                               # Full system tests
    └── test_complete_workflow.py      # End-to-end scenarios
```

### Test Coverage Goals

- **Unit tests**: >80% coverage for all services
- **Integration tests**: All API endpoints tested
- **E2E tests**: Critical user workflows

### Running Tests

```bash
# Run all tests
pytest tests/

# Run unit tests only
pytest tests/unit/

# Run with coverage
pytest tests/ --cov=api --cov=database --cov-report=html
```

---

## Performance Characteristics

### Caching Strategy

| Cache Type | TTL | Max Size | Purpose |
|------------|-----|----------|---------|
| TLE Cache | 1 hour | 10,000 entries | CelesTrak TLE data |
| Document Cache | 24 hours | 5,000 entries | UN document metadata |
| Query Cache | 5 minutes | 1,000 entries | Frequent database queries |

### Database Indexes

- **Satellites Collection**: Indexed on `norad_id`, `country`, `status`, `orbital_band`
- **Graph Edges**: Indexed on `_from`, `_to`, `edge_type`

### Expected Performance

- **Satellite search**: <100ms (cached queries), <500ms (database queries)
- **TLE lookup**: <10ms (cache hit), <1000ms (cache miss + API call)
- **Graph traversal**: <200ms (single hop), <1000ms (multi-hop)

---

## Deployment Architecture

### Development
```
localhost:8000 → FastAPI (api/main.py)
localhost:8529 → ArangoDB
localhost:3000 → React Dev Server (Vite)
```

### Production
```
[Load Balancer]
    │
    ├─→ [FastAPI Instance 1] ─┐
    ├─→ [FastAPI Instance 2] ─┼─→ [ArangoDB Cluster]
    └─→ [FastAPI Instance 3] ─┘
    
[CDN] → [Static React App]
```

### Container Strategy

```dockerfile
# API Container
FROM python:3.11-slim
COPY api/ /app/api/
COPY database/ /app/database/
COPY config.py requirements.txt /app/
RUN pip install -r requirements.txt
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Frontend Container
FROM node:20-alpine as builder
COPY react-app/ /app/
RUN npm install && npm run build
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
```

---

## Additional Services

### AgentService (`api/services/agent_service.py`)

**Purpose**: LangGraph-powered conversational AI assistant — serves `POST /v2/ask`

**Architecture**: ReAct agent (`agent → tools → agent` loop) compiled with LangGraph `StateGraph`

**Tools**:
1. `search_knowledge_base` — RAG retrieval over indexed project documentation (ChromaDB)
2. `get_satellite_by_norad_id` — Direct AQL lookup by integer NORAD catalog ID
3. `search_satellites` — Live satellite registry search
4. `run_aql_query` — Read-only AQL queries against ArangoDB (FOR/RETURN only; write keywords blocked)

**Session management**: In-memory `_session_histories` dict keyed by UUID `session_id` enables multi-turn conversation.

**Initialization**: Called once at startup. Requires `OPENAI_API_KEY` — gracefully degrades to unavailable state if missing.

---

### AqlAgentService (`api/services/aql_agent_service.py`)

**Purpose**: Translate natural language into AQL, execute it, and return both the generated query and results — serves `POST /v2/aql`

**Architecture**: Custom `StateGraph` pipeline with four nodes:

```
clarify → ask (END)          # human-in-the-loop: ask user to resolve ambiguity
        → translate → execute → translate (retry ×3) → END
```

**Key behaviours**:
- **Ambiguity detection**: `clarify` node calls the LLM with a focused prompt to detect
  schema ambiguities (e.g. "country" → `country_of_origin` vs registration nation) and
  returns a clarifying question to the client before generating any AQL
- **Deterministic country resolution**: `_annotate_question_with_countries()` maps ~120
  country aliases (ISO 2/3 codes, adjective forms, common names) to exact stored values
  before the LLM sees the question — no LLM judgment involved
- **Live enum injection**: distinct values of `country_of_origin`, `status`, and
  `orbital_band` are fetched from ArangoDB at startup and injected into the system prompt
- **Error-correction loop**: if AQL execution fails, the LLM sees the error and rewrites
  the query (up to 3 attempts)
- **Inline values**: generated AQL uses string literals, not bind variables, so queries
  are self-contained and directly runnable in the AQL Editor UI

**Initialization**: Called once at startup after the DB connection is established (requires
a live DB to fetch enum values). Requires `OPENAI_API_KEY`.

See [`docs/LANGGRAPH_AGENT_ARCHITECTURE.md`](docs/LANGGRAPH_AGENT_ARCHITECTURE.md) for full
details on both agent graphs, LangChain patterns, and extension guidance.

---

### IndexService (`api/services/index_service.py`)

**Purpose**: Build and serve the ChromaDB RAG vector store from project documentation

**Indexed sources** (loaded from repo root at startup):
- `ARCHITECTURE.md`, `DEVELOPER_GUIDE.md`, `API_DOCUMENTATION.md`, `README.md`
- `docs/MULTI_SOURCE_DATA_ARCHITECTURE.md`, `docs/OBSERVATIONS_IMPORT_API.md`, `docs/MONGODB_README.md`

**Behaviour**: If a persisted store exists at `AGENT_VECTOR_STORE_PATH` (`.chroma`), it is loaded; otherwise a new store is built and embedded using `text-embedding-3-small`.

---

### CollisionService (`api/services/collision_service.py`)

Computes pairwise collision risk scores between satellites based on orbital proximity data. Populates `collision_risk_edges`.

---

### LineageService (`api/services/lineage_service.py`)

Traverses the `satellite_lineage` edge collection to build family trees (ancestors/descendants) for a given satellite.

---

### PropagationService (`api/services/propagation_service.py`)

Uses SGP4 (via `sgp4`) and Skyfield to propagate TLE elements forward in time, computing position/velocity state vectors.

---

### GmatService (`api/services/gmat_service.py`)

**Purpose**: High-fidelity orbit propagation using NASA GMAT R2022a as a subprocess.

**Propagator**: Runge-Kutta 89 (RK89) adaptive integrator, accuracy `1e-12`

**Force model**: EGM96 8×8 spherical harmonic gravity field (no atmospheric drag, no solar radiation pressure)

**Key functions**:

| Function | Description |
|----------|-------------|
| `propagate_hifi(line1, line2, duration_hours, step_seconds)` | Main entry point — converts TLE to Keplerian elements, fills the GMAT script template, runs `GmatConsole`, parses the report file, and returns an ephemeris dict |
| `is_available()` | Returns `True` if a usable GMAT binary is found on `PATH` or under `GMAT_HOME/bin` |
| `check_data_files()` | Returns a list of missing required GMAT data files (e.g. `EGM96.cof`) |
| `run_smoke_test()` | Runs a 60-second smoke propagation to verify end-to-end GMAT operation |
| `validate_script(script_text)` | Validates a GMAT script for required keywords and unresolved placeholders |

**TLE → Keplerian conversion** (internal, no GMAT dependency):
- Mean motion (rev/day) → semi-major axis via vis-viva
- Mean anomaly → true anomaly via iterative Kepler equation solver
- Epoch string → UTCGregorian format expected by GMAT

**Script template**: `gmat_scripts/templates/propagation.script` — a parameterized GMAT script with placeholders (`%EPOCH%`, `%SMA_KM%`, etc.) replaced at runtime.

**Return format** (from `propagate_hifi`):

```python
{
    "propagator": "GMAT_RK89_EGM96",
    "tle_epoch": "22 Apr 2026 10:00:00.000",
    "valid_from": "2026-04-22T10:00:00+00:00",
    "valid_until": "2026-04-23T10:00:00+00:00",
    "step_seconds": 60,
    "orbital_period_minutes": 92.7,
    "num_points": 1440,
    "ephemeris_points": [
        {
            "timestamp": "...",
            "eci": {"x_km": ..., "y_km": ..., "z_km": ...},
            "geodetic": {"latitude": ..., "longitude": ..., "altitude_km": ...},
            "propagation_age_minutes": None,
        }
    ],
    "keplerian_elements": {
        "sma_km": ..., "ecc": ..., "inc_deg": ...,
        "raan_deg": ..., "aop_deg": ..., "ta_deg": ...
    },
}
```

**Installation requirements**:
- Set `GMAT_HOME` environment variable (default: `/opt/gmat`)
- GMAT R2022a binary at `$GMAT_HOME/bin/GmatConsole-R2022a` or `GmatConsole`
- `EGM96.cof` gravity file at `$GMAT_HOME/data/gravity/Earth/EGM96.cof`

---

### SpaceTrackService (`api/services/spacetrack_service.py`)

Authenticates with Space-Track.org and fetches historical TLE data as a fallback when CelesTrak does not have a record.

---

### DiscosService (`api/services/discos_service.py`)

**Purpose**: ESA DISCOSweb v2 API client — fetches space object metadata, fragmentation events, launch events, launch vehicles, launch sites, and entities from ESA's DISCOS database.

**Authentication**: Bearer token from `DISCOS_API_TOKEN` env var. All requests include `DiscosWeb-Api-Version: 2` and `Accept: application/vnd.api+json` headers.

**Caching**: All responses are cached for 24 hours by default (`DISCOS_CACHE_TTL`). Cache is stored in-memory with thread-safe access.

**Rate limiting**: 429 responses are retried with exponential backoff (up to 5 retries). When the remaining rate-limit budget (`X-Ratelimit-Remaining`) falls below 5 requests, the service proactively pauses before making the next call.

**Key functions**:

| Function | Description |
|----------|-------------|
| `get_objects(filters)` | Fetch paginated space objects with optional JSON:API filter params |
| `get_object_by_cospar(cospar_id)` | Look up a single object by COSPAR / international designator |
| `get_object_by_discos_id(discos_id)` | Look up a single object by its DISCOS internal ID |
| `get_fragmentation_events(filters)` | Fetch fragmentation/breakup events |
| `get_launch_events(filters)` | Fetch launch events |
| `get_launch_vehicles(filters)` | Fetch launch vehicles |
| `get_launch_sites(filters)` | Fetch launch sites |
| `get_entities(filters)` | Fetch operator/country entities |
| `get_object_attributions(discos_id)` | Fetch fragmentation attributions for an object |
| `health_check()` | Verify connectivity by fetching a single object |
| `clear_cache()` | Clear the in-memory response cache |

**Configuration** (via `ExternalServicesConfig`):
- `DISCOS_BASE_URL`: default `https://discosweb.esoc.esa.int/api`
- `DISCOS_API_TOKEN`: required for any DISCOS API call
- `DISCOS_CACHE_TTL`: default 86400 seconds (24 hours)
- `DISCOS_REQUEST_TIMEOUT`: default 30 seconds

**Population scripts** using this service:
- `scripts/population/ingest_discos_objects.py` — bulk ingest DISCOS object metadata into `objects` collection
- `scripts/population/ingest_discos_launches.py` — ingest launch events into `launch_events` collection
- `scripts/population/ingest_discos_fragmentations.py` — ingest fragmentation events into `fragmentation_events` collection (stores `epoch`, `altitude`, `latitude`, `longitude`, `eventType`, `comment`, `discos_id`; does not map `fragmentCount` or `casualtyRisk`, which are absent from the DISCOS API response)
- `scripts/population/ingest_discos_attributions.py` — create `fragmented_from` and `caused_by` edges
- `scripts/population/ingest_discos_launch_sites.py` — ingest launch sites into `launch_sites` collection
- `scripts/population/ingest_discos_launch_vehicles.py` — ingest launch vehicles into `launch_vehicles` collection
- `scripts/population/ingest_discos_entities.py` — ingest entities into `entities` collection

---

### GmatManeuverService (`api/services/gmat_maneuver_service.py`)

**Purpose**: Kestrel rendezvous maneuver planning — serves `POST /v2/kestrel/maneuver-plan`

**Planning pipeline**:
1. Parse TLE for both the Kestrel spacecraft and the target object
2. Compute analytical Hohmann transfer baseline (ΔV₁, ΔV₂, transfer time, wait time)
3. If `GmatService.is_available()`: run GMAT RK89/EGM96 propagation to produce high-fidelity burn epochs and closest-approach distance
4. Return combined result with `gmat_verified: true/false`

**Output fields**: `dv1_ms`, `dv2_ms`, `dv_total_ms`, `dv_plane_change_ms`, `transfer_time_s`, `wait_time_s`, `total_time_s`, `burn1_epoch`, `burn2_epoch`, `closest_approach_km`, `closest_approach_time`, `kestrel_kep`, `target_kep`

---

### KestrelAgentService (`api/services/kestrel_agent_service.py`)

**Purpose**: LangGraph agent specialized for Kestrel mission planning — called from `POST /v2/kestrel/...`

**Architecture**: ReAct agent with tools for TLE lookup, maneuver computation, and AQL queries. Maintains session state for multi-turn mission planning conversations.

**Initialization**: Called once at startup. Requires `OPENAI_API_KEY`.

---

## Future Enhancements

### Planned Improvements

1. **GraphQL API**: Add GraphQL support alongside REST
2. **Real-time Updates**: WebSocket support for live satellite tracking
3. **Advanced Caching**: Redis for distributed caching across instances
4. **Rate Limiting**: Per-client rate limiting
5. **API Versioning**: v3 with breaking changes

### Scalability Considerations

- **Horizontal Scaling**: Stateless API design allows easy horizontal scaling
- **Caching Layer**: Consider Redis for distributed caching across instances
- **Database Sharding**: Partition satellites by orbital band or region
- **CDN Integration**: Serve TLE data via CDN for global distribution

---

## Conclusion

The refactored architecture provides:

- ✅ **Maintainability**: Small, focused modules (<400 lines each)
- ✅ **Testability**: Comprehensive test suite with >80% coverage
- ✅ **Performance**: Unified caching with LRU eviction
- ✅ **Scalability**: Stateless design ready for horizontal scaling
- ✅ **Developer Experience**: Clear structure, easy to navigate
- ✅ **Reliability**: Reduced code duplication, single source of truth

The codebase is now production-ready and easier to maintain and extend.
