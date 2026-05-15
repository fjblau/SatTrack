#!/usr/bin/env python3
"""
Promote "Unknown" debris objects to specific fragmentation debris classes.

Many objects classified as "Unknown" are actually tracked debris fragments whose
parent object is known via DISCOS source data or the `fragmented_from` graph edges.
This script recovers that information and applies more specific object_class values:

  Rocket Body parent  →  "Rocket Fragmentation Debris"
  Payload parent      →  "Payload Fragmentation Debris"

Two promotion passes are run in order (each only updates objects still "Unknown"):

  Pass 1 — DISCOS source envelope
    Objects whose sources.discos.object_class is "Rocket Debris" or "Payload Debris"
    but whose canonical.object_class is still "Unknown".  (These were missed when
    promote_discos_object_class.py ran before DISCOS data was fully available.)

  Pass 2 — fragmented_from graph edges
    Objects with a `fragmented_from` edge pointing to a parent whose
    canonical.object_class is "Rocket Body" or "Payload".

Usage:
    python scripts/maintenance/promote_debris_class.py [--dry-run] [--yes]

OPTIONS:
    --dry-run   Show what would change without writing anything
    --yes / -y  Skip the interactive confirmation prompt
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
    "Rocket Debris":              "Rocket Fragmentation Debris",
    "Rocket Fragmentation Debris": "Rocket Fragmentation Debris",
    "Payload Debris":             "Payload Fragmentation Debris",
    "Payload Fragmentation Debris": "Payload Fragmentation Debris",
}

PARENT_CLASS_TO_DEBRIS = {
    "Rocket Body":                "Rocket Fragmentation Debris",
    "Rocket Fragmentation Debris": "Rocket Fragmentation Debris",
    "Payload":                    "Payload Fragmentation Debris",
    "Payload Fragmentation Debris": "Payload Fragmentation Debris",
}


def _update_object(col, obj, new_class, operator, now, dry_run):
    key = obj["_key"]
    old_class = obj.get("canonical", {}).get("object_class", "Unknown")
    if dry_run:
        logger.info(f"[DRY RUN] {key}: {old_class!r} → {new_class!r}  (via {operator})")
        return True
    transformations = obj.get("metadata", {}).get("transformations", [])
    transformations.append({
        "source": operator,
        "action": "promote_object_class",
        "timestamp": now,
        "operator": operator,
        "old_value": old_class,
        "new_value": new_class,
    })
    transformations = transformations[-10:]
    col.update({
        "_key": key,
        "canonical": {
            **obj.get("canonical", {}),
            "object_class": new_class,
        },
        "metadata": {
            **obj.get("metadata", {}),
            "transformations": transformations,
        },
    })
    return True


def pass1_discos(col, dry_run, now):
    """Promote from sources.discos.object_class where canonical is still Unknown."""
    cursor = db_module.db.aql.execute(
        """
        FOR obj IN objects
            FILTER obj.canonical.object_class == "Unknown"
               AND obj.sources.discos.object_class != null
            RETURN obj
        """
    )
    objects = list(cursor)
    logger.info(f"Pass 1 — DISCOS source: {len(objects)} candidate(s)")

    promoted = 0
    skipped = 0
    for obj in objects:
        discos_class = obj.get("sources", {}).get("discos", {}).get("object_class", "")
        new_class = DISCOS_CLASS_MAP.get(discos_class)
        if not new_class:
            skipped += 1
            continue
        if _update_object(col, obj, new_class, "promote_debris_class:discos", now, dry_run):
            promoted += 1

    logger.info(f"Pass 1 done — promoted={promoted} skipped={skipped}")
    return promoted


def pass2_lineage(col, dry_run, now):
    """Promote from fragmented_from graph edges based on parent object_class."""
    cursor = db_module.db.aql.execute(
        """
        FOR obj IN objects
            FILTER obj.canonical.object_class == "Unknown"
            FOR e IN fragmented_from
                FILTER e._from == obj._id
                LET parent = DOCUMENT(e._to)
                FILTER parent != null
                   AND parent.canonical.object_class IN [
                       "Rocket Body",
                       "Rocket Fragmentation Debris",
                       "Payload",
                       "Payload Fragmentation Debris"
                   ]
                RETURN {
                    obj: obj,
                    parent_class: parent.canonical.object_class,
                    edge_confidence: e.confidence
                }
        """
    )
    rows = list(cursor)
    logger.info(f"Pass 2 — lineage graph: {len(rows)} candidate(s)")

    promoted = 0
    skipped = 0
    seen = set()
    for row in rows:
        obj = row["obj"]
        key = obj["_key"]
        if key in seen:
            skipped += 1
            continue
        seen.add(key)

        new_class = PARENT_CLASS_TO_DEBRIS.get(row["parent_class"])
        if not new_class:
            skipped += 1
            continue
        if _update_object(col, obj, new_class, "promote_debris_class:lineage", now, dry_run):
            promoted += 1

    logger.info(f"Pass 2 done — promoted={promoted} skipped={skipped}")
    return promoted


def _print_class_distribution():
    cursor = db_module.db.aql.execute(
        """
        FOR obj IN objects
            COLLECT cls = obj.canonical.object_class WITH COUNT INTO cnt
            SORT cnt DESC
            RETURN {class: cls, count: cnt}
        """
    )
    rows = list(cursor)
    logger.info("Current object_class distribution:")
    for row in rows:
        logger.info(f"  {str(row['class']):40s}: {row['count']:>8,}")


def run(dry_run=False, yes=False):
    if not db_conn.connect_arangodb():
        logger.error("Failed to connect to ArangoDB")
        return False

    col = db_module.db.collection("objects")
    now = datetime.now(timezone.utc).isoformat()

    _print_class_distribution()

    unknown_count = list(db_module.db.aql.execute(
        'RETURN COUNT(FOR obj IN objects FILTER obj.canonical.object_class == "Unknown" RETURN 1)'
    ))[0]
    logger.info(f"\nTotal 'Unknown' objects to process: {unknown_count:,}")

    if dry_run:
        logger.info("[DRY RUN] No changes will be written.\n")
    elif not yes:
        try:
            resp = input(
                f"\nProceed with promoting up to {unknown_count:,} 'Unknown' objects? (y/N): "
            ).strip().lower()
        except EOFError:
            logger.error("stdin not interactive — re-run with --yes")
            db_conn.disconnect_arangodb()
            return False
        if resp not in ("y", "yes"):
            logger.info("Cancelled.")
            db_conn.disconnect_arangodb()
            return False

    total_promoted = 0
    total_promoted += pass1_discos(col, dry_run, now)
    total_promoted += pass2_lineage(col, dry_run, now)

    logger.info(f"\nTotal promoted across both passes: {total_promoted:,}")

    if not dry_run:
        logger.info("\nFinal distribution after promotion:")
        _print_class_distribution()

    db_conn.disconnect_arangodb()
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Promote Unknown debris objects to specific fragmentation classes")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()
    success = run(dry_run=args.dry_run, yes=args.yes)
    sys.exit(0 if success else 1)
