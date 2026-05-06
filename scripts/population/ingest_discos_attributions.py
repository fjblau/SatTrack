#!/usr/bin/env python3
"""
Ingest DISCOS fragmentation attributions: create caused_by edges.

Self-completing: when the script processes an event and DISCOS reports fragments
attributed to it, those fragments are ingested into the objects collection as needed
(using ensure_discos_object_exists) before the edges are created. Running this script
for an event guarantees that every fragment DISCOS attributes to that event exists in
the objects collection with proper aliases, source envelopes, and edges.

Architecture: Per-event sub-jobs with master coordinator pattern.
- The master coordinator fetches all fragmentation events.
- For each event, fetches full fragment object payloads from DISCOS.
- Ensures each fragment exists in objects (match-or-create via shared helper).
- Creates caused_by edges (fragment → event).
- Objects with no explicit DISCOS attribution do NOT get a caused_by edge.

Idempotency:
- fragment_count_kessler is only updated when the value changes; no transformation is logged
  when the count is unchanged.
- ensure_discos_object_exists returns verified_unchanged for already-processed fragments,
  writing a verify transformation without re-ingesting data.
- caused_by edges are upserted — re-running produces no duplicate edges.

Resumability:
- If processing fails partway through an event, the next run picks up where it left off.
  Fragments already processed have sources.discos envelopes; ensure_discos_object_exists
  returns verified_unchanged for them and the edge upsert is idempotent.

Failure isolation:
- A single fragment failure (404, malformed payload, etc.) does not abort the event.
  The failure is logged with the fragment's DISCOS ID and reason.
  A summary of failed fragments is surfaced at the end of each event.

Performance:
- get_fragmentation_object_payloads_with_count tries the JSON:API related-resource endpoint
  (/fragmentations/{id}/objects) first. If DISCOS returns full records, no extra API calls
  are needed. If it returns identifier-only entries, a batch-fetch optimisation fetches full
  objects in groups of 100 via filter=in(id,...).
- caused_by edges are upserted in a single AQL batch per event.
- attribution_status updates are batched per event using AQL with mergeObjects.

Run order: 7th in the DISCOS ingestion sequence (after fragmentations).
Note: ingest_discos_objects is no longer a hard prerequisite; fragments are ingested
lazily by this script. Running ingest_discos_objects first is still useful for bulk
catalog presence but is not required for fragment provenance completeness.

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
from api.services.discos_service import get_fragmentation_object_payloads_with_count
from database.discos_object_operations import ensure_discos_object_exists

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


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


def _process_event(event_doc: dict, dry_run: bool, now: str) -> dict:
    """
    Process a single fragmentation event: fetch full fragment payloads, ensure each fragment
    exists in the objects collection, then create caused_by edges.

    Returns counts dict with keys: processed, edges_created, pending, failed.
    """
    event_key = event_doc.get("_key", "")
    event_id = event_doc.get("_id", "")
    discos_event_id = event_doc.get("sources", {}).get("discos", {}).get("discos_id")
    if not discos_event_id:
        return {"processed": 0, "edges_created": 0, "pending": 0, "failed": 0}

    fragment_payloads, total_count = get_fragmentation_object_payloads_with_count(str(discos_event_id))

    frag_events_col = db_module.db.collection("fragmentation_events")
    try:
        current_canonical = event_doc.get("canonical", {})
        kessler_count = len(fragment_payloads)
        existing_kessler = current_canonical.get("fragment_count_kessler")

        if kessler_count != existing_kessler:
            transformations = event_doc.get("metadata", {}).get("transformations", [])
            transformations = transformations[-9:] + [{
                "source": "discos",
                "action": "update_fragment_count",
                "timestamp": now,
                "operator": "ingest_discos_attributions",
                "fragment_count_kessler": kessler_count,
            }]
            frag_events_col.update({
                "_key": event_key,
                "canonical": {**current_canonical, "fragment_count_kessler": kessler_count},
                "metadata": {**event_doc.get("metadata", {}), "transformations": transformations},
            })
        else:
            logger.debug(f"fragment_count_kessler unchanged ({kessler_count}) for {event_key}; skipping log")
    except Exception as exc:
        logger.warning(f"Failed to update fragment_count_kessler on {event_key}: {exc}")

    if total_count is not None and len(fragment_payloads) != total_count:
        logger.warning(
            f"Pagination mismatch for {event_key}: DISCOS totalCount={total_count}, "
            f"local payloads fetched={len(fragment_payloads)}"
        )

    if not fragment_payloads:
        return {"processed": 0, "edges_created": 0, "pending": 0, "failed": 0}

    edges_to_insert = []
    attributed_keys = []
    failed_fragments = []

    for payload in fragment_payloads:
        frag_discos_id = payload.get("discos_id")

        if dry_run:
            logger.info(f"[DRY RUN] Would ensure fragment discos_id={frag_discos_id} and create caused_by edge → {event_id}")
            edges_to_insert.append({"_from": f"objects/DISCOS-{frag_discos_id}", "_to": event_id})
            attributed_keys.append(f"DISCOS-{frag_discos_id}")
            continue

        try:
            fragment_key, status = ensure_discos_object_exists(
                payload,
                db_module.db,
                operator="ingest_discos_attributions",
            )
            edges_to_insert.append({
                "_from": f"objects/{fragment_key}",
                "_to": event_id,
                "confidence": payload.get("confidence"),
            })
            attributed_keys.append(fragment_key)
        except Exception as exc:
            logger.warning(
                f"Failed to ensure fragment discos_id={frag_discos_id} for event {event_key}: {exc}"
            )
            failed_fragments.append({"discos_id": frag_discos_id, "reason": str(exc)})

    if dry_run:
        return {
            "processed": len(fragment_payloads),
            "edges_created": len(edges_to_insert),
            "pending": 0,
            "failed": len(failed_fragments),
        }

    edges_created = _batch_upsert_caused_by(db_module.db, edges_to_insert, now)
    _batch_set_attributed(db_module.db, attributed_keys)

    if failed_fragments:
        logger.warning(
            f"Event {event_key}: {len(failed_fragments)} fragment(s) failed — "
            + ", ".join(f"discos_id={f['discos_id']} ({f['reason']})" for f in failed_fragments)
        )

    if total_count is not None and edges_created != total_count:
        logger.warning(
            f"Edge count mismatch after upsert for {event_key}: "
            f"DISCOS totalCount={total_count}, edges_created={edges_created}"
        )

    return {
        "processed": len(fragment_payloads),
        "edges_created": edges_created,
        "pending": 0,
        "failed": len(failed_fragments),
    }


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
    total_failed = 0
    now = datetime.now(timezone.utc).isoformat()

    for i, event_doc in enumerate(events):
        event_key = event_doc.get("_key", "?")
        logger.info(f"[{i+1}/{len(events)}] Processing event {event_key}")

        try:
            counts = _process_event(event_doc, dry_run=dry_run, now=now)
            total_processed += counts["processed"]
            total_edges += counts["edges_created"]
            total_failed += counts["failed"]
        except Exception as exc:
            logger.error(f"Failed processing event {event_key}: {exc}")

    logger.info(
        f"Done — events={len(events)} fragments_processed={total_processed} "
        f"edges_created={total_edges} fragment_failures={total_failed}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest DISCOS attributions (self-completing fragment ingestion)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-events", type=int, default=0, help="Limit number of events to process (0 = all)")
    args = parser.parse_args()
    run(dry_run=args.dry_run, max_events=args.max_events)
