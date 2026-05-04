#!/usr/bin/env python3
"""
Promote attribution metadata and confidence scores onto fragmented_from edges.

Reads existing fragmented_from edges and updates confidence scores and attribution metadata
based on DISCOS source data.

Usage:
    python scripts/maintenance/promote_discos_attributions.py [--dry-run]
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


def run(dry_run: bool = False):
    if not db_conn.connect_arangodb():
        logger.error("Failed to connect to ArangoDB")
        sys.exit(1)

    cursor = db_module.db.aql.execute("FOR e IN fragmented_from RETURN e")
    edges = list(cursor)
    logger.info(f"Processing {len(edges)} fragmented_from edges")

    col = db_module.db.collection("fragmented_from")
    promoted = 0
    skipped = 0
    now = datetime.now(timezone.utc).isoformat()

    for edge in edges:
        confidence = edge.get("confidence")
        if confidence is None:
            skipped += 1
            continue

        if confidence >= 0.9:
            confidence_label = "high"
        elif confidence >= 0.7:
            confidence_label = "medium"
        else:
            confidence_label = "low"

        if edge.get("confidence_label") == confidence_label:
            skipped += 1
            continue

        if dry_run:
            logger.info(
                f"[DRY RUN] Would promote confidence_label={confidence_label!r} "
                f"on edge {edge.get('_key')}"
            )
            promoted += 1
            continue

        transformations = edge.get("metadata", {}).get("transformations", [])
        transformations.append({
            "source": "discos",
            "action": "promote_confidence_label",
            "timestamp": now,
            "operator": "promote_discos_attributions",
            "confidence": confidence,
            "label": confidence_label,
        })
        transformations = transformations[-10:]

        col.update({
            "_key": edge["_key"],
            "confidence_label": confidence_label,
            "metadata": {
                **edge.get("metadata", {}),
                "transformations": transformations,
            },
        })
        promoted += 1

    logger.info(f"Done — promoted={promoted} skipped={skipped} total={len(edges)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Promote DISCOS attribution confidence labels")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
