"""
Observation graph operations — builds and queries observation edge collections in ArangoDB.

Edge collections:
  - observation_satellite_edges: observation -> satellite
  - observation_source_edges: observation -> observation_sources vertex
  - observation_correlation_edges: observation <-> observation (anomaly co-occurrence / temporal proximity)
  - observation_temporal_edges: observation -> observation (sequential chain per satellite)
"""

import database as db_module
from database.connection import (
    COLLECTION_OBSERVATIONS,
    COLLECTION_OBSERVATION_SOURCES,
    COLLECTION_NAME,
    EDGE_COLLECTION_OBS_SATELLITE,
    EDGE_COLLECTION_OBS_SOURCE,
    EDGE_COLLECTION_OBS_CORRELATION,
    EDGE_COLLECTION_OBS_TEMPORAL,
)


def _get_db():
    db = db_module.db
    if db is None:
        raise RuntimeError("Database not connected")
    return db


# ---------------------------------------------------------------------------
# Edge population
# ---------------------------------------------------------------------------

def populate_observation_satellite_edges(batch_size: int = 1000):
    """Create edges from each observation to its parent satellite (by norad_id)."""
    db = _get_db()
    edge_col = db.collection(EDGE_COLLECTION_OBS_SATELLITE)

    # First build a norad_id -> satellite _id/_key lookup
    sat_cursor = db.aql.execute(
        """
        FOR s IN @@satellites
            FILTER s.canonical.norad_cat_id != null
            RETURN { norad_id: s.canonical.norad_cat_id, _id: s._id, _key: s._key }
        """,
        bind_vars={"@satellites": COLLECTION_NAME},
    )
    sat_map = {r["norad_id"]: r for r in sat_cursor}

    # Then iterate observations in pages
    inserted = 0
    skipped = 0
    offset = 0
    while True:
        obs_cursor = db.aql.execute(
            """
            FOR obs IN @@observations
                LIMIT @offset, @batch
                RETURN { _key: obs._key, _id: obs._id, norad_id: obs.norad_id, observation_epoch: obs.observation_epoch, source: obs.source }
            """,
            bind_vars={"@observations": COLLECTION_OBSERVATIONS, "offset": offset, "batch": batch_size},
        )
        rows = list(obs_cursor)
        if not rows:
            break

        edges = []
        for obs in rows:
            sat = sat_map.get(obs["norad_id"])
            if sat:
                edges.append({
                    "_key": f"{obs['_key']}_{sat['_key']}",
                    "_from": obs["_id"],
                    "_to": sat["_id"],
                    "norad_id": obs["norad_id"],
                    "observation_epoch": obs.get("observation_epoch"),
                    "source": obs.get("source"),
                })

        if edges:
            result = edge_col.import_bulk(edges, on_duplicate="ignore")
            inserted += result.get("created", 0)
            skipped += result.get("ignored", 0)

        offset += batch_size

    return {"inserted": inserted, "skipped": skipped}


def populate_observation_source_edges(batch_size: int = 1000):
    """Create source vertex documents and edges from observations to their sources."""
    import hashlib as _hashlib

    db = _get_db()
    source_col = db.collection(COLLECTION_OBSERVATION_SOURCES)
    edge_col = db.collection(EDGE_COLLECTION_OBS_SOURCE)

    # Collect distinct sources first
    src_cursor = db.aql.execute(
        "FOR obs IN @@observations COLLECT source = obs.source FILTER source != null RETURN source",
        bind_vars={"@observations": COLLECTION_OBSERVATIONS},
    )
    sources = list(src_cursor)

    # Upsert source vertices
    for source_name in sources:
        source_key = _hashlib.md5(source_name.encode()).hexdigest()
        try:
            source_col.insert({"_key": source_key, "name": source_name, "type": "source"})
        except Exception:
            pass  # already exists

    # Create edges in pages
    inserted = 0
    skipped = 0
    offset = 0
    while True:
        obs_cursor = db.aql.execute(
            """
            FOR obs IN @@observations
                FILTER obs.source != null
                LIMIT @offset, @batch
                RETURN { _key: obs._key, _id: obs._id, source: obs.source, observation_epoch: obs.observation_epoch, health_score: obs.derived_health_score }
            """,
            bind_vars={"@observations": COLLECTION_OBSERVATIONS, "offset": offset, "batch": batch_size},
        )
        rows = list(obs_cursor)
        if not rows:
            break

        edges = []
        for obs in rows:
            source_key = _hashlib.md5(obs["source"].encode()).hexdigest()
            edges.append({
                "_key": f"{obs['_key']}_{source_key}",
                "_from": obs["_id"],
                "_to": f"{COLLECTION_OBSERVATION_SOURCES}/{source_key}",
                "source_name": obs["source"],
                "observation_epoch": obs.get("observation_epoch"),
                "health_score": obs.get("health_score"),
            })

        if edges:
            result = edge_col.import_bulk(edges, on_duplicate="ignore")
            inserted += result.get("created", 0)
            skipped += result.get("ignored", 0)

        offset += batch_size

    return {"inserted": inserted, "skipped": skipped}


