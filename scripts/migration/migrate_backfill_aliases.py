#!/usr/bin/env python3
"""
Migrate: Backfill identifier_aliases on every object document.

Adds top-level field:
    identifier_aliases: {
        norad: "<norad_cat_id as string>",    (if canonical.norad_cat_id is set)
        cospar: "<international_designator>", (if canonical.international_designator is set)
    }

Existing identifier_aliases values are preserved; only missing keys are added.

USAGE:
    python migrate_backfill_aliases.py [--dry-run]
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import database as db_module


def run(dry_run=False):
    if not db_module.connect_mongodb():
        print("Failed to connect to ArangoDB")
        return False

    db = db_module.db
    COLLECTION = db_module.COLLECTION_NAME

    if not db.has_collection(COLLECTION):
        print(f"ERROR: Collection '{COLLECTION}' not found. Run migrate_collection_rename first.")
        return False

    total_cursor = db.aql.execute(
        "RETURN COUNT(FOR doc IN @@collection RETURN 1)",
        bind_vars={"@collection": COLLECTION},
    )
    total = list(total_cursor)[0] or 0
    print(f"=== Backfill identifier_aliases ===\n")
    print(f"Total documents: {total:,}")

    if dry_run:
        print("[DRY-RUN] No changes made.")
        db_module.disconnect_mongodb()
        return True

    response = input(f"\nBackfill identifier_aliases on all {total:,} documents? (y/N): ").strip().lower()
    if response not in ("y", "yes"):
        print("Cancelled.")
        db_module.disconnect_mongodb()
        return False

    timestamp = datetime.now(timezone.utc).isoformat()

    update_aql = """
    FOR doc IN @@collection
        LET existing_aliases = doc.identifier_aliases || {}

        LET norad_val = (
            doc.canonical.norad_cat_id != null
            ? TO_STRING(doc.canonical.norad_cat_id)
            : existing_aliases.norad
        )
        LET cospar_val = (
            doc.canonical.international_designator != null
            ? doc.canonical.international_designator
            : existing_aliases.cospar
        )

        LET new_aliases = MERGE(existing_aliases, {
            norad:  norad_val,
            cospar: cospar_val
        })

        FILTER new_aliases != existing_aliases

        UPDATE doc WITH {
            identifier_aliases: new_aliases,
            metadata: MERGE(doc.metadata || {}, {
                last_updated_at: @timestamp
            })
        } IN @@collection

        COLLECT WITH COUNT INTO updated
        RETURN updated
    """

    print("\nBackfilling...")
    cursor = db.aql.execute(
        update_aql,
        bind_vars={"@collection": COLLECTION, "timestamp": timestamp},
    )
    updated = list(cursor)[0] or 0
    print(f"Updated {updated:,} documents with identifier_aliases.")

    norad_count_cursor = db.aql.execute(
        "RETURN COUNT(FOR doc IN @@collection FILTER doc.identifier_aliases.norad != null RETURN 1)",
        bind_vars={"@collection": COLLECTION},
    )
    norad_count = list(norad_count_cursor)[0] or 0
    print(f"\nDocuments with identifier_aliases.norad: {norad_count:,}")

    db_module.disconnect_mongodb()
    return True


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    success = run(dry_run=dry_run)
    sys.exit(0 if success else 1)
