# CelesTrak TLE Import Guide

Import Two-Line Element (TLE) orbital data from CelesTrak and merge it with existing satellite registry data in ArangoDB using the envelope pattern.

## Overview

The CelesTrak import adds TLE (Two-Line Element) data to satellites already in the `satellites` collection. The envelope pattern automatically:

1. **Merges data from multiple sources** — UNOOSA registry + CelesTrak TLE data
2. **Resolves conflicts** — Uses source priority (UNOOSA > CelesTrak > Space-Track)
3. **Preserves all data** — Keeps raw source data in `sources.*` sections
4. **Updates canonical automatically** — Derived from highest-priority sources

## What is TLE Data?

TLE (Two-Line Element) format contains orbital elements for tracking satellites. Example:

```
ISS (ZARYA FGB)
1 25544U 98067A   25349.64833335  .00016717  00000-0  29853-3 0  9998
2 25544  51.6432 247.7832 0002671  86.3996  41.1872 15.54248026435929
```

From TLE, we extract:
- **Name**: ISS (ZARYA FGB)
- **International Designator**: 1998-067A (from line 1, positions 9–17)
- **Orbital Parameters**: apogee/perigee (calculated), inclination (51.64°), period (92.65 min)

## Running the Import

```bash
# Fetch latest TLE from CelesTrak (requires internet)
python3 scripts/import/import_tle_api.py
```

The script:
1. Fetches TLE files from multiple CelesTrak categories
2. Parses each TLE record and derives orbital parameters
3. Looks up matching satellite documents by `international_designator` or NORAD ID
4. Merges TLE data into `sources.celestrak`
5. Recalculates `canonical` using source priority

## Document Structure After Import

When TLE data is added to an existing UNOOSA satellite:

```json
{
  "_id": "satellites/2025-206B",
  "identifier": "2025-206B",
  "canonical": {
    "satellite_name": "(GLONASS)",
    "country_of_origin": "Russian Federation",
    "international_designator": "2025-206B",
    "status": "in orbit",
    "apogee_km": 19140.0,
    "perigee_km": 19100.0,
    "inclination_deg": 64.8,
    "norad_cat_id": 25544
  },
  "sources": {
    "unoosa": {
      "name": "(GLONASS)",
      "country_of_origin": "Russian Federation",
      "status": "in orbit"
    },
    "celestrak": {
      "tle_line1": "1 25544U ...",
      "tle_line2": "2 25544  64.8 ...",
      "apogee_km": 19140.0,
      "perigee_km": 19100.0,
      "inclination_deg": 64.8
    }
  },
  "metadata": {
    "sources_available": ["unoosa", "celestrak"],
    "source_priority": ["unoosa", "celestrak", "spacetrack"],
    "last_updated_at": "2025-12-15T02:00:00Z"
  }
}
```

## Understanding Source Priority

| Field | UNOOSA | CelesTrak | Space-Track | Used From |
|-------|--------|-----------|-------------|-----------|
| `satellite_name` | "GLONASS" | "GLONASS-K1" | — | UNOOSA (higher priority) |
| `apogee_km` | — | 19140.0 | — | CelesTrak |
| `status` | "in orbit" | — | — | UNOOSA |
| `norad_cat_id` | — | 25544 | 25544 | CelesTrak |

## CelesTrak Sources

The import fetches from these CelesTrak categories:

| Category | Purpose |
|----------|---------|
| Space Stations | ISS, Tiangong, etc. |
| Earth Resources | Remote sensing satellites |
| Search & Rescue | SARSAT missions |
| Disaster Monitoring | DMC constellation |
| Weather | Meteorological satellites |
| Geostationary | GEO communications |
| High Earth Orbit | GPS, GLONASS, Galileo |
| CubeSats | Small experimental satellites |

## API Examples

### Search for Satellites with Orbital Data

```bash
# Find satellites in orbit
curl 'http://localhost:8000/v2/satellites?status=in%20orbit&limit=10' | jq .

# Filter by country
curl 'http://localhost:8000/v2/satellites?country=Russian%20Federation&limit=5' | jq .
```

### AI-Assisted AQL Queries

```bash
# Ask in plain English — the AQL agent generates and runs the query
curl -X POST http://localhost:8000/v2/aql \
  -H 'Content-Type: application/json' \
  -d '{"question": "Which satellites have the highest apogee?"}' | jq .
```

### Direct AQL

```bash
curl -X POST http://localhost:8000/v2/graph/aql \
  -H 'Content-Type: application/json' \
  -d '{"query": "FOR s IN satellites FILTER s.canonical.apogee_km > 35000 SORT s.canonical.apogee_km DESC LIMIT 10 RETURN {name: s.canonical.satellite_name, apogee: s.canonical.apogee_km}"}' | jq .
```

## Periodic Updates

Set up automatic TLE updates via cron (daily at 2 AM):

```bash
crontab -e
# Add:
0 2 * * * cd /path/to/kessler && python3 scripts/import/import_tle_api.py >> /tmp/kessler-tle.log 2>&1
```

## Troubleshooting

### No Documents Matched

Ensure the UNOOSA/GCAT registry is imported first:

```bash
# Step 1: Import registry
python3 scripts/import/import_gcat_bulk.py

# Step 2: Then import TLE
python3 scripts/import/import_tle_api.py
```

### CelesTrak Unreachable

```bash
# Check CelesTrak status: https://celestrak.org/
# Check your connection:
curl https://celestrak.org/SOCRATES/query.php
```

### ArangoDB Connection Failed

```bash
curl http://localhost:8529/_api/version
# Should return {"server":"arango","version":"..."}
```

## References

- `docs/MULTI_SOURCE_DATA_ARCHITECTURE.md` — Envelope pattern and data model
- `docs/DATA_IMPORT_COMMANDS.md` — Full import command reference
- `docs/GRAPH_RELATIONSHIPS.md` — Graph schema and edge semantics
- CelesTrak: https://celestrak.org/
- TLE format: https://celestrak.org/NORAD/documentation/tle-fmt.php
