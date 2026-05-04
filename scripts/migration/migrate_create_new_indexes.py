#!/usr/bin/env python3
"""
Migrate: Create new indexes on the 'objects' collection.

Adds hash indexes on:
- canonical.object_class
- identifier_aliases.norad
- identifier_aliases.cospar

USAGE:
    python migrate_create_new_indexes.py [--dry-run]
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


def run(dry_run=False):
    if not db_module.connect_mongodb():
        print("Failed to connect to ArangoDB")
        return False

    db = db_module.db
    COLLECTION = db_module.COLLECTION_NAME

    if not db.has_collection(COLLECTION):
        print(f"ERROR: Collection '{COLLECTION}' not found. Run migrate_collection_rename first.")
        return False

    print(f"=== Create new indexes on '{COLLECTION}' ===\n")

    new_indexes = [
        {"fields": ["canonical.object_class"], "unique": False, "description": "canonical.object_class (hash)"},
        {"fields": ["identifier_aliases.norad"], "unique": False, "description": "identifier_aliases.norad (hash)"},
        {"fields": ["identifier_aliases.cospar"], "unique": False, "description": "identifier_aliases.cospar (hash)"},
    ]

    for idx in new_indexes:
        print(f"Index: {idx['description']}")
        if dry_run:
            print("  [DRY-RUN] Would create index")
        else:
            col = db.collection(COLLECTION)
            col.add_persistent_index(fields=idx["fields"], unique=idx["unique"])
            print(f"  Created.")

    print("\nDone.")
    db_module.disconnect_mongodb()
    return True


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    success = run(dry_run=dry_run)
    sys.exit(0 if success else 1)