def populate_observation_temporal_edges(batch_size: int = 1000):
    """Create sequential edges between consecutive observations of the same satellite."""
    db = _get_db()
    edge_col = db.collection(EDGE_COLLECTION_OBS_TEMPORAL)

    # Get distinct norad_ids that have observations
    id_cursor = db.aql.execute(
        "FOR obs IN @@observations COLLECT norad_id = obs.norad_id WITH COUNT INTO cnt FILTER cnt > 1 RETURN norad_id",
        bind_vars={"@observations": COLLECTION_OBSERVATIONS},
    )
    norad_ids = list(id_cursor)

    inserted = 0
    skipped = 0

    # Process each satellite's observations independently
    for norad_id in norad_ids:
        obs_cursor = db.aql.execute(
            """
            FOR obs IN @@observations
                FILTER obs.norad_id == @norad_id
                SORT obs.observation_epoch ASC
                RETURN { _key: obs._key, _id: obs._id, observation_epoch: obs.observation_epoch, health: obs.derived_health_score }
            """,
            bind_vars={"@observations": COLLECTION_OBSERVATIONS, "norad_id": norad_id},
        )
        obs_list = list(obs_cursor)

        edges = []
        for i in range(len(obs_list) - 1):
            prev = obs_list[i]
            nxt = obs_list[i + 1]
            prev_h = prev.get("health")
            nxt_h = nxt.get("health")
            edges.append({
                "_key": f"{prev['_key']}_{nxt['_key']}",
                "_from": prev["_id"],
                "_to": nxt["_id"],
                "norad_id": norad_id,
                "from_epoch": prev["observation_epoch"],
                "to_epoch": nxt["observation_epoch"],
                "health_delta": (nxt_h - prev_h) if (nxt_h is not None and prev_h is not None) else None,
            })

        if edges:
            result = edge_col.import_bulk(edges, on_duplicate="ignore")
            inserted += result.get("created", 0)
            skipped += result.get("ignored", 0)

    return {"inserted": inserted, "skipped": skipped}


def populate_observation_correlation_edges(
    time_window_hours: int = 24,
    batch_size: int = 1000,
):
    """Create edges between observations that share anomaly co-occurrence within a time window.

    Done in Python to avoid O(n^2) AQL execution on remote DB.
    """
    from datetime import datetime as _dt, timedelta

    db = _get_db()
    edge_col = db.collection(EDGE_COLLECTION_OBS_CORRELATION)

    # Fetch all anomalous observations (typically a small subset)
    cursor = db.aql.execute(
        """
        FOR obs IN @@observations
            FILTER obs.thermal.anomaly_flag == true
            SORT obs.observation_epoch ASC
            RETURN { _key: obs._key, _id: obs._id, norad_id: obs.norad_id, epoch: obs.observation_epoch }
        """,
        bind_vars={"@observations": COLLECTION_OBSERVATIONS},
    )
    anomalous = list(cursor)

    def _parse_epoch(s):
        try:
            return _dt.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None

    inserted = 0
    skipped = 0
    edges = []

    for i in range(len(anomalous)):
        a = anomalous[i]
        a_dt = _parse_epoch(a["epoch"])
        if a_dt is None:
            continue
        for j in range(i + 1, len(anomalous)):
            b = anomalous[j]
            if a["norad_id"] == b["norad_id"]:
                continue
            b_dt = _parse_epoch(b["epoch"])
            if b_dt is None:
                continue
            diff_hours = abs((a_dt - b_dt).total_seconds()) / 3600
            if diff_hours > time_window_hours:
                # Since sorted by epoch, once we pass the window, later items will be even further
                if b_dt > a_dt:
                    break
                continue

            key_parts = sorted([a["_key"], b["_key"]])
            edges.append({
                "_key": f"{key_parts[0]}_{key_parts[1]}",
                "_from": a["_id"],
                "_to": b["_id"],
                "correlation_type": "anomaly_co_occurrence",
                "time_diff_hours": round(diff_hours, 1),
                "norad_ids": [a["norad_id"], b["norad_id"]],
            })

            if len(edges) >= batch_size:
                result = edge_col.import_bulk(edges, on_duplicate="ignore")
                inserted += result.get("created", 0)
                skipped += result.get("ignored", 0)
                edges = []

    if edges:
        result = edge_col.import_bulk(edges, on_duplicate="ignore")
        inserted += result.get("created", 0)
        skipped += result.get("ignored", 0)

    return {"inserted": inserted, "skipped": skipped}


