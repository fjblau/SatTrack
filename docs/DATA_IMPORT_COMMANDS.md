# Data Import Quick Reference

All commands to import and manage satellite data in Kessler (ArangoDB backend).

## Prerequisites

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Ensure ArangoDB is running
curl http://localhost:8529/_api/version  # Should return {"server":"arango","version":"..."}

# 3. Set connection env vars (or use defaults)
export ARANGO_HOST=http://localhost:8529
export ARANGO_USER=root
export ARANGO_PASSWORD=kessler_dev_password

# 4. Ensure API is running (in another terminal)
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

## ArangoDB Quick Start (Docker)

```bash
docker run -d \
  --name arangodb \
  -p 8529:8529 \
  -e ARANGO_ROOT_PASSWORD=kessler_dev_password \
  arangodb:latest
```

Web UI available at http://localhost:8529 (user: `root`, password: `kessler_dev_password`).

## Import Workflows

### Fresh Setup (Recommended)

```bash
# 1. Import UNOOSA/GCAT satellite registry
python3 scripts/import/import_gcat_bulk.py

# 2. Add CelesTrak TLE orbital data
python3 scripts/import/import_tle_api.py

# 3. Populate graph edge collections
python3 scripts/population/populate_orbital_proximity.py
python3 scripts/population/populate_collision_risks.py
python3 scripts/population/populate_constellation_network.py
python3 scripts/population/populate_registration_network.py
python3 scripts/population/populate_satellite_lineage.py
```

### Observations (Optional)

```bash
# Import SatNOGS health observations
python3 scripts/import/import_satnogs_status.py

# Link observations to satellites and sources
python3 scripts/population/populate_observation_edges.py
```

### Supplemental Sources

```bash
# Space-Track TLE data (requires Space-Track account)
python3 scripts/import/import_spacetrack_tle.py

# Kaggle satellite catalog
python3 scripts/import/import_kaggle_catalog_arango.py
```

## Command Reference

### Registry Import

```bash
# UNOOSA/GCAT bulk import
python3 scripts/import/import_gcat_bulk.py
```

Reads the GCAT satellite catalog and creates envelope documents in the `satellites` collection.

### TLE Import

```bash
# CelesTrak TLE (fetches from live API)
python3 scripts/import/import_tle_api.py
```

Fetches TLE files from CelesTrak and merges orbital elements into existing satellite documents.

### Backup & Restore

```bash
# Export current ArangoDB data to JSON
python3 scripts/import/export_arangodb.py

# Restore from exported JSON dump
python3 scripts/import/import_arangodb_data.py
```

## Verification

### Check ArangoDB Connection

```bash
python3 -c "
from database.connection import connect_arangodb, db
if connect_arangodb():
    print('Connected. Collections:', db.collections())
else:
    print('Connection failed')
"
```

### Count Satellites

```bash
python3 -c "
from database.connection import connect_arangodb, db
connect_arangodb()
count = db.aql.execute('RETURN LENGTH(satellites)').next()
print(f'Total satellites: {count}')
"
```

### Query via AQL

```bash
# Using arangosh (if installed)
arangosh --server.endpoint tcp://localhost:8529 \
  --server.username root \
  --server.password kessler_dev_password \
  --javascript.execute-string "db._query('FOR s IN satellites LIMIT 3 RETURN s.identifier').toArray()"
```

### List Edge Counts

```bash
python3 -c "
from database.connection import connect_arangodb, db
connect_arangodb()
edges = ['constellation_membership','orbital_proximity','collision_risk_edges','satellite_lineage','registration_links']
for e in edges:
    try:
        n = db.aql.execute(f'RETURN LENGTH({e})').next()
        print(f'{e}: {n}')
    except Exception as ex:
        print(f'{e}: missing ({ex})')
"
```

## API Testing

### Health Check

```bash
curl http://localhost:8000/v2/ask/status | jq .
```

### Search Satellites

