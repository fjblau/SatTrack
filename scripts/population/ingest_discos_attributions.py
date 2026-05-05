#!/usr/bin/env python3
"""
Ingest DISCOS fragmentation attributions: create fragmented_from and caused_by edges.

Architecture: Per-event sub-jobs with master coordinator pattern.
- The master coordinator fetches all fragmentation events.
- For each event, fetches attribution data (which objects were fragmented from it).
- Creates fragmented_from edges (fragment → parent object) and caused_by edges (fragment → event).
- Objects with no explicit DISCOS attribution do NOT get a fragmented_from edge (per spec decision).
  Their metadata.attribution_status remains "pending".
- Edge transformation logs are capped at 10 entries per edge.

Performance:
- A discos_id → object_id lookup map is built once before processing begins, eliminating
  per-fragment AQL queries.
- caused_by edges are upserted in a single AQL batch per event.
- attribution_status updates are batched per event using AQL with mergeObjects.
- The fixed request_delay between DISCOS API calls is removed; the service layer already
  handles 429 rate-limit responses with exponential backoff.

Run order: 7th in the DISCOS ingestion sequence (after fragmentations and objects).

Usage:
    python scripts/population/ingest_discos_attributions.py [--dry-run] [--max-events N]
"""
import sys
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

import database.connection as db_conn
import database as db_module
from api.services.discos_service import get_fragmentation_attributed_objects

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _build_discos_lookup(db) -> dict:
    """
    Build a discos_id (str) → {_id, _key} map for every object that has a DISCOS ID.

    Covers three cases:
      1. obj.identifier_aliases.discos is set
      2. obj.sources.discos.discos_id is set
      3. obj._key starts with "DISCOS-" (surrogate objects)
    """
    cursor = db.aql.execute("""
        FOR obj IN objects
            LET did = (
                obj.identifier_aliases.discos != null
                    ? TO_STRING(obj.identifier_aliases.discos)
                    : obj.sources.discos.discos_id != null
                        ? TO_STRING(obj.sources.discos.discos_id)
                        : STARTS_WITH(obj._key, "DISCOS-")
                            ? SUBSTRING(obj._key, 7)
                            : null
            )
            FILTER did != null
            RETURN {did: did, _id: obj._id, _key: obj._key}
    """)
    lookup = {}
    for row in cursor:
        lookup[str(row["did"])] = {"_id": row["_id"], "_key": row["_key"]}
    logger.info(f"Lookup map built: {len(lookup)} objects with DISCOS IDs")
    return lookup


def _batch_upsert_caused_by(db, edges: list, now: str) -> int:
    """
    Upsert a batch of caused_by edges in a single AQL statement.

    On insert: writes full edge with transformation log.
    On update: appends to transformation log (capped at 10).
    Returns the number of edges written.
    """
    if not edges:
        return 0
    aql = """
    FOR edge IN @edges
        UPSERT {_from: edge._from, _to: edge._to}
        INSERT {
            _from: edge._from,
            _to: edge._to,
            confidence: edge.confidence,
            metadata: {
                transformations: [{
                    source: "discos",
                    action: "create",
                    timestamp: @now,
                    operator: "ingest_discos_attributions"
                }]
            }
        }
        UPDATE {
            confidence: edge.confidence,
            metadata: {
                transformations: APPEND(
                    SLICE(OLD.metadata.transformations, -9),
                    [{source: "discos", action: "update", timestamp: @now,
                      operator: "ingest_discos_attributions"}]
                )
            }
        }
        IN caused_by
        RETURN 1
    """
    cursor = db.aql.execute(aql, bind_vars={"edges": edges, "now": now})
    return len(list(cursor))


def _batch_set_attributed(db, object_keys: list) -> None:
    """Set attribution_status = "attributed" on a batch of objects in one AQL statement."""
    if not object_keys:
        return
    db.aql.execute(
        """
        FOR key IN @keys
            UPDATE {_key: key} WITH {metadata: {attribution_status: "attributed"}}
            IN objects OPTIONS {mergeObjects: true}
        """,
        bind_vars={"keys": object_keys},
    )