def populate_all_observation_edges(time_window_hours: int = 24, batch_size: int = 1000):
    """Run all four edge population steps and return combined results."""
    results = {}
    results["satellite_edges"] = populate_observation_satellite_edges(batch_size)
    results["source_edges"] = populate_observation_source_edges(batch_size)
    results["temporal_edges"] = populate_observation_temporal_edges(batch_size)
    results["correlation_edges"] = populate_observation_correlation_edges(time_window_hours, batch_size)
    return results


# ---------------------------------------------------------------------------
# Auto-populate edges for a single observation (called on import)
# ---------------------------------------------------------------------------

def create_edges_for_observation(obs_doc: dict):
    """Create satellite and source edges for a single newly-imported observation.

    Called inline during observation import for real-time edge creation.
    obs_doc must include _id, _key, norad_id, source, observation_epoch.
    """
    db = _get_db()

    # satellite edge
    sat_cursor = db.aql.execute(
        """
        FOR s IN @@satellites
            FILTER s.canonical.norad_cat_id == @norad_id
            LIMIT 1
            RETURN s
        """,
        bind_vars={"@satellites": COLLECTION_NAME, "norad_id": obs_doc["norad_id"]},
    )
    sat = next(sat_cursor, None)
    if sat:
        edge_col = db.collection(EDGE_COLLECTION_OBS_SATELLITE)
        edge_key = f"{obs_doc['_key']}_{sat['_key']}"
        try:
            edge_col.insert({
                "_key": edge_key,
                "_from": obs_doc["_id"],
                "_to": sat["_id"],
                "norad_id": obs_doc["norad_id"],
                "observation_epoch": obs_doc.get("observation_epoch"),
                "source": obs_doc.get("source"),
            })
        except Exception:
            pass  # duplicate edge, ignore

    # source edge
    if obs_doc.get("source"):
        import hashlib
        source_key = hashlib.md5(obs_doc["source"].encode()).hexdigest()
        source_col = db.collection(COLLECTION_OBSERVATION_SOURCES)
        try:
            source_col.insert({
                "_key": source_key,
                "name": obs_doc["source"],
                "type": "source",
            })
        except Exception:
            pass  # already exists

        edge_col = db.collection(EDGE_COLLECTION_OBS_SOURCE)
        edge_key = f"{obs_doc['_key']}_{source_key}"
        try:
            edge_col.insert({
                "_key": edge_key,
                "_from": obs_doc["_id"],
                "_to": f"{COLLECTION_OBSERVATION_SOURCES}/{source_key}",
                "source_name": obs_doc["source"],
                "observation_epoch": obs_doc.get("observation_epoch"),
                "health_score": obs_doc.get("derived_health_score"),
            })
        except Exception:
            pass

    # temporal edge — link to previous observation of same satellite
    prev_cursor = db.aql.execute(
        """
        FOR obs IN @@observations
            FILTER obs.norad_id == @norad_id
            FILTER obs.observation_epoch < @epoch
            SORT obs.observation_epoch DESC
            LIMIT 1
            RETURN obs
        """,
        bind_vars={
            "@observations": COLLECTION_OBSERVATIONS,
            "norad_id": obs_doc["norad_id"],
            "epoch": obs_doc["observation_epoch"],
        },
    )
    prev = next(prev_cursor, None)
    if prev:
        edge_col = db.collection(EDGE_COLLECTION_OBS_TEMPORAL)
        edge_key = f"{prev['_key']}_{obs_doc['_key']}"
        prev_health = prev.get("derived_health_score")
        obs_health = obs_doc.get("derived_health_score")
        try:
            edge_col.insert({
                "_key": edge_key,
                "_from": prev["_id"],
                "_to": obs_doc["_id"],
                "norad_id": obs_doc["norad_id"],
                "from_epoch": prev["observation_epoch"],
                "to_epoch": obs_doc["observation_epoch"],
                "health_delta": (obs_health - prev_health) if (obs_health is not None and prev_health is not None) else None,
            })
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Graph query functions (return Cytoscape-compatible format)
# ---------------------------------------------------------------------------

