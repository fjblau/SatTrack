# Kessler Developer Guide

Complete guide for developers contributing to the Kessler project.

---

## Table of Contents

1. [Development Setup](#development-setup)
2. [Project Structure](#project-structure)
3. [Coding Standards](#coding-standards)
4. [Adding New Features](#adding-new-features)
5. [Using Services](#using-services)
6. [Database Operations](#database-operations)
7. [Graph Analytics](#graph-analytics)
8. [Testing](#testing)
9. [Deployment](#deployment)
10. [Troubleshooting](#troubleshooting)

---

## Development Setup

### Prerequisites

- **Python**: 3.11 or higher
- **Node.js**: 20 or higher
- **ArangoDB**: 3.11 or higher
- **Git**: For version control

### Initial Setup

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
# .env file

# ArangoDB — host must include scheme (http:// or https://)
ARANGO_HOST=http://localhost:8529
ARANGO_USER=root
ARANGO_PASSWORD=kessler_dev_password

# API server
API_HOST=127.0.0.1
API_PORT=8000
LOG_LEVEL=info
CORS_ORIGINS=http://localhost:3000

# Authentication
APP_USERNAME=admin
APP_PASSWORD=changeme

# TLE caching
TLE_CACHE_TTL=3600
MAX_CACHE_SIZE=1000

# AI agent (required for /v2/ask)
OPENAI_API_KEY=your_openai_api_key
AGENT_MODEL=gpt-4o-mini

# Space-Track (optional TLE fallback)
SPACETRACK_USERNAME=your_email@example.com
SPACETRACK_PASSWORD=your_password
```

### Running the Application

```bash
# Start everything (API + Frontend)
./start.sh

# Or start individually:

# Start API server
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000

# Start frontend dev server
cd react-app
npm run dev
```

### Verify Setup

```bash
# Check API is running
curl http://localhost:8000/v2/stats

# Check frontend is running
open http://localhost:3000
```

---

## Project Structure

```
kessler/
├── api/                        # API layer
│   ├── main.py                 # FastAPI app entry point & lifespan
│   ├── middleware/auth.py       # Bearer-token authentication middleware
│   ├── routers/                # API endpoints (one file per domain)
│   │   ├── auth.py             # POST /v2/auth/login, POST /v2/auth/logout
│   │   ├── satellites.py       # Legacy satellite endpoints (deprecated → use objects.py)
│   │   ├── objects.py          # Space-object lookup (/v2/objects/*)
│   │   ├── provenance.py       # Provenance graph (/v2/provenance/*)
│   │   ├── inference.py        # ML inference stubs (/v2/inference/*)
│   │   ├── metadata.py         # Filter values (countries, statuses, orbital bands)
│   │   ├── graphs.py           # Graph analytics endpoints
│   │   ├── documents.py        # UN document metadata
│   │   ├── tle.py              # TLE retrieval & propagation
│   │   ├── tle_history.py      # Historical TLE archive (/v2/tle-history/*)
│   │   ├── ephemeris.py        # Ephemeris generation & CZML export
│   │   ├── mqtt.py             # MQTT configuration & publishing
│   │   ├── observations.py     # Observation ingestion & analytics
│   │   ├── admin.py            # Admin script runner & GMAT status
│   │   ├── agent.py            # AI assistants (/v2/ask, /v2/aql)
│   │   ├── kestrel.py          # Rendezvous maneuver planning
│   │   ├── insurance.py        # Insurance overlay (/v2/insurance/*)
│   │   ├── customer_tasks.py   # Customer task management (/v2/customer-tasks/*)
│   │   ├── analytics.py        # ML analytics: health, anomaly, maneuver, re-entry (/v2/analytics/*)
│   │   └── docs.py             # HTML documentation viewer (/v2/docs)
│   ├── services/               # Business logic
│   │   ├── cache_service.py    # LRU + TTL caching
│   │   ├── orbital_service.py  # Orbital calculations from TLE
│   │   ├── tle_service.py      # TLE fetching (CelesTrak / Space-Track)
│   │   ├── tle_history_service.py # Historical TLE fetch & caching
│   │   ├── document_service.py # UN document metadata extraction
│   │   ├── collision_service.py # Collision risk computation
│   │   ├── lineage_service.py  # Satellite family-tree traversal
│   │   ├── propagation_service.py # SGP4/Skyfield orbit propagation
│   │   ├── gmat_service.py     # GMAT high-fidelity propagation
│   │   ├── gmat_maneuver_service.py # Kestrel Hohmann + GMAT maneuver planning
│   │   ├── spacetrack_service.py # Space-Track API integration
│   │   ├── discos_service.py   # ESA DISCOSweb v2 API client
│   │   ├── report_service.py   # PDF report generation (ReportLab)
│   │   ├── health_score_service.py # RSO health score (0–100)
│   │   ├── anomaly_detection_service.py # Attitude-anomaly detection
│   │   ├── maneuver_detection_service.py # Maneuver-event extraction
│   │   ├── reentry_estimation_service.py # Re-entry epoch estimation
│   │   ├── rso_summary_service.py # Precomputed RSO summary cache
│   │   ├── similarity_search_service.py  # Orbital-profile similarity search
│   │   ├── index_service.py    # ChromaDB RAG vector store
│   │   ├── agent_service.py    # LangGraph general assistant
│   │   ├── aql_agent_service.py # LangGraph AQL translation agent
│   │   └── kestrel_agent_service.py # LangGraph Kestrel mission agent
│   └── utils/                  # Utilities
│       └── converters.py       # Format converters
│
├── database/                   # Data layer
│   ├── connection.py           # ArangoDB connection & schema init
│   ├── operations.py           # CRUD (objects collection)
│   ├── identifier_operations.py # Alias-based lookups
│   ├── graph_operations.py     # Edge CRUD & index management
│   ├── graph_analytics.py      # AQL graph analytics
│   ├── observation_graph_ops.py # Observation edge creation & traversal
│   ├── ephemeris_ops.py        # Ephemeris envelope CRUD
│   ├── maneuver_plan_ops.py    # Kestrel maneuver plan CRUD
│   ├── customer_task_ops.py    # Customer task state machine
│   ├── tle_history_ops.py      # TLE history storage & queries
│   ├── discos_object_operations.py # DISCOS enrichment & attribution
│   ├── merge_operations.py     # Object de-duplication utilities
│   ├── demo_config.py          # Demo-mode settings (ArangoDB-backed)
│   ├── transformations.py      # Data canonicalization
│   ├── mqtt_config.py          # MQTT config storage
│   ├── data/                   # Static data
│   │   └── country_codes.json  # Country mappings
│   └── utils/                  # Database utilities
│       ├── normalization.py    # Country code normalization
│       └── field_utils.py      # Nested field manipulation
│
├── scripts/                    # Utility scripts
│   ├── import/                 # Data import scripts
│   ├── verification/           # Verification scripts
│   ├── population/             # Graph population scripts
│   └── maintenance/            # Maintenance scripts
│
├── tests/                      # Test suite
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── e2e/                    # End-to-end tests
│
├── react-app/                  # Frontend (React 19 + Vite)
│   └── src/
│       ├── components/         # React components
│       ├── utils/
│       │   ├── apiFetch.js     # Authenticated fetch wrapper
│       │   └── orbitUtils.js   # Client-side orbital utilities
│       └── config/
│           └── constants.js    # API endpoint constants
│
├── config.py                   # Centralized configuration
├── mqtt_publisher.py           # MQTT publishing service
├── mqtt_scheduler.py           # MQTT scheduling service
└── start.sh                    # Startup script (API + frontend)
```

---

## Coding Standards

### Python Style

Follow **PEP 8** with these specifics:

- **Line length**: 100 characters max
- **Indentation**: 4 spaces (no tabs)
- **Imports**: Organized (stdlib, third-party, local)
- **Docstrings**: Google style for functions and classes
- **Type hints**: Use for function signatures

**Example:**

```python
from typing import Optional, Dict, Any
from datetime import datetime

async def search_satellites(
    country: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Search satellites with filters.
    
    Args:
        country: ISO 3166-1 alpha-3 country code
        status: Satellite status (operational, decayed, etc.)
        limit: Maximum number of results
        
    Returns:
        Dictionary with total count and results list
        
    Raises:
        DatabaseError: If database query fails
    """
    # Implementation
    pass
```

### Module Organization

**Routers** (API endpoints):
```python
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

router = APIRouter(prefix="/v2/satellites", tags=["Satellites"])

@router.get("/search")
async def search_satellites(
    country: Optional[str] = None,
    limit: int = 100
):
    """Search satellites with filters."""
    # Call service layer
    pass
```

**Services** (Business logic):
```python
from typing import Optional, Dict, Any

class SatelliteService:
    """Service for satellite operations."""
    
    def __init__(self):
        self.cache = CacheService.get_cache("satellite_cache")
    
    async def search(
        self,
        country: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """Search satellites with filters."""
        # Implementation
        pass
```

**Database** (Data access):
```python
from typing import Optional, List, Dict, Any
from database.connection import get_satellites_collection

async def find_satellites(
    filters: Dict[str, Any],
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Execute database query for satellites."""
    collection = await get_satellites_collection()
    # Execute query
    pass
```

---

## Adding New Features

### Adding a New API Endpoint

**1. Create router function:**

```python
# api/routers/satellites.py

@router.get("/by-launch-year/{year}")
async def get_satellites_by_launch_year(
    year: int,
    limit: int = 100
):
    """Get all satellites launched in a specific year."""
    # Validate year
    if year < 1957 or year > datetime.now().year:
        raise HTTPException(status_code=400, detail="Invalid year")
    
    # Call database
    satellites = await operations.search_satellites(
        launch_year_start=year,
        launch_year_end=year,
        limit=limit
    )
    
    return satellites
```

**2. Add database query (if needed):**

```python
# database/operations.py

async def search_by_launch_year(year: int, limit: int) -> List[Dict]:
    """Search satellites by launch year."""
    collection = await get_satellites_collection()
    
    query = """
    FOR doc IN satellites
        FILTER doc.launch_year == @year
        LIMIT @limit
        RETURN doc
    """
    
    cursor = await collection.aql.execute(
        query,
        bind_vars={"year": year, "limit": limit}
    )
    return await cursor.batch()
```

**3. Write tests:**

```python
# tests/integration/test_launch_year_api.py

import pytest
from httpx import AsyncClient
from api.main import app

@pytest.mark.asyncio
async def test_get_satellites_by_launch_year():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/v2/satellites/by-launch-year/2023")
        
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        
        # Verify all satellites are from 2023
        for sat in data["results"]:
            assert sat["launch_year"] == 2023
```

**4. Update documentation:**

Add endpoint to `API_DOCUMENTATION.md`.

---

### Adding a New Service

**1. Create service class:**

```python
# api/services/collision_service.py

from typing import List, Dict, Any
from api.services.cache_service import CacheService
from api.services.orbital_service import OrbitalService

class CollisionService:
    """Service for collision detection and risk assessment."""
    
    def __init__(self):
        self.cache = CacheService.get_cache("collision_cache", ttl=300)
        self.orbital_service = OrbitalService()
    
    async def calculate_collision_risk(
        self,
        sat1_norad_id: str,
        sat2_norad_id: str
    ) -> Dict[str, Any]:
        """
        Calculate collision risk between two satellites.
        
        Args:
            sat1_norad_id: NORAD ID of first satellite
            sat2_norad_id: NORAD ID of second satellite
            
        Returns:
            Dictionary with risk assessment
        """
        # Check cache
        cache_key = f"{sat1_norad_id}_{sat2_norad_id}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        # Fetch TLE data
        # Calculate orbital positions
        # Assess collision risk
        risk_data = {
            "risk_level": "low",
            "min_distance_km": 150.0,
            "time_of_closest_approach": "2026-02-10T15:30:00Z"
        }
        
        # Cache result
        self.cache.set(cache_key, risk_data)
        
        return risk_data
```

**2. Write unit tests:**

```python
# tests/unit/test_collision_service.py

import pytest
from api.services.collision_service import CollisionService

@pytest.mark.asyncio
async def test_calculate_collision_risk():
    service = CollisionService()
    
    risk = await service.calculate_collision_risk("25544", "25545")
    
    assert "risk_level" in risk
    assert "min_distance_km" in risk
    assert risk["risk_level"] in ["low", "medium", "high"]

@pytest.mark.asyncio
async def test_collision_risk_caching():
    service = CollisionService()
    
    # First call - cache miss
    risk1 = await service.calculate_collision_risk("25544", "25545")
    
    # Second call - cache hit
    risk2 = await service.calculate_collision_risk("25544", "25545")
    
    # Should be identical
    assert risk1 == risk2
    
    # Check cache statistics
    stats = service.cache.get_statistics()
    assert stats["hits"] >= 1
```

---

## Using Services

### CacheService

**Purpose**: Unified caching with TTL and LRU eviction.

**Basic Usage:**

```python
from api.services.cache_service import CacheService

# Get cache instance (singleton per name)
cache = CacheService.get_cache("my_cache", ttl=3600, max_size=1000)

# Set value
cache.set("key1", {"data": "value"})

# Get value
value = cache.get("key1")  # Returns {"data": "value"} or None

# Get or fetch (recommended)
def fetch_data():
    return {"data": "expensive_operation"}

value = cache.get_or_fetch("key1", fetch_func=fetch_data)
# If key exists: returns cached value
# If key missing: calls fetch_func, caches result, returns it

# Clear cache
cache.clear()

# Get statistics
stats = cache.get_statistics()
print(f"Hit rate: {stats['hit_rate']:.2%}")
print(f"Hits: {stats['hits']}, Misses: {stats['misses']}")
```

**Advanced Usage:**

```python
# Multiple named caches
tle_cache = CacheService.get_cache("tle", ttl=3600)
doc_cache = CacheService.get_cache("documents", ttl=86400)

# Different TTLs for different data
tle_cache.set("25544", tle_data)  # Expires in 1 hour
doc_cache.set("A/AC.105/INF/123", doc_data)  # Expires in 24 hours

# Manual eviction
cache.delete("key1")

# Reset statistics
cache.reset_stats()
```

---

### OrbitalService

**Purpose**: Unified orbital calculations from TLE data.

**Basic Usage:**

```python
from api.services.orbital_service import OrbitalService

service = OrbitalService()

# Calculate full orbital parameters
tle_line1 = "1 25544U 98067A   26037.50000000  .00002182  00000-0  41420-4 0  9990"
tle_line2 = "2 25544  51.6400 208.4300 0001390  90.5300 269.5900 15.54225995415956"

params = service.calculate_orbital_parameters(tle_line1, tle_line2)
# Returns:
# {
#   "mean_motion": 15.54,
#   "eccentricity": 0.0001,
#   "inclination": 51.6,
#   "semi_major_axis_km": 6793.0,
#   "orbital_period_minutes": 92.7,
#   "apogee_km": 422.0,
#   "perigee_km": 416.0,
#   "orbital_band": "LEO"
# }
```

**Individual Calculations:**

```python
# Get orbital period from mean motion
period = service.get_orbital_period(mean_motion=15.54)
# Returns: 92.7 (minutes)

# Get semi-major axis from mean motion
sma = service.get_semi_major_axis(mean_motion=15.54)
# Returns: 6793.0 (km)

# Classify orbital band
band = service.classify_orbital_band(altitude_km=500)
# Returns: "LEO"

# Extract epoch from TLE
epoch = service.extract_tle_epoch(tle_line1)
# Returns: datetime object
```

**Complete Orbital State:**

```python
from datetime import datetime

state = service.calculate_orbital_state(
    tle_line1,
    tle_line2,
    timestamp=datetime.now()
)
# Returns full orbital state including position and velocity
```

---

## Database Operations

### Connection Management

```python
from database import connect_arangodb, disconnect_arangodb

# Connect (typically in application startup)
await connect_arangodb()

# Use database
# ...

# Disconnect (typically in application shutdown)
await disconnect_arangodb()
```

### CRUD Operations

**Find by ID:**

```python
from database.operations import find_satellite

satellite = await find_satellite(norad_id="25544")
```

**Search with filters:**

```python
from database.operations import search_satellites

results = await search_satellites(
    country="USA",
    status="operational",
    orbital_band="LEO",
    limit=100
)
```

**Get metadata:**

```python
from database.operations import (
    get_all_countries,
    get_all_statuses,
    get_all_orbital_bands
)

countries = await get_all_countries()
statuses = await get_all_statuses()
bands = await get_all_orbital_bands()
```

### Graph Operations

```python
from database.graph_operations import (
    get_constellation_graph,
    get_registration_document_graph
)

# Get constellation graph
graph = await get_constellation_graph("Starlink")

# Get registration document graph
doc_graph = await get_registration_document_graph("A/AC.105/INF/123")
```

### Custom Queries

```python
from database.connection import get_satellites_collection

async def custom_query():
    collection = await get_satellites_collection()
    
    # AQL query
    query = """
    FOR doc IN satellites
        FILTER doc.launch_year >= @year
        SORT doc.launch_date DESC
        LIMIT @limit
        RETURN {
            norad_id: doc.norad_id,
            name: doc.name,
            launch_date: doc.launch_date
        }
    """
    
    cursor = await collection.aql.execute(
        query,
        bind_vars={"year": 2020, "limit": 100}
    )
    
    return await cursor.batch()
```

---

## Graph Analytics

### Overview

The Kessler application uses ArangoDB's graph database capabilities to perform advanced network analysis on satellite relationships. The graph analytics module provides functions for path finding, centrality analysis, community detection, and multi-dimensional queries.

### Graph Structure

**Node Collections:**
- `satellites` - Satellite documents
- `registration_documents` - UN registration documents

**Edge Collections:**
- `constellation_membership` - Satellite → Constellation
- `registration_links` - Satellite → Registration document
- `orbital_proximity` - Satellite → Satellite (similar orbits)
- `collision_risk_edges` - Satellite → Satellite (collision risks)
- `satellite_lineage` - Satellite → Satellite (predecessor/successor)

### Path Finding

**Find shortest path between satellites:**

```python
from database.graph_analytics import find_shortest_path

path = find_shortest_path(
    from_id="satellites/25544",
    to_id="satellites/48274",
    edge_types=["constellation_membership", "orbital_proximity"],
    max_depth=10
)

if path:
    print(f"Path distance: {path['distance']}")
    print(f"Vertices: {path['vertices']}")
    print(f"Edges: {path['edges']}")
```

**Find all paths:**

```python
from database.graph_analytics import find_all_paths

paths = find_all_paths(
    from_id="satellites/25544",
    to_id="satellites/48274",
    max_depth=5,
    limit=10
)

for i, path in enumerate(paths):
    print(f"Path {i+1}: {path['distance']} hops")
```

### Centrality Analysis

**Degree centrality** - Identifies satellites with most connections:

```python
from database.graph_analytics import calculate_degree_centrality

results = calculate_degree_centrality(
    node_collection="satellites",
    edge_collections=["constellation_membership", "orbital_proximity"],
    limit=100
)

for result in results:
    print(f"{result['satellite']['name']}: degree={result['degree']}")
```

**Betweenness centrality** - Identifies critical bridge satellites:

```python
from database.graph_analytics import calculate_betweenness_centrality

results = calculate_betweenness_centrality(
    node_collection="satellites",
    edge_collections=["constellation_membership", "orbital_proximity"],
    limit=50,
    sample_size=1000
)

for result in results:
    print(f"{result['satellite']['name']}: score={result['score']:.3f}")
```

**Closeness centrality** - Identifies central satellites:

```python
from database.graph_analytics import calculate_closeness_centrality

results = calculate_closeness_centrality(
    node_collection="satellites",
    edge_collections=["constellation_membership"],
    limit=50,
    max_depth=5
)
```

### Collision Risk Analysis

**Get collision risk neighbors:**

```python
from database.graph_analytics import get_collision_risk_neighbors

risks = get_collision_risk_neighbors(
    satellite_id="satellites/25544",
    min_risk_score=0.5
)

for risk in risks:
    print(f"Risk with {risk['target']['name']}: {risk['risk_score']:.2f}")
```

**Analyze collision clusters:**

```python
from database.graph_analytics import analyze_collision_clusters

clusters = analyze_collision_clusters(
    orbital_band="LEO",
    min_cluster_size=3
)

for cluster in clusters:
    print(f"Cluster {cluster['cluster_id']}: {cluster['size']} satellites")
```

### Multi-Dimensional Queries

**Cross-constellation proximity:**

```python
from database.graph_analytics import find_cross_constellation_proximity

results = find_cross_constellation_proximity(
    orbital_band="LEO",
    limit=100
)

for result in results:
    print(f"{result['constellation1']} <-> {result['constellation2']}")
    print(f"  Proximity: {result['proximity_km']:.1f} km")
```

**Country cooperation network:**

```python
from database.graph_analytics import find_country_cooperation_network

network = find_country_cooperation_network(min_connections=2)

for conn in network['connections']:
    print(f"{conn['country1']} <-> {conn['country2']}")
    print(f"  Shared satellites: {conn['shared_satellites']}")
```

**Function-based clusters:**

```python
from database.graph_analytics import find_function_based_clusters

clusters = find_function_based_clusters(
    orbital_band="LEO",
    min_cluster_size=5
)

for cluster in clusters:
    print(f"{cluster['function']}: {len(cluster['satellites'])} satellites")
```

### Community Detection

**Label propagation algorithm:**

```python
from database.graph_analytics import detect_communities

communities = detect_communities(
    algorithm="label_propagation",
    edge_types=["constellation_membership", "orbital_proximity"],
    min_community_size=5
)

print(f"Found {len(communities)} communities")
for comm in communities:
    print(f"Community {comm['community_id']}: {comm['size']} satellites")
```

**Connected components:**

```python
communities = detect_communities(
    algorithm="connected_components",
    edge_types=["orbital_proximity"],
    min_community_size=10
)
```

### Temporal Analysis

**Graph evolution timeline:**

```python
from database.graph_analytics import calculate_graph_evolution_timeline

timeline = calculate_graph_evolution_timeline(
    start_year=2020,
    end_year=2025,
    granularity="year"
)

for entry in timeline:
    print(f"{entry['year']}: {entry['node_count']} satellites")
    print(f"  Density: {entry['density']:.4f}")
    print(f"  Avg degree: {entry['avg_degree']:.2f}")
```

**Graph snapshot:**

```python
from database.graph_analytics import get_graph_snapshot_by_date

snapshot = get_graph_snapshot_by_date(
    date="2023-01-01",
    edge_types=["constellation_membership"]
)

print(f"Nodes: {snapshot['node_count']}")
print(f"Edges: {snapshot['edge_count']}")
```

### Recommendations

**Similar satellites:**

```python
from database.graph_analytics import get_similar_satellites

recommendations = get_similar_satellites(
    satellite_id="satellites/25544",
    limit=10
)

for rec in recommendations:
    print(f"{rec['satellite']['name']}: score={rec['score']:.2f}")
    print(f"  Reason: {rec['reason']}")
```

**Neighbor-based recommendations:**

```python
from database.graph_analytics import get_neighbor_based_recommendations

recommendations = get_neighbor_based_recommendations(
    satellite_id="satellites/25544",
    limit=10
)
```

**Collaborative filtering:**

```python
from database.graph_analytics import get_collaborative_filtering_recommendations

recommendations = get_collaborative_filtering_recommendations(
    satellite_id="satellites/25544",
    limit=10
)
```

### Graph Algorithms Reference

| Algorithm | Purpose | Complexity | Use Case |
|-----------|---------|------------|----------|
| **Shortest Path** | Find shortest path between nodes | O(V+E) | Connection discovery |
| **Degree Centrality** | Count direct connections | O(V) | Identify hubs |
| **Betweenness Centrality** | Measure bridge importance | O(V²E) | Find critical nodes |
| **Closeness Centrality** | Measure average distance | O(VE) | Find central nodes |
| **Label Propagation** | Community detection | O(E) | Cluster detection |
| **Connected Components** | Find isolated subgraphs | O(V+E) | Network segmentation |

### Performance Optimization

**Caching:**

All graph queries use intelligent caching with different TTLs:

```python
from api.services.cache_service import get_cache

# Path queries - 1 hour TTL
path_cache = get_cache("path_queries", ttl=3600, max_size=2000)

# Centrality - 12 hour TTL
centrality_cache = get_cache("centrality_queries", ttl=43200, max_size=500)

# Communities - 12 hour TTL
community_cache = get_cache("community_queries", ttl=43200, max_size=300)
```

**Pre-computing metrics:**

Use the background job for expensive operations:

```bash
# Run precomputation script
python scripts/maintenance/precompute_graph_metrics.py

# Schedule as cron job (daily at 2 AM)
0 2 * * * cd /path/to/kessler && python scripts/maintenance/precompute_graph_metrics.py
```

**Benchmarking:**

Monitor graph query performance:

```bash
# Run benchmarks
python scripts/maintenance/benchmark_graph_queries.py --runs 5

# Check cache statistics
curl http://localhost:8000/v2/graphs/cache/stats/all
```

### Best Practices

**1. Limit graph depth:**
```python
# Good: reasonable depth
path = find_shortest_path(from_id, to_id, max_depth=5)

# Bad: excessive depth
path = find_shortest_path(from_id, to_id, max_depth=100)  # Too slow
```

**2. Use specific edge types:**
```python
# Good: targeted traversal
centrality = calculate_degree_centrality(
    edge_collections=["constellation_membership"]
)

# Less efficient: all edges
centrality = calculate_degree_centrality(
    edge_collections=None  # Uses all edges
)
```

**3. Implement pagination:**
```python
from api.utils.pagination import paginate_results

# Paginate large result sets
paginated = paginate_results(
    results=large_query_results,
    offset=0,
    limit=100
)
```

**4. Monitor cache performance:**
```python
# Check hit rates regularly
stats = cache.get_statistics()
if stats['hit_rate'] < 0.5:
    # Consider increasing cache size or adjusting TTL
    pass
```

**5. Use sampling for expensive algorithms:**
```python
# For large graphs, use sampling
betweenness = calculate_betweenness_centrality(
    sample_size=1000  # Sample 1000 nodes instead of all
)
```

### Common Patterns

**Pattern 1: Path-based analysis**
```python
def analyze_satellite_connections(sat1_id, sat2_id):
    """Find and analyze connections between satellites."""
    path = find_shortest_path(sat1_id, sat2_id, max_depth=5)
    
    if not path:
        return {"connected": False}
    
    return {
        "connected": True,
        "distance": path['distance'],
        "intermediate_nodes": len(path['vertices']) - 2,
        "relationship_types": [e['type'] for e in path['edges']]
    }
```

**Pattern 2: Network importance ranking**
```python
def rank_satellites_by_importance(edge_types, limit=50):
    """Rank satellites by network importance."""
    degree_results = calculate_degree_centrality(
        edge_collections=edge_types,
        limit=limit
    )
    
    betweenness_results = calculate_betweenness_centrality(
        edge_collections=edge_types,
        limit=limit
    )
    
    # Combine scores
    importance_scores = {}
    for result in degree_results:
        sat_id = result['satellite']['norad_id']
        importance_scores[sat_id] = result['score']
    
    for result in betweenness_results:
        sat_id = result['satellite']['norad_id']
        importance_scores[sat_id] += result['score']
    
    return sorted(importance_scores.items(), key=lambda x: x[1], reverse=True)
```

**Pattern 3: Risk assessment**
```python
def assess_satellite_collision_risk(satellite_id):
    """Comprehensive collision risk assessment."""
    risks = get_collision_risk_neighbors(satellite_id, min_risk_score=0.3)
    
    high_risk = [r for r in risks if r['risk_score'] > 0.7]
    medium_risk = [r for r in risks if 0.5 <= r['risk_score'] <= 0.7]
    low_risk = [r for r in risks if r['risk_score'] < 0.5]
    
    return {
        "total_risks": len(risks),
        "high_risk_count": len(high_risk),
        "medium_risk_count": len(medium_risk),
        "low_risk_count": len(low_risk),
        "highest_risk": max(risks, key=lambda x: x['risk_score']) if risks else None
    }
```

---

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test category
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/

# Run specific test file
pytest tests/unit/test_cache_service.py

# Run specific test function
pytest tests/unit/test_cache_service.py::test_basic_get_set

# Run with coverage
pytest tests/ --cov=api --cov=database --cov-report=html

# Run with verbose output
pytest tests/ -v

# Run tests matching pattern
pytest tests/ -k "cache"
```

### Writing Unit Tests

**Test services in isolation:**

```python
# tests/unit/test_my_service.py

import pytest
from api.services.my_service import MyService

@pytest.fixture
def service():
    """Create service instance for testing."""
    return MyService()

def test_basic_operation(service):
    """Test basic service operation."""
    result = service.do_something("input")
    
    assert result == "expected_output"
    assert result is not None

@pytest.mark.asyncio
async def test_async_operation(service):
    """Test async service operation."""
    result = await service.do_something_async("input")
    
    assert result["status"] == "success"
```

### Writing Integration Tests

**Test API endpoints:**

```python
# tests/integration/test_satellite_api.py

import pytest
from httpx import AsyncClient
from api.main import app

@pytest.mark.asyncio
async def test_search_satellites():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/v2/search?country=USA&limit=10")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total" in data
        assert "results" in data
        assert len(data["results"]) <= 10

@pytest.mark.asyncio
async def test_get_satellite_by_id():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/v2/satellite/25544")
        
        assert response.status_code == 200
        satellite = response.json()
        
        assert satellite["norad_id"] == "25544"
        assert "name" in satellite
        assert "orbital_band" in satellite
```

### Test Coverage Goals

- **Unit tests**: >80% coverage for services
- **Integration tests**: All API endpoints covered
- **E2E tests**: Critical user workflows covered

---

## Deployment

### Production Checklist

- [ ] Set strong database password
- [ ] Configure CORS origins (not `*`)
- [ ] Set appropriate cache sizes
- [ ] Enable logging
- [ ] Set up monitoring
- [ ] Configure backup strategy
- [ ] Test disaster recovery

### Environment Variables for Production

```bash
ARANGO_HOST=production.arangodb.com
ARANGO_USER=kessler_api
ARANGO_PASSWORD=strong_password_here

API_PORT=8000
CORS_ORIGINS=https://kessler.space,https://app.kessler.space

TLE_CACHE_TTL=3600
MAX_CACHE_SIZE=50000

LOG_LEVEL=warning
```

### Docker Deployment

```bash
# Build API container
docker build -f Dockerfile.railway -t kessler-api .

# Run API container
docker run -p 8000:8000 --env-file .env kessler-api

# Build frontend container
cd react-app
docker build -t kessler-frontend .
docker run -p 3000:80 kessler-frontend
```

---

## Troubleshooting

### Common Issues

#### Database Connection Failed

**Error**: `RuntimeError: Failed to connect to ArangoDB`

**Solutions**:
1. Verify ArangoDB is running: `curl http://localhost:8529/_api/version`
2. Check credentials in `.env`
3. Verify database exists
4. Check firewall/network settings

---

#### Import Errors

**Error**: `ModuleNotFoundError: No module named 'api'`

**Solutions**:
1. Ensure you're in project root
2. Add project root to Python path:
   ```python
   import sys
   from pathlib import Path
   sys.path.insert(0, str(Path(__file__).parent.parent))
   ```
3. Check virtual environment is activated

---

#### Cache Not Working

**Error**: Cache hit rate is 0%

**Solutions**:
1. Ensure using same cache instance (singleton)
2. Check TTL is not too short
3. Verify cache size is sufficient
4. Check cache statistics: `cache.get_statistics()`

---

#### TLE Data Stale

**Error**: TLE data is outdated

**Solutions**:
1. Check TLE cache TTL (default: 1 hour)
2. Clear TLE cache: `tle_cache.clear()`
3. Verify CelesTrak is accessible
4. Check for rate limiting

---

### Debug Mode

Enable debug logging:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
```

Or set in environment:

```bash
export LOG_LEVEL=debug
```

---

## Best Practices

### Do's ✅

- **Use services for business logic** - Keep routers thin
- **Use CacheService for caching** - Don't create manual caches
- **Use OrbitalService for calculations** - Don't duplicate logic
- **Write tests for new features** - Maintain >80% coverage
- **Use type hints** - Makes code self-documenting
- **Handle errors gracefully** - Return meaningful error messages
- **Document complex logic** - Use docstrings and comments

### Don'ts ❌

- **Don't put business logic in routers** - Use services
- **Don't duplicate code** - Extract to services/utilities
- **Don't hardcode values** - Use config.py
- **Don't skip tests** - Tests prevent regressions
- **Don't ignore error handling** - Handle all edge cases
- **Don't commit secrets** - Use environment variables
- **Don't modify database directly** - Use database/operations.py

---

## Resources

- **FastAPI Documentation**: https://fastapi.tiangolo.com
- **ArangoDB Documentation**: https://www.arangodb.com/docs
- **Pytest Documentation**: https://docs.pytest.org
- **API Documentation**: `API_DOCUMENTATION.md`
- **Migration Guide**: `MIGRATION_GUIDE.md`
- **Architecture**: `ARCHITECTURE.md`

---

## Getting Help

- **Interactive API Docs**: http://localhost:8000/docs
- **Code Examples**: Check `tests/` directory
- **GitHub Issues**: Report bugs or request features
- **Stack Overflow**: Tag with `kessler` and `satellite-tracking`

---

**Last Updated**: February 6, 2026  
**Version**: 2.0.0
