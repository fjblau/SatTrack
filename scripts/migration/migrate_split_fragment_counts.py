#!/usr/bin/env python3
"""
Migrate: Split canonical.fragment_count into three distinct fragment count fields.

Renames canonical.fragment_count → canonical.fragment_count_kessler on every
fragmentation_events document that still has the old field.  Removes the old field.
Adds fragment_count_discos and fragment_count_estimated (both null) if not yet present.

Idempotent: re-running after migration completes is a safe no-op (the AQL FILTER
ensures only documents with the old field are touched).

Migration is logged as a transformation entry on each affected document with
action="migrate_split_fragment_counts".

USAGE:
    python scripts/migration/migrate_split_fragment_counts.py [--dry-run] [--yes]

Pass --yes (or -y) to skip the interactive confirmation prompt.
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


def run(dry_run: bool = False, yes: bool = False) -> bool:
    if not db_conn.connect_arangodb():
        logger.error("Failed to connect to ArangoDB")
        return False

    db = db_module.db

    count_cursor = db.aql.execute(
        "RETURN COUNT(FOR e IN fragmentation_events FILTER e.canonical.fragment_count != null RETURN 1)"
    )
    affected = list(count_cursor)[0] or 0

    logger.info(f"fragmentation_events documents with old canonical.fragment_count: {affected}")

    if affected == 0:
        logger.info("Nothing to migrate — migration already complete or collection is empty.")
        return True

    if dry_run:
        logger.info(f"[DRY RUN] Would migrate {affected} documents. No changes made.")
        return True

    if yes:
        logger.info(f"Migrating {affected} documents (--yes flag set).")
    else:
        try:
            response = input(
                f"\nMigrate {affected} fragmentation_events documents? "
                f"(renames canonical.fragment_count → canonical.fragment_count_kessler) (y/N): "
            ).strip().lower()
        except EOFError:
            logger.error("stdin is not interactive. Re-run with --yes to skip this prompt.")
            return False
        if response not in ("y", "yes"):
            logger.info("Cancelled.")
            return False

    now = datetime.now(timezone.utc).isoformat()

    migrate_aql = """
    FOR e IN fragmentation_events
        FILTER e.canonical.fragment_count != null

        LET old_count = e.canonical.fragment_count
        LET new_canonical = MERGE(
            UNSET(e.canonical, "fragment_count"),
            {
                fragment_count_kessler: old_count,
                fragment_count_discos: e.canonical.fragment_count_discos,
                fragment_count_estimated: e.canonical.fragment_count_estimated
            }
        )
        LET new_transformations = APPEND(
            SLICE(e.metadata.transformations || [], -9),
            [{
                source: "migration",
                action: "migrate_split_fragment_counts",
                timestamp: @now,
                operator: "migrate_split_fragment_counts",
                renamed_from: "canonical.fragment_count",
                renamed_to: "canonical.fragment_count_kessler",
                value: old_count
            }]
        )
        LET new_metadata = MERGE(e.metadata || {}, {transformations: new_transformations})

        REPLACE e WITH MERGE(e, {canonical: new_canonical, metadata: new_metadata})
        IN fragmentation_events

        COLLECT WITH COUNT INTO updated
        RETURN updated
    """

    cursor = db.aql.execute(migrate_aql, bind_vars={"now": now})
    migrated = list(cursor)[0] or 0
    logger.info(f"Migrated {migrated} documents.")

    remaining_cursor = db.aql.execute(
        "RETURN COUNT(FOR e IN fragmentation_events FILTER e.canonical.fragment_count != null RETURN 1)"
    )
    remaining = list(remaining_cursor)[0] or 0
    if remaining > 0:
        logger.warning(f"{remaining} documents still have canonical.fragment_count — investigate.")
        return False

    logger.info("Migration complete. All documents use the new fragment count fields.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrate canonical.fragment_count → canonical.fragment_count_kessler"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()
    success = run(dry_run=args.dry_run, yes=args.yes)
    sys.exit(0 if success else 1)
