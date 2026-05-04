#!/usr/bin/env python3
"""
Promote DISCOS event type classifications to canonical fields on fragmentation_events documents.

Usage:
    python scripts/maintenance/promote_discos_event_types.py [--dry-run]
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

EVENT_TYPE_MAP = {
    "explosion": "Explosion",
    "collision": "Collision",
    "asat": "ASAT Test",
    "degradation": "Degradation",
    "unknown": "Unknown",
}


def normalize_event_type(raw: str) -> str:
    if not raw:
        return "Unknown"
    return EVENT_TYPE_MAP.get(raw.lower(), raw)


def run(dry_run: bool = False):
    if not db_conn.connect_arangodb():
        logger.error("Failed to connect to ArangoDB")
        sys.exit(1)

    cursor = db_module.db.aql.execute("FOR e IN fragmentation_events RETURN e")
    events = list(cursor)
    logger.info(f"Processing {len(events)} fragmentation_events")

    col = db_module.db.collection("fragmentation_events")
    promoted = 0
    skipped = 0
    now = datetime.now(timezone.utc).isoformat()

    for event in events:
        raw_type = (
            event.get("sources", {}).get("discos", {}).get("raw", {}).get("type")
            or event.get("sources", {}).get("discos", {}).get("raw", {}).get("eventType")
            or event.get("canonical", {}).get("event_type")
        )
        if not raw_type:
            skipped += 1
            continue

        normalized = normalize_event_type(raw_type)
        if event.get("canonical", {}).get("event_type") == normalized:
            skipped += 1
            continue

        if dry_run:
            logger.info(f"[DRY RUN] Would promote event_type on {event['_key']}: {raw_type!r} → {normalized!r}")
            promoted += 1
            continue

        transformations = event.get("metadata", {}).get("transformations", [])
        transformations.append({
            "source": "discos",
            "action": "promote_event_type",
            "timestamp": now,
            "operator": "promote_discos_event_types",
            "from": raw_type,
            "to": normalized,
        })
        transformations = transformations[-10:]

        col.update({
            "_key": event["_key"],
            "canonical": {
                **event.get("canonical", {}),
                "event_type": normalized,
            },
            "metadata": {
                **event.get("metadata", {}),
                "transformations": transformations,
            },
        })
        promoted += 1

    logger.info(f"Done — promoted={promoted} skipped={skipped} total={len(events)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Promote DISCOS event types")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
