#!/usr/bin/env python3
"""
Promote GCAT parent relationships: write canonical.parent_gcat_id and create
fragmented_from edges so parent objects appear in the provenance graph.

For each object that has sources.gcat.parent set, this script:
  1. Promotes the value to canonical.parent_gcat_id (so the raw link is queryable).
  2. Resolves the parent object in the objects collection (by GCAT JCAT identifier).
  3. Creates a fragmented_from edge from child → parent in the provenance graph.

Both operations are executed as batched AQL queries (BATCH_SIZE records per
HTTP call) to avoid HTTP read-timeout errors on large collections.  Only
records that have sources.gcat.parent set are affected.

Usage:
    python scripts/maintenance/promote_gcat_parent_edges.py [--dry-run] [--yes]

Options:
    --dry-run   Preview changes without writing to the database.
    --yes       Skip the confirmation prompt.
    -v          Print identifiers for records whose parent could not be found.
"""
import sys
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import database.connection as db_conn
import database as db_module

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

COL = db_conn.COLLECTION_NAME
EDGE_COL = db_conn.EDGE_COLLECTION_FRAGMENTED_FROM

BATCH_SIZE = 5_000

_CANONICAL_UPDATE_QUERY = """
FOR doc IN @@col
    FILTER doc.sources.gcat.parent != null
       AND doc.sources.gcat.parent != ""
       AND (doc.canonical.parent_gcat_id == null OR doc.canonical.parent_gcat_id == "")
    LIMIT @batch_size
    LET parent_jcat = doc.sources.gcat.parent
    UPDATE doc WITH {
        canonical: MERGE(doc.canonical, { parent_gcat_id: parent_jcat }),
        metadata: MERGE(doc.metadata, {
            transformations: APPEND(
                doc.metadata.transformations || [],
                [{
                    source_field: "sources.gcat.parent",
                    target_field: "canonical.parent_gcat_id",
                    value: parent_jcat,
                    timestamp: @ts,
                    promoted_by: "promote_gcat_parent_edges"
                }]
            )
        })
    } IN @@col
    COLLECT WITH COUNT INTO updated
    RETURN updated
"""

_EDGE_UPSERT_QUERY = """
FOR child_id IN @child_ids
    LET child = DOCUMENT(@@col, child_id)
    FILTER child != null
    LET parent_jcat = child.sources.gcat.parent
    FILTER parent_jcat != null AND parent_jcat != ""
    LET parent_by_key = DOCUMENT(@@col, CONCAT("GCAT-", parent_jcat))
    LET parent_by_scan = FIRST(
        FOR p IN @@col
            FILTER p.sources.gcat.jcat == parent_jcat
            LIMIT 1
            RETURN p
    )
    LET parent = parent_by_key != null ? parent_by_key : parent_by_scan
    FILTER parent != null
    UPSERT { _from: child._id, _to: parent._id }
    INSERT {
        _key: CONCAT(child._key, "--", parent._key),
        _from: child._id,
        _to: parent._id,
        source: "gcat",
        relationship_type: "parent",
        confidence: 1.0,
        confidence_label: "high",
        metadata: {
            transformations: [{
                source: "gcat",
                action: "create",
                timestamp: @ts,
                operator: "promote_gcat_parent_edges"
            }]
        }
    }
    UPDATE {
        metadata: MERGE(OLD.metadata || {}, {
            transformations: SLICE(
                APPEND(
                    OLD.metadata.transformations || [],
                    [{
                        source: "gcat",
                        action: "update",
                        timestamp: @ts,
                        operator: "promote_gcat_parent_edges"
                    }]
                ),
                -10
            )
        })
    }
    IN @@edge_col
    COLLECT WITH COUNT INTO cnt
    RETURN cnt
"""

_NOT_FOUND_QUERY = """
FOR child_id IN @child_ids
    LET child = DOCUMENT(@@col, child_id)
    FILTER child != null
    LET parent_jcat = child.sources.gcat.parent
    FILTER parent_jcat != null AND parent_jcat != ""
    LET parent_by_key = DOCUMENT(@@col, CONCAT("GCAT-", parent_jcat))
    LET parent_by_scan = FIRST(
        FOR p IN @@col
            FILTER p.sources.gcat.jcat == parent_jcat
            LIMIT 1
            RETURN p
    )
    LET parent = parent_by_key != null ? parent_by_key : parent_by_scan
    FILTER parent == null
    RETURN { id: child.identifier, parent_jcat: parent_jcat }
"""


