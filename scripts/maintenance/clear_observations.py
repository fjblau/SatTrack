#!/usr/bin/env python3
"""
Clear all observation data (documents, source vertices, and all graph edges) from the database.

Collections cleared:
  - observations                  (vertex)
  - observation_sources           (vertex)
  - observation_satellite_edges   (edge)
  - observation_source_edges      (edge)
  - observation_temporal_edges    (edge)
  - observation_correlation_edges (edge)

Usage:
    python scripts/maintenance/clear_observations.py [--dry-run]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import database.connection as db_conn
from database.connection import (
    COLLECTION_OBSERVATIONS,
    COLLECTION_OBSERVATION_SOURCES,
    EDGE_COLLECTION_OBS_SATELLITE,
    EDGE_COLLECTION_OBS_SOURCE,
    EDGE_COLLECTION_OBS_TEMPORAL,
    EDGE_COLLECTION_OBS_CORRELATION,
)

COLLECTIONS_TO_CLEAR = [
    COLLECTION_OBSERVATIONS,
    COLLECTION_OBSERVATION_SOURCES,
    EDGE_COLLECTION_OBS_SATELLITE,
    EDGE_COLLECTION_OBS_SOURCE,
    EDGE_COLLECTION_OBS_TEMPORAL,
    EDGE_COLLECTION_OBS_CORRELATION,
]


def clear_collection(col_name: str, dry_run: bool) -> int:
    db = db_conn.db
    if not db.has_collection(col_name):
        return 0

    count = db.collection(col_name).count()
    if dry_run:
        print(f"  [{col_name}] [DRY RUN] would delete {count} documents", flush=True)
    else:
        db.collection(col_name).truncate()
        print(f"  [{col_name}] deleted {count} documents", flush=True)
    return count


def run(dry_run: bool):
    print(f"Clear Observations — {'DRY RUN' if dry_run else 'LIVE'}", flush=True)

    if not db_conn.connect_arangodb():
        print("Failed to connect to ArangoDB")
        sys.exit(1)

    print("Clearing collections...", flush=True)
    total_deleted = 0
    for col_name in COLLECTIONS_TO_CLEAR:
        total_deleted += clear_collection(col_name, dry_run)

    print(flush=True)
    print(f"{'Would delete' if dry_run else 'Deleted'} {total_deleted} documents across {len(COLLECTIONS_TO_CLEAR)} collections", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Clear all observation data from the database")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be deleted without actually deleting")
    args = parser.parse_args()

    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
