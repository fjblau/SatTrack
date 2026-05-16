#!/usr/bin/env python3
"""
Compute and store location data for observations using TLE history.

For every observation in the observations collection, finds the closest
previous TLE from the tle_history collection (matched by norad_id and
observation_epoch), then uses SGP4 propagation to compute the satellite's
geodetic position (latitude, longitude, altitude) at the observation time.
Also extracts parsed TLE orbital parameters and stores everything in a
`location` sub-document on each observation.

Runs in batches for maximum throughput:
  - One AQL query fetches a page of observations needing processing
  - One AQL query fetches all relevant TLE records for that page's NORAD IDs
  - Python performs binary search + SGP4 per observation
  - One AQL bulk-update writes all computed locations back

USAGE:
    python compute_observation_locations.py [--batch-size N] [--dry-run] [--yes] [--recompute]

OPTIONS:
    --batch-size N   Documents per batch (default: 200)
    --dry-run        Preview without writing to database
    --yes            Skip confirmation prompt
    --recompute      Recompute even for observations that already have location
"""

import sys
import argparse
import bisect
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from database import connect_arangodb
import database.connection as db_conn
from database.connection import COLLECTION_OBSERVATIONS, COLLECTION_TLE_HISTORY


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--batch-size", type=int, default=200, metavar="N")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--recompute", action="store_true", help="Recompute existing location nodes")
    return p.parse_args()


def parse_epoch(epoch_str: str) -> Optional[datetime]:
    if not epoch_str:
        return None
    try:
        return datetime.fromisoformat(epoch_str.replace("Z", "+00:00"))
    except ValueError:
        return None


def compute_orbital_params(line2: str) -> Optional[dict]:
    import math
    GM = 398600.4418
    EARTH_RADIUS_KM = 6378.137
    try:
        inclination = float(line2[8:16])
        eccentricity = float("0." + line2[26:33])
        mean_motion_rev_day = float(line2[52:63])
        period_minutes = 1440.0 / mean_motion_rev_day
        n_rad_per_sec = (mean_motion_rev_day * 2 * math.pi) / 86400.0
        semi_major_axis = (GM / (n_rad_per_sec ** 2)) ** (1.0 / 3.0)
        apogee = semi_major_axis * (1 + eccentricity) - EARTH_RADIUS_KM
        perigee = semi_major_axis * (1 - eccentricity) - EARTH_RADIUS_KM
        return {
            "inclination_degrees": round(inclination, 4),
            "eccentricity": round(eccentricity, 7),
            "mean_motion_rev_day": round(mean_motion_rev_day, 6),
            "period_minutes": round(period_minutes, 4),
            "semi_major_axis_km": round(semi_major_axis, 4),
            "apogee_km": round(apogee, 4),
            "perigee_km": round(perigee, 4),
        }
    except (IndexError, ValueError, ZeroDivisionError):
        return None


def compute_geodetic(line1: str, line2: str, obs_dt: datetime) -> Optional[dict]:
    try:
        from sgp4.api import Satrec, jday
        from skyfield.api import load, wgs84
        from skyfield.positionlib import Geocentric
        from skyfield.units import Distance

        satellite = Satrec.twoline2rv(line1, line2)
        jd, fr = jday(obs_dt.year, obs_dt.month, obs_dt.day,
                      obs_dt.hour, obs_dt.minute,
                      obs_dt.second + obs_dt.microsecond / 1e6)
        e, pos, _ = satellite.sgp4(jd, fr)
        if e != 0 or pos is None:
            return None
        x_km, y_km, z_km = pos

        ts = load.timescale()
        t = ts.from_datetime(obs_dt)
        position = Geocentric(
            [Distance(km=x_km).au, Distance(km=y_km).au, Distance(km=z_km).au],
            t=t,
            center=399,
        )
        geo = wgs84.geographic_position_of(position)
        return {
            "latitude": round(geo.latitude.degrees, 6),
            "longitude": round(geo.longitude.degrees, 6),
            "altitude_km": round(geo.elevation.km, 4),
        }
    except Exception:
        return None