def _chunks(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def run(dry_run: bool, yes: bool, verbose: bool):
    if not db_conn.connect_arangodb():
        logger.error("Failed to connect to ArangoDB")
        return False

    db = db_conn.db

    cursor = db.aql.execute(
        """
        FOR doc IN @@col
            FILTER doc.sources.gcat.parent != null
               AND doc.sources.gcat.parent != ""
            RETURN {
                _key:   doc._key,
                _id:    doc._id,
                id:     doc.identifier,
                parent: doc.sources.gcat.parent,
                existing_canonical_parent: doc.canonical.parent_gcat_id
            }
        """,
        bind_vars={"@col": COL},
    )
    candidates = list(cursor)

    print(f"\n=== Promote GCAT Parent → canonical + fragmented_from edge ===")
    print(f"Objects with sources.gcat.parent set: {len(candidates):,}")

    if not candidates:
        print("Nothing to do.")
        return True

    already_promoted = sum(1 for c in candidates if c["existing_canonical_parent"])
    print(f"Already have canonical.parent_gcat_id: {already_promoted:,}")
    print(f"Will promote: {len(candidates) - already_promoted:,}")

    print("\nSample (up to 5):")
    for c in candidates[:5]:
        print(f"  {c['id']}  →  parent JCAT: {c['parent']}")

    child_ids = [c["_id"] for c in candidates]

    if dry_run:
        not_found = []
        for chunk in _chunks(child_ids, BATCH_SIZE):
            cursor = db.aql.execute(
                _NOT_FOUND_QUERY,
                bind_vars={"@col": COL, "child_ids": chunk},
            )
            not_found.extend(cursor)
        print(f"\n[DRY-RUN] Previewing changes for {len(candidates):,} objects.")
        print(f"  canonical.parent_gcat_id would be promoted: {len(candidates) - already_promoted:,}")
        print(f"  fragmented_from edges would be upserted   : {len(candidates) - len(not_found):,}")
        print(f"  Parent objects not found                  : {len(not_found):,}")
        if verbose and not_found:
            for nf in not_found:
                logger.info(f"  Parent not found: {nf['id']}  (GCAT JCAT={nf['parent_jcat']})")
        return True

    if not yes:
        try:
            resp = input(f"\nProceed? (y/N): ").strip().lower()
        except EOFError:
            resp = "y"
        if resp not in ("y", "yes"):
            print("Cancelled.")
            return False

    now = datetime.now(timezone.utc).isoformat()

    promoted_canonical = 0
    while True:
        cursor = db.aql.execute(
            _CANONICAL_UPDATE_QUERY,
            bind_vars={"@col": COL, "ts": now, "batch_size": BATCH_SIZE},
        )
        count = (list(cursor) or [0])[0]
        promoted_canonical += count
        logger.info(f"  canonical promotion: {promoted_canonical:,} so far...")
        if count < BATCH_SIZE:
            break

    edges_upserted = 0
    for chunk in _chunks(child_ids, BATCH_SIZE):
        cursor = db.aql.execute(
            _EDGE_UPSERT_QUERY,
            bind_vars={"@col": COL, "@edge_col": EDGE_COL, "ts": now, "child_ids": chunk},
        )
        edges_upserted += (list(cursor) or [0])[0]
        logger.info(f"  edge upsert: {edges_upserted:,} so far...")

    parent_not_found = len(candidates) - edges_upserted

    if verbose and parent_not_found > 0:
        not_found = []
        for chunk in _chunks(child_ids, BATCH_SIZE):
            cursor = db.aql.execute(
                _NOT_FOUND_QUERY,
                bind_vars={"@col": COL, "child_ids": chunk},
            )
            not_found.extend(cursor)
        for nf in not_found:
            logger.warning(f"  Parent not found: {nf['id']}  (GCAT JCAT={nf['parent_jcat']})")

    print(f"\n=== Summary ===")
    print(f"canonical.parent_gcat_id promoted        : {promoted_canonical:,}")
    print(f"fragmented_from edges created/updated    : {edges_upserted:,}")
    print(f"Parent objects not found                 : {parent_not_found:,}")

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Promote GCAT parent field to canonical and create fragmented_from edges"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("-v", "--verbose", action="store_true", help="Log each document with missing parent")
    args = parser.parse_args()
    success = run(dry_run=args.dry_run, yes=args.yes, verbose=args.verbose)
    sys.exit(0 if success else 1)
