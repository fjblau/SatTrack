#!/usr/bin/env python3
"""
Promote GCAT parent relationships: write canonical.parent_gcat_id and create
fragmented_from edges so parent objects appear in the provenance graph.

For each object that has sources.gcat.parent set, this script:
  1. Promotes the value to canonical.parent_gcat_id (so the raw link is queryable).
  2. Resolves the parent object in the objects collection (by GCAT JCAT identifier).
  3. Creates a fragmented_from edge from child → parent in the provenance graph.

Usage:
    python scripts/maintenance/promote_gcat_parent_edges.py [--dry-run] [--yes]

Options:
    --dry-run   Preview changes without writing to the database.
    --yes       Skip the confirmation prompt.
    -v          Print each affected document identifier.
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


def _find_parent_doc(db, jcat_id: str):
    """
    Locate a parent object by its GCAT JCAT identifier.

    Tries the canonical key format "GCAT-{jcat_id}" first, then falls back to a
    full collection scan matching sources.gcat.jcat.
    """
    try:
        doc = db.collection(COL).get(f"GCAT-{jcat_id}")
        if doc:
            return doc
    except Exception:
        pass

    cursor = db.aql.execute(
        "FOR doc IN @@col FILTER doc.sources.gcat.jcat == @jcat LIMIT 1 RETURN doc",
        bind_vars={"@col": COL, "jcat": jcat_id},
    )
    rows = list(cursor)
    return rows[0] if rows else None


def _upsert_edge(db, from_id: str, to_id: str, extra: dict, dry_run: bool) -> bool:
    if dry_run:
        logger.info(f"  [DRY RUN] edge {from_id} → {to_id}")
        return True

    now = datetime.now(timezone.utc).isoformat()
    col = db.collection(EDGE_COL)
    cursor = db.aql.execute(
        "FOR e IN @@col FILTER e._from == @f AND e._to == @t LIMIT 1 RETURN e",
        bind_vars={"@col": EDGE_COL, "f": from_id, "t": to_id},
    )
    existing = (list(cursor) or [None])[0]

    edge_doc = {"_from": from_id, "_to": to_id, **extra}
    if existing:
        transformations = existing.get("metadata", {}).get("transformations", [])
        transformations.append({
            "source": "gcat",
            "action": "update",
            "timestamp": now,
            "operator": "promote_gcat_parent_edges",
        })
        col.update({"_key": existing["_key"], **edge_doc,
                     "metadata": {**existing.get("metadata", {}),
                                  "transformations": transformations[-10:]}})
    else:
        child_key = from_id.split("/", 1)[-1]
        parent_key = to_id.split("/", 1)[-1]
        transformations = [{
            "source": "gcat",
            "action": "create",
            "timestamp": now,
            "operator": "promote_gcat_parent_edges",
        }]
        edge_doc["_key"] = f"{child_key}--{parent_key}"
        edge_doc["metadata"] = {"transformations": transformations}
        col.insert(edge_doc)
    return True


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

    if dry_run:
        print(f"\n[DRY-RUN] Previewing edge creation for {len(candidates):,} objects.\n")
    elif not yes:
        try:
            resp = input(f"\nProceed? (y/N): ").strip().lower()
        except EOFError:
            resp = "y"
        if resp not in ("y", "yes"):
            print("Cancelled.")
            return False

    now = datetime.now(timezone.utc).isoformat()
    objects_col = db.collection(COL)

    promoted_canonical = 0
    edges_created = 0
    parent_not_found = 0
    errors = 0

    for child in candidates:
        child_key = child["_key"]
        child_id = child["_id"]
        parent_jcat = child["parent"]

        if verbose:
            logger.info(f"Processing {child['id']}  parent={parent_jcat}")

        parent_doc = _find_parent_doc(db, parent_jcat)
        if not parent_doc:
            logger.warning(f"  Parent not found for {child['id']} (GCAT JCAT={parent_jcat})")
            parent_not_found += 1
            continue

        parent_id = parent_doc["_id"]

        if not dry_run:
            try:
                existing_doc = objects_col.get(child_key)
                current_canonical = existing_doc.get("canonical", {})
                if not current_canonical.get("parent_gcat_id"):
                    transformations = existing_doc.get("metadata", {}).get("transformations", [])
                    transformations.append({
                        "source_field": "sources.gcat.parent",
                        "target_field": "canonical.parent_gcat_id",
                        "value": parent_jcat,
                        "timestamp": now,
                        "promoted_by": "promote_gcat_parent_edges",
                    })
                    objects_col.update({
                        "_key": child_key,
                        "canonical": {**current_canonical, "parent_gcat_id": parent_jcat},
                        "metadata": {
                            **existing_doc.get("metadata", {}),
                            "transformations": transformations[-10:],
                        },
                    })
                    promoted_canonical += 1
            except Exception as exc:
                logger.error(f"  Failed to promote canonical for {child['id']}: {exc}")
                errors += 1
                continue
        else:
            promoted_canonical += 1

        ok = _upsert_edge(
            db,
            from_id=child_id,
            to_id=parent_id,
            extra={
                "source": "gcat",
                "relationship_type": "parent",
                "confidence": 1.0,
                "confidence_label": "high",
            },
            dry_run=dry_run,
        )
        if ok:
            edges_created += 1
        else:
            errors += 1

    print(f"\n=== Summary ===")
    print(f"canonical.parent_gcat_id promoted : {promoted_canonical:,}")
    print(f"fragmented_from edges created/updated: {edges_created:,}")
    print(f"Parent objects not found           : {parent_not_found:,}")
    if errors:
        print(f"Errors                             : {errors:,}")

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Promote GCAT parent field to canonical and create fragmented_from edges"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("-v", "--verbose", action="store_true", help="Log each document")
    args = parser.parse_args()
    success = run(dry_run=args.dry_run, yes=args.yes, verbose=args.verbose)
    sys.exit(0 if success else 1)
