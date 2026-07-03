---
description: Repository Information Overview
alwaysApply: true
---

# Kessler Repository Information

## Summary
Kessler is a satellite tracking and orbital debris monitoring application providing a UNOOSA (United Nations Office for Outer Space Affairs) satellite registry viewer, Kestrel rendezvous mission planner, ephemeris generation, and AI-powered assistance. The project uses a modular Python FastAPI backend backed by ArangoDB (multi-model document + graph database), with a React frontend for interactive visualization, filtering, and mission planning.

## Repository Structure

### Main Components
- **api/**: Modular FastAPI backend — routers, services, middleware
- **database/**: ArangoDB data layer — connection, CRUD, graph analytics, MQTT config
- **react-app/**: React frontend application with Vite build tool
- **scripts/**: Organized utility scripts (import, verification, population, maintenance)
- **gmat_scripts/**: GMAT script templates and ephemeris output
- **config.py**: Centralized environment-aware configuration
- **mqtt_publisher.py / mqtt_scheduler.py**: MQTT TLE publishing services

### Directory Layout
```
root/
├── api/                          # FastAPI backend
│   ├── main.py                   # FastAPI app entry point & lifespan
│   ├── middleware/auth.py         # Bearer-token authentication middleware
│   ├── routers/                  # API endpoints by domain
│   │   ├── auth.py               # POST /v2/auth/login, POST /v2/auth/logout
│   │   ├── satellites.py         # Satellite search & retrieval (legacy /v2/satellite/* — deprecated)
│   │   ├── objects.py            # Space-object lookup by NORAD/COSPAR/alias (/v2/objects/*)
│   │   ├── provenance.py         # Provenance graph traversal (/v2/provenance/*)
│   │   ├── inference.py          # ML inference stubs (/v2/inference/*; not yet implemented)
│   │   ├── metadata.py           # Countries, statuses, orbital bands, stats
│   │   ├── graphs.py             # Graph visualization & analytics
│   │   ├── documents.py          # UN document metadata
│   │   ├── tle.py                # TLE data & orbit propagation
│   │   ├── tle_history.py        # Historical TLE storage & position lookup (/v2/tle-history/*)
│   │   ├── ephemeris.py          # Ephemeris generation (SGP4 + GMAT HIFI), CZML export
│   │   ├── mqtt.py               # MQTT configuration & publishing
│   │   ├── observations.py       # Observation import, analytics, graph data
│   │   ├── admin.py              # Admin script execution, run tracking, GMAT status
│   │   ├── agent.py              # POST /v2/ask, POST /v2/aql, GET /v2/ask/status (AI agents)
│   │   ├── kestrel.py            # Kestrel rendezvous maneuver planning
│   │   ├── insurance.py          # Insurance overlay APIs (/v2/insurance/*)
│   │   ├── customer_tasks.py     # Customer task management (/v2/customer-tasks/*)
│   │   ├── analytics.py          # ML-powered RSO analytics: health, anomaly, maneuver, re-entry (/v2/analytics/*)
│   │   └── docs.py               # In-app HTML documentation viewer (/v2/docs)
│   └── services/                 # Business logic
│       ├── cache_service.py      # LRU cache with TTL
│       ├── orbital_service.py    # Orbital calculations from TLE
│       ├── tle_service.py        # TLE fetching (CelesTrak / Space-Track)
│       ├── tle_history_service.py # Historical TLE fetch & caching (Space-Track bulk requests)
│       ├── document_service.py   # UN document metadata extraction
│       ├── collision_service.py  # Collision risk computation
│       ├── lineage_service.py    # Satellite lineage traversal
│       ├── propagation_service.py # SGP4/Skyfield orbit propagation
│       ├── gmat_service.py       # GMAT high-fidelity propagation (RK89 + EGM96)
│       ├── gmat_maneuver_service.py # Kestrel Hohmann + GMAT maneuver planning
│       ├── spacetrack_service.py  # Space-Track API integration
│       ├── discos_service.py     # ESA DISCOSweb v2 API client (objects, launches, fragmentations, entities)
│       ├── report_service.py     # ReportLab PDF generation (observation reports, evidence packages)
│       ├── health_score_service.py # Calibrated RSO health score (0–100) from TLE BSTAR/perigee/eccentricity
│       ├── anomaly_detection_service.py # Attitude-anomaly detection and severity scoring from TLE history
│       ├── maneuver_detection_service.py # Maneuver-event extraction from TLE history delta-v series
│       ├── reentry_estimation_service.py # Re-entry epoch estimation from perigee decay series
│       ├── rso_summary_service.py # Precomputed per-object RSO summary cache (rso_summary collection)
│       ├── similarity_search_service.py  # Orbital-profile similarity search across the objects catalog
│       ├── index_service.py      # ChromaDB RAG vector store build & load
│       ├── agent_service.py      # LangGraph general assistant (/v2/ask)
│       ├── aql_agent_service.py  # LangGraph AQL translation agent (/v2/aql)
│       └── kestrel_agent_service.py # LangGraph Kestrel mission agent
│
├── database/                     # Data layer
│   ├── connection.py             # ArangoDB connection & schema init (all collections & named graphs)
│   ├── operations.py             # CRUD operations (objects collection)
│   ├── identifier_operations.py  # Alias-based lookups (norad, cospar, discos, vimpel, kestrel)
│   ├── graph_operations.py       # Edge CRUD & index management
│   ├── graph_analytics.py        # AQL analytics (centrality, communities)
│   ├── observation_graph_ops.py  # Observation edge creation & traversal
│   ├── ephemeris_ops.py          # Ephemeris envelope storage
│   ├── maneuver_plan_ops.py      # Kestrel maneuver plan storage
│   ├── customer_task_ops.py      # Customer task state machine, transitions, allowed-state map
│   ├── tle_history_ops.py        # TLE history storage, coverage queries, nearest-TLE lookup
│   ├── discos_object_operations.py # DISCOS object enrichment, surrogate cleanup, attribution ingest
│   ├── merge_operations.py       # Object de-duplication and merge utilities
│   ├── demo_config.py            # Demo-mode app_settings (tab/subtab visibility) stored in ArangoDB
│   ├── transformations.py        # Data canonicalization
│   ├── mqtt_config.py            # MQTT configuration storage
│   ├── data/country_codes.json   # ISO 3166-1 alpha-3 mappings
│   └── utils/
│       ├── normalization.py      # Country code normalization
│       └── field_utils.py        # Nested field manipulation utilities
│
├── react-app/                    # React frontend application
│   ├── src/
│   │   ├── App.jsx               # Root component — navigation & routing
│   │   ├── components/           # React components (see Frontend section)
│   │   ├── utils/
│   │   │   ├── apiFetch.js       # Authenticated fetch wrapper
│   │   │   └── orbitUtils.js     # Orbital calculation utilities (client-side)
│   │   └── config/constants.js   # API endpoint constants
│   ├── package.json
│   ├── vite.config.js
│   └── index.html
│
├── gmat_scripts/                 # GMAT propagation
│   ├── templates/propagation.script  # Parameterized GMAT script
│   └── output/                   # Ephemeris output files (transient)
│
├── scripts/
│   ├── import/                   # Data import scripts
│   ├── verification/             # Data verification scripts
│   ├── population/               # Graph population scripts
│   └── maintenance/              # Data maintenance scripts
│
├── tests/                        # Test suite
│   ├── unit/                     # Unit tests
│   ├── integration/              # Integration tests
│   └── e2e/                      # End-to-end tests
│
├── config.py                     # Centralized configuration
├── mqtt_publisher.py             # MQTT publishing service
├── mqtt_scheduler.py             # MQTT scheduling
└── start.sh                      # Startup script (both services)
```

## Backend (Python FastAPI)

### Language & Runtime
**Language**: Python  
**Version**: Python 3.11+  
**Runtime**: uvicorn (ASGI server)  
**Entry Point**: `api/main.py` → `api.main:app`  
**Port**: 127.0.0.1:8000

### Main Dependencies
- **fastapi**: Web framework and API routing
- **python-arango**: ArangoDB client
- **pandas**: Data manipulation and CSV handling
- **numpy**: Numerical operations
- **requests**: HTTP client for fetching TLE data
- **sgp4, skyfield**: Orbit propagation
- **langgraph, langchain-openai, langchain-chroma**: AI agent framework and RAG
- **chromadb**: Vector store for RAG
- **paho-mqtt, apscheduler**: MQTT publishing and scheduling
- **pdfplumber**: PDF parsing for document extraction
- **czml3**: CZML (Cesium) export for ephemeris visualization
- **uvicorn**: ASGI application server
- **python-dotenv**: Environment variable management

### Application Structure
- **Entry Point**: `api/main.py` — lifespan initializes DB, MQTT, AI index, agents, and TLE cache warmup
- **Routing**: Modular routers for each domain under `/v2/` prefix
- **Authentication**: Bearer-token middleware (`api/middleware/auth.py`), demo mode supported
- **TLE Caching**: `CacheService` LRU + TTL cache, 1-hour TTL, warmed on startup
- **AI Agents**: LangGraph ReAct agents — general assistant, AQL translator, and Kestrel mission planner
- **GMAT Integration**: Optional high-fidelity propagation (RK89 + EGM96); degrades gracefully if GMAT not installed
- **Database**: ArangoDB (`kessler` database)
- **CORS**: Configurable via `CORS_ORIGINS` environment variable (default: `http://localhost:3000`)

### Build & Installation
```bash
# Install dependencies (requires pip)
pip install -r requirements.txt

# Run the API server
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

## Frontend (React + Vite)

### Language & Runtime
**Language**: JavaScript/JSX  
**Runtime**: Node.js 20+  
**Framework**: React 19.2.3  
**Build Tool**: Vite 7.2.7  
**Port**: localhost:3000

### Main Dependencies
- **react / react-dom**: UI framework
- **vite / @vitejs/plugin-react**: Build tool and dev server
- **cytoscape / cytoscape-cola**: Graph visualization

### Application Structure
- **Entry Point**: `src/main.jsx`
- **Root Component**: `src/App.jsx`
- **Navigation**: Top-level tabs with sub-navigation where applicable:
  - **Satellite Catalog** (sub-tabs: Satellite Catalog, Satellite Graphs, Function Similarity, Registration Docs, Timeline)
  - **Observations** (non-demo; sub-tabs: Observations, Observation Graphs, Observation Dashboard)
  - **Admin**
  - **AQL Editor** (non-demo)
  - **Ephemeris** (non-demo)
  - **Kestrel Mission**
  - **Kestrel Data**
  - **? Help**

### Components
- `Filters.jsx`: Filter UI for satellite search
- `DataTable.jsx`: Satellite data grid
- `DetailPanel.jsx`: Detailed satellite information panel
- `GraphExplorer.jsx`: Satellite graph visualization (Satellite Graphs sub-tab)
- `GraphViewer.jsx`: Advanced graph viewer (used within GraphExplorer)
- `TimelineChart.jsx`: Launch timeline by year (Timeline sub-tab)
- `FunctionAnalytics.jsx`: Function similarity analytics
- `RegistrationDocumentAnalytics.jsx`: Registration document statistics
- `ObservationsView.jsx`: Observational data list and filtering
- `ObservationGraphs.jsx`: Health trends, anomaly analysis, source statistics, graph views
- `ObservationDashboard.jsx`: Multi-domain sensor observations per satellite
- `EphemerisPage.jsx`: SGP4/GMAT ephemeris generation and CZML export
- `KestrelMissionPage.jsx`: Kestrel rendezvous mission planning (maneuver ΔV, burn epochs, proximity analysis)
- `KestrelDataPage.jsx`: Kestrel satellite data dashboard
- `KestrelCesiumViewer.jsx`: CesiumJS orbit visualization for Kestrel missions
- `KestrelDataGlobe.jsx`: 3D globe visualization for Kestrel data
- `KestrelDataDials.jsx`: Real-time telemetry dials for Kestrel
- `CesiumViewer.jsx`: General-purpose CesiumJS 3D viewer
- `CentralityView.jsx`: Graph centrality analysis visualization
- `CollisionRiskView.jsx`: Collision risk network visualization
- `ConstellationBrowser.jsx`: Constellation membership browser
- `SatelliteNeighborhood.jsx`: Per-satellite neighborhood graph
- `EvolutionTimelineView.jsx`: Satellite lineage/evolution timeline
- `PathFinderPanel.jsx`: Graph shortest-path finder
- `OrbitCalculationModal.jsx`: On-demand orbital parameter calculation
- `ObservationsModal.jsx`: Observation detail modal
- `ObservationsFilters.jsx`: Observation-specific filter controls
- `DataRecordModal.jsx`: Raw record viewer
- `AqlEditorPage.jsx`: Interactive AQL query editor
- `AdminPage.jsx`: Admin script runner
- `HelpPage.jsx`: LangGraph AI-powered help assistant
- `LoginPage.jsx`: Authentication (username/password → Bearer token)

### Build & Installation
```bash
cd react-app
npm install
npm run dev        # Development server
npm run build      # Production build
npm run preview    # Preview production build
```

### Vite Configuration
- Dev server on port 3000
- API proxy: `/api` → `http://127.0.0.1:8000`
- React plugin enabled for JSX support

## Database (ArangoDB)

### Connection
- **Host**: `ARANGO_HOST` env var (default: `http://localhost:8529`)
- **Database**: `kessler`
- **Backward compatibility**: `connect_mongodb()` / `disconnect_mongodb()` are aliases for `connect_arangodb()` / `disconnect_arangodb()`

### Vertex Collections
| Collection | Description |
|---|---|
| `objects` | Primary space-object registry (UNOOSA + NORAD + DISCOS); `satellites` is a legacy alias |
| `registration_documents` | UN registration document metadata |
| `observations` | Observational data records (health, mass, thermal, spin) |
| `observation_sources` | Observation data source metadata |
| `ephemeris_envelopes` | Stored ephemeris envelopes (SGP4 / GMAT) |
| `kestrel_maneuver_plans` | Kestrel rendezvous maneuver plans |
| `mqtt_configurations` | MQTT broker configurations |
| `tle_history` | Per-NORAD historical TLE archive (epoch, line1, line2) |
| `tle_history_coverage` | Coverage metadata per NORAD ID (date ranges fetched) |
| `rso_summary` | Precomputed ML summary per NORAD ID (health, anomaly, maneuver, re-entry) |
| `fragmentation_events` | Fragmentation/breakup event records (from DISCOS) |
| `entities` | Launch entities (operators, manufacturers) from DISCOS |
| `launch_events` | Individual launch records |
| `launch_vehicles` | Launch vehicle definitions |
| `launch_sites` | Launch site definitions |
| `parties` | Insurance parties (operators, underwriters) |
| `policies` | Insurance policies |
| `insured_interests` | Insured interest records per satellite |
| `loss_events` | Loss event records |
| `claims` | Insurance claims |
| `risk_scores` | Per-satellite risk score records |
| `anomaly_predictions` | ML-predicted anomaly records |
| `shells` | Orbital-shell definitions (insurance exposure bucketing) |
| `kestrels` | Kestrel surveillance satellites |
| `kestrel_tasks` | Kestrel observation tasks |
| `coverage_windows` | Computed coverage windows (Kestrel → target) |
| `customer_tasks` | Customer-contracted observation tasks |
| `customer_task_transitions` | State-machine transition log per customer task |
| `task_deliverables` | Deliverable artefacts produced by customer tasks |
| `task_sla_alerts` | SLA breach alert records per customer task |
| `app_settings` | Application-level settings (e.g. demo-mode tab visibility) |

### Edge Collections & Named Graphs
**`satellite_relationships`** graph:
- `constellation_membership` — satellite → constellation hub
- `registration_links` — satellite → UN registration document
- `orbital_proximity` — satellites within ±50 km apogee/perigee, ±5° inclination
- `collision_risk_edges` — computed collision-risk pairs with risk score
- `satellite_lineage` — predecessor/successor satellite generations

**`observation_relationships`** graph:
- `observation_satellite_edges` — observation → satellite
- `observation_source_edges` — observation → source
- `observation_correlation_edges` — correlated observations
- `observation_temporal_edges` — sequential observation chain per NORAD ID

**`provenance_relationships`** graph:
- `fragmented_from` — object → fragmentation event
- `caused_by` — fragmentation event → parent object
- `launched_by` — object → launch entity
- `launched_via` — object → launch vehicle
- `launched_from` — object → launch site

**`insurance`** graph:
- `policy_covers_satellite` — policy → satellite
- `policy_has_interest` — policy → insured interest
- `interest_held_by` — insured interest → party
- `claim_arises_from` — claim → loss event
- `loss_event_involves` — loss event → satellite
- `satellite_in_shell` — satellite → orbital shell
- `risk_score_for` — risk score → satellite
- `prediction_for` — anomaly prediction → satellite
- `kestrel_observed` — Kestrel task → observed satellite
- `kestrel_can_see` — Kestrel satellite → coverage window
- `task_targets` — Kestrel task → target satellite
- `event_witnessed_by` — loss event → Kestrel satellite

**Customer-task edges** (flat collections, not a named graph):
- `task_requested_by` — customer task → requesting party
- `task_targets_object` — customer task → target space object
- `task_relates_to_policy` — customer task → insurance policy
- `task_relates_to_loss_event` — customer task → loss event
- `task_produced_deliverable` — customer task → deliverable

## Configuration (`config.py`)
```
ARANGO_HOST          → ArangoDB host URL
ARANGO_USER          → ArangoDB username
ARANGO_PASSWORD      → ArangoDB password
API_PORT             → API server port (default: 8000)
CORS_ORIGINS         → Comma-separated allowed origins
APP_USERNAME         → Login username
APP_PASSWORD         → Login password
OPENAI_API_KEY       → OpenAI API key (required for AI assistant)
AGENT_MODEL          → LLM model for agents (default: gpt-4o-mini)
SPACETRACK_USERNAME  → Space-Track login email (optional TLE fallback)
SPACETRACK_PASSWORD  → Space-Track login password
TLE_CACHE_TTL        → TLE cache time-to-live in seconds (default: 3600)
MAX_CACHE_SIZE       → Maximum cache entries (default: 1000)
```

## Git Workflow Rules

**CRITICAL — check before every commit or push:**

1. **Never push to a merged PR's branch.** Before committing or pushing, always verify the current branch's PR is still open:
   ```bash
   gh pr view --json state --head $(git branch --show-current)
   ```
   If `state` is `"MERGED"`, **stop**. Create a new branch from `main` for any further changes.

2. **One logical change = one branch = one PR.** If a task produces follow-up changes (e.g. registering a new script in the Admin page after writing the script), those follow-up changes go on their own branch and their own PR — not appended to an already-created or merged PR.

3. **New branch workflow:**
   ```bash
   git fetch origin main
   git checkout -b fix/descriptive-name origin/main
   # make changes, commit
   git push -u origin fix/descriptive-name
   gh pr create --base main --head fix/descriptive-name ...
   ```

### Adding a New Maintenance/Migration Script

Every script added under `scripts/` **must** also be registered in `SCRIPT_CATALOGUE` in `api/routers/admin.py` so it is runnable from the Admin UI. Do this in the **same PR** as the script itself — not a separate follow-up PR.

Required fields per entry:
```python
{
    "id":                 "<script_filename_without_.py>",
    "name":               "<Human-readable name>",
    "description":        "<One-sentence description of what it does and safety notes>",
    "category":           "maintenance" | "migration" | "import" | "verification",
    "path":               "scripts/<subdir>/<filename>.py",
    "order_hint":         <int>,
    "depends_on":         ["<other_script_id>", ...],
    "estimated_duration": "<human string>",
    "reversibility":      "reversible" | "irreversible" | "read-only",
}
```

### Script Performance — Batch Operations Required

When writing any maintenance, load, or update script that touches multiple records, **always use batch operations**. Never process records one at a time in a Python loop when the database can do the work in bulk.

**ArangoDB — prefer AQL `FOR … UPDATE` over Python loops:**
```python
# WRONG — one round-trip per document
for doc in docs:
    col.update({"_key": doc["_key"], "canonical": {...}})

# RIGHT — single AQL statement updates all matching documents at once
db.aql.execute("""
    FOR doc IN @@col
        FILTER <condition>
        UPDATE doc WITH { canonical: MERGE(doc.canonical, @patch) } IN @@col
""", bind_vars={"@col": COL, "patch": {...}})
```

**Python-arango bulk inserts:**
```python
# WRONG — one insert per document
for doc in docs:
    col.insert(doc)

# RIGHT — single call for the whole batch
col.insert_many(docs, return_new=False)
```

**Edge creation:** build the full list of edge dicts in memory first, then call `col.insert_many(edges, overwrite_mode="replace")` once.

**When a per-document loop is unavoidable** (e.g. logic that genuinely can't be expressed in AQL), process in chunks of 500–1000 and print progress after each chunk.

## Project Operations

### Starting Both Services
```bash
# From repository root
./start.sh
```

Starts:
- FastAPI backend on http://127.0.0.1:8000
- React dev server on http://localhost:3000
- API documentation at http://127.0.0.1:8000/docs
- In-app documentation viewer at http://127.0.0.1:8000/v2/docs

### Running Tests
```bash
pytest tests/
pytest tests/unit/
pytest tests/ --cov=api --cov=database --cov-report=html
```

## Architecture Notes
- **Layered Architecture**: Routers → Services → Database, with no circular dependencies
- **Database**: ArangoDB multi-model (documents + named graphs + AQL queries)
- **AI Agents**: Three LangGraph agents — general RAG assistant, AQL translator, Kestrel mission planner
- **Kestrel**: Analytical Hohmann baseline maneuver planning, optionally verified by GMAT high-fidelity propagation
- **Ephemeris**: SGP4-based propagation via Skyfield, with optional GMAT RK89+EGM96 high-fidelity track; exportable as CZML for CesiumJS
- **GMAT Integration**: Optional — degrades gracefully when GMAT is not installed
- **Frontend**: CesiumJS integration for 3D orbit visualization (Kestrel mission and ephemeris views)
- **CORS**: Configurable (defaults to localhost:3000 for development)
