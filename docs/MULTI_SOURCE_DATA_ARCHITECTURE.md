# Multi-Source Data Architecture with Envelope Pattern

Complete guide to the Kessler satellite tracking system's multi-source data management using ArangoDB and the envelope pattern.

## Architecture Overview

The system uses an **envelope pattern** to manage satellite data from multiple sources:

```
┌─────────────────────────────────────────┐
│         ArangoDB Document (Envelope)    │
├─────────────────────────────────────────┤
│ identifier: "2025-206B"                 │
├─────────────────────────────────────────┤
│ ✅ CANONICAL (Merged/Authoritative)     │
│    ├─ satellite_name (from UNOOSA)      │
│    ├─ country_of_origin (from UNOOSA)   │
│    ├─ international_designator          │
│    ├─ apogee_km / perigee_km            │
│    └─ status / orbital_band             │
├─────────────────────────────────────────┤
│ 📁 SOURCES (Raw Data from Each Source)  │
│    ├─ unoosa: {...}                     │
│    ├─ celestrak: {...}                  │
│    └─ spacetrack: {...} (supplemental)  │
├─────────────────────────────────────────┤
│ 📊 METADATA (Tracking Info)             │
│    ├─ created_at                        │
│    ├─ last_updated_at                   │
│    ├─ sources_available: [...]          │
│    └─ source_priority: [...]            │
└─────────────────────────────────────────┘
```

## Key Principles

### 1. Single Source of Truth (Per Field)

Each field in `canonical` comes from the **highest-priority source** that has it:

```
Priority: UNOOSA > CelesTrak > Space-Track

canonical.satellite_name = unoosa.name  (if available)
                           OR celestrak.name (if unoosa doesn't have it)
                           OR spacetrack.name (if neither has it)
```

### 2. No Data Loss

All source data is preserved in the `sources` section:

```json
{
  "canonical": {
    "satellite_name": "GLONASS-K1",
    "country_of_origin": "Russian Federation",
    "apogee_km": 19140.0
  },
  "sources": {
    "unoosa": { "name": "GLONASS-K1", "country_of_origin": "Russian Federation" },
    "celestrak": { "apogee_km": 19140.0, "tle_line1": "1 ..." }
  }
}
```

### 3. Automatic Merging

The canonical section is **automatically updated** when new sources are added. The import scripts call `update_canonical()` after each merge, regenerating the authoritative view from all available sources.

### 4. Transparent Sourcing

The `metadata.sources_available` field shows which sources contributed to each document:

```json
{
  "metadata": {
    "sources_available": ["unoosa", "celestrak"],
    "source_priority": ["unoosa", "celestrak", "spacetrack"]
  }
}
```

## Database: ArangoDB

Kessler stores all satellite data in **ArangoDB** — a native multi-model graph database. The `satellites` collection holds envelope documents; related vertex and edge collections model the orbital graph.

### Collections

| Collection | Type | Description |
|-----------|------|-------------|
| `satellites` | vertex | Primary satellite registry (envelope pattern) |
| `registration_documents` | vertex | UN document metadata |
| `observations` | vertex | Health & tracking records |
| `observation_sources` | vertex | Submitter metadata |
| `constellation_membership` | edge | Satellite → satellite (constellation) |
| `registration_links` | edge | Satellite → registration_document |
| `orbital_proximity` | edge | Satellite → satellite (proximity) |
| `collision_risk_edges` | edge | Satellite → satellite (risk_score) |
| `satellite_lineage` | edge | Satellite → satellite (predecessor/successor) |

### Connection

```python
from arango import ArangoClient

client = ArangoClient(hosts="http://localhost:8529")
db = client.db("kessler", username="root", password="kessler_dev_password")
```

Default connection env vars:

| Variable | Default |
|----------|---------|
| `ARANGO_HOST` | `http://localhost:8529` |
| `ARANGO_USER` | `root` |
| `ARANGO_PASSWORD` | `kessler_dev_password` |

## Import Workflow

### Step 1: Import UNOOSA Registry

```bash
python3 scripts/import/import_gcat_bulk.py
```

Loads the UNOOSA/GCAT satellite registry into the `satellites` collection as envelope documents with `sources.unoosa` populated.

### Step 2: Add CelesTrak TLE Data

```bash
python3 scripts/import/import_tle_api.py
```

Fetches TLE data from CelesTrak and merges it into existing satellite documents, populating `sources.celestrak` and updating `canonical.apogee_km`, `canonical.perigee_km`, `canonical.inclination_deg`, etc.

### Step 3: Populate Graph Edges

```bash
python3 scripts/population/populate_orbital_proximity.py
python3 scripts/population/populate_collision_risks.py
python3 scripts/population/populate_constellation_network.py
python3 scripts/population/populate_registration_network.py
python3 scripts/population/populate_satellite_lineage.py
```

Each script adds a specific edge collection to the graph.

### Step 4: Add Observations (Optional)

```bash
python3 scripts/import/import_satnogs_status.py
python3 scripts/population/populate_observation_edges.py
```

Imports satellite health observations and links them to satellites via `observation_satellite_edges`.

