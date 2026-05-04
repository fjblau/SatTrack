#!/usr/bin/env python3
"""
Migrate: Rename ArangoDB 'satellites' collection to 'objects'.

Steps:
1. Verify 'satellites' collection exists and 'objects' does not (or is empty).
2. Rename the collection in-place via ArangoDB collection rename API.
3. Recreate core indexes on the renamed collection.
4. Ensure satellite_relationships named graph points at 'objects'.

USAGE:
    python migrate_collection_rename.py [--dry-run]
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
OLD_COLLECTION = "satellites"
NEW_COLLECTION = "objects"
GRAPH_NAME = "satellite_relationships"


def run(dry_run=False):
    client = ArangoClient(hosts=ARANGO_HOST)
    db = client.db(DB_NAME, username=ARANGO_USER, password=ARANGO_PASSWORD)

    has_old = db.has_collection(OLD_COLLECTION)
    has_new = db.has_collection(NEW_COLLECTION)

    print(f"Collection '{OLD_COLLECTION}' exists: {has_old}")
    print(f"Collection '{NEW_COLLECTION}' exists: {has_new}")

    if not has_old and has_new:
        print(f"Collection already renamed to '{NEW_COLLECTION}'. Nothing to do.")
    elif not has_old and not has_new:
        print("ERROR: Neither 'satellites' nor 'objects' collection found.")
        return False
    elif has_old and has_new:
        old_count = db.collection(OLD_COLLECTION).count()
        new_count = db.collection(NEW_COLLECTION).count()
        print(f"Both collections exist: satellites={old_count}, objects={new_count}")
        if new_count > 0:
            print("ERROR: 'objects' collection already has documents. Cannot safely rename.")
            return False
        print("'objects' collection is empty. Will drop it and rename 'satellites' → 'objects'.")
        if not dry_run:
            if db.has_graph(GRAPH_NAME):
                print(f"Dropping graph '{GRAPH_NAME}' so the empty '{NEW_COLLECTION}' collection can be deleted...")
                db.delete_graph(GRAPH_NAME, drop_collections=False)
            db.delete_collection(NEW_COLLECTION)
    
    if has_old:
        count = db.collection(OLD_COLLECTION).count()
        print(f"\nWill rename '{OLD_COLLECTION}' ({count:,} documents) → '{NEW_COLLECTION}'")

        if dry_run:
            print("[DRY-RUN] No changes made.")
            return True

        col = db.collection(OLD_COLLECTION)
        col.rename(NEW_COLLECTION)
        print(f"Renamed '{OLD_COLLECTION}' → '{NEW_COLLECTION}'")

    objects_col = db.collection(NEW_COLLECTION)
    print("\nRecreating indexes on 'objects'...")
    objects_col.add_persistent_index(fields=["canonical.international_designator"], unique=False)
    objects_col.add_persistent_index(fields=["canonical.registration_number"], unique=False)
    objects_col.add_persistent_index(fields=["identifier"], unique=True)
    print("Core indexes recreated.")

    if db.has_graph(GRAPH_NAME):
        graph = db.graph(GRAPH_NAME)
        edge_defs = graph.edge_definitions()
        needs_update = any(
            OLD_COLLECTION in (ed.get("from_vertex_collections", []) + ed.get("to_vertex_collections", []))
            for ed in edge_defs
        )
        if needs_update:
            print(f"\nGraph '{GRAPH_NAME}' still references '{OLD_COLLECTION}'. Recreating...")
            db.delete_graph(GRAPH_NAME)
            _create_satellite_relationships_graph(db)
            print(f"Graph '{GRAPH_NAME}' recreated pointing at '{NEW_COLLECTION}'.")
        else:
            print(f"\nGraph '{GRAPH_NAME}' already points at '{NEW_COLLECTION}'.")
    else:
        print(f"\nGraph '{GRAPH_NAME}' does not exist. Creating...")
        _create_satellite_relationships_graph(db)
        print(f"Graph '{GRAPH_NAME}' created.")

    print("\nMigration complete.")
    return True


def _create_satellite_relationships_graph(db):
    edge_collections = [
        "constellation_membership",
        "registration_links",
        "orbital_proximity",
        "collision_risk_edges",
        "satellite_lineage",
    ]
    for ecol in edge_collections:
        if not db.has_collection(ecol):
            db.create_collection(ecol, edge=True)

    db.create_graph(
        GRAPH_NAME,
        edge_definitions=[
            {"edge_collection": "constellation_membership", "from_vertex_collections": [NEW_COLLECTION], "to_vertex_collections": [NEW_COLLECTION]},
            {"edge_collection": "registration_links", "from_vertex_collections": [NEW_COLLECTION], "to_vertex_collections": ["registration_documents"]},
            {"edge_collection": "orbital_proximity", "from_vertex_collections": [NEW_COLLECTION], "to_vertex_collections": [NEW_COLLECTION]},
            {"edge_collection": "collision_risk_edges", "from_vertex_collections": [NEW_COLLECTION], "to_vertex_collections": [NEW_COLLECTION]},
            {"edge_collection": "satellite_lineage", "from_vertex_collections": [NEW_COLLECTION], "to_vertex_collections": [NEW_COLLECTION]},
        ],
    )


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    success = run(dry_run=dry_run)
    sys.exit(0 if success else 1)
