from datetime import datetime, timezone
from typing import Optional, Dict, List
import logging

import database.connection as db_conn
from database.connection import COLLECTION_TLE_HISTORY, COLLECTION_TLE_HISTORY_COVERAGE

logger = logging.getLogger(__name__)


def _db():
    if db_conn.db is None:
        raise RuntimeError("Database not connected")
    return db_conn.db


def get_coverage(norad_id: str) -> Optional[Dict]:
    """
    Return the stored coverage document for a NORAD ID, or None if no TLEs have
    been fetched yet.

    The document shape is:
        { norad_id, covered_from, covered_to, tle_count, last_fetched_at }
    where covered_from / covered_to are ISO-8601 date strings (YYYY-MM-DD).
    """
    try:
        col = _db().collection(COLLECTION_TLE_HISTORY_COVERAGE)
        key = str(norad_id)
        if col.has(key):
            return col.get(key)
        return None
    except Exception as e:
        logger.error(f"get_coverage failed for NORAD {norad_id}: {e}")
        return None


def is_range_covered(norad_id: str, from_date: str, to_date: str) -> bool:
    """
    Return True if [from_date, to_date] is fully contained within the stored
    coverage range for norad_id.

    from_date / to_date are ISO-8601 date strings: "YYYY-MM-DD".
    """
    cov = get_coverage(norad_id)
    if cov is None:
        return False
    return cov["covered_from"] <= from_date and cov["covered_to"] >= to_date


def store_tle_batch(norad_id: str, entries: List[Dict]) -> int:
    """
    Upsert a batch of TLE history records into the tle_history collection.

    Each entry must contain: gp_id, tle_epoch, line1, line2, object_name.
    The document _key is "{norad_id}_{gp_id}" to ensure uniqueness per SpaceTrack GP entry.

    Returns the number of new documents inserted (duplicates are skipped).
    """
    if not entries:
        return 0

    col = _db().collection(COLLECTION_TLE_HISTORY)
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0

    for e in entries:
        gp_id = str(e.get("gp_id", ""))
        key = f"{norad_id}_{gp_id}" if gp_id else None
        if not key:
            continue

        doc = {
            "_key": key,
            "norad_id": str(norad_id),
            "gp_id": gp_id,
            "tle_epoch": e["tle_epoch"],
            "line1": e["line1"],
            "line2": e["line2"],
            "object_name": e.get("object_name", ""),
            "fetched_at": now,
        }

        try:
            if not col.has(key):
                col.insert(doc)
                inserted += 1
        except Exception as exc:
            logger.warning(f"Failed to insert TLE history doc {key}: {exc}")

    logger.info(f"Stored {inserted} new TLE history records for NORAD {norad_id}")
    return inserted


def update_coverage(norad_id: str, from_date: str, to_date: str, tle_count: int) -> None:
    """
    Upsert the coverage document for norad_id, extending covered_from/covered_to
    as needed so the stored range is always the union of all fetched ranges.
    """
    col = _db().collection(COLLECTION_TLE_HISTORY_COVERAGE)
    key = str(norad_id)
    now = datetime.now(timezone.utc).isoformat()

    existing = get_coverage(norad_id)
    if existing:
        new_from = min(existing["covered_from"], from_date)
        new_to = max(existing["covered_to"], to_date)
        new_count = existing.get("tle_count", 0) + tle_count
        col.update({
            "_key": key,
            "covered_from": new_from,
            "covered_to": new_to,
            "tle_count": new_count,
            "last_fetched_at": now,
        })
    else:
        col.insert({
            "_key": key,
            "norad_id": str(norad_id),
            "covered_from": from_date,
            "covered_to": to_date,
            "tle_count": tle_count,
            "last_fetched_at": now,
        })


def find_nearest_tle(norad_id: str, target_dt: datetime) -> Optional[Dict]:
    """
    Return the TLE from tle_history whose epoch is closest to target_dt,
    preferring a TLE whose epoch is before target_dt (better for SGP4 propagation).

    Returns a dict with: line1, line2, tle_epoch, object_name, gp_id, norad_id
    or None if no TLEs are stored for this satellite.
    """
    target_iso = target_dt.isoformat()

    aql = """
    LET before = (
        FOR t IN @@col
            FILTER t.norad_id == @norad_id AND t.tle_epoch <= @target
            SORT t.tle_epoch DESC
            LIMIT 1
            RETURN t
    )
    LET after = (
        FOR t IN @@col
            FILTER t.norad_id == @norad_id AND t.tle_epoch > @target
            SORT t.tle_epoch ASC
            LIMIT 1
            RETURN t
    )
    LET candidate = LENGTH(before) > 0 ? before[0] : (LENGTH(after) > 0 ? after[0] : null)
    RETURN candidate
    """

    try:
        cursor = _db().aql.execute(
            aql,
            bind_vars={
                "@col": COLLECTION_TLE_HISTORY,
                "norad_id": str(norad_id),
                "target": target_iso,
            },
        )
        results = list(cursor)
        if results and results[0] is not None:
            return results[0]
        return None
    except Exception as e:
        logger.error(f"find_nearest_tle failed for NORAD {norad_id} at {target_iso}: {e}")
        return None


def get_tle_count_for_range(norad_id: str, from_date: str, to_date: str) -> int:
    """Return the number of TLE history records stored for norad_id within the date range."""
    aql = """
    RETURN LENGTH(
        FOR t IN @@col
            FILTER t.norad_id == @norad_id
            FILTER t.tle_epoch >= @from AND t.tle_epoch <= @to
            RETURN 1
    )
    """
    try:
        cursor = _db().aql.execute(
            aql,
            bind_vars={
                "@col": COLLECTION_TLE_HISTORY,
                "norad_id": str(norad_id),
                "from": from_date,
                "to": to_date + "T23:59:59",
            },
        )
        results = list(cursor)
        return results[0] if results else 0
    except Exception as e:
        logger.error(f"get_tle_count_for_range failed: {e}")
        return 0
