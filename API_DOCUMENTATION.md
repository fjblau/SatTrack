# Kessler API Documentation

Complete API reference for the Kessler satellite tracking application.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Authentication](#authentication)
3. [Endpoints](#endpoints)
   - [Auth](#auth)
   - [Satellites](#satellites)
   - [Metadata](#metadata)
   - [Graphs](#graphs)
   - [Documents](#documents)
   - [TLE Data](#tle-data)
   - [Ephemeris](#ephemeris)
   - [MQTT Configuration](#mqtt-configuration)
   - [Observations](#observations)
   - [Admin](#admin)
   - [AI Assistant (Agent)](#ai-assistant-agent)
   - [AQL Translation Agent](#aql-translation-agent)
4. [Response Formats](#response-formats)
5. [Error Handling](#error-handling)
6. [Rate Limiting](#rate-limiting)
7. [Examples](#examples)

---

## Getting Started

### Base URL

```
http://localhost:8000  # Development
https://api.kessler.space  # Production
```

### Interactive Documentation

FastAPI provides automatic interactive API documentation:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

### Quick Example

```bash
# Search for all operational US satellites
curl "http://localhost:8000/v2/search?country=USA&status=operational"

# Get satellite by NORAD ID
curl "http://localhost:8000/v2/satellite/25544"

# Get TLE data for ISS
curl "http://localhost:8000/v2/tle/25544"
```

---

## Authentication

All endpoints (except `POST /v2/auth/login`) require a **Bearer token** in the `Authorization` header:

```
Authorization: Bearer <token>
```

Tokens are obtained via `POST /v2/auth/login` and are valid for the lifetime of the server process (in-memory store). Demo mode tokens have read-only access and do not expose observation or AQL editor features.

---

## Endpoints

### Auth

#### Login

```http
POST /v2/auth/login
```

**Request Body:**

```json
{ "username": "admin", "password": "changeme" }
```

Use `username: "demo"` / `password: "demo"` for restricted demo access.

**Response:**

```json
{ "token": "abc123...", "is_demo": false }
```

---

#### Logout

```http
POST /v2/auth/logout
```

**Request Body:**

```json
{ "token": "abc123..." }
```

**Response:**

```json
{ "detail": "Logged out" }
```

---

### Satellites

#### Search Satellites

```http
GET /v2/search
```

Search and filter satellites from the registry.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `country` | string | No | Filter by country code (ISO 3166-1 alpha-3) |
| `status` | string | No | Filter by status (operational, decayed, etc.) |
| `orbital_band` | string | No | Filter by orbital band (LEO, MEO, GEO, HEO) |
| `congestion_risk` | string | No | Filter by congestion risk level |
| `constellation` | string | No | Filter by constellation name |
| `launch_year_start` | integer | No | Filter by launch year (start range) |
| `launch_year_end` | integer | No | Filter by launch year (end range) |
| `skip` | integer | No | Number of results to skip (pagination) |
| `limit` | integer | No | Maximum results to return (default: 100, max: 1000) |
| `sort_by` | string | No | Sort field (launch_date, name, norad_id) |
| `sort_order` | string | No | Sort order (asc, desc) |

**Response:**

```json
{
  "total": 1234,
  "skip": 0,
  "limit": 100,
  "results": [
    {
      "_key": "25544",
      "norad_id": "25544",
      "name": "ISS (ZARYA)",
      "country": "USA",
      "status": "operational",
      "launch_date": "1998-11-20",
      "orbital_band": "LEO",
      "constellation": "ISS",
      "tle": {
        "line1": "1 25544U 98067A   ...",
        "line2": "2 25544  51.6...",
        "epoch": "2026-02-06T12:00:00Z"
      },
      "orbital_parameters": {
        "semi_major_axis_km": 6793.0,
        "eccentricity": 0.0001,
        "inclination": 51.6,
        "apogee_km": 422.0,
        "perigee_km": 416.0,
        "orbital_period_minutes": 92.7
      }
    }
  ]
}
```

**Example:**

```bash
curl "http://localhost:8000/v2/search?country=USA&orbital_band=LEO&limit=10"
```

---

#### Get Satellite by Identifier

```http
GET /v2/satellite/{identifier}
```

Retrieve detailed information about a single satellite.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `identifier` | string | Yes | NORAD ID, COSPAR ID, or satellite name |

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `include_tle` | boolean | No | Include TLE data (default: true) |
| `include_orbital` | boolean | No | Include orbital parameters (default: true) |

**Response:**

```json
{
  "_key": "25544",
  "norad_id": "25544",
  "cospar_id": "1998-067A",
  "name": "ISS (ZARYA)",
  "country": "USA",
  "status": "operational",
  "launch_date": "1998-11-20",
  "launch_site": "Baikonur Cosmodrome",
  "orbital_band": "LEO",
  "constellation": "ISS",
  "purpose": "Space Station",
  "tle": {
    "line1": "1 25544U 98067A   26037.50000000  .00002182  00000-0  41420-4 0  9990",
    "line2": "2 25544  51.6400 208.4300 0001390  90.5300 269.5900 15.54225995415956",
    "epoch": "2026-02-06T12:00:00Z",
    "age_hours": 0.5
  },
  "orbital_parameters": {
    "semi_major_axis_km": 6793.0,
    "eccentricity": 0.0001,
    "inclination": 51.6,
    "apogee_km": 422.0,
    "perigee_km": 416.0,
    "orbital_period_minutes": 92.7,
    "mean_motion": 15.54
  },
  "registration_document": {
    "document_key": "A/AC.105/INF/123",
    "title": "ISS Registration",
    "url": "https://documents.un.org/..."
  }
}
```

**Example:**

```bash
# By NORAD ID
curl "http://localhost:8000/v2/satellite/25544"

# By COSPAR ID
curl "http://localhost:8000/v2/satellite/1998-067A"

# By name (URL encoded)
curl "http://localhost:8000/v2/satellite/ISS%20(ZARYA)"
```

---

### Metadata

#### Get All Countries

```http
GET /v2/countries
```

Retrieve list of all countries with satellites.

**Response:**

```json
{
  "countries": [
    {
      "code": "USA",
      "name": "United States",
      "satellite_count": 5432
    },
    {
      "code": "RUS",
      "name": "Russia",
      "satellite_count": 1987
    }
  ]
}
```

---

#### Get All Statuses

```http
GET /v2/statuses
```

Retrieve list of all satellite statuses.

**Response:**

```json
{
  "statuses": [
    {
      "value": "operational",
      "count": 4321
    },
    {
      "value": "decayed",
      "count": 8765
    }
  ]
}
```

---

#### Get All Orbital Bands

```http
GET /v2/orbital-bands
```

Retrieve list of orbital bands (LEO, MEO, GEO, HEO).

**Response:**

```json
{
  "orbital_bands": [
    {
      "value": "LEO",
      "name": "Low Earth Orbit",
      "altitude_range": "160-2000 km",
      "count": 12345
    },
    {
      "value": "GEO",
      "name": "Geostationary Orbit",
      "altitude_range": "~35,786 km",
      "count": 567
    }
  ]
}
```

---

#### Get Statistics

```http
GET /v2/stats
```

Retrieve overall statistics about the satellite registry.

**Response:**

```json
{
  "total_satellites": 15432,
  "operational": 6543,
  "decayed": 7654,
  "by_country": {
    "USA": 5432,
    "RUS": 1987,
    "CHN": 1234
  },
  "by_orbital_band": {
    "LEO": 12345,
    "MEO": 234,
    "GEO": 567,
    "HEO": 123
  },
  "by_launch_year": {
    "2023": 456,
    "2024": 678,
    "2025": 789
  }
}
```

---

### Graphs

#### Get Constellation Graph

```http
GET /v2/graphs/constellation/{constellation_name}
```

Retrieve graph of satellites in a constellation.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `constellation_name` | string | Yes | Name of constellation (e.g., "Starlink", "OneWeb") |

**Response:**

```json
{
  "constellation": "Starlink",
  "nodes": [
    {
      "id": "25544",
      "label": "Starlink-1",
      "type": "satellite",
      "properties": {
        "norad_id": "25544",
        "status": "operational"
      }
    }
  ],
  "edges": [
    {
      "from": "25544",
      "to": "25545",
      "type": "proximity",
      "properties": {
        "distance_km": 50.0
      }
    }
  ]
}
```

---

#### Get Registration Document Graph

```http
GET /v2/graphs/registration-document/{doc_key}
```

Retrieve graph of satellites registered under a UN document.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `doc_key` | string | Yes | UN document key (e.g., "A/AC.105/INF/123") |

**Response:**

```json
{
  "document": {
    "key": "A/AC.105/INF/123",
    "title": "Registration of Space Objects",
    "url": "https://documents.un.org/..."
  },
  "satellites": [
    {
      "norad_id": "25544",
      "name": "ISS (ZARYA)",
      "country": "USA"
    }
  ]
}
```

---

#### Get Graph Statistics

```http
GET /v2/graphs/stats
```

Retrieve statistics about graph data.

**Response:**

```json
{
  "total_nodes": 15432,
  "total_edges": 45678,
  "constellations": 234,
  "registration_documents": 567,
  "edge_types": {
    "proximity": 23456,
    "constellation": 12345,
    "registration": 9877
  }
}
```

---

#### Find Path Between Satellites

```http
GET /v2/graphs/paths/{from_id}/{to_id}
```

Find shortest or all paths between two satellites using graph traversal.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `from_id` | string | Yes | Source satellite NORAD ID |
| `to_id` | string | Yes | Target satellite NORAD ID |

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `algorithm` | string | No | Path algorithm: `shortest` (default) or `all` |
| `max_depth` | integer | No | Maximum traversal depth (default: 10, max: 20) |
| `edge_types` | array[string] | No | Edge types to traverse (default: all) |

**Response:**

```json
{
  "from": {
    "norad_id": "25544",
    "name": "ISS (ZARYA)"
  },
  "to": {
    "norad_id": "48274",
    "name": "TIANGONG"
  },
  "algorithm": "shortest",
  "path": {
    "vertices": [...],
    "edges": [...],
    "distance": 3
  }
}
```

**Example:**

```bash
curl "http://localhost:8000/v2/graphs/paths/25544/48274?algorithm=shortest&max_depth=5"
```

---

#### Calculate Network Centrality

```http
GET /v2/graphs/analytics/centrality
```

Calculate centrality metrics to identify important nodes in the satellite network.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `metric` | string | Yes | Centrality metric: `degree`, `betweenness`, or `closeness` |
| `edge_types` | array[string] | No | Edge types to include (default: all) |
| `limit` | integer | No | Number of top results (default: 100, max: 500) |
| `min_degree` | integer | No | Minimum degree for betweenness/closeness (default: 2) |

**Response:**

```json
{
  "metric": "degree",
  "edge_types": ["constellation_membership", "orbital_proximity"],
  "total_nodes_analyzed": 13452,
  "results": [
    {
      "satellite": {
        "norad_id": "25544",
        "name": "ISS (ZARYA)"
      },
      "score": 0.85,
      "degree": 342
    }
  ]
}
```

**Example:**

```bash
curl "http://localhost:8000/v2/graphs/analytics/centrality?metric=degree&limit=50"
```

---

#### Get Collision Risks

```http
GET /v2/graphs/collision-risks
```

Retrieve collision risk network showing satellites with potential collision risks.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `orbital_band` | string | No | Filter by orbital band (LEO, MEO, GEO) |
| `min_risk_score` | float | No | Minimum risk score (0.0-1.0, default: 0.5) |
| `limit` | integer | No | Maximum edges to return (default: 100, max: 1000) |

**Response:**

```json
{
  "orbital_band": "LEO",
  "min_risk_score": 0.5,
  "total_risk_edges": 1247,
  "nodes": [...],
  "edges": [
    {
      "from": "satellites/2025-001A",
      "to": "satellites/2025-002B",
      "risk_score": 0.85,
      "min_distance_km": 12.5,
      "crossing_time": "2025-02-15T12:30:00Z"
    }
  ]
}
```

**Example:**

```bash
curl "http://localhost:8000/v2/graphs/collision-risks?orbital_band=LEO&min_risk_score=0.7"
```

---

#### Get Collision Risks for Satellite

```http
GET /v2/graphs/collision-risks/{satellite_id}
```

Get collision risk edges for a specific satellite.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `satellite_id` | string | Yes | Satellite NORAD ID |

**Response:**

```json
{
  "satellite": {
    "norad_id": "25544",
    "name": "ISS (ZARYA)"
  },
  "risk_count": 23,
  "risks": [...]
}
```

---

#### Get Collision Risk Statistics

```http
GET /v2/graphs/collision-risks/statistics
```

Retrieve collision risk statistics by orbital band.

**Response:**

```json
{
  "total_risk_edges": 3456,
  "by_orbital_band": {
    "LEO": 2890,
    "MEO": 234,
    "GEO": 332
  },
  "high_risk_count": 567
}
```

---

#### Get Collision Clusters

```http
GET /v2/graphs/collision-risks/clusters
```

Identify clusters of satellites with collision risks.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `orbital_band` | string | No | Filter by orbital band |
| `min_cluster_size` | integer | No | Minimum cluster size (default: 3) |

**Response:**

```json
{
  "orbital_band": "LEO",
  "clusters": [
    {
      "cluster_id": 0,
      "size": 45,
      "satellites": [...]
    }
  ]
}
```

---

#### Get Cross-Constellation Proximity

```http
GET /v2/graphs/cross-constellation-proximity
```

Find satellites from different constellations in orbital proximity.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `orbital_band` | string | No | Filter by orbital band |
| `limit` | integer | No | Maximum results (default: 100, max: 500) |

**Response:**

```json
{
  "orbital_band": "LEO",
  "total_matches": 234,
  "relationships": [
    {
      "satellite1": {...},
      "satellite2": {...},
      "constellation1": "Starlink",
      "constellation2": "OneWeb",
      "proximity_km": 45.2
    }
  ]
}
```

---

#### Get Country Cooperation Network

```http
GET /v2/graphs/country-cooperation-network
```

Analyze country relationships through shared satellites and documents.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `min_connections` | integer | No | Minimum shared satellites (default: 1) |

**Response:**

```json
{
  "countries": [...],
  "connections": [
    {
      "country1": "USA",
      "country2": "RUS",
      "shared_satellites": 5,
      "shared_documents": 2
    }
  ]
}
```

---

#### Get Function-Based Clusters

```http
GET /v2/graphs/function-clusters
```

Find satellite clusters based on function and orbital proximity.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `orbital_band` | string | No | Filter by orbital band |
| `min_cluster_size` | integer | No | Minimum cluster size (default: 5) |

**Response:**

```json
{
  "clusters": [
    {
      "function": "Earth Observation",
      "orbital_band": "LEO",
      "satellites": [...]
    }
  ]
}
```

---

#### Get Satellite Lineage

```http
GET /v2/graphs/lineage/{satellite_id}
```

Retrieve satellite family tree showing predecessor/successor relationships.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `satellite_id` | string | Yes | Satellite NORAD ID |

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `direction` | string | No | Traversal direction: `ancestors`, `descendants`, or `both` (default) |
| `max_generations` | integer | No | Maximum generations to traverse (default: 5) |

**Response:**

```json
{
  "satellite": {...},
  "lineage": {
    "ancestors": [...],
    "descendants": [...],
    "generation": 3
  }
}
```

---

#### Detect Communities

```http
GET /v2/graphs/communities
```

Detect communities (clusters) in the satellite network.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `algorithm` | string | No | Algorithm: `label_propagation` or `connected_components` (default) |
| `edge_types` | array[string] | No | Edge types to consider (default: all) |
| `min_community_size` | integer | No | Minimum community size (default: 5) |

**Response:**

```json
{
  "algorithm": "label_propagation",
  "total_communities": 47,
  "communities": [
    {
      "community_id": 0,
      "size": 234,
      "satellites": [...]
    }
  ]
}
```

---

#### Get Graph Evolution Timeline

```http
GET /v2/graphs/evolution/timeline
```

Analyze how the satellite network evolved over time.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_year` | integer | No | Start year (default: 1957) |
| `end_year` | integer | No | End year (default: current year) |
| `granularity` | string | No | Time granularity: `year` or `month` (default: year) |

**Response:**

```json
{
  "start_year": 2020,
  "end_year": 2025,
  "granularity": "year",
  "timeline": [
    {
      "year": 2020,
      "node_count": 3456,
      "edge_count": 12345,
      "density": 0.0012,
      "avg_degree": 3.5
    }
  ]
}
```

---

#### Get Satellite Recommendations

```http
GET /v2/graphs/recommendations/{satellite_id}
```

Get satellite recommendations based on graph structure similarity.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `satellite_id` | string | Yes | Satellite NORAD ID |

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `strategy` | string | No | Strategy: `similarity`, `neighbors`, or `collaborative` (default) |
| `limit` | integer | No | Number of recommendations (default: 10, max: 50) |

**Response:**

```json
{
  "satellite": {...},
  "strategy": "collaborative",
  "recommendations": [
    {
      "satellite": {...},
      "score": 0.87,
      "reason": "Similar network position and shared neighbors"
    }
  ]
}
```

---

#### Get Cache Statistics

```http
GET /v2/graphs/cache/stats/all
```

Retrieve statistics for all graph query caches.

**Response:**

```json
{
  "caches": {
    "path_queries": {
      "hit_rate": 0.65,
      "size": 1234,
      "max_size": 2000,
      "hits": 4567,
      "misses": 2345,
      "ttl": 3600
    }
  },
  "overall": {
    "total_hits": 12345,
    "total_misses": 5678,
    "overall_hit_rate": 0.685
  }
}
```

---

#### Clear Specific Cache

```http
POST /v2/graphs/cache/clear/{cache_name}
```

Clear a specific graph query cache.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `cache_name` | string | Yes | Cache name (e.g., `path_queries`, `centrality_queries`) |

---

#### Clear All Caches

```http
POST /v2/graphs/cache/clear/all
```

Clear all graph query caches.

---

### Documents

#### Resolve Document URL

```http
GET /api/documents/resolve
```

Resolve UN document key to PDF URL.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `doc_key` | string | Yes | UN document key (e.g., "A/AC.105/INF/123") |

**Response:**

```json
{
  "doc_key": "A/AC.105/INF/123",
  "pdf_url": "https://documents.un.org/api/symbol/A-AC.105-INF-123/format/pdf",
  "english_url": "https://documents.un.org/api/symbol/A-AC.105-INF-123/language/E/format/pdf"
}
```

---

#### Get Document Metadata

```http
GET /api/documents/metadata
```

Extract metadata from UN document.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `doc_key` | string | Yes | UN document key |

**Response:**

```json
{
  "doc_key": "A/AC.105/INF/123",
  "title": "Registration of Space Objects Launched by...",
  "date": "2023-05-15",
  "languages": ["E", "F", "S", "R", "C", "A"],
  "pdf_urls": {
    "english": "https://documents.un.org/.../E/format/pdf",
    "french": "https://documents.un.org/.../F/format/pdf"
  }
}
```

---

### TLE Data

#### Get TLE by NORAD ID

```http
GET /v2/tle/{norad_id}
```

Retrieve Two-Line Element (TLE) data for a satellite.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `norad_id` | integer | Yes | NORAD catalog number |

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `include_orbital` | boolean | No | Include calculated orbital parameters (default: true) |

**Response:**

```json
{
  "norad_id": 25544,
  "name": "ISS (ZARYA)",
  "tle": {
    "line1": "1 25544U 98067A   26037.50000000  .00002182  00000-0  41420-4 0  9990",
    "line2": "2 25544  51.6400 208.4300 0001390  90.5300 269.5900 15.54225995415956",
    "epoch": "2026-02-06T12:00:00Z",
    "age_hours": 0.5
  },
  "orbital_parameters": {
    "semi_major_axis_km": 6793.0,
    "eccentricity": 0.0001,
    "inclination": 51.6,
    "mean_motion": 15.54,
    "apogee_km": 422.0,
    "perigee_km": 416.0,
    "orbital_period_minutes": 92.7,
    "orbital_band": "LEO"
  }
}
```

**Example:**

```bash
curl "http://localhost:8000/v2/tle/25544"
```

**Notes:**

- TLE data is cached for 1 hour
- Data is fetched from CelesTrak
- Returns 404 if NORAD ID not found

---

### Ephemeris

High-fidelity ephemeris generation and storage. Supports two propagators:

- **`SGP4`** (default): Fast, standard SGP4/SDP4 propagation via the `sgp4` library. Available on all deployments.
- **`HIFI`**: GMAT-based propagation using the Runge-Kutta 89 integrator with EGM96 8×8 gravity. Returns 503 if GMAT is not installed on the server.

---

#### Generate Ephemeris

```http
POST /v2/ephemeris/generate
```

Propagates a satellite's TLE forward and saves the resulting ephemeris envelope.

**Request Body:**

```json
{
  "norad_id": 25544,
  "duration_hours": 24.0,
  "step_seconds": 60,
  "propagator": "SGP4"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `norad_id` | integer | Yes | NORAD catalog number |
| `duration_hours` | float | No | Propagation window length (default: 24, max: 168) |
| `step_seconds` | integer | No | Time step in seconds (default: 60, range: 10–3600) |
| `propagator` | string | No | `"SGP4"` (default) or `"HIFI"` for GMAT high-fidelity propagation |

**Response:**

```json
{
  "envelope_id": "abc123",
  "norad_id": 25544,
  "satellite_name": "ISS (ZARYA)",
  "generated_at": "2026-04-22T10:00:00Z",
  "valid_from": "2026-04-22T10:00:00Z",
  "valid_until": "2026-04-23T10:00:00Z",
  "step_seconds": 60,
  "num_points": 1440,
  "orbital_period_minutes": 92.7
}
```

**HIFI propagator details** (when `propagator: "HIFI"`):

- Uses NASA GMAT R2022a `GmatConsole` binary (set `GMAT_HOME` environment variable)
- Force model: EGM96 8×8 spherical harmonic gravity, no drag, no SRP
- Integrator: Runge-Kutta 89 (adaptive step, accuracy `1e-12`)
- TLE elements are converted from mean motion to Keplerian elements before being passed to GMAT
- Returns `503 Service Unavailable` if the GMAT binary is not found

**Errors:**

| Code | Reason |
|------|--------|
| 400 | Invalid `duration_hours` or `step_seconds`, or TLE parsing failure |
| 404 | NORAD ID not found in TLE sources |
| 503 | `propagator: "HIFI"` requested but GMAT is not installed |

**Example:**

```bash
# SGP4 propagation (24 h, 60 s steps)
curl -X POST "http://localhost:8000/v2/ephemeris/generate" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"norad_id": 25544, "duration_hours": 24, "step_seconds": 60}'

# GMAT high-fidelity propagation (requires GMAT installed)
curl -X POST "http://localhost:8000/v2/ephemeris/generate" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"norad_id": 25544, "duration_hours": 24, "step_seconds": 60, "propagator": "HIFI"}'
```

---

#### List Ephemeris Envelopes

```http
GET /v2/ephemeris
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `norad_id` | integer | Filter by NORAD ID |
| `limit` | integer | Page size (default: 50, max: 200) |
| `offset` | integer | Pagination offset (default: 0) |

**Response:**

```json
{
  "data": [
    {
      "_key": "abc123",
      "norad_id": 25544,
      "satellite_name": "ISS (ZARYA)",
      "propagator": "GMAT_RK89_EGM96",
      "generated_at": "2026-04-22T10:00:00Z",
      "valid_from": "2026-04-22T10:00:00Z",
      "valid_until": "2026-04-23T10:00:00Z",
      "num_points": 1440
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

---

#### Get Ephemeris Envelope

```http
GET /v2/ephemeris/{envelope_id}
```

Returns the full ephemeris envelope including all propagated points.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `envelope_id` | string | Ephemeris envelope ID |

**Response:**

```json
{
  "_key": "abc123",
  "norad_id": 25544,
  "satellite_name": "ISS (ZARYA)",
  "propagator": "GMAT_RK89_EGM96",
  "tle_line1": "1 25544U ...",
  "tle_line2": "2 25544 ...",
  "source_tle_epoch": "22 Apr 2026 10:00:00.000",
  "generated_at": "2026-04-22T10:00:00Z",
  "valid_from": "2026-04-22T10:00:00Z",
  "valid_until": "2026-04-23T10:00:00Z",
  "step_seconds": 60,
  "duration_hours": 24.0,
  "orbital_period_minutes": 92.7,
  "num_points": 1440,
  "ephemeris_points": [
    {
      "timestamp": "2026-04-22T10:00:00+00:00",
      "eci": { "x_km": 3456.7, "y_km": -5123.4, "z_km": 1234.5 },
      "geodetic": {
        "latitude": 51.6,
        "longitude": -75.3,
        "altitude_km": 418.2
      },
      "propagation_age_minutes": null
    }
  ],
  "keplerian_elements": {
    "sma_km": 6792.5,
    "ecc": 0.0001387,
    "inc_deg": 51.6400,
    "raan_deg": 208.4300,
    "aop_deg": 90.5300,
    "ta_deg": 269.5900
  }
}
```

> `keplerian_elements` is only present when the `HIFI` propagator was used; it contains the Keplerian elements passed to GMAT.

---

#### Get Ephemeris as CZML

```http
GET /v2/ephemeris/{envelope_id}/czml
```

Returns the ephemeris formatted as [CZML](https://github.com/AnalyticalGraphicsInc/czml-writer/wiki/CZML-Guide) for direct use in Cesium / CesiumJS visualizations.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `envelope_id` | string | Ephemeris envelope ID |

**Response:** `application/json` CZML array

```json
[
  {
    "id": "document",
    "name": "Ephemeris for ISS (ZARYA)",
    "version": "1.0",
    "clock": {
      "interval": "2026-04-22T10:00:00Z/2026-04-23T10:00:00Z",
      "currentTime": "2026-04-22T10:00:00Z",
      "multiplier": 60
    }
  },
  {
    "id": "satellite/25544",
    "name": "ISS (ZARYA)",
    "availability": "2026-04-22T10:00:00Z/2026-04-23T10:00:00Z",
    "position": {
      "epoch": "2026-04-22T10:00:00Z",
      "cartographicDegrees": [...],
      "interpolationAlgorithm": "LAGRANGE",
      "interpolationDegree": 5
    },
    "point": { "color": {"rgba": [255, 255, 0, 255]}, "pixelSize": 8 },
    "path": { "width": 1, "leadTime": 3600, "trailTime": 3600 },
    "label": { "text": "ISS (ZARYA)", "show": true }
  }
]
```

---

#### Delete Ephemeris Envelope

```http
DELETE /v2/ephemeris/{envelope_id}
```

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `envelope_id` | string | Ephemeris envelope ID |

**Response:**

```json
{ "deleted": true, "envelope_id": "abc123" }
```

---

### MQTT Configuration

#### List MQTT Configurations

```http
GET /v2/mqtt/configurations
```

Retrieve all MQTT publishing configurations.

**Response:**

```json
{
  "configurations": [
    {
      "_key": "config-1",
      "satellite_id": "25544",
      "broker_url": "mqtt://broker.example.com:1883",
      "topic": "satellites/iss/telemetry",
      "interval_seconds": 60,
      "enabled": true,
      "created_at": "2026-01-15T10:30:00Z"
    }
  ]
}
```

---

#### Create MQTT Configuration

```http
POST /v2/mqtt/configurations
```

Create a new MQTT publishing configuration.

**Request Body:**

```json
{
  "satellite_id": "25544",
  "broker_url": "mqtt://broker.example.com:1883",
  "topic": "satellites/iss/telemetry",
  "interval_seconds": 60,
  "username": "user",
  "password": "pass"
}
```

**Response:**

```json
{
  "_key": "config-1",
  "satellite_id": "25544",
  "broker_url": "mqtt://broker.example.com:1883",
  "topic": "satellites/iss/telemetry",
  "interval_seconds": 60,
  "enabled": true,
  "created_at": "2026-02-06T12:00:00Z"
}
```

---

#### Update MQTT Configuration

```http
PUT /v2/mqtt/configurations/{config_id}
```

Update an existing MQTT configuration.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `config_id` | string | Yes | Configuration ID |

**Request Body:**

```json
{
  "interval_seconds": 120,
  "enabled": false
}
```

**Response:**

```json
{
  "_key": "config-1",
  "satellite_id": "25544",
  "interval_seconds": 120,
  "enabled": false,
  "updated_at": "2026-02-06T12:05:00Z"
}
```

---

#### Delete MQTT Configuration

```http
DELETE /v2/mqtt/configurations/{config_id}
```

Delete an MQTT configuration.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `config_id` | string | Yes | Configuration ID |

**Response:**

```json
{
  "message": "Configuration deleted successfully",
  "config_id": "config-1"
}
```

---

## Response Formats

### Success Response

All successful responses have HTTP status 200-299 and JSON body:

```json
{
  "field1": "value1",
  "field2": "value2"
}
```

### Error Response

All error responses have HTTP status 400-599 and JSON body:

```json
{
  "error": {
    "code": "SATELLITE_NOT_FOUND",
    "message": "Satellite with NORAD ID 99999 not found",
    "details": {
      "norad_id": 99999
    }
  }
}
```

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request successful |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid parameters |
| 404 | Not Found | Resource not found |
| 500 | Internal Server Error | Server error |
| 503 | Service Unavailable | Database or external service unavailable |

### Error Codes

| Code | Description |
|------|-------------|
| `SATELLITE_NOT_FOUND` | Satellite with given identifier not found |
| `INVALID_NORAD_ID` | NORAD ID must be a positive integer |
| `TLE_FETCH_FAILED` | Failed to fetch TLE data from CelesTrak |
| `DATABASE_ERROR` | Database query failed |
| `INVALID_PARAMETERS` | Invalid query parameters |

---

## Rate Limiting

**Current Version**: No rate limiting

**Future Versions**: 
- Free tier: 100 requests/minute
- Authenticated: 1000 requests/minute

---

## Examples

### Python Examples

#### Search Satellites

```python
import requests

# Search for operational US LEO satellites
response = requests.get("http://localhost:8000/v2/search", params={
    "country": "USA",
    "status": "operational",
    "orbital_band": "LEO",
    "limit": 10
})

satellites = response.json()
for sat in satellites["results"]:
    print(f"{sat['norad_id']}: {sat['name']}")
```

#### Get TLE Data

```python
import requests

# Get TLE for ISS
norad_id = 25544
response = requests.get(f"http://localhost:8000/v2/tle/{norad_id}")

tle_data = response.json()
print(f"TLE Line 1: {tle_data['tle']['line1']}")
print(f"TLE Line 2: {tle_data['tle']['line2']}")
print(f"Orbital Period: {tle_data['orbital_parameters']['orbital_period_minutes']} min")
```

---

### JavaScript Examples

#### Search Satellites

```javascript
// Search for operational Starlink satellites
fetch('http://localhost:8000/v2/search?constellation=Starlink&status=operational&limit=10')
  .then(response => response.json())
  .then(data => {
    console.log(`Found ${data.total} satellites`);
    data.results.forEach(sat => {
      console.log(`${sat.norad_id}: ${sat.name}`);
    });
  });
```

#### Get Satellite Details

```javascript
// Get ISS details
const noradId = 25544;
fetch(`http://localhost:8000/v2/satellite/${noradId}`)
  .then(response => response.json())
  .then(satellite => {
    console.log(`Name: ${satellite.name}`);
    console.log(`Country: ${satellite.country}`);
    console.log(`Orbital Band: ${satellite.orbital_band}`);
    console.log(`Apogee: ${satellite.orbital_parameters.apogee_km} km`);
    console.log(`Perigee: ${satellite.orbital_parameters.perigee_km} km`);
  });
```

---

### cURL Examples

#### Search with Multiple Filters

```bash
curl -X GET "http://localhost:8000/v2/search" \
  -G \
  --data-urlencode "country=USA" \
  --data-urlencode "status=operational" \
  --data-urlencode "orbital_band=LEO" \
  --data-urlencode "launch_year_start=2020" \
  --data-urlencode "limit=50"
```

#### Create MQTT Configuration

```bash
curl -X POST "http://localhost:8000/v2/mqtt/configurations" \
  -H "Content-Type: application/json" \
  -d '{
    "satellite_id": "25544",
    "broker_url": "mqtt://broker.example.com:1883",
    "topic": "satellites/iss/telemetry",
    "interval_seconds": 60
  }'
```

---

### Observations

#### Import Observations

```http
POST /v2/observations/import
```

Bulk-import observation records. Only satellites with `observations_enabled: true` in their canonical fields are accepted.

**Request Body:**

```json
{
  "observations": [
    {
      "norad_id": 25544,
      "observation_epoch": "2026-02-06T12:00:00Z",
      "source": "groundstation-alpha",
      "object_name": "ISS",
      "object_type": "payload",
      "origin_country": "USA",
      "derived_health_score": 87.5,
      "estimated_mass_kg": 420000,
      "spin_rate_rpm": 0.0,
      "thermal": { "anomaly_flag": false }
    }
  ]
}
```

**Field validation:**
- `norad_id`: positive integer
- `observation_epoch`: ISO 8601 datetime string
- `source`: non-empty string
- `derived_health_score`: 0–100
- `estimated_mass_kg`, `spin_rate_rpm`: non-negative

**Response:**

```json
{
  "inserted": 1,
  "skipped_duplicates": 0,
  "skipped_not_allowed": 0,
  "errors": [],
  "total_submitted": 1
}
```

---

#### Get Allowed Objects

```http
GET /v2/observations/allowed-objects
```

List all satellites that have `observations_enabled: true`.

**Response:**

```json
{
  "data": [
    { "norad_id": 25544, "name": "ISS (ZARYA)" }
  ],
  "total": 1
}
```

---

#### Enable / Disable Observation Tracking

```http
PUT /v2/observations/allowed-objects/{norad_id}
DELETE /v2/observations/allowed-objects/{norad_id}
```

Enable or disable observation tracking for a satellite.

---

#### List Observations

```http
GET /v2/observations
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `norad_id` | integer | Filter by NORAD ID |
| `source` | string | Filter by data source |
| `start_epoch` | string | ISO 8601 start datetime |
| `end_epoch` | string | ISO 8601 end datetime |
| `anomaly_only` | boolean | Return only anomalous records |
| `sort_by` | string | Field to sort by |
| `sort_order` | string | `asc` or `desc` |
| `skip` | integer | Pagination offset |
| `limit` | integer | Page size |

---

#### Observation Analytics

```http
GET /v2/observations/analytics/health-over-time
GET /v2/observations/analytics/anomaly-distribution
GET /v2/observations/analytics/source-distribution
```

Aggregated analytics over observation data.

---

#### Observation Graph Endpoints

```http
GET /v2/graphs/satellite-observations          # Observations for a satellite
GET /v2/graphs/observations/neighborhood       # Observation neighborhood graph
GET /v2/graphs/observations/source-network     # Source network graph
GET /v2/graphs/observations/temporal-chain     # Temporal health chain
GET /v2/graphs/observations/anomaly-correlation # Anomaly correlation graph
GET /v2/graphs/observations/graph-stats        # Observation graph statistics
POST /v2/graphs/observations/populate-edges    # Populate observation edges
```

---

### Admin

#### Get GMAT Status

```http
GET /v2/admin/gmat-status
```

Check whether the GMAT engine is installed and functional on the server. Runs a 60-second smoke test (EGM96 gravity, minimal propagation) to verify end-to-end operation.

**Response:**

```json
{
  "gmat_home": "/opt/gmat",
  "gmat_home_exists": true,
  "bin_dir_contents": ["GmatConsole-R2022a", "libGmat.so"],
  "binary_found": "/opt/gmat/bin/GmatConsole-R2022a",
  "binary_executable": true,
  "version_output": "GMAT R2022a ...",
  "missing_data_files": [],
  "egm96_path": "/opt/gmat/data/gravity/Earth/EGM96.cof",
  "smoke_test": {
    "ok": true,
    "output": "...",
    "error": null
  },
  "status": "ready"
}
```

**`status` values:**

| Value | Meaning |
|-------|---------|
| `not_installed` | GMAT binary not found anywhere on the server |
| `installed` | Binary found but smoke test was not run (not executable) |
| `installed_but_broken` | Binary found and executable but smoke test failed |
| `ready` | Binary found, executable, smoke test passed — safe to use `"HIFI"` propagator |

**`missing_data_files`** lists any required data files (e.g. `EGM96.cof`) that are absent. If non-empty, HIFI propagation will fail even if the binary is present.

**Environment variable:** Set `GMAT_HOME` (default: `/opt/gmat`) to point to your GMAT installation directory.

---

#### List Available Scripts

```http
GET /v2/admin/scripts
```

Returns the catalogue of runnable maintenance and population scripts.

**Response:**

```json
{
  "scripts": [
    {
      "id": "populate_collision_risks",
      "name": "Populate Collision Risks",
      "description": "Compute and populate collision risk edges",
      "category": "population"
    },
    {
      "id": "enrich_launch_data",
      "name": "Enrich Launch Data",
      "description": "Enriches satellite documents with launch dates and country data",
      "category": "maintenance"
    }
  ]
}
```

**Available script IDs:**

| ID | Category | Description |
|----|----------|-------------|
| `enrich_launch_data` | maintenance | Enrich satellites with launch dates and country data |
| `promote_kaggle_orbital` | maintenance | Promote Kaggle orbital parameters to canonical fields |
| `promote_attributes` | maintenance | Promote attributes across satellite records |
| `promote_launch_site` | maintenance | Promote launch site data to canonical fields |
| `populate_collision_risks` | population | Compute and populate collision risk edges |
| `populate_constellation_network` | population | Build constellation membership graph |
| `populate_orbital_proximity` | population | Populate orbital proximity edges |
| `populate_registration_network` | population | Build registration document links |

---

#### Run a Script

```http
POST /v2/admin/scripts/{script_id}/run
```

Executes the named script as a background subprocess.

**Response:**

```json
{ "run_id": "uuid-...", "status": "started", "script_id": "populate_collision_risks" }
```

---

#### Get Run Status

```http
GET /v2/admin/runs/{run_id}
```

**Response:**

```json
{
  "run_id": "uuid-...",
  "script_id": "populate_collision_risks",
  "status": "completed",
  "started_at": "2026-02-06T12:00:00Z",
  "completed_at": "2026-02-06T12:05:00Z",
  "output": "...",
  "error": null
}
```

---

### AI Assistant (Agent)

Kessler ships two LangGraph-powered agents. Both require `OPENAI_API_KEY` on the server.
Check readiness with `GET /v2/ask/status` before use.

See [`docs/LANGGRAPH_AGENT_ARCHITECTURE.md`](docs/LANGGRAPH_AGENT_ARCHITECTURE.md) for full
implementation details, graph topologies, and extension guidance.

The **General Assistant** uses a ReAct agent backed by OpenAI and a ChromaDB RAG index
over project documentation. It supports multi-turn conversation via `session_id`.

---

#### Check Agent Status

```http
GET /v2/ask/status
```

**Response:**

```json
{ "agent_ready": true, "index_ready": true, "aql_agent_ready": true }
```

---

#### Ask a Question

```http
POST /v2/ask
```

**Request Body:**

```json
{
  "question": "What graph relationships does Kessler track?",
  "session_id": null
}
```

Pass `session_id` from a previous response to continue a multi-turn conversation.

**Response:**

```json
{
  "answer": "Kessler tracks the following graph relationships...",
  "sources": ["ARCHITECTURE.md", "API_DOCUMENTATION.md"],
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Tools the agent can use:**
- `search_knowledge_base` — RAG over indexed project documentation
- `get_satellite_by_norad_id` — direct lookup by integer NORAD catalog ID
- `search_satellites` — live satellite registry lookup
- `run_aql_query` — read-only AQL queries (FOR/RETURN only)

**Example:**

```bash
curl -X POST "http://localhost:8000/v2/ask" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "How many satellites are in LEO?"}'
```

---

### AQL Translation Agent

Translates a natural language question into an AQL query, executes it against ArangoDB,
and returns both the generated query and the results. The generated AQL is self-contained
(no bind variables) so it can be copied directly into the AQL Editor and modified.

#### How it works

1. **Ambiguity check**: if the question is ambiguous (e.g. "show satellites by country"
   could mean origin or registration), the agent returns a `clarifying_question` and no
   AQL. Re-submit with the `clarification` field set to proceed.
2. **Country resolution**: ISO codes and adjective forms ("AT", "AUT", "Austrian") are
   resolved deterministically to the exact stored value ("Austria") before the LLM runs.
3. **Error correction**: if ArangoDB rejects the generated AQL, the LLM sees the error
   and rewrites the query (up to 3 attempts).

---

#### Translate Natural Language to AQL

```http
POST /v2/aql
```

**Request Body:**

```json
{
  "question": "Show the active Austrian satellites",
  "clarification": null
}
```

Pass `clarification` (user's answer) when the previous response contained a
`clarifying_question`.

**Response — successful query:**

```json
{
  "aql": "FOR s IN satellites FILTER s.canonical.country_of_origin == 'Austria' AND s.canonical.status == 'in orbit' LIMIT 20 RETURN s",
  "bind_vars": {},
  "result": [ { ... }, { ... } ],
  "explanation": "Returns up to 20 active satellites registered in Austria.",
  "error": "",
  "clarifying_question": ""
}
```

**Response — clarification needed:**

```json
{
  "aql": "",
  "bind_vars": {},
  "result": [],
  "explanation": "",
  "error": "",
  "clarifying_question": "Do you mean satellites by country of origin, or by launch registration country?"
}
```

Re-submit the same `question` with `"clarification": "country of origin"` to proceed.

**Example:**

```bash
curl -X POST "http://localhost:8000/v2/aql" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "Show the 10 satellites with the highest collision risk scores"}'
```

**With clarification:**

```bash
curl -X POST "http://localhost:8000/v2/aql" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "Show satellites by country", "clarification": "country of origin"}'
```

---

## OpenAPI Specification

The complete OpenAPI 3.0 specification is available at:

```
http://localhost:8000/openapi.json
```

Import this into tools like Postman, Insomnia, or API testing frameworks.

---

## Support

- **Interactive Docs**: `http://localhost:8000/docs`
- **GitHub Issues**: Report bugs or request features
- **Developer Guide**: See `DEVELOPER_GUIDE.md` for implementation details

---

**Last Updated**: April 10, 2026  
**API Version**: 2.1.0
