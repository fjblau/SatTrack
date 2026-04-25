# Kessler

> Satellite tracking and orbital debris monitoring application with UNOOSA registry viewer

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19.2+-blue.svg)](https://react.dev/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Overview

Kessler provides a comprehensive satellite tracking system combining:

- **UNOOSA Registry Viewer**: Browse UN satellite registry data
- **Real-time TLE Data**: Live Two-Line Element data from CelesTrak
- **Orbital Calculations**: Real-time orbital parameter calculations
- **Graph Visualization**: Constellation and registration document relationships
- **MQTT Publishing**: Publish satellite telemetry via MQTT

---

## Features

### Core Features

- 🛰️ **Satellite Catalog**: Browse and filter satellites by country, status, orbital band, object type, congestion risk
- 📊 **Orbital Calculations**: Real-time apogee, perigee, period, and orbital band via SGP4/Skyfield
- 🗺️ **Satellite Graphs**: Visualize constellation networks, registration relationships, collision risks, lineage trees
- 📈 **Launch Timeline**: Track satellite launches over time by year and month
- 📡 **TLE Data**: Fresh Two-Line Element data from CelesTrak (with Space-Track fallback)
- 🔔 **MQTT Publishing**: Scheduled TLE publishing to external MQTT brokers
- 🔭 **Observations**: Observational data with health trends, anomaly analysis, source statistics, and graph views
- 📋 **Observation Dashboard**: Multi-domain sensor observations per satellite
- 📉 **Collision Risk Network**: Graph of high-risk orbital proximity pairs
- 🚀 **Kestrel Mission Planner**: Rendezvous maneuver planning with analytical Hohmann baseline and optional GMAT RK89/EGM96 verification; burn epoch computation, ΔV budgets, and closest-approach analysis
- 🌐 **Ephemeris Generation**: SGP4/Skyfield and GMAT high-fidelity ephemeris with CesiumJS CZML export and 3D visualization
- 🤖 **AI Help Assistant**: LangGraph-powered chat that answers questions using RAG + live data tools
- 🔑 **Authentication**: Bearer-token login with demo mode

### Technical Features

- ✅ **Modular Architecture**: Routers → Services → Database separation of concerns
- ✅ **Unified Caching**: LRU cache with TTL for TLE and document data
- ✅ **Two Named Graphs**: `satellite_relationships` and `observation_relationships` in ArangoDB
- ✅ **Three LangGraph Agents**: General RAG assistant, AQL translator, and Kestrel mission planner
- ✅ **GMAT Integration**: Optional high-fidelity RK89/EGM96 propagation; degrades gracefully without GMAT
- ✅ **CesiumJS 3D Visualization**: Orbit and mission visualization via CZML export
- ✅ **In-App Documentation**: Markdown docs served as HTML at `/v2/docs`
- ✅ **Type Safety**: Full type hints and Pydantic models throughout
- ✅ **OpenAPI Docs**: Auto-generated interactive API documentation
- ✅ **Configuration Management**: Environment-based configuration via `config.py`

---

## Quick Start

### Prerequisites

- **Python** 3.11 or higher
- **Node.js** 20 or higher
- **ArangoDB** 3.11 or higher

### Installation

```bash
# Clone repository
git clone https://github.com/your-org/kessler.git
cd kessler

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd react-app
npm install
cd ..

# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env
```

### Environment Configuration

```bash
# Database
ARANGO_HOST=http://localhost:8529
ARANGO_USER=root
ARANGO_PASSWORD=kessler_dev_password

# API
API_PORT=8000
CORS_ORIGINS=http://localhost:3000

# Authentication (required)
APP_USERNAME=admin
APP_PASSWORD=changeme

# LangGraph AI Assistant (required for Help tab)
OPENAI_API_KEY=sk-...
AGENT_MODEL=gpt-4o-mini

# Space-Track (optional TLE fallback)
SPACETRACK_USERNAME=your_email@example.com
SPACETRACK_PASSWORD=your_password

# Caching
TLE_CACHE_TTL=3600
MAX_CACHE_SIZE=1000
```

### Running the Application

```bash
# Start both API and frontend
./start.sh

# Or start individually:

# Start API server
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000

# In-app documentation
# http://localhost:8000/v2/docs

# Start frontend (in separate terminal)
cd react-app
npm run dev
```

### Access the Application

- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **API**: http://localhost:8000

---

## Project Structure

```
kessler/
├── api/                        # API layer
│   ├── main.py                 # FastAPI app entry point & lifespan
│   ├── middleware/auth.py       # Bearer-token authentication middleware
│   ├── routers/                # API endpoints by domain
│   │   ├── auth.py             # Login / logout
│   │   ├── satellites.py       # Satellite search & retrieval
│   │   ├── metadata.py         # Countries, statuses, orbital bands, stats
│   │   ├── graphs.py           # Graph visualization & analytics
│   │   ├── documents.py        # UN document metadata
│   │   ├── tle.py              # TLE data & orbit propagation
│   │   ├── ephemeris.py        # Ephemeris generation (SGP4 + GMAT), CZML export
│   │   ├── mqtt.py             # MQTT configuration & publishing
│   │   ├── observations.py     # Observation import & analytics
│   │   ├── admin.py            # Admin script runner, GMAT status
│   │   ├── agent.py            # AI assistant (/v2/ask), AQL agent (/v2/aql)
│   │   ├── kestrel.py          # Kestrel rendezvous maneuver planning
│   │   └── docs.py             # In-app HTML documentation viewer (/v2/docs)
│   └── services/               # Business logic
│       ├── cache_service.py    # LRU cache with TTL
│       ├── orbital_service.py  # Orbital calculations from TLE
│       ├── tle_service.py      # TLE fetching (CelesTrak / Space-Track)
│       ├── document_service.py # UN document metadata extraction
│       ├── collision_service.py # Collision risk computation
│       ├── lineage_service.py  # Satellite lineage traversal
│       ├── propagation_service.py # SGP4/Skyfield propagation
│       ├── gmat_service.py     # GMAT high-fidelity propagation (RK89 + EGM96)
│       ├── gmat_maneuver_service.py # Kestrel Hohmann + GMAT maneuver planning
│       ├── spacetrack_service.py  # Space-Track API integration
│       ├── index_service.py    # ChromaDB RAG vector store
│       ├── agent_service.py    # LangGraph general assistant (/v2/ask)
│       ├── aql_agent_service.py # LangGraph AQL translation agent (/v2/aql)
│       └── kestrel_agent_service.py # LangGraph Kestrel mission agent
│
├── database/                   # Data layer
│   ├── connection.py           # ArangoDB connection & schema init
│   ├── operations.py           # Satellite CRUD operations
│   ├── graph_operations.py     # Edge CRUD & indexes
│   ├── graph_analytics.py      # AQL analytics (centrality, communities)
│   ├── observation_graph_ops.py # Observation edge creation & traversal
│   ├── ephemeris_ops.py        # Ephemeris envelope storage
│   ├── maneuver_plan_ops.py    # Kestrel maneuver plan storage
│   ├── transformations.py      # Data canonicalization
│   └── mqtt_config.py          # MQTT configuration storage
│
├── scripts/                    # Utility scripts
│   ├── import/                 # Data import scripts
│   ├── verification/           # Data verification scripts
│   ├── population/             # Graph population scripts
│   └── maintenance/            # Data maintenance scripts
│
├── tests/                      # Test suite
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── e2e/                    # End-to-end tests
│
├── react-app/                  # React frontend
│   └── src/
│       ├── components/         # React components
│       │   ├── HelpPage.jsx    # AI assistant chat interface
│       │   ├── AqlEditorPage.jsx # Interactive AQL editor
│       │   ├── AdminPage.jsx   # Admin script runner
│       │   ├── EphemerisPage.jsx # Ephemeris generation & CZML export
│       │   ├── KestrelMissionPage.jsx # Rendezvous mission planning
│       │   ├── KestrelDataPage.jsx # Kestrel satellite data dashboard
│       │   └── ...             # Data, graph, observation, Cesium views
│       ├── utils/apiFetch.js   # Authenticated fetch wrapper
│       ├── utils/orbitUtils.js # Client-side orbital calculation utilities
│       └── config/constants.js # API endpoint constants
│
├── config.py                   # Centralized configuration
├── mqtt_publisher.py           # MQTT publishing service
├── mqtt_scheduler.py           # MQTT scheduling
└── start.sh                    # Startup script
```

---

## API Documentation

### Interactive Documentation

FastAPI provides automatic interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### Quick Examples

```bash
# Login and get token
TOKEN=$(curl -s -X POST "http://localhost:8000/v2/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"changeme"}' | jq -r .token)

# Search satellites
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/v2/search?country=USA&status=operational&limit=10"

# Get satellite by NORAD ID
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/v2/satellite/25544"

# Get TLE data for ISS
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/v2/tle/25544"

# Ask the AI assistant
curl -s -X POST "http://localhost:8000/v2/ask" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question":"What orbital bands does Kessler track?"}'
```

For complete API documentation, see [API_DOCUMENTATION.md](./API_DOCUMENTATION.md).

---

## Development

### Setup Development Environment

```bash
# Install dependencies
pip install -r requirements.txt
cd react-app && npm install && cd ..

# Run tests
pytest tests/

# Run with coverage
pytest tests/ --cov=api --cov=database --cov-report=html

# Start API in development mode (auto-reload)
uvicorn api.main:app --reload

# Start frontend in development mode
cd react-app && npm run dev
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run unit tests only
pytest tests/unit/

# Run specific test file
pytest tests/unit/test_cache_service.py

# Run with verbose output
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=api --cov=database --cov-report=html
open htmlcov/index.html
```

### Code Style

- **Python**: PEP 8 style guide
- **Line length**: 100 characters max
- **Type hints**: Required for function signatures
- **Docstrings**: Google style
- **Tests**: Required for new features (>80% coverage)

### Documentation

- **[ARCHITECTURE.md](./ARCHITECTURE.md)**: System architecture and design
- **[API_DOCUMENTATION.md](./API_DOCUMENTATION.md)**: Complete API reference
- **[DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md)**: Developer handbook
- **[MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md)**: Migration from v1 to v2

---

## Deployment

### Docker Deployment

```bash
# Build API container
docker build -f Dockerfile.railway -t kessler-api .

# Run API container
docker run -p 8000:8000 --env-file .env kessler-api

# Build frontend container
cd react-app
npm run build
docker build -t kessler-frontend .
docker run -p 3000:80 kessler-frontend
```

### Environment Variables (Production)

```bash
# Database
ARANGO_HOST=production.arangodb.com
ARANGO_USER=kessler_api
ARANGO_PASSWORD=strong_password_here

# API
API_PORT=8000
CORS_ORIGINS=https://kessler.space,https://app.kessler.space

# Caching
TLE_CACHE_TTL=3600
MAX_CACHE_SIZE=50000

# Logging
LOG_LEVEL=warning
```

### Production Checklist

- [ ] Set strong database credentials
- [ ] Configure CORS origins (not `*`)
- [ ] Set appropriate cache sizes
- [ ] Enable production logging
- [ ] Set up monitoring and alerts
- [ ] Configure backup strategy
- [ ] Test disaster recovery
- [ ] Enable HTTPS
- [ ] Set up rate limiting

---

## Architecture

### Layered Architecture

```
┌─────────────────────────────┐
│     External Clients        │
│  (React, MQTT, Webhooks)    │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│        API Layer            │
│  Routers → Services         │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│      Database Layer         │
│  Operations, Queries        │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│   External Services         │
│  ArangoDB, CelesTrak        │
└─────────────────────────────┘
```

### Key Services

**CacheService**: Unified caching with TTL and LRU eviction
```python
from api.services.cache_service import CacheService

cache = CacheService.get_cache("my_cache", ttl=3600)
value = cache.get_or_fetch("key", fetch_func=lambda: expensive_operation())
```

**OrbitalService**: Unified orbital calculations
```python
from api.services.orbital_service import OrbitalService

service = OrbitalService()
params = service.calculate_orbital_parameters(tle_line1, tle_line2)
```

**GmatManeuverService**: Kestrel rendezvous maneuver planning
- Computes analytical Hohmann transfer baseline
- Optionally verifies with GMAT RK89/EGM96 high-fidelity propagation
- Returns burn epochs, ΔV budget, and closest-approach distance

For detailed architecture documentation, see [ARCHITECTURE.md](./ARCHITECTURE.md).

---

## Data Sources

- **UNOOSA Registry**: United Nations Office for Outer Space Affairs satellite registry
- **CelesTrak**: Two-Line Element (TLE) data for active satellites
- **Space-Track**: Historical TLE data
- **GCAT (General Catalog)**: Launch and satellite catalog data

---

## Technology Stack

### Backend

- **Python** 3.11+
- **FastAPI**: Modern web framework with automatic OpenAPI docs
- **ArangoDB**: Multi-model database (documents + graphs)
- **Uvicorn**: ASGI server
- **LangGraph / LangChain**: AI agent framework
- **ChromaDB**: Vector store for RAG
- **OpenAI**: LLM provider for the AI assistant
- **SGP4 / Skyfield**: Orbit propagation
- **Paho MQTT**: MQTT broker integration
- **Pytest**: Testing framework

### Frontend

- **React** 19.2+
- **Vite**: Build tool and dev server
- **JavaScript/JSX**: UI components

### Data Processing

- **Pandas**: Data manipulation
- **NumPy**: Numerical calculations
- **Requests**: HTTP client
- **BeautifulSoup**: Web scraping

---

## Performance

### Caching Strategy

| Cache Type | TTL | Max Size | Purpose |
|------------|-----|----------|---------|
| TLE Cache | 1 hour | 10,000 | CelesTrak TLE data |
| Document Cache | 24 hours | 5,000 | UN document metadata |

### Expected Performance

- **Satellite search**: <100ms (cached), <500ms (database)
- **TLE lookup**: <10ms (cache hit), <1000ms (cache miss + API call)
- **Graph traversal**: <200ms (single hop), <1000ms (multi-hop)

### Database Indexes

- **Satellites**: `norad_id`, `country`, `status`, `orbital_band`
- **Graph Edges**: `_from`, `_to`, `edge_type`

---

## Testing

### Test Coverage

- **Total Tests**: 51+ unit tests, 13+ integration tests
- **Coverage**: >80% for services, 100% for critical paths
- **Test Execution**: ~4 seconds

### Test Categories

- **Unit Tests**: Services, utilities, data transformations
- **Integration Tests**: API endpoints, database operations
- **E2E Tests**: Complete user workflows

---

## Metrics

### Before Refactoring (v1)

- ❌ **api.py**: 2,241 lines (monolithic)
- ❌ **db.py**: 1,274 lines (monolithic)
- ❌ **Code duplication**: 3+ places
- ❌ **Test coverage**: <20%
- ❌ **Unorganized**: 40+ scripts in root

### After Refactoring (v2)

- ✅ **API module**: 2,843 lines (organized in routers + services)
- ✅ **Database module**: 1,348 lines (organized by concern)
- ✅ **Code duplication**: Zero
- ✅ **Test coverage**: >80%
- ✅ **Organized**: Scripts grouped by purpose

For detailed metrics, see [REFACTORING_METRICS.md](./REFACTORING_METRICS.md).

---

## Contributing

### How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for your changes
4. Ensure tests pass (`pytest tests/`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Contribution Guidelines

- Write tests for new features (>80% coverage)
- Follow PEP 8 style guide
- Add type hints to function signatures
- Document complex logic with docstrings
- Update documentation for API changes

---

## Troubleshooting

### Common Issues

#### Database Connection Failed

```bash
# Check ArangoDB is running
curl http://localhost:8529/_api/version

# Verify credentials in .env
cat .env | grep ARANGO
```

#### TLE Data Not Updating

```bash
# Clear TLE cache
python -c "from api.services.cache_service import CacheService; CacheService.get_cache('tle_cache').clear()"

# Check CelesTrak is accessible
curl https://celestrak.org/NORAD/elements/gp.php?CATNR=25544
```

#### Import Errors

```bash
# Ensure you're in project root
pwd

# Add project root to Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

For more troubleshooting, see [DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md#troubleshooting).

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- **UNOOSA**: United Nations Office for Outer Space Affairs for satellite registry data
- **CelesTrak**: Dr. T.S. Kelso for TLE data
- **Space-Track**: US Space Force for historical TLE data
- **Jonathan McDowell**: General Catalog (GCAT) data

---

## Links

- **Documentation**: [docs/](./docs/)
- **API Reference**: [API_DOCUMENTATION.md](./API_DOCUMENTATION.md)
- **Architecture**: [ARCHITECTURE.md](./ARCHITECTURE.md)
- **Developer Guide**: [DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md)
- **Migration Guide**: [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md)
- **Interactive API Docs**: http://localhost:8000/docs (when running)

---

## Contact

- **Issues**: [GitHub Issues](https://github.com/your-org/kessler/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/kessler/discussions)
- **Email**: kessler@example.com

---

**Built with ❤️ for the space community**