def get_source_reliability_network(min_observations: int = 5, limit: int = 100):
    """Build a source reliability network: sources connected to satellites, weighted by observation count and avg health."""
    db = _get_db()

    cursor = db.aql.execute(
        """
        FOR edge IN @@obs_sat_edges
            LET obs = DOCUMENT(edge._from)
            LET sat = DOCUMENT(edge._to)
            FILTER obs != null AND sat != null
            COLLECT source_name = obs.source, sat_id = sat._id, sat_name = sat.canonical.name, sat_key = sat._key, norad = obs.norad_id
            AGGREGATE obs_count = LENGTH(1), avg_health = AVERAGE(obs.derived_health_score)
            FILTER obs_count >= @min_obs
            SORT obs_count DESC
            LIMIT @limit
            RETURN {
                source_name,
                sat_id, sat_name, sat_key, norad,
                obs_count, avg_health
            }
        """,
        bind_vars={
            "@obs_sat_edges": EDGE_COLLECTION_OBS_SATELLITE,
            "min_obs": min_observations,
            "limit": limit,
        },
    )
    rows = list(cursor)

    # Build Cytoscape nodes and edges
    source_nodes = {}
    sat_nodes = {}
    edges = []

    for row in rows:
        src_id = f"source/{row['source_name']}"
        if src_id not in source_nodes:
            source_nodes[src_id] = {
                "id": src_id,
                "name": row["source_name"],
                "type": "source",
                "background_color": "#e67e22",
                "node_size": 40,
            }

        sat_id = row["sat_id"]
        if sat_id not in sat_nodes:
            sat_nodes[sat_id] = {
                "id": sat_id,
                "name": row["sat_name"] or str(row["norad"]),
                "type": "satellite",
                "background_color": "#2ecc71",
                "node_size": 30,
                "norad_id": row["norad"],
            }

        edges.append({
            "id": f"e_{row['source_name']}_{row['sat_key']}",
            "source": src_id,
            "target": sat_id,
            "type": "observed_by",
            "weight": row["obs_count"],
            "avg_health": row["avg_health"],
            "edge_label": str(row["obs_count"]),
            "edge_width": min(max(row["obs_count"] / 5, 1), 8),
        })

    return {
        "nodes": list(source_nodes.values()) + list(sat_nodes.values()),
        "edges": edges,
        "stats": {
            "total_nodes": len(source_nodes) + len(sat_nodes),
            "total_edges": len(edges),
            "source_count": len(source_nodes),
            "satellite_count": len(sat_nodes),
        },
    }


def get_temporal_chain(norad_id: int, limit: int = 50):
    """Get a temporal observation chain for a satellite — sequential observations linked over time."""
    db = _get_db()

    cursor = db.aql.execute(
        """
        FOR edge IN @@temporal_edges
            FILTER edge.norad_id == @norad_id
            SORT edge.from_epoch ASC
            LIMIT @limit
            LET from_obs = DOCUMENT(edge._from)
            LET to_obs = DOCUMENT(edge._to)
            RETURN {
                edge: edge,
                from_obs: from_obs,
                to_obs: to_obs
            }
        """,
        bind_vars={
            "@temporal_edges": EDGE_COLLECTION_OBS_TEMPORAL,
            "norad_id": norad_id,
            "limit": limit,
        },
    )
    rows = list(cursor)

    nodes = {}
    edges = []

    for row in rows:
        fo = row["from_obs"]
        to = row["to_obs"]
        if fo and fo["_id"] not in nodes:
            health = fo.get("derived_health_score")
            color = _health_color(health)
            nodes[fo["_id"]] = {
                "id": fo["_id"],
                "name": fo.get("observation_epoch", "")[:16],
                "type": "observation",
                "background_color": color,
                "health_score": health,
                "source": fo.get("source"),
                "node_size": 30,
            }
        if to and to["_id"] not in nodes:
            health = to.get("derived_health_score")
            color = _health_color(health)
            nodes[to["_id"]] = {
                "id": to["_id"],
                "name": to.get("observation_epoch", "")[:16],
                "type": "observation",
                "background_color": color,
                "health_score": health,
                "source": to.get("source"),
                "node_size": 30,
            }

        edge = row["edge"]
        delta = edge.get("health_delta")
        edges.append({
            "id": edge["_id"],
            "source": edge["_from"],
            "target": edge["_to"],
            "type": "temporal_sequence",
            "health_delta": delta,
            "edge_label": f"{delta:+.1f}" if delta is not None else "",
            "edge_color": "#e74c3c" if (delta is not None and delta < -5) else "#2ecc71" if (delta is not None and delta > 5) else "#95a5a6",
            "edge_width": 2,
        })

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "stats": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "norad_id": norad_id,
        },
    }


