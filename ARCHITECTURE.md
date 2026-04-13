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
│   │   ├── satellites.py        # Satellite search & retrieval
│   │   ├── metadata.py          # Countries, statuses, orbital bands, stats
│   │   ├── graphs.py            # Graph visualization & analytics endpoints
│   │   ├── documents.py         # UN document metadata
│   │   ├── tle.py               # TLE data endpoints & orbit propagation
│   │   ├── mqtt.py              # MQTT configuration & publishing
│   │   ├── observations.py      # Observation import, analytics, graph data
│   │   ├── admin.py             # Admin script execution & run tracking
│   │   └── agent.py             # POST /v2/ask, POST /v2/aql, GET /v2/ask/status (AI agents)
│   ├── services/                # Business logic services
│   │   ├── cache_service.py     # Unified caching with LRU & TTL
│   │   ├── orbital_service.py   # Orbital calculations from TLE
│   │   ├── tle_service.py       # TLE fetching & parsing (CelesTrak / Space-Track)
│   │   ├── document_service.py  # UN document metadata extraction
│   │   ├── collision_service.py # Collision risk computation
│   │   ├── lineage_service.py   # Satellite family-tree traversal
│   │   ├── propagation_service.py # SGP4/Skyfield orbit propagation
│   │   ├── spacetrack_service.py  # Space-Track API integration
│   │   ├── index_service.py     # ChromaDB RAG vector store build & load
│   │   ├── agent_service.py     # LangGraph general assistant (RAG + tools, /v2/ask)
│   │   └── aql_agent_service.py # LangGraph AQL translation agent (/v2/aql)
│   └── utils/
│       └── converters.py        # Format conversion utilities
│
├── database/                    # Data Layer
│   ├── connection.py            # ArangoDB connection, collection & graph init
│   ├── operations.py            # CRUD operations (satellites)
│   ├── graph_operations.py      # Graph edge CRUD & index management
│   ├── graph_analytics.py       # AQL graph analytics (centrality, communities, etc.)
│   ├── observation_graph_ops.py # Observation edge creation & graph traversal
│   ├── transformations.py       # Data canonicalization & transformation
│   ├── mqtt_config.py           # MQTT configuration storage
│   ├── data/
│   │   └── country_codes.json   # ISO 3166-1 alpha-3 mappings
│   └── utils/
│       ├── normalization.py     # Country code normalization
│       └── field_utils.py       # Nested field manipulation utilities
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
│       │   └── apiFetch.js      # Authenticated fetch wrapper
│       └── components/
│           ├── DataTable.jsx    # Satellite data grid
│           ├── DetailPanel.jsx  # Satellite detail view
│           ├── Filters.jsx      # Search filter sidebar
│           ├── GraphExplorer.jsx/GraphViewer.jsx  # Graph visualization
│           ├── TimelineChart.jsx  # Launch timeline
│           ├── ObservationsView.jsx/ObservationGraphs.jsx
│           ├── AqlEditorPage.jsx  # Interactive AQL query editor
│           ├── HelpPage.jsx     # AI assistant chat interface
│           ├── AdminPage.jsx    # Admin script runner
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
│  │  - PropagationService, SpaceTrack    │   │
│  │  - IndexService, AgentService        │   │
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
| `satellites` | Primary satellite registry — all UNOOSA/NORAD records with canonical fields | `identifier` (unique), `canonical.international_designator`, `canonical.registration_number` |
| `registration_documents` | UN registration document metadata | — |
| `observations` | Observational data records (health, mass, thermal, spin) | `norad_id`, `source`, `observation_epoch` |
| `observation_sources` | Observation data source metadata | — |
| `mqtt_configurations` | MQTT broker configurations for TLE publishing | — |

#### Edge Collections

| Collection | From | To | Description |
|-----------|------|----|-------------|
| `constellation_membership` | `satellites` | `satellites` | Maps a satellite to its constellation hub |
| `registration_links` | `satellites` | `registration_documents` | Satellite ↔ UN registration document |
| `orbital_proximity` | `satellites` | `satellites` | Satellites within ±50 km apogee/perigee, ±5° inclination |
| `collision_risk_edges` | `satellites` | `satellites` | Computed collision-risk pairs with risk score and min-distance |
| `satellite_lineage` | `satellites` | `satellites` | Predecessor/successor relationships between satellite generations |
| `observation_satellite_edges` | `observations` | `satellites` | Links an observation to the satellite being tracked |
| `observation_source_edges` | `observations` | `observation_sources` | Links an observation to its reporting source |
| `observation_correlation_edges` | `observations` | `observations` | Correlates observations sharing characteristics (same source, band, etc.) |
| `observation_temporal_edges` | `observations` | `observations` | Sequential chain of observations over time for the same NORAD ID |

#### Named Graphs

**`satellite_relationships`**
- Vertex collections: `satellites`, `registration_documents`
- Edge collections: `constellation_membership`, `registration_links`, `orbital_proximity`, `collision_risk_edges`, `satellite_lineage`
- Used for: constellation browsing, registration document graphs, proximity analysis, collision risk network, lineage trees

**`observation_relationships`**
- Vertex collections: `observations`, `satellites`, `observation_sources`
- Edge collections: `observation_satellite_edges`, `observation_source_edges`, `observation_correlation_edges`, `observation_temporal_edges`
- Used for: observation neighborhood graphs, source networks, temporal health chains, anomaly correlation

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

# LangGraph AI Agents (required for /v2/ask and /v2/aql)
OPENAI_API_KEY=sk-...
AGENT_MODEL=gpt-4o-mini
AGENT_VECTOR_STORE_PATH=.chroma
AGENT_EMBEDDING_MODEL=text-embedding-3-small

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
│   └── ...
│
├── integration/                       # API + Database tests
│   ├── test_satellite_api.py          # Test /v2/search, /v2/satellite/*
│   ├── test_metadata_api.py           # Test /v2/countries, /v2/stats
│   ├── test_graph_api.py              # Test /v2/graphs/*
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

### SpaceTrackService (`api/services/spacetrack_service.py`)

Authenticates with Space-Track.org and fetches historical TLE data as a fallback when CelesTrak does not have a record.

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
