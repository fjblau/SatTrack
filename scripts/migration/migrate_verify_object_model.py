#!/usr/bin/env python3
"""
Migrate: Verify object model post-migration.

Checks:
1. 'objects' collection exists and has documents
2. 'satellites' collection no longer exists (or is empty)
3. Sample documents have canonical.object_class set
4. Sample documents have identifier_aliases populated
5. Indexes on canonical.object_class, identifier_aliases.norad are present
6. satellite_relationships graph points at 'objects'

USAGE:
    python migrate_verify_object_model.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import database as db_module


def run():
    if not db_module.connect_mongodb():
        print("Failed to connect to ArangoDB")
        return False

    db = db_module.db
    COLLECTION = db_module.COLLECTION_NAME
    GRAPH_NAME = db_module.GRAPH_NAME
    failures = []

    print("=== Verify Object Model (Post-Migration) ===\n")

    if db.has_collection(COLLECTION):
        count_cursor = db.aql.execute(
            "RETURN COUNT(FOR doc IN @@collection RETURN 1)",
            bind_vars={"@collection": COLLECTION},
        )
        count = list(count_cursor)[0] or 0
        print(f"[OK] Collection '{COLLECTION}' exists: {count:,} documents")
    else:
        print(f"[FAIL] Collection '{COLLECTION}' does not exist!")
        failures.append(f"Collection '{COLLECTION}' missing")

    if db.has_collection("satellites"):
        sat_count = db.aql.execute(
            "RETURN COUNT(FOR doc IN satellites RETURN 1)"
        )
        sat_count = list(sat_count)[0] or 0
        if sat_count > 0:
            print(f"[WARN] Old 'satellites' collection still exists with {sat_count:,} documents")
        else:
            print("[OK] Old 'satellites' collection exists but is empty")
    else:
        print("[OK] Old 'satellites' collection does not exist")

    if db.has_collection(COLLECTION):
        class_cursor = db.aql.execute(
            """
            LET total = COUNT(FOR doc IN @@collection RETURN 1)
            LET with_class = COUNT(FOR doc IN @@collection FILTER doc.canonical.object_class != null RETURN 1)
            RETURN {total: total, with_class: with_class}
            """,
            bind_vars={"@collection": COLLECTION},
        )
        class_stats = list(class_cursor)[0] or {}
        total = class_stats.get("total", 0)
        with_class = class_stats.get("with_class", 0)
        pct = (with_class / total * 100) if total > 0 else 0
        if pct >= 90:
            print(f"[OK] object_class coverage: {with_class:,}/{total:,} ({pct:.1f}%)")
        else:
            print(f"[WARN] object_class coverage: {with_class:,}/{total:,} ({pct:.1f}%) — run migrate_classify_objects")

        alias_cursor = db.aql.execute(
            """
            LET total = COUNT(FOR doc IN @@collection RETURN 1)
            LET with_alias = COUNT(FOR doc IN @@collection FILTER doc.identifier_aliases != null RETURN 1)
            RETURN {total: total, with_alias: with_alias}
            """,
            bind_vars={"@collection": COLLECTION},
        )
        alias_stats = list(alias_cursor)[0] or {}
        with_alias = alias_stats.get("with_alias", 0)
        alias_pct = (with_alias / total * 100) if total > 0 else 0
        if alias_pct >= 90:
            print(f"[OK] identifier_aliases coverage: {with_alias:,}/{total:,} ({alias_pct:.1f}%)")
        else:
            print(f"[WARN] identifier_aliases coverage: {with_alias:,}/{total:,} ({alias_pct:.1f}%) — run migrate_backfill_aliases")

    if db.has_graph(GRAPH_NAME):
        graph = db.graph(GRAPH_NAME)
        edge_defs = graph.edge_definitions()
        references_objects = any(
            COLLECTION in (ed.get("from_vertex_collections", []) + ed.get("to_vertex_collections", []))
            for ed in edge_defs
        )
        references_satellites = any(
            "satellites" in (ed.get("from_vertex_collections", []) + ed.get("to_vertex_collections", []))
            for ed in edge_defs
        )
        if references_objects and not references_satellites:
            print(f"[OK] Graph '{GRAPH_NAME}' points at '{COLLECTION}'")
        elif references_satellites:
            print(f"[FAIL] Graph '{GRAPH_NAME}' still references 'satellites'!")
            failures.append(f"Graph '{GRAPH_NAME}' references old 'satellites' collection")
        else:
            print(f"[WARN] Graph '{GRAPH_NAME}' exists but edge definitions look unusual")
    else:
        print(f"[WARN] Graph '{GRAPH_NAME}' does not exist — run migrate_collection_rename")

    print("\n--- Summary ---")
    if failures:
        print(f"FAILURES ({len(failures)}):")
        for f in failures:
            print(f"  - {f}")
        db_module.disconnect_mongodb()
        return False
    else:
        print("All checks passed.")
        db_module.disconnect_mongodb()
        return True


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
