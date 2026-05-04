#!/usr/bin/env python3
"""
Promote DISCOS-sourced attributes (mass, RCS, shape) to canonical fields on object documents.

Only promotes from the DISCOS source envelope; does not overwrite fields set by higher-priority sources.

Usage:
    python scripts/maintenance/promote_discos_object_attributes.py [--dry-run]
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

PROMOTED_FIELDS = [
    ("mass_kg", "mass_kg"),
    ("xSectAvg", "rcs"),
    ("shape", "shape"),
]


def run(dry_run: bool = False):
    if not db_conn.connect_arangodb():
        logger.error("Failed to connect to ArangoDB")
        sys.exit(1)

    cursor = db_module.db.aql.execute(
        "FOR obj IN objects FILTER obj.sources.discos != null RETURN obj"
    )
    objects = list(cursor)
    logger.info(f"Processing {len(objects)} objects with DISCOS source envelope")

    col = db_module.db.collection("objects")
    promoted = 0
    skipped = 0
    now = datetime.now(timezone.utc).isoformat()

    for obj in objects:
        discos_src = obj.get("sources", {}).get("discos", {})
        if not discos_src:
            skipped += 1
            continue

        updates = {}
        transformations_added = []

        for discos_field, canonical_field in PROMOTED_FIELDS:
            value = discos_src.get(discos_field)
            if value is None:
                continue
            existing = obj.get("canonical", {}).get(canonical_field)
            if existing is not None:
                continue
            updates[canonical_field] = value
            transformations_added.append({
                "field": canonical_field,
                "from_source": "discos",
                "value": value,
            })

        if not updates:
            skipped += 1
            continue

        if dry_run:
            logger.info(f"[DRY RUN] Would promote on {obj['_key']}: {list(updates.keys())}")
            promoted += 1
            continue

        transformations = obj.get("metadata", {}).get("transformations", [])
        transformations.append({
            "source": "discos",
            "action": "promote_attributes",
            "timestamp": now,
            "operator": "promote_discos_object_attributes",
            "fields": transformations_added,
        })
        transformations = transformations[-10:]

        col.update({
            "_key": obj["_key"],
            "canonical": {
                **obj.get("canonical", {}),
                **updates,
            },
            "metadata": {
                **obj.get("metadata", {}),
                "transformations": transformations,
            },
        })
        promoted += 1

    logger.info(f"Done — promoted={promoted} skipped={skipped} total={len(objects)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Promote DISCOS object attributes")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
