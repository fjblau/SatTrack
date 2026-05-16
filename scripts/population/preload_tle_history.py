#!/usr/bin/env python3
"""
Preload historical TLEs for all satellites that appear in the Observations collection.

For each unique norad_id in observations, the script:
  1. Finds the min/max observation_epoch as the date range bounds.
  2. Checks whether TLE history for that norad_id + date range is already in the
     tle_history collection (zero API calls if already covered).
  3. If not covered, fetches the full range from SpaceTrack gp_history in a single
     bulk request and stores all returned TLEs.
  4. Waits 15 seconds before the next SpaceTrack call to respect rate limits.

No delay is introduced when the data is already cached — the wait only applies when
a live SpaceTrack request is actually made.

Requires SPACETRACK_USERNAME and SPACETRACK_PASSWORD to be set in the environment
(or .env file). Safe to re-run — already-covered satellites are skipped instantly.

Usage:
    python scripts/population/preload_tle_history.py [--delay SECONDS]
"""

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import database.connection as db_conn
from database.connection import COLLECTION_OBSERVATIONS
from api.services.tle_history_service import ensure_tle_history
from api.services.spacetrack_service import _credentials_configured


def get_observation_ranges(db) -> list[dict]:
    """
    Query the observations collection for every unique norad_id together with
    the earliest and latest observation_epoch for that satellite.

    Returns a list of dicts: { norad_id, min_epoch, max_epoch, observation_count }
    sorted by norad_id ascending.
    """
    aql = """
    FOR obs IN @@col
        FILTER obs.norad_id != null AND obs.observation_epoch != null
        COLLECT norad_id = TO_STRING(obs.norad_id)
            AGGREGATE
                min_epoch = MIN(obs.observation_epoch),
                max_epoch = MAX(obs.observation_epoch),
                n         = COUNT(1)
        SORT norad_id ASC
        RETURN { norad_id, min_epoch, max_epoch, observation_count: n }
    """
    cursor = db.aql.execute(aql, bind_vars={"@col": COLLECTION_OBSERVATIONS})
    return list(cursor)


def epoch_to_date(epoch_str: str) -> str:
    """Extract YYYY-MM-DD from an ISO-8601 observation_epoch string."""
    return epoch_str[:10]


def run(delay_seconds: int):
    print("Preload TLE History", flush=True)
    print(f"Rate-limit delay between SpaceTrack calls: {delay_seconds}s", flush=True)
    print(flush=True)

    if not db_conn.connect_arangodb():
        print("ERROR: Failed to connect to ArangoDB", flush=True)
        sys.exit(1)

    if not _credentials_configured():
        print(
            "WARNING: SPACETRACK_USERNAME / SPACETRACK_PASSWORD are not set.\n"
            "Already-cached TLE history will still be served from the DB, but new\n"
            "ranges cannot be fetched. Set credentials and re-run to fetch missing data.",
            flush=True,
        )

    db = db_conn.db

    if not db.has_collection(COLLECTION_OBSERVATIONS):
        print("Observations collection does not exist — nothing to do.", flush=True)
        return

    print("Scanning observations collection for unique satellites...", flush=True)
    ranges = get_observation_ranges(db)

    if not ranges:
        print("No observations found — nothing to preload.", flush=True)
        return

    total = len(ranges)
    print(f"Found {total} unique satellite(s) in observations.\n", flush=True)

    fetched_count = 0
    skipped_count = 0
    error_count = 0
    api_calls_made = 0

    for i, row in enumerate(ranges, start=1):
        norad_id = str(row["norad_id"])
        min_epoch = row["min_epoch"]
        max_epoch = row["max_epoch"]
        obs_count = row["observation_count"]

        from_date = epoch_to_date(min_epoch)
        to_date = epoch_to_date(max_epoch)

        print(
            f"[{i}/{total}] NORAD {norad_id:>8}  |  {obs_count:>5} obs  |  {from_date} → {to_date}",
            flush=True,
        )

        try:
            result = ensure_tle_history(norad_id, from_date, to_date)
        except Exception as exc:
            print(f"  ERROR: {exc}", flush=True)
            error_count += 1
            continue

        if result.get("already_covered"):
            cached = result.get("tle_count", 0)
            print(f"  Already cached ({cached} TLEs stored) — skipped", flush=True)
            skipped_count += 1
        else:
            fetched = result.get("fetched", 0)
            warning = result.get("warning")
            if warning:
                print(f"  WARNING: {warning}", flush=True)
            else:
                print(f"  Fetched and stored {fetched} TLE(s) from SpaceTrack", flush=True)
            fetched_count += 1
            api_calls_made += 1

            if i < total:
                print(f"  Waiting {delay_seconds}s before next SpaceTrack request...", flush=True)
                time.sleep(delay_seconds)

        print(flush=True)

    print("=" * 60, flush=True)
    print(f"Complete.", flush=True)
    print(f"  Satellites processed : {total}", flush=True)
    print(f"  Already cached       : {skipped_count}", flush=True)
    print(f"  Newly fetched        : {fetched_count}", flush=True)
    print(f"  SpaceTrack API calls : {api_calls_made}", flush=True)
    if error_count:
        print(f"  Errors               : {error_count}", flush=True)
    print(flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Preload historical TLEs for all satellites in the Observations collection"
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=15,
        metavar="SECONDS",
        help="Seconds to wait between SpaceTrack API calls (default: 15)",
    )
    args = parser.parse_args()
    run(delay_seconds=args.delay)


if __name__ == "__main__":
    main()
