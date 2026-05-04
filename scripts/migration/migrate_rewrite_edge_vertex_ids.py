#!/usr/bin/env python3
"""
Migrate: Rewrite stale 'satellites/' vertex IDs to 'objects/' in all edge collections.

When the 'satellites' collection was renamed to 'objects' (Spec 1), ArangoDB's
rename operation updated the vertex documents but left all edge _from/_to fields
pointing at 'satellites/<key>'. ArangoDB treats _from/_to as immutable, so edges
must be deleted and re-inserted with corrected IDs.

Edge collections checked (across all three named graphs):
  satellite_relationships graph:
    constellation_membership, registration_links, orbital_proximity,
    collision_risk_edges, satellite_lineage
  observation_relationships graph:
    observation_satellite_edges, observation_source_edges,
    observation_correlation_edges, observation_temporal_edges
  provenance_relationships graph:
    fragmented_from, caused_by, launched_by, launched_via, launched_from

USAGE:
    python migrate_rewrite_edge_vertex_ids.py [--dry-run]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from arango import ArangoClient
import os

ARANGO_HOST = os.getenv("ARANGO_HOST", "http://localhost:8529")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "kessler_dev_password")
DB_NAME = "kessler"
OLD_PREFIX = "satellites/"
NEW_PREFIX = "objects/"

EDGE_COLLECTIONS = [
    "constellation_membership",
    "registration_links",
    "orbital_proximity",
    "collision_risk_edges",
    "satellite_lineage",
    "observation_satellite_edges",
    "observation_source_edges",
    "observation_correlation_edges",
    "observation_temporal_edges",
    "fragmented_from",
    "caused_by",
    "launched_by",
    "launched_via",
    "launched_from",
]

BATCH_SIZE = 500


def normalize(id_str):
    if id_str and id_str.startswith(OLD_PREFIX):
        return NEW_PREFIX + id_str[len(OLD_PREFIX):]
    return id_str


def migrate_collection(db, col_name, dry_run):
    if not db.has_collection(col_name):
        print(f"  [{col_name}] skipped (collection does not exist)")
        return 0

    col = db.collection(col_name)

    cursor = db.aql.execute(
        """
        FOR e IN @@col
            FILTER STARTS_WITH(e._from, @old) OR STARTS_WITH(e._to, @old)
            RETURN e
        """,
        bind_vars={"@col": col_name, "old": OLD_PREFIX},
        batch_size=BATCH_SIZE,
    )
    stale = list(cursor)

    if not stale:
        print(f"  [{col_name}] no stale edges")
        return 0

    print(f"  [{col_name}] {len(stale)} stale edge(s) found")
    if dry_run:
        for e in stale[:5]:
            print(f"    would fix: {e['_id']}  _from={e['_from']}  _to={e['_to']}")
        if len(stale) > 5:
            print(f"    ... and {len(stale) - 5} more")
        return len(stale)

    fixed = 0
    errors = 0
    for edge in stale:
        new_edge = {k: v for k, v in edge.items() if k not in ("_id", "_rev")}
        new_edge["_from"] = normalize(edge["_from"])
        new_edge["_to"] = normalize(edge["_to"])
        try:
            col.delete(edge["_key"])
            col.insert(new_edge)
            fixed += 1
        except Exception as exc:
            print(f"    ERROR on {edge['_id']}: {exc}")
            errors += 1

    print(f"  [{col_name}] fixed {fixed}, errors {errors}")
    return fixed


def run(dry_run=False):
    print(f"{'[DRY-RUN] ' if dry_run else ''}Connecting to {ARANGO_HOST}/{DB_NAME}...")
    client = ArangoClient(hosts=ARANGO_HOST)
    db = client.db(DB_NAME, username=ARANGO_USER, password=ARANGO_PASSWORD)

    total_fixed = 0
    for col_name in EDGE_COLLECTIONS:
        total_fixed += migrate_collection(db, col_name, dry_run)

    if dry_run:
        print(f"\n[DRY-RUN] Would rewrite {total_fixed} edge(s). No changes made.")
    else:
        print(f"\nDone. Total edges rewritten: {total_fixed}")

    return True


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    success = run(dry_run)
    sys.exit(0 if success else 1)
