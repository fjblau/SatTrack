#!/usr/bin/env python3
"""
Migrate: Add canonical.object_class to every object document.

Maps from canonical.object_type (including ALL CAPS production values) to
the DISCOSweb-aligned object_class enum:

  Payload                     → Payload
  Rocket Body / R/B           → Rocket Body
  Mission-Related Object      → Mission-Related Object
  Debris / DEB / DEBRIS       → Unknown (refined by Spec 2 DISCOS promote)
  Unknown / UNK / UNKNOWN     → Unknown
  PAYLOAD / PAY               → Payload
  ROCKET BODY                 → Rocket Body

canonical.object_type is KEPT (deprecated; removed in follow-on PR).

USAGE:
    python migrate_classify_objects.py [--dry-run] [--yes]

Pass --yes (or -y) to skip the interactive confirmation prompt (required
when stdin is not a TTY, e.g. Docker / Railway / CI environments).
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


OBJECT_TYPE_TO_CLASS = {
    "PAYLOAD":                  "Payload",
    "PAY":                      "Payload",
    "Payload":                  "Payload",
    "payload":                  "Payload",
    "ROCKET BODY":              "Rocket Body",
    "R/B":                      "Rocket Body",
    "Rocket Body":              "Rocket Body",
    "rocket body":              "Rocket Body",
    "DEBRIS":                   "Unknown",
    "DEB":                      "Unknown",
    "Debris":                   "Unknown",
    "debris":                   "Unknown",
    "UNKNOWN":                  "Unknown",
    "UNK":                      "Unknown",
    "Unknown":                  "Unknown",
    "unknown":                  "Unknown",
    "Mission-Related Object":   "Mission-Related Object",
    "MRO":                      "Mission-Related Object",
    "Rocket Fragmentation Debris":   "Rocket Fragmentation Debris",
    "Payload Fragmentation Debris":  "Payload Fragmentation Debris",
}

VALID_CLASSES = {
    "Payload",
    "Rocket Body",
    "Mission-Related Object",
    "Rocket Fragmentation Debris",
    "Payload Fragmentation Debris",
    "Unknown",
}


def classify(object_type):
    if object_type is None:
        return "Unknown"
    stripped = object_type.strip()
    result = OBJECT_TYPE_TO_CLASS.get(stripped)
    if result:
        return result
    upper = stripped.upper()
    result = OBJECT_TYPE_TO_CLASS.get(upper)
    if result:
        return result
    if upper.startswith("P"):
        return "Payload"
    if upper.startswith("R"):
        return "Rocket Body"
    if upper.startswith("D"):
        return "Unknown"
    return "Unknown"


def run(dry_run=False, yes=False):
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

    sample_cursor = db.aql.execute(
        """
        FOR doc IN @@collection
            COLLECT type = doc.canonical.object_type WITH COUNT INTO cnt
            SORT cnt DESC
            RETURN {type: type, count: cnt}
        """,
        bind_vars={"@collection": COLLECTION},
    )
    sample = list(sample_cursor)

    print(f"=== Classify objects (add canonical.object_class) ===\n")
    print(f"Total documents: {total:,}")
    print("\nCurrent object_type distribution:")
    for row in sample:
        cls = classify(row["type"])
        print(f"  {str(row['type']):30s}: {row['count']:>8,}  →  {cls}")

    if dry_run:
        print("\n[DRY-RUN] No changes made.")
        db_module.disconnect_mongodb()
        return True

    if yes:
        print(f"\nClassify all {total:,} documents? (y/N): y  [--yes flag set]")
    else:
        try:
            response = input(f"\nClassify all {total:,} documents? (y/N): ").strip().lower()
        except EOFError:
            print("\nERROR: stdin is not interactive. Re-run with --yes to skip this prompt.")
            db_module.disconnect_mongodb()
            return False
        if response not in ("y", "yes"):
            print("Cancelled.")
            db_module.disconnect_mongodb()
            return False

    timestamp = datetime.now(timezone.utc).isoformat()

    update_aql = """
    FOR doc IN @@collection
        LET raw = doc.canonical.object_type
        LET upper = raw != null ? UPPER(TRIM(TO_STRING(raw))) : "UNKNOWN"

        LET object_class = (
            upper == "PAYLOAD"       ? "Payload"      :
            upper == "PAY"           ? "Payload"      :
            upper == "ROCKET BODY"   ? "Rocket Body"  :
            upper == "R/B"           ? "Rocket Body"  :
            upper == "DEBRIS"        ? "Unknown"       :
            upper == "DEB"           ? "Unknown"       :
            upper == "UNKNOWN"       ? "Unknown"       :
            upper == "UNK"           ? "Unknown"       :
            "Unknown"
        )

        FILTER doc.canonical.object_class == null OR doc.canonical.object_class != object_class

        UPDATE doc WITH {
            canonical: MERGE(doc.canonical, { object_class: object_class }),
            metadata: MERGE(doc.metadata || {}, {
                transformations: APPEND(
                    doc.metadata.transformations || [],
                    [{
                        timestamp: @timestamp,
                        source_field: "canonical.object_type",
                        target_field: "canonical.object_class",
                        old_value: doc.canonical.object_class,
                        value: object_class,
                        promoted_by: "migrate_classify_objects"
                    }]
                ),
                last_updated_at: @timestamp
            })
        } IN @@collection

        COLLECT WITH COUNT INTO updated
        RETURN updated
    """

    print("\nUpdating documents...")
    cursor = db.aql.execute(
        update_aql,
        bind_vars={"@collection": COLLECTION, "timestamp": timestamp},
    )
    updated = list(cursor)[0] or 0
    print(f"Updated {updated:,} documents with object_class.")

    verify_cursor = db.aql.execute(
        """
        FOR doc IN @@collection
            COLLECT cls = doc.canonical.object_class WITH COUNT INTO cnt
            SORT cnt DESC
            RETURN {class: cls, count: cnt}
        """,
        bind_vars={"@collection": COLLECTION},
    )
    print("\nFinal object_class distribution:")
    for row in list(verify_cursor):
        print(f"  {str(row['class']):40s}: {row['count']:>8,}")

    db_module.disconnect_mongodb()
    return True


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    yes = "--yes" in sys.argv or "-y" in sys.argv
    success = run(dry_run=dry_run, yes=yes)
    sys.exit(0 if success else 1)