def find_closest_previous_tle(tle_list: list[dict], obs_epoch_str: str) -> Optional[dict]:
    """
    Binary-search tle_list (sorted ascending by tle_epoch) for the latest TLE
    whose epoch is <= obs_epoch_str. Falls back to the earliest TLE if none
    precedes the observation.
    """
    if not tle_list:
        return None
    epochs = [t["tle_epoch"] for t in tle_list]
    idx = bisect.bisect_right(epochs, obs_epoch_str) - 1
    if idx >= 0:
        return tle_list[idx]
    return tle_list[0]


def process_batch(db, obs_batch: list[dict], tle_map: dict[str, list[dict]], dry_run: bool) -> dict:
    now_iso = datetime.now(timezone.utc).isoformat()
    updates = []
    skipped_no_tle = 0
    skipped_no_propagation = 0

    for obs in obs_batch:
        norad_id = str(obs.get("norad_id", ""))
        obs_epoch_str = obs.get("observation_epoch", "")
        obs_dt = parse_epoch(obs_epoch_str)
        if obs_dt is None:
            skipped_no_propagation += 1
            continue

        tle_list = tle_map.get(norad_id)
        if not tle_list:
            skipped_no_tle += 1
            continue

        tle = find_closest_previous_tle(tle_list, obs_epoch_str)
        if not tle:
            skipped_no_tle += 1
            continue

        line1 = tle.get("line1", "")
        line2 = tle.get("line2", "")

        orbital = compute_orbital_params(line2)
        geodetic = compute_geodetic(line1, line2, obs_dt)

        if geodetic is None:
            skipped_no_propagation += 1
            continue

        location = {
            **geodetic,
            **(orbital or {}),
            "tle_epoch": tle.get("tle_epoch"),
            "tle_line1": line1,
            "tle_line2": line2,
            "computed_at": now_iso,
        }

        updates.append({"_key": obs["_key"], "location": location})

    written = 0
    if updates and not dry_run:
        db.aql.execute(
            """
            FOR item IN @updates
                UPDATE { _key: item._key } WITH { location: item.location } IN @@col
            """,
            bind_vars={"updates": updates, "@col": COLLECTION_OBSERVATIONS},
        )
        written = len(updates)

    return {
        "written": written if not dry_run else 0,
        "dry_run_would_write": len(updates) if dry_run else 0,
        "skipped_no_tle": skipped_no_tle,
        "skipped_no_propagation": skipped_no_propagation,
    }


def fetch_tle_map(db, norad_ids: list[str]) -> dict[str, list[dict]]:
    """
    Fetch all TLE history records for the given NORAD IDs in one query.
    Returns a dict mapping norad_id -> list of TLE dicts sorted by tle_epoch ASC.
    """
    if not norad_ids:
        return {}
    cursor = db.aql.execute(
        """
        FOR t IN @@col
            FILTER t.norad_id IN @norad_ids
            SORT t.norad_id ASC, t.tle_epoch ASC
            RETURN { norad_id: t.norad_id, tle_epoch: t.tle_epoch,
                     line1: t.line1, line2: t.line2, gp_id: t.gp_id }
        """,
        bind_vars={"@col": COLLECTION_TLE_HISTORY, "norad_ids": norad_ids},
    )
    tle_map: dict[str, list[dict]] = {}
    for row in cursor:
        nid = row["norad_id"]
        tle_map.setdefault(nid, []).append(row)
    return tle_map


