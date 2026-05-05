#!/usr/bin/env python3
"""
Find and clear TLE data where the NORAD in the stored TLE line1 does not match
the object's canonical.norad_cat_id.

This can happen when the intl_des TLE fallback fires before the object's full
document has loaded (race condition in the UI), returning the first piece of the
launch (e.g. payload) instead of the correct piece (e.g. rocket body).

Affected fields cleared per object:
  - canonical.tle          (the stored TLE dict)
  - sources.tleapi         (the raw tleapi source envelope)

After running this script, the correct TLE will be fetched on next page load
(now that the NORAD-mismatch guards are in place in the service and router).

Usage:
    python scripts/maintenance/fix_tle_norad_mismatch.py [--dry-run]
"""
import sys
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

import database.connection as db_conn
import database as db_module

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _norad_from_line1(line1: str) -> str:
    """Extract the zero-stripped NORAD catalogue number from TLE line 1."""
    try:
        return line1[2:7].strip().lstrip("0")
    except Exception:
        return ""


def run(dry_run: bool = False):
    if not db_conn.connect_arangodb():
        logger.error("Failed to connect to ArangoDB")
        sys.exit(1)

    cursor = db_module.db.aql.execute("""
        FOR obj IN objects
            FILTER obj.canonical.tle.line1 != null
               AND obj.canonical.norad_cat_id != null
            RETURN {
                _key: obj._key,
                norad: obj.canonical.norad_cat_id,
                tle_line1: obj.canonical.tle.line1,
                tleapi_norad: obj.sources.tleapi.norad_id
            }
    """)

    mismatches = []
    for row in cursor:
        obj_norad = str(row["norad"]).strip().lstrip("0")
        tle_norad = _norad_from_line1(row["tle_line1"] or "")
        if tle_norad and tle_norad != obj_norad:
            mismatches.append(row)

    logger.info(f"Found {len(mismatches)} objects with mismatched TLE NORAD")

    if not mismatches:
        return

    col = db_module.db.collection("objects")
    now = datetime.now(timezone.utc).isoformat()
    cleared = 0
    errors = 0

    for row in mismatches:
        obj_norad = str(row["norad"]).strip().lstrip("0")
        tle_norad = _norad_from_line1(row["tle_line1"] or "")
        tleapi_norad = str(row.get("tleapi_norad") or "").strip().lstrip("0")

        if dry_run:
            logger.info(
                f"[DRY RUN] {row['_key']}: obj_norad={obj_norad} "
                f"tle_norad={tle_norad} tleapi_norad={tleapi_norad} — would clear TLE"
            )
            cleared += 1
            continue

        try:
            existing = col.get(row["_key"])
            if not existing:
                logger.warning(f"Object {row['_key']} not found; skipping")
                continue

            transformations = existing.get("metadata", {}).get("transformations", [])
            transformations = transformations[-9:] + [{
                "source": "fix_tle_norad_mismatch",
                "action": "clear_mismatched_tle",
                "timestamp": now,
                "operator": "fix_tle_norad_mismatch",
                "detail": f"Cleared TLE with NORAD {tle_norad} from object with NORAD {obj_norad}",
            }]

            sources = existing.get("sources", {})
            sources.pop("tleapi", None)

            canonical = existing.get("canonical", {})
            canonical.pop("tle", None)

            col.update({
                "_key": row["_key"],
                "canonical": canonical,
                "sources": sources,
                "metadata": {
                    **existing.get("metadata", {}),
                    "transformations": transformations,
                },
            })
            logger.info(
                f"Cleared mismatched TLE from {row['_key']} "
                f"(obj_norad={obj_norad}, tle_norad={tle_norad})"
            )
            cleared += 1
        except Exception as exc:
            logger.error(f"Failed to clear TLE on {row['_key']}: {exc}")
            errors += 1

    logger.info(f"Done — cleared={cleared} errors={errors} total_mismatches={len(mismatches)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clear TLEs whose NORAD doesn't match the object's NORAD")
    parser.add_argument("--dry-run", action="store_true", help="Report mismatches without modifying the DB")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
