# Kessler Graph Relationships

This document describes all graph relationships (edges) tracked in the Kessler ArangoDB database.

---

## Named Graphs

Kessler maintains two named ArangoDB graphs.

### Graph 1: `satellite_relationships`

Connects satellites to each other and to registration documents.

**Vertex collections:** `satellites`, `registration_documents`

**Edge collections:**

| Edge Collection | From | To | Meaning |
|----------------|------|----|---------|
| `constellation_membership` | `satellites` | `satellites` | A satellite belongs to a named constellation |
| `registration_links` | `satellites` | `registration_documents` | A satellite is registered under a UN document |
| `orbital_proximity` | `satellites` | `satellites` | Two satellites share a close orbit (within ±50 km apogee/perigee, ±5° inclination) |
| `collision_risk_edges` | `satellites` | `satellites` | Two satellites have a computed collision risk — edge stores risk score and minimum distance |
| `satellite_lineage` | `satellites` | `satellites` | One satellite is a predecessor or successor of another |

---

### Graph 2: `observation_relationships`

Connects observational records to the satellites they track and to their data sources.

**Vertex collections:** `observations`, `satellites`, `observation_sources`

**Edge collections:**

| Edge Collection | From | To | Meaning |
|----------------|------|----|---------|
| `observation_satellite_edges` | `observations` | `satellites` | An observation record tracks a specific satellite |
| `observation_source_edges` | `observations` | `observation_sources` | An observation was reported by a specific data source |
| `observation_correlation_edges` | `observations` | `observations` | Two observations are correlated (same source, band, or characteristics) |
| `observation_temporal_edges` | `observations` | `observations` | Sequential observations of the same satellite over time (health chain) |

---

## All Collections Summary

### Vertex (Document) Collections

| Collection | Contents |
|-----------|----------|
| `satellites` | Primary satellite registry — UNOOSA/NORAD records with orbital and canonical data |
| `registration_documents` | UN registration document metadata |
| `observations` | Observational records — health score, mass, spin rate, thermal anomaly flag |
| `observation_sources` | Metadata about sources that submit observation data |
| `mqtt_configurations` | MQTT broker configurations for TLE publishing |

### Edge Collections (all relationships)

| Collection | Graph | Purpose |
|-----------|-------|---------|
| `constellation_membership` | satellite_relationships | Satellite → constellation |
| `registration_links` | satellite_relationships | Satellite → UN document |
| `orbital_proximity` | satellite_relationships | Close-orbit satellite pairs |
| `collision_risk_edges` | satellite_relationships | High-risk orbital proximity pairs |
| `satellite_lineage` | satellite_relationships | Satellite predecessor/successor chains |
| `observation_satellite_edges` | observation_relationships | Observation → satellite |
| `observation_source_edges` | observation_relationships | Observation → data source |
| `observation_correlation_edges` | observation_relationships | Correlated observations |
| `observation_temporal_edges` | observation_relationships | Time-ordered observation chain |

---

## Example AQL Queries

### Find all satellites in a constellation
```aql
FOR v, e IN 1..1 OUTBOUND "satellites/25544" constellation_membership
  RETURN v.canonical.name
```

### Find satellites with collision risk
```aql
FOR v, e IN 1..1 ANY "satellites/2023-001A" collision_risk_edges
  FILTER e.risk_score > 0.7
  RETURN { satellite: v.canonical.name, risk: e.risk_score, distance_km: e.min_distance_km }
```

### Find observation health chain for a satellite
```aql
FOR v, e IN 1..5 OUTBOUND "observations/some-key" observation_temporal_edges
  RETURN { epoch: v.observation_epoch, health: v.derived_health_score }
```

### Find all satellites registered under a UN document
```aql
FOR v, e IN 1..1 INBOUND "registration_documents/A-AC-105-INF-123" registration_links
  RETURN v.canonical.name
```