def get_anomaly_correlation_network(limit: int = 100):
    """Get the anomaly co-occurrence network — satellites linked by simultaneous anomalies."""
    db = _get_db()

    cursor = db.aql.execute(
        """
        FOR edge IN @@corr_edges
            LIMIT @limit
            LET from_obs = DOCUMENT(edge._from)
            LET to_obs = DOCUMENT(edge._to)
            RETURN {
                edge: edge,
                from_obs: from_obs,
                to_obs: to_obs
            }
        """,
        bind_vars={
            "@corr_edges": EDGE_COLLECTION_OBS_CORRELATION,
            "limit": limit,
        },
    )
    rows = list(cursor)

    # Aggregate to satellite-level view
    sat_pairs = {}
    for row in rows:
        fo = row["from_obs"]
        to = row["to_obs"]
        if not fo or not to:
            continue
        pair_key = tuple(sorted([fo["norad_id"], to["norad_id"]]))
        if pair_key not in sat_pairs:
            sat_pairs[pair_key] = {
                "norad_a": pair_key[0],
                "norad_b": pair_key[1],
                "name_a": fo.get("object_name") or str(pair_key[0]),
                "name_b": to.get("object_name") or str(pair_key[1]),
                "co_occurrences": 0,
                "avg_time_diff": 0,
            }
        sat_pairs[pair_key]["co_occurrences"] += 1
        sat_pairs[pair_key]["avg_time_diff"] += row["edge"].get("time_diff_hours", 0)

    nodes = {}
    edges = []
    for pair in sat_pairs.values():
        pair["avg_time_diff"] /= max(pair["co_occurrences"], 1)
        for prefix, norad, name in [("a", pair["norad_a"], pair["name_a"]), ("b", pair["norad_b"], pair["name_b"])]:
            nid = f"sat/{norad}"
            if nid not in nodes:
                nodes[nid] = {
                    "id": nid,
                    "name": name,
                    "type": "satellite",
                    "norad_id": norad,
                    "background_color": "#e74c3c",
                    "node_size": 30 + min(pair["co_occurrences"] * 3, 20),
                }
        edges.append({
            "id": f"corr_{pair['norad_a']}_{pair['norad_b']}",
            "source": f"sat/{pair['norad_a']}",
            "target": f"sat/{pair['norad_b']}",
            "type": "anomaly_correlation",
            "co_occurrences": pair["co_occurrences"],
            "avg_time_diff_hours": round(pair["avg_time_diff"], 1),
            "edge_label": str(pair["co_occurrences"]),
            "edge_color": "#e74c3c",
            "edge_width": min(max(pair["co_occurrences"], 1), 6),
        })

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "stats": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "satellite_pairs": len(sat_pairs),
        },
    }


def get_observation_graph_stats():
    """Return counts for all observation edge collections."""
    db = _get_db()
    stats = {}
    for name, col_name in [
        ("satellite_edges", EDGE_COLLECTION_OBS_SATELLITE),
        ("source_edges", EDGE_COLLECTION_OBS_SOURCE),
        ("temporal_edges", EDGE_COLLECTION_OBS_TEMPORAL),
        ("correlation_edges", EDGE_COLLECTION_OBS_CORRELATION),
    ]:
        if db.has_collection(col_name):
            stats[name] = db.collection(col_name).count()
        else:
            stats[name] = 0

    if db.has_collection(COLLECTION_OBSERVATIONS):
        stats["observations"] = db.collection(COLLECTION_OBSERVATIONS).count()
    if db.has_collection(COLLECTION_OBSERVATION_SOURCES):
        stats["sources"] = db.collection(COLLECTION_OBSERVATION_SOURCES).count()

    return stats


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _health_color(score):
    if score is None:
        return "#95a5a6"
    if score >= 80:
        return "#2ecc71"
    if score >= 50:
        return "#f39c12"
    return "#e74c3c"