def run(args):
    connect_arangodb()
    db = db_conn.db
    if db is None:
        print("ERROR: Could not connect to database.", file=sys.stderr)
        sys.exit(1)

    filter_clause = "" if args.recompute else "FILTER obs.location == null"
    count_cursor = db.aql.execute(
        f"""
        RETURN LENGTH(
            FOR obs IN @@col
                {filter_clause}
                RETURN 1
        )
        """,
        bind_vars={"@col": COLLECTION_OBSERVATIONS},
    )
    total_pending = list(count_cursor)[0]

    label = "all" if args.recompute else "without location"
    print(f"Observations {label}: {total_pending:,}")

    if total_pending == 0:
        print("Nothing to do.")
        return

    if not args.yes and not args.dry_run:
        answer = input(f"Compute locations for {total_pending:,} observations? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted.")
            return

    batch_size = args.batch_size
    # When filtering (location == null), successfully written records leave the
    # filtered set, so the pool self-advances — always query at offset 0.
    # When recomputing (no filter), the pool is stable so offset pagination is needed.
    use_offset_pagination = args.recompute
    offset = 0
    total_written = 0
    total_dry = 0
    total_no_tle = 0
    total_no_prop = 0
    batch_num = 0
    total_processed = 0

    while True:
        query_offset = offset if use_offset_pagination else 0
        obs_cursor = db.aql.execute(
            f"""
            FOR obs IN @@col
                {filter_clause}
                LIMIT @offset, @batch
                RETURN {{ _key: obs._key, norad_id: obs.norad_id,
                          observation_epoch: obs.observation_epoch }}
            """,
            bind_vars={"@col": COLLECTION_OBSERVATIONS, "offset": query_offset, "batch": batch_size},
        )
        obs_batch = list(obs_cursor)
        if not obs_batch:
            break

        norad_ids = list({str(obs["norad_id"]) for obs in obs_batch})
        tle_map = fetch_tle_map(db, norad_ids)

        result = process_batch(db, obs_batch, tle_map, args.dry_run)
        total_written += result["written"]
        total_dry += result["dry_run_would_write"]
        total_no_tle += result["skipped_no_tle"]
        total_no_prop += result["skipped_no_propagation"]
        total_processed += len(obs_batch)

        batch_num += 1
        print(
            f"  Batch {batch_num}: {len(obs_batch)} obs | "
            f"written={result['written']} dry={result['dry_run_would_write']} "
            f"no_tle={result['skipped_no_tle']} no_prop={result['skipped_no_propagation']} "
            f"({total_processed}/{total_pending})"
        )

        if use_offset_pagination:
            offset += batch_size
        else:
            skipped_this_batch = result["skipped_no_tle"] + result["skipped_no_propagation"]
            if skipped_this_batch == len(obs_batch):
                # Every record in this batch was skipped (no TLE / no propagation).
                # These records will never get a location node written, so they stay
                # in the filtered set forever. Advance the offset past them to avoid
                # an infinite loop.
                offset += batch_size

    print()
    if args.dry_run:
        print(f"DRY RUN: would have written {total_dry:,} location nodes")
    else:
        print(f"Done. Written: {total_written:,}  no_tle: {total_no_tle:,}  no_propagation: {total_no_prop:,}")


def compute_locations_for_norad_ids(
    db,
    norad_ids,
    dry_run: bool = False,
    batch_size: int = 200,
) -> dict:
    """Compute location for observations of specific NORAD IDs that lack a location.

    Intended for use by import scripts after inserting new observations.
    Returns totals: written, skipped_no_tle, skipped_no_propagation.
    """
    norad_ids_list = [str(n) for n in norad_ids]
    if not norad_ids_list:
        return {"written": 0, "skipped_no_tle": 0, "skipped_no_propagation": 0}

    total_written = 0
    total_no_tle = 0
    total_no_prop = 0
    offset = 0

    while True:
        obs_cursor = db.aql.execute(
            """
            FOR obs IN @@col
                FILTER obs.location == null AND obs.norad_id IN @norad_ids
                LIMIT @offset, @batch
                RETURN { _key: obs._key, norad_id: obs.norad_id,
                         observation_epoch: obs.observation_epoch }
            """,
            bind_vars={
                "@col": COLLECTION_OBSERVATIONS,
                "norad_ids": norad_ids_list,
                "offset": offset,
                "batch": batch_size,
            },
        )
        obs_batch = list(obs_cursor)
        if not obs_batch:
            break

        tle_norad_ids = list({str(obs["norad_id"]) for obs in obs_batch})
        tle_map = fetch_tle_map(db, tle_norad_ids)

        result = process_batch(db, obs_batch, tle_map, dry_run)
        total_written += result["written"]
        total_no_tle += result["skipped_no_tle"]
        total_no_prop += result["skipped_no_propagation"]

        skipped_this_batch = result["skipped_no_tle"] + result["skipped_no_propagation"]
        if skipped_this_batch == len(obs_batch):
            offset += batch_size

    return {
        "written": total_written,
        "skipped_no_tle": total_no_tle,
        "skipped_no_propagation": total_no_prop,
    }


if __name__ == "__main__":
    run(parse_args())