## Data Flow Diagram

```
UNOOSA / GCAT CSV
    ↓
    ├─→ scripts/import/import_gcat_bulk.py
    ↓
ArangoDB: satellites collection (envelope docs)
    ↓
    ├─→ canonical: {registry info}
    ├─→ sources.unoosa: {registry info}
    └─→ metadata: {tracking}

                    ↓↓↓

CelesTrak TLE API
    ↓
    ├─→ scripts/import/import_tle_api.py
    ↓
ArangoDB: satellites (updated)
    ↓
    ├─→ canonical: {registry + orbital elements}
    ├─→ sources.unoosa: {registry}
    ├─→ sources.celestrak: {TLE}
    └─→ metadata: {tracking + celestrak}

                    ↓↓↓

Graph Population Scripts
    ↓
ArangoDB: edge collections
    ↓
    ├─→ orbital_proximity edges
    ├─→ collision_risk_edges
    ├─→ constellation_membership edges
    ├─→ registration_links edges
    └─→ satellite_lineage edges

                    ↓↓↓

API (/v2/*)
    ↓
React Frontend / External Clients
```

## Benefits

### 1. **Flexibility**
- Add new sources without changing existing data
- No schema migrations needed for new fields
- Each source can have different field sets

### 2. **Data Quality**
- Keep best data from each source
- UNOOSA for authoritative registration info
- CelesTrak for precise orbital elements
- Space-Track for supplemental tracking data

### 3. **Audit Trail**
- See exactly which source provided each piece of data
- Historical tracking via `updated_at` timestamps
- Resolve discrepancies by checking `sources.*`

### 4. **No Conflicts**
- Source priority rules eliminate manual decision-making
- Consistent, predictable behavior
- Easy to adjust priority if needed

### 5. **Graph Queries**
- ArangoDB graph traversal over edge collections
- AQL for complex multi-hop queries
- LangGraph AI agent translates natural language → AQL (see `docs/LANGGRAPH_AGENT_ARCHITECTURE.md`)

## Implementation Details

### Database Layer (`database/`)

| File | Purpose |
|------|---------|
| `database/connection.py` | ArangoDB connection & collection setup |
| `database/operations.py` | CRUD operations on the `satellites` collection |
| `database/graph_operations.py` | Graph traversal and edge management |
| `database/graph_analytics.py` | AQL analytics queries (~2500 lines) |
| `database/transformations.py` | Field normalization & canonical merging |

### Import Scripts (`scripts/import/`)

| Script | Purpose |
|--------|---------|
| `import_gcat_bulk.py` | UNOOSA/GCAT registry bulk import |
| `import_tle_api.py` | CelesTrak TLE fetch & merge |
| `import_spacetrack_tle.py` | Space-Track supplemental TLE |
| `import_kaggle_catalog_arango.py` | Kaggle satellite catalog import |
| `import_satnogs_status.py` | SatNOGS observation import |
| `import_arangodb_data.py` | Restore from exported dump |
| `export_arangodb.py` | Export current DB to JSON |

### Population Scripts (`scripts/population/`)

| Script | Purpose |
|--------|---------|
| `populate_orbital_proximity.py` | Compute & store proximity edges |
| `populate_collision_risks.py` | Compute & store collision risk edges |
| `populate_constellation_network.py` | Build constellation membership edges |
| `populate_registration_network.py` | Link satellites to UN documents |
| `populate_satellite_lineage.py` | Build predecessor/successor edges |
| `populate_observation_edges.py` | Link observations to satellites/sources |

## Getting Started

1. **Start ArangoDB**:
   ```bash
   docker run -p 8529:8529 -e ARANGO_ROOT_PASSWORD=kessler_dev_password arangodb
   ```
   Or connect to a hosted ArangoDB instance via `ARANGO_HOST`.

2. **Import satellite registry**:
   ```bash
   python3 scripts/import/import_gcat_bulk.py
   ```

3. **Add TLE orbital data**:
   ```bash
   python3 scripts/import/import_tle_api.py
   ```

4. **Populate graph edges**:
   ```bash
   python3 scripts/population/populate_orbital_proximity.py
   python3 scripts/population/populate_collision_risks.py
   ```

5. **Start the API**:
   ```bash
   python -m uvicorn api.main:app --port 8000
   curl http://localhost:8000/v2/satellites?limit=5
   ```

## Summary

The **envelope pattern** with **source priority** creates a robust, flexible system for managing satellite data from multiple sources:

- **Flexible**: Add new sources without breaking changes
- **Lossless**: All source data preserved in `sources.*`
- **Automatic**: Canonical updates on every import
- **Transparent**: See where each piece of data comes from
- **Graph-native**: ArangoDB edges enable graph analytics and traversal
- **AI-queryable**: LangGraph AQL agent translates natural language queries

## References

- `docs/GRAPH_RELATIONSHIPS.md` — Full graph schema and edge semantics
- `docs/LANGGRAPH_AGENT_ARCHITECTURE.md` — AI query agent architecture
- `docs/OBSERVATIONS_IMPORT_API.md` — Observation data import details
- `ARCHITECTURE.md` — Full system architecture
