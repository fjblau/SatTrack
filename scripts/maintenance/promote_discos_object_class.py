#!/usr/bin/env python3
"""
Promote DISCOS object type classification to canonical.object_class on object documents.

DISCOSweb uses a specific classification scheme. This script maps DISCOS objectClass values
to the internal canonical.object_class values used across the system.

Usage:
    python scripts/maintenance/promote_discos_object_class.py [--dry-run]
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

DISCOS_CLASS_MAP = {
    "Payload": "Payload",
    "Payload Debris": "Payload Fragmentation Debris",
    "Payload Fragmentation Debris": "Payload Fragmentation Debris",
    "Rocket Body": "Rocket Body",
    "Rocket Debris": "Rocket Fragmentation Debris",
    "Rocket Fragmentation Debris": "Rocket Fragmentation Debris",
    "Unknown": "Unknown",
    "Other Debris": "Unknown",
}


def map_object_class(discos_class: str) -> str:
    if not discos_class:
        return "Unknown"
    return DISCOS_CLASS_MAP.get(discos_class, discos_class)


def run(dry_run: bool = False):
    if not db_conn.connect_arangodb():
        logger.error("Failed to connect to ArangoDB")
        sys.exit(1)

    cursor = db_module.db.aql.execute(
        """
        FOR obj IN objects
            FILTER obj.sources.discos != null
               AND obj.sources.discos.object_class != null
            RETURN obj
        """
    )
    objects = list(cursor)
    logger.info(f"Processing {len(objects)} objects with DISCOS objectClass")

    col = db_module.db.collection("objects")
    promoted = 0
    skipped = 0
    now = datetime.now(timezone.utc).isoformat()

    for obj in objects:
        discos_class = obj.get("sources", {}).get("discos", {}).get("object_class")
        if not discos_class:
            skipped += 1
            continue

        mapped = map_object_class(discos_class)
        existing_class = obj.get("canonical", {}).get("object_class")

        if existing_class and existing_class != "Unknown":
            skipped += 1
            continue

        if existing_class == mapped:
            skipped += 1
            continue

        if dry_run:
            logger.info(
                f"[DRY RUN] Would promote object_class on {obj['_key']}: "
                f"{discos_class!r} → {mapped!r}"
            )
            promoted += 1
            continue

        transformations = obj.get("metadata", {}).get("transformations", [])
        transformations.append({
            "source": "discos",
            "action": "promote_object_class",
            "timestamp": now,
            "operator": "promote_discos_object_class",
            "from_discos": discos_class,
            "to_canonical": mapped,
        })
        transformations = transformations[-10:]

        col.update({
            "_key": obj["_key"],
            "canonical": {
                **obj.get("canonical", {}),
                "object_class": mapped,
            },
            "metadata": {
                **obj.get("metadata", {}),
                "transformations": transformations,
            },
        })
        promoted += 1

    logger.info(f"Done — promoted={promoted} skipped={skipped} total={len(objects)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Promote DISCOS object class")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
