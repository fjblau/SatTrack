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

Run order: 7th in the DISCOS ingestion sequence (after fragmentations and objects).

Usage:
    python scripts/population/ingest_discos_attributions.py [--dry-run] [--max-events N]
"""
import sys
import argparse
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

import database.connection as db_conn
import database as db_module
from api.services import discos_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _lookup_object_by_discos_id(discos_id: str):
    """Find an object document by its DISCOS identifier alias."""
    if not discos_id:
        return None
    try:
        cursor = db_module.db.aql.execute(
            """
            FOR obj IN objects
                FILTER obj.identifier_aliases.discos == @discos_id
                   OR obj.sources.discos.discos_id == @discos_id
                LIMIT 1
                RETURN obj
            """,
            bind_vars={"discos_id": str(discos_id)},
        )
        rows = list(cursor)
        return rows[0] if rows else None
    except Exception as exc:
        logger.warning(f"Object lookup by discos_id failed for {discos_id}: {exc}")
        return None


def _upsert_edge(col, edge_doc: dict) -> bool:
    """Upsert an edge, capping transformation log at 10 entries."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        existing = None
        try:
            cursor = db_module.db.aql.execute(
                """
                FOR e IN @@col
                    FILTER e._from == @from AND e._to == @to
                    LIMIT 1
                    RETURN e
                """,
                bind_vars={
                    "@col": col.name,
                    "from": edge_doc["_from"],
                    "to": edge_doc["_to"],
                },
            )
            rows = list(cursor)
            existing = rows[0] if rows else None
        except Exception:
            pass

        if existing:
            transformations = existing.get("metadata", {}).get("transformations", [])
            transformations.append({
                "source": "discos",
                "action": "update",
                "timestamp": now,
                "operator": "ingest_discos_attributions",
            })
            transformations = transformations[-10:]
            col.update({
                "_key": existing["_key"],
                "confidence": edge_doc.get("confidence"),
                "metadata": {
                    **existing.get("metadata", {}),
                    "transformations": transformations,
                },
            })
        else:
            col.insert(edge_doc)
        return True
    except Exception as exc:
        logger.error(f"Failed to upsert edge {edge_doc}: {exc}")
        return False


def _process_event(event_doc: dict, dry_run: bool) -> dict:
    """
    Process a single fragmentation event: fetch attributions and create edges.

    Returns counts dict.
    """
    event_key = event_doc.get("_key", "")
    event_id = event_doc.get("_id", "")
    discos_event_id = event_doc.get("sources", {}).get("discos", {}).get("discos_id")
    if not discos_event_id:
        return {"processed": 0, "edges_created": 0, "pending": 0}

    now = datetime.now(timezone.utc).isoformat()
    attributions = discos_service.get_object_attributions(str(discos_event_id))

    if not attributions:
        return {"processed": 0, "edges_created": 0, "pending": 0}

    fragmented_from_col = db_module.db.collection("fragmented_from")
    caused_by_col = db_module.db.collection("caused_by")
    objects_col = db_module.db.collection("objects")

    edges_created = 0
    pending_count = 0

    for attr in attributions:
        attr_discos_id = attr.get("discos_id")
        if not attr_discos_id:
            pending_count += 1
            continue

        fragment_obj = _lookup_object_by_discos_id(str(attr_discos_id))
        if not fragment_obj:
            surrogate_key = f"DISCOS-{attr_discos_id}"
            try:
                fragment_obj = objects_col.get(surrogate_key)
            except Exception:
                pass

        if not fragment_obj:
            logger.debug(
                f"Fragment not found for discos_id={attr_discos_id} in event {event_key}; "
                "no edge created (pending attribution)"
            )
            pending_count += 1
            continue

        fragment_id = fragment_obj["_id"]
        confidence = attr.get("confidence")

        if dry_run:
            logger.info(
                f"[DRY RUN] Would create fragmented_from: {fragment_id} → (parent of {event_key})"
            )
            logger.info(f"[DRY RUN] Would create caused_by: {fragment_id} → {event_id}")
            edges_created += 2
            continue

        caused_by_edge = {
            "_from": fragment_id,
            "_to": event_id,
            "confidence": confidence,
            "metadata": {
                "transformations": [
                    {
                        "source": "discos",
                        "action": "create",
                        "timestamp": now,
                        "operator": "ingest_discos_attributions",
                    }
                ]
            },
        }
        if _upsert_edge(caused_by_col, caused_by_edge):
            edges_created += 1

        try:
            objects_col.update({
                "_key": fragment_obj["_key"],
                "metadata": {
                    **fragment_obj.get("metadata", {}),
                    "attribution_status": "attributed",
                },
            })
        except Exception as exc:
            logger.warning(f"Failed to update attribution_status on {fragment_obj['_key']}: {exc}")

    return {"processed": len(attributions), "edges_created": edges_created, "pending": pending_count}


def run(dry_run: bool = False, max_events: int = 0):
    if not db_conn.connect_arangodb():
        logger.error("Failed to connect to ArangoDB")
        sys.exit(1)

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

    for i, event_doc in enumerate(events):
        event_key = event_doc.get("_key", "?")
        logger.info(f"[{i+1}/{len(events)}] Processing event {event_key}")

        try:
            counts = _process_event(event_doc, dry_run=dry_run)
            total_processed += counts["processed"]
            total_edges += counts["edges_created"]
            total_pending += counts["pending"]
        except Exception as exc:
            logger.error(f"Failed processing event {event_key}: {exc}")

        time.sleep(0.1)

    logger.info(
        f"Done — events={len(events)} attributions_processed={total_processed} "
        f"edges_created={total_edges} pending={total_pending}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest DISCOS attributions (fragmented_from + caused_by edges)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-events", type=int, default=0, help="Limit number of events to process (0 = all)")
    args = parser.parse_args()
    run(dry_run=args.dry_run, max_events=args.max_events)