```bash
# Search by name
curl 'http://localhost:8000/v2/satellites?q=ISS&limit=5' | jq .

# Filter by country
curl 'http://localhost:8000/v2/satellites?country=Russian%20Federation&limit=5' | jq .

# Filter by status
curl 'http://localhost:8000/v2/satellites?status=in%20orbit&limit=10' | jq .
```

### AQL Editor (AI-assisted)

```bash
curl -X POST http://localhost:8000/v2/aql \
  -H 'Content-Type: application/json' \
  -d '{"question": "Show the 10 satellites with highest collision risk"}' | jq .
```

### Direct AQL Execution

```bash
curl -X POST http://localhost:8000/v2/graph/aql \
  -H 'Content-Type: application/json' \
  -d '{"query": "FOR s IN satellites FILTER s.canonical.status == '\''in orbit'\'' LIMIT 5 RETURN s.canonical.satellite_name"}' | jq .
```

## Scheduled Updates

### Set Up Daily TLE Update (macOS/Linux)

```bash
crontab -e
# Add (runs daily at 2 AM):
0 2 * * * cd /path/to/kessler && python3 scripts/import/import_tle_api.py >> /tmp/kessler-tle.log 2>&1
```

## Troubleshooting

### ArangoDB Not Running

```bash
# Check if running
docker ps | grep arangodb

# Start via Docker
docker start arangodb

# Or start natively (if installed)
arangod --database.directory /var/lib/arangodb3
```

### Import Fails — Connection Refused

```bash
# Verify ArangoDB is reachable
curl http://localhost:8529/_api/version

# Check env vars
echo $ARANGO_HOST $ARANGO_USER
```

### Missing Collections

If graph edge collections are absent, re-run the population scripts:

```bash
python3 scripts/population/populate_orbital_proximity.py
python3 scripts/population/populate_collision_risks.py
```

### AQL Syntax Errors

Use the AQL Editor in the Web UI (http://localhost:8529) or the `/v2/graph/aql` endpoint to test queries interactively. The AI agent (`/v2/aql`) can also generate and auto-retry corrected queries.

## Database Maintenance

### Backup (Docker volume)

```bash
docker exec arangodb arangodump \
  --server.password kessler_dev_password \
  --output-directory /tmp/kessler-backup
docker cp arangodb:/tmp/kessler-backup ./backup
```

### Restore

```bash
docker cp ./backup arangodb:/tmp/kessler-backup
docker exec arangodb arangorestore \
  --server.password kessler_dev_password \
  --input-directory /tmp/kessler-backup
```

## Performance Notes

| Operation | Approximate Time | Notes |
|-----------|-----------------|-------|
| GCAT bulk import (5000+ docs) | ~10 seconds | Batch upsert |
| CelesTrak TLE merge | ~30 seconds | Network dependent |
| Orbital proximity population | 1–5 minutes | Pairwise calculation |
| Collision risk population | 2–10 minutes | Depends on dataset size |
| AQL query (indexed) | <100 ms | With persistent indexes |

## Complete Setup Checklist

- [ ] ArangoDB running and reachable at port 8529
- [ ] Python 3.11+ with `python-arango` installed
- [ ] Import UNOOSA/GCAT registry: `scripts/import/import_gcat_bulk.py`
- [ ] Import TLE data: `scripts/import/import_tle_api.py`
- [ ] Populate graph edges (population scripts)
- [ ] API running: `python -m uvicorn api.main:app --port 8000`
- [ ] Test API: `curl http://localhost:8000/v2/ask/status`
- [ ] Schedule periodic TLE updates via cron (optional)

## References

- `docs/MULTI_SOURCE_DATA_ARCHITECTURE.md` — Envelope pattern and data model
- `docs/GRAPH_RELATIONSHIPS.md` — Graph schema and edge semantics
- `docs/LANGGRAPH_AGENT_ARCHITECTURE.md` — AI query agent
- `ARCHITECTURE.md` — Full system architecture
