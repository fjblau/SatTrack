#!/usr/bin/env python3
"""
Normalize canonical.object_type values across all satellite records.

Different import sources have stored object types with inconsistent labels:
  - "PAY"          → "PAYLOAD"   (Space-Track / UNOOSA abbreviation)
  - "DEB"          → "DEBRIS"    (Space-Track abbreviation)
  - "R/B"          → "ROCKET BODY"
  - "UNK"          → "UNKNOWN"
  - Raw GCAT codes → mapped by first byte (P→PAYLOAD, D→DEBRIS, C/R→ROCKET BODY)

After this script runs every record will have one of:
  PAYLOAD | DEBRIS | ROCKET BODY | UNKNOWN

USAGE:
    python normalize_object_types.py [--dry-run]
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import database as db_module

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


CANONICAL_VALUES = {"PAYLOAD", "DEBRIS", "ROCKET BODY", "UNKNOWN"}

DIRECT_MAP = {
    "PAY":          "PAYLOAD",
    "DEB":          "DEBRIS",
    "R/B":          "ROCKET BODY",
    "UNK":          "UNKNOWN",
    "ROCKET BODY":  "ROCKET BODY",
    "PAYLOAD":      "PAYLOAD",
    "DEBRIS":       "DEBRIS",
    "UNKNOWN":      "UNKNOWN",
}

BYTE1_MAP = {
    "P": "PAYLOAD",
    "S": "PAYLOAD",
    "D": "DEBRIS",
    "C": "ROCKET BODY",
    "R": "ROCKET BODY",
    "X": "UNKNOWN",
    "Z": "UNKNOWN",
}


def normalize(raw):
    """Return the canonical object_type for a raw value, or None if already correct."""
    if raw is None:
        return None
    stripped = raw.strip()
    if not stripped:
        return None
    upper = stripped.upper()
    if upper in DIRECT_MAP:
        result = DIRECT_MAP[upper]
    else:
        byte1 = stripped[0].upper()
        result = BYTE1_MAP.get(byte1, "UNKNOWN")
    return result if result != stripped else None


def normalize_object_types(dry_run=False):
    if not db_module.connect_mongodb():
        print("Failed to connect to ArangoDB")
        return False

    db = db_module.db
    COLLECTION = db_module.COLLECTION_NAME

    count_query = """
    FOR doc IN @@collection
        FILTER doc.canonical.object_type != null
        COLLECT WITH COUNT INTO c
        RETURN c
    """
    total_with_type = list(db.aql.execute(count_query, bind_vars={"@collection": COLLECTION}))[0]

    sample_query = """
    FOR doc IN @@collection
        FILTER doc.canonical.object_type != null
        LIMIT 200
        RETURN doc.canonical.object_type
    """
    raw_values = list(db.aql.execute(sample_query, bind_vars={"@collection": COLLECTION}))

    from collections import Counter
    value_counts = Counter(raw_values)

    print("=== Normalize canonical.object_type ===\n")
    print(f"Records with object_type set: {total_with_type:,}")
    print("\nCurrent value distribution (sampled):")
    for val, cnt in value_counts.most_common():
        normalized = normalize(val)
        flag = "" if normalized is None else f"  →  {normalized}"
        print(f"  {str(val):30s}: {cnt:,}{flag}")

    if dry_run:
        print("\n[DRY-RUN] No changes made.")
        return True

    response = input(f"\nNormalize object_type across all {total_with_type:,} records? (y/N): ").strip().lower()
    if response not in ("y", "yes"):
        print("Cancelled.")
        return False

    timestamp = datetime.now(timezone.utc).isoformat()

    update_query = """
    FOR doc IN @@collection
        FILTER doc.canonical.object_type != null

        LET raw = doc.canonical.object_type
        LET upper = UPPER(TRIM(raw))
        LET byte1 = UPPER(LEFT(TRIM(raw), 1))

        LET normalized = (
            upper == "PAYLOAD"      ? "PAYLOAD"      :
            upper == "PAY"          ? "PAYLOAD"      :
            upper == "DEBRIS"       ? "DEBRIS"        :
            upper == "DEB"          ? "DEBRIS"        :
            upper == "ROCKET BODY"  ? "ROCKET BODY"  :
            upper == "R/B"          ? "ROCKET BODY"  :
            upper == "UNKNOWN"      ? "UNKNOWN"       :
            upper == "UNK"          ? "UNKNOWN"       :
            byte1 == "P"            ? "PAYLOAD"      :
            byte1 == "S"            ? "PAYLOAD"      :
            byte1 == "D"            ? "DEBRIS"        :
            byte1 == "C"            ? "ROCKET BODY"  :
            byte1 == "R"            ? "ROCKET BODY"  :
            "UNKNOWN"
        )

        FILTER normalized != raw

        UPDATE doc WITH {
            canonical: MERGE(doc.canonical, { object_type: normalized }),
            metadata: MERGE(doc.metadata || {}, {
                transformations: APPEND(
                    doc.metadata.transformations || [],
                    [{
                        timestamp: @timestamp,
                        source_field: "canonical.object_type",
                        target_field: "canonical.object_type",
                        old_value: raw,
                        value: normalized,
                        promoted_by: "normalize_object_types_script"
                    }]
                ),
                last_updated_at: @timestamp
            })
        } IN @@collection

        COLLECT WITH COUNT INTO updated
        RETURN updated
    """

    print("\nUpdating records...")
    cursor = db.aql.execute(
        update_query,
        bind_vars={"@collection": COLLECTION, "timestamp": timestamp}
    )
    updated = list(cursor)[0]
    print(f"✓ Normalized {updated:,} records")

    verify_query = """
    FOR doc IN @@collection
        FILTER doc.canonical.object_type != null
        COLLECT type = doc.canonical.object_type WITH COUNT INTO cnt
        SORT cnt DESC
        RETURN { type, cnt }
    """
    rows = list(db.aql.execute(verify_query, bind_vars={"@collection": COLLECTION}))
    print("\nFinal distribution:")
    for row in rows:
        print(f"  {str(row['type']):30s}: {row['cnt']:,}")

    db_module.disconnect_mongodb()
    return True


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    success = normalize_object_types(dry_run=dry_run)
    sys.exit(0 if success else 1)
