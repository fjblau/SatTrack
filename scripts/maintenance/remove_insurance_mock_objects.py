#!/usr/bin/env python3
"""
Remove insurance mock satellite objects from the objects catalog.

When seed_insurance_demo.py was run with a broken resolve_satellite_key (wrong
field: canonical.norad_id vs canonical.norad_cat_id), it created INS-SAT-<norad>
stub objects in the objects collection alongside the real catalog entries with the
same NORAD ID, producing duplicate NORAD IDs visible in the catalog.

This script:
  1. Finds all objects with _insurance_mock == True (key prefix INS-SAT-*).
  2. Removes any edges in the general graph edge collections that reference them.
  3. Removes any edges in the insurance graph edge collections that reference them.
  4. Removes the mock objects themselves from the objects collection.

Safe to run before re-running seed_insurance_demo.py (which has since been fixed
to resolve against canonical.norad_cat_id).

Usage:
    python scripts/maintenance/remove_insurance_mock_objects.py [--dry-run]
"""
import sys
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import database as db_module
from database.connection import (
    connect_mongodb,
    COLLECTION_NAME,
    EDGE_COLLECTION_CONSTELLATION,
    EDGE_COLLECTION_REGISTRATION,
    EDGE_COLLECTION_PROXIMITY,
    EDGE_COLLECTION_COLLISION_RISK,
    EDGE_COLLECTION_SATELLITE_LINEAGE,
    EDGE_INSURANCE_POLICY_COVERS_SAT,
    EDGE_INSURANCE_POLICY_HAS_INTEREST,
    EDGE_INSURANCE_INTEREST_HELD_BY,
    EDGE_INSURANCE_CLAIM_ARISES_FROM,
    EDGE_INSURANCE_LOSS_EVENT_INVOLVES,
    EDGE_INSURANCE_SAT_IN_SHELL,
    EDGE_INSURANCE_RISK_SCORE_FOR,
    EDGE_INSURANCE_PREDICTION_FOR,
    EDGE_INSURANCE_KESTREL_OBSERVED,
    EDGE_INSURANCE_KESTREL_CAN_SEE,
    EDGE_INSURANCE_TASK_TARGETS,
    EDGE_INSURANCE_EVENT_WITNESSED_BY,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ALL_EDGE_COLLECTIONS = [
    EDGE_COLLECTION_CONSTELLATION,
    EDGE_COLLECTION_REGISTRATION,
    EDGE_COLLECTION_PROXIMITY,
    EDGE_COLLECTION_COLLISION_RISK,
    EDGE_COLLECTION_SATELLITE_LINEAGE,
    EDGE_INSURANCE_POLICY_COVERS_SAT,
    EDGE_INSURANCE_POLICY_HAS_INTEREST,
    EDGE_INSURANCE_INTEREST_HELD_BY,
    EDGE_INSURANCE_CLAIM_ARISES_FROM,
    EDGE_INSURANCE_LOSS_EVENT_INVOLVES,
    EDGE_INSURANCE_SAT_IN_SHELL,
    EDGE_INSURANCE_RISK_SCORE_FOR,
    EDGE_INSURANCE_PREDICTION_FOR,
    EDGE_INSURANCE_KESTREL_OBSERVED,
    EDGE_INSURANCE_KESTREL_CAN_SEE,
    EDGE_INSURANCE_TASK_TARGETS,
    EDGE_INSURANCE_EVENT_WITNESSED_BY,
]


def find_mock_objects() -> list[dict]:
    cursor = db_module.db.aql.execute("""
        FOR doc IN @@col
            FILTER doc._insurance_mock == true
               OR STARTS_WITH(doc._key, "INS-SAT-")
            RETURN { _key: doc._key, _id: doc._id,
                     norad_id: doc.canonical.norad_id OR doc.canonical.norad_cat_id,
                     name: doc.canonical.name OR doc.identifier }
    """, bind_vars={"@col": COLLECTION_NAME})
    return list(cursor)


def remove_edges_referencing(object_ids: list[str], dry_run: bool) -> int:
    removed = 0
    for edge_col in ALL_EDGE_COLLECTIONS:
        try:
            cursor = db_module.db.aql.execute("""
                FOR doc IN @@col
                    FILTER doc._from IN @ids OR doc._to IN @ids
                    RETURN doc._key
            """, bind_vars={"@col": edge_col, "ids": object_ids})
            keys = list(cursor)
            if not keys:
                continue
            logger.info(f"  Edge collection '{edge_col}': {len(keys)} edges to remove")
            if not dry_run:
                db_module.db.aql.execute("""
                    FOR doc IN @@col
                        FILTER doc._from IN @ids OR doc._to IN @ids
                        REMOVE doc IN @@col
                """, bind_vars={"@col": edge_col, "ids": object_ids})
            removed += len(keys)
        except Exception as exc:
            logger.warning(f"  Could not clean '{edge_col}': {exc}")
    return removed


def run(dry_run: bool = False):
    if not connect_mongodb():
        logger.error("Failed to connect to ArangoDB")
        sys.exit(1)

    logger.info("Searching for insurance mock objects in the catalog...")
    mock_objects = find_mock_objects()

    if not mock_objects:
        logger.info("No insurance mock objects found — nothing to do.")
        return

    logger.info(f"Found {len(mock_objects)} mock object(s):")
    for obj in mock_objects:
        logger.info(f"  _key={obj['_key']}  norad_id={obj['norad_id']}  name={obj['name']}")

    object_ids = [obj["_id"] for obj in mock_objects]

    logger.info("Removing edges that reference mock objects...")
    edges_removed = remove_edges_referencing(object_ids, dry_run)
    logger.info(f"  Total edges removed: {edges_removed}")

    logger.info(f"Removing {len(mock_objects)} mock object(s) from '{COLLECTION_NAME}'...")
    if not dry_run:
        keys = [obj["_key"] for obj in mock_objects]
        db_module.db.aql.execute("""
            FOR doc IN @@col
                FILTER doc._key IN @keys
                REMOVE doc IN @@col
        """, bind_vars={"@col": COLLECTION_NAME, "keys": keys})

    action = "[DRY RUN] Would remove" if dry_run else "Removed"
    logger.info(f"Done. {action} {len(mock_objects)} mock object(s) and {edges_removed} edge(s).")
    if dry_run:
        logger.info("Re-run without --dry-run to apply changes.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Remove insurance mock satellite objects (INS-SAT-*) from the catalog"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would be removed without modifying the DB")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
