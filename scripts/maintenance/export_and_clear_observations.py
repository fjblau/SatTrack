#!/usr/bin/env python3
"""
Export all observation data (documents, source vertices, and all graph edges) to
timestamped JSONL backup files, then truncate the collections.

Collections exported and cleared:
  - observations                  (vertex)
  - observation_sources           (vertex)
  - observation_satellite_edges   (edge)
  - observation_source_edges      (edge)
  - observation_temporal_edges    (edge)
  - observation_correlation_edges (edge)

The backup is written to:  <repo_root>/backups/observations_<YYYYMMDD_HHMMSS>/

Usage:
    python scripts/maintenance/export_and_clear_observations.py [--dry-run] [--output-dir DIR]
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
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

COLLECTIONS_TO_EXPORT = [
    COLLECTION_OBSERVATIONS,
    COLLECTION_OBSERVATION_SOURCES,
    EDGE_COLLECTION_OBS_SATELLITE,
    EDGE_COLLECTION_OBS_SOURCE,
    EDGE_COLLECTION_OBS_TEMPORAL,
    EDGE_COLLECTION_OBS_CORRELATION,
]


def export_collection(col_name: str, output_path: Path, batch_size: int = 2000) -> int:
    db = db_conn.db
    if not db.has_collection(col_name):
        print(f"  [{col_name}] collection does not exist — skipping", flush=True)
        return 0

    col = db.collection(col_name)
    total = col.count()
    print(f"  [{col_name}] {total} documents → {output_path.name}", flush=True)

    written = 0
    offset = 0
    with output_path.open("w") as f:
        while True:
            cursor = db.aql.execute(
                "FOR doc IN @@col LIMIT @offset, @batch RETURN doc",
                bind_vars={"@col": col_name, "offset": offset, "batch": batch_size},
            )
            docs = list(cursor)
            if not docs:
                break
            for doc in docs:
                f.write(json.dumps(doc, default=str) + "\n")
            written += len(docs)
            offset += batch_size

    return written


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


def run(output_dir: str | None, dry_run: bool):
    print(f"Export & Clear Observations — {'DRY RUN' if dry_run else 'LIVE'}", flush=True)

    if not db_conn.connect_arangodb():
        print("Failed to connect to ArangoDB")
        sys.exit(1)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if output_dir:
        backup_dir = Path(output_dir)
    else:
        backup_dir = Path(__file__).parent.parent.parent / "backups" / f"observations_{timestamp}"

    backup_dir.mkdir(parents=True, exist_ok=True)
    print(f"Backup directory: {backup_dir}", flush=True)
    print(flush=True)

    print("Exporting collections...", flush=True)
    total_exported = 0
    for col_name in COLLECTIONS_TO_EXPORT:
        output_path = backup_dir / f"{col_name}.jsonl"
        n = export_collection(col_name, output_path)
        total_exported += n

    meta = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "collections": COLLECTIONS_TO_EXPORT,
        "total_documents": total_exported,
        "dry_run": dry_run,
    }
    (backup_dir / "metadata.json").write_text(json.dumps(meta, indent=2))

    print(f"\nTotal exported: {total_exported} documents", flush=True)
    print(flush=True)

    print("Clearing collections...", flush=True)
    total_deleted = 0
    for col_name in COLLECTIONS_TO_EXPORT:
        total_deleted += clear_collection(col_name, dry_run)

    print(flush=True)
    print(f"{'Would delete' if dry_run else 'Deleted'} {total_deleted} documents across {len(COLLECTIONS_TO_EXPORT)} collections", flush=True)
    print(f"Backup saved to: {backup_dir}", flush=True)
    print(f"BACKUP_DIR: {backup_dir}", flush=True)
    print(flush=True)
    print("Next steps:", flush=True)
    print("  1. Run 'Import Kestrel Proxy v2 Observations' (upload .xlsx)", flush=True)
    print("  2. Run 'Populate Observation Edges' to rebuild all graph edges", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Export and clear all observation data")
    parser.add_argument("--output-dir", default=None,
                        help="Directory to write backup files (default: backups/observations_<timestamp>/)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Export only — do not delete from database")
    args = parser.parse_args()

    run(output_dir=args.output_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
