#!/usr/bin/env python3
"""
Promote fragmentation event metadata to canonical fields.

Promotes epoch, altitude_km, latitude, longitude from sources.discos.raw to canonical
when those canonical fields are not yet set.

Also promotes fragment_count_discos from sources.discos.raw.objectsCount (with fallbacks
to cataloguedFragments and nFragments for API version compatibility). The promotion is
idempotent: if canonical.fragment_count_discos already equals the source value, no
transformation is logged.

Usage:
    python scripts/maintenance/promote_discos_fragmentations.py [--dry-run]
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

_DISCOS_COUNT_FIELD_CANDIDATES = ("objectsCount", "cataloguedFragments", "nFragments")


def _extract_discos_count(raw: dict):
    for field in _DISCOS_COUNT_FIELD_CANDIDATES:
        val = raw.get(field)
        if val is not None:
            try:
                return int(val), field
            except (TypeError, ValueError):
                pass
    return None, None


def run(dry_run: bool = False):
    if not db_conn.connect_arangodb():
        logger.error("Failed to connect to ArangoDB")
        sys.exit(1)

    cursor = db_module.db.aql.execute(
        "FOR e IN fragmentation_events FILTER e.sources.discos.raw != null RETURN e"
    )
    events = list(cursor)
    logger.info(f"Processing {len(events)} fragmentation events")

    col = db_module.db.collection("fragmentation_events")
    promoted = 0
    skipped = 0
    now = datetime.now(timezone.utc).isoformat()

    for event in events:
        raw = event.get("sources", {}).get("discos", {}).get("raw", {})
        if not raw:
            skipped += 1
            continue

        updates = {}
        promotion_log_entries = []
        current_canonical = event.get("canonical", {})

        raw_epoch = raw.get("epoch") or raw.get("date")
        if raw_epoch and not current_canonical.get("epoch"):
            updates["epoch"] = raw_epoch

        raw_alt = raw.get("altitude") or raw.get("altitude_km")
        if raw_alt is not None and current_canonical.get("altitude_km") is None:
            updates["altitude_km"] = raw_alt

        raw_lat = raw.get("latitude")
        if raw_lat is not None and current_canonical.get("latitude") is None:
            updates["latitude"] = raw_lat

        raw_lon = raw.get("longitude")
        if raw_lon is not None and current_canonical.get("longitude") is None:
            updates["longitude"] = raw_lon

        discos_count, count_field = _extract_discos_count(raw)
        if discos_count is not None:
            existing_discos_count = current_canonical.get("fragment_count_discos")
            if discos_count != existing_discos_count:
                updates["fragment_count_discos"] = discos_count
                promotion_log_entries.append({
                    "source": "discos",
                    "action": "promote",
                    "timestamp": now,
                    "operator": "promote_discos_fragmentations",
                    "source_field": f"sources.discos.raw.{count_field}",
                    "target_field": "canonical.fragment_count_discos",
                    "value": discos_count,
                })

        if not updates:
            skipped += 1
            continue

        if dry_run:
            logger.info(f"[DRY RUN] Would promote on {event['_key']}: {list(updates.keys())}")
            promoted += 1
            continue

        transformations = event.get("metadata", {}).get("transformations", [])
        if promotion_log_entries:
            transformations.extend(promotion_log_entries)
        else:
            transformations.append({
                "source": "discos",
                "action": "promote",
                "timestamp": now,
                "operator": "promote_discos_fragmentations",
                "fields": list(updates.keys()),
            })
        transformations = transformations[-10:]

        col.update({
            "_key": event["_key"],
            "canonical": {**current_canonical, **updates},
            "metadata": {
                **event.get("metadata", {}),
                "transformations": transformations,
            },
        })
        promoted += 1

    logger.info(f"Done — promoted={promoted} skipped={skipped} total={len(events)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Promote DISCOS fragmentation metadata")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