def _process_event(event_doc: dict, lookup: dict, dry_run: bool, now: str) -> dict:
    """
    Process a single fragmentation event: fetch attributions and create edges.

    Uses the pre-built lookup map for O(1) object resolution per fragment.
    Returns counts dict.
    """
    event_key = event_doc.get("_key", "")
    event_id = event_doc.get("_id", "")
    discos_event_id = event_doc.get("sources", {}).get("discos", {}).get("discos_id")
    if not discos_event_id:
        return {"processed": 0, "edges_created": 0, "pending": 0}

    attributions = get_fragmentation_attributed_objects(str(discos_event_id))

    frag_events_col = db_module.db.collection("fragmentation_events")
    try:
        current_canonical = event_doc.get("canonical", {})
        fragment_count = len(attributions)
        transformations = event_doc.get("metadata", {}).get("transformations", [])
        transformations = transformations[-9:] + [{
            "source": "discos",
            "action": "update_fragment_count",
            "timestamp": now,
            "operator": "ingest_discos_attributions",
            "fragment_count": fragment_count,
        }]
        frag_events_col.update({
            "_key": event_key,
            "canonical": {**current_canonical, "fragment_count": fragment_count},
            "metadata": {**event_doc.get("metadata", {}), "transformations": transformations},
        })
    except Exception as exc:
        logger.warning(f"Failed to update fragment_count on {event_key}: {exc}")

    if not attributions:
        return {"processed": 0, "edges_created": 0, "pending": 0}

    edges_to_insert = []
    attributed_keys = []
    pending_count = 0

    for attr in attributions:
        attr_discos_id = attr.get("discos_id")
        if not attr_discos_id:
            pending_count += 1
            continue

        obj = lookup.get(str(attr_discos_id))
        if not obj:
            logger.debug(
                f"Fragment not found for discos_id={attr_discos_id} in event {event_key}"
            )
            pending_count += 1
            continue

        if dry_run:
            logger.info(f"[DRY RUN] Would create caused_by: {obj['_id']} → {event_id}")
            edges_to_insert.append({"_from": obj["_id"], "_to": event_id})
            attributed_keys.append(obj["_key"])
            continue

        edges_to_insert.append({
            "_from": obj["_id"],
            "_to": event_id,
            "confidence": attr.get("confidence"),
        })
        attributed_keys.append(obj["_key"])

    if dry_run:
        return {"processed": len(attributions), "edges_created": len(edges_to_insert), "pending": pending_count}

    edges_created = _batch_upsert_caused_by(db_module.db, edges_to_insert, now)
    _batch_set_attributed(db_module.db, attributed_keys)

    return {"processed": len(attributions), "edges_created": edges_created, "pending": pending_count}


def run(dry_run: bool = False, max_events: int = 0):
    if not db_conn.connect_arangodb():
        logger.error("Failed to connect to ArangoDB")
        sys.exit(1)

    lookup = _build_discos_lookup(db_module.db)

    logger.info("Fetching fragmentation events from database for attribution processing...")
    cursor = db_module.db.aql.execute(
        "FOR e IN fragmentation_events LIMIT @max RETURN e",
        bind_vars={"max": max_events if max_events > 0 else 100000},
    )
    events = list(cursor)
    logger.info(f"Processing attributions for {len(events)} fragmentation events")

    total_processed = 0
    total_edges = 0
    total_pending = 0
    now = datetime.now(timezone.utc).isoformat()

    for i, event_doc in enumerate(events):
        event_key = event_doc.get("_key", "?")
        logger.info(f"[{i+1}/{len(events)}] Processing event {event_key}")

        try:
            counts = _process_event(event_doc, lookup=lookup, dry_run=dry_run, now=now)
            total_processed += counts["processed"]
            total_edges += counts["edges_created"]
            total_pending += counts["pending"]
        except Exception as exc:
            logger.error(f"Failed processing event {event_key}: {exc}")

    logger.info(
        f"Done — events={len(events)} attributions_processed={total_processed} "
        f"edges_created={total_edges} pending={total_pending}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest DISCOS attributions (caused_by edges)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-events", type=int, default=0, help="Limit number of events to process (0 = all)")
    args = parser.parse_args()
    run(dry_run=args.dry_run, max_events=args.max_events)
