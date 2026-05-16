"""
TLE history service — rate-limit-safe access to historical SpaceTrack TLEs.

Design:
- Historical TLEs are fetched from SpaceTrack in one bulk API call per
  (norad_id, date-range) and stored permanently in the tle_history collection.
- A coverage document per norad_id tracks what date range has been fetched.
- Subsequent requests for the same (or narrower) range hit only the DB.
- SpaceTrack is only contacted when a genuinely uncovered range is requested.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict
import logging

from api.services.spacetrack_service import fetch_tle_history_range
from database.tle_history_ops import (
    is_range_covered,
    store_tle_batch,
    update_coverage,
    find_nearest_tle,
    get_coverage,
)

logger = logging.getLogger(__name__)

_EPOCH_BUFFER_DAYS = 2


def _date_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def ensure_tle_history(norad_id: str, from_date: str, to_date: str) -> Dict:
    """
    Ensure the DB contains TLE history for norad_id covering [from_date, to_date].

    If the range is already fully covered, no API call is made.
    If coverage is partial or absent, the uncovered portion (extended by
    _EPOCH_BUFFER_DAYS on each end) is fetched from SpaceTrack in one call,
    stored, and the coverage record updated.

    from_date / to_date: "YYYY-MM-DD" strings.

    Returns a summary dict:
        { norad_id, from_date, to_date, already_covered, tle_count, fetched }
    """
    norad_id = str(norad_id)

    if is_range_covered(norad_id, from_date, to_date):
        cov = get_coverage(norad_id)
        logger.info(f"TLE history for NORAD {norad_id} [{from_date}–{to_date}] already in DB")
        return {
            "norad_id": norad_id,
            "from_date": from_date,
            "to_date": to_date,
            "already_covered": True,
            "tle_count": cov.get("tle_count", 0) if cov else 0,
            "fetched": 0,
        }

    from_dt = datetime.strptime(from_date, "%Y-%m-%d") - timedelta(days=_EPOCH_BUFFER_DAYS)
    to_dt = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=_EPOCH_BUFFER_DAYS)
    fetch_from = _date_str(from_dt)
    fetch_to = _date_str(to_dt)

    cov = get_coverage(norad_id)
    if cov:
        if cov["covered_from"] <= from_date:
            fetch_from = _date_str(
                datetime.strptime(cov["covered_to"], "%Y-%m-%d") + timedelta(days=1)
            )
        elif cov["covered_to"] >= to_date:
            fetch_to = _date_str(
                datetime.strptime(cov["covered_from"], "%Y-%m-%d") - timedelta(days=1)
            )

    logger.info(f"Fetching TLE history from SpaceTrack for NORAD {norad_id} [{fetch_from}–{fetch_to}]")
    entries = fetch_tle_history_range(norad_id, fetch_from, fetch_to)

    if not entries:
        logger.warning(f"SpaceTrack returned no TLE history for NORAD {norad_id} [{fetch_from}–{fetch_to}]")
        return {
            "norad_id": norad_id,
            "from_date": from_date,
            "to_date": to_date,
            "already_covered": False,
            "tle_count": 0,
            "fetched": 0,
            "warning": "SpaceTrack returned no data for this range",
        }

    inserted = store_tle_batch(norad_id, entries)
    update_coverage(norad_id, fetch_from, fetch_to, inserted)

    return {
        "norad_id": norad_id,
        "from_date": from_date,
        "to_date": to_date,
        "already_covered": False,
        "tle_count": inserted,
        "fetched": inserted,
    }


def get_position_at(norad_id: str, target_dt: datetime) -> Optional[Dict]:
    """
    Return the satellite's geodetic position at target_dt using the nearest
    stored historical TLE, propagated with SGP4.

    Automatically ensures TLE history is available for the target date
    (±2-day buffer) before querying.

    Returns a dict:
        {
            norad_id, target_time,
            position: { latitude, longitude, altitude_km },
            tle_used: { tle_epoch, line1, line2, age_hours },
            source: "tle_history"
        }
    or None if no TLE is available.
    """
    from api.services.propagation_service import PropagationService, PropagationError
    from sgp4.api import Satrec

    norad_id = str(norad_id)
    if target_dt.tzinfo is None:
        target_dt = target_dt.replace(tzinfo=timezone.utc)

    date_str = _date_str(target_dt)
    ensure_tle_history(norad_id, date_str, date_str)

    tle_doc = find_nearest_tle(norad_id, target_dt)
    if not tle_doc:
        logger.warning(f"No TLE history available for NORAD {norad_id} near {target_dt.isoformat()}")
        return None

    line1 = tle_doc["line1"]
    line2 = tle_doc["line2"]
    tle_epoch_str = tle_doc["tle_epoch"]

    try:
        tle_epoch = datetime.fromisoformat(tle_epoch_str.replace("Z", "+00:00"))
        if tle_epoch.tzinfo is None:
            tle_epoch = tle_epoch.replace(tzinfo=timezone.utc)
    except ValueError:
        tle_epoch = None

    age_hours = None
    if tle_epoch:
        age_hours = round(abs((target_dt - tle_epoch).total_seconds()) / 3600.0, 2)

    try:
        satellite = Satrec.twoline2rv(line1, line2)
        pos = PropagationService._calculate_position(satellite, target_dt)
    except Exception as e:
        logger.error(f"SGP4 propagation failed for NORAD {norad_id} at {target_dt.isoformat()}: {e}")
        return None

    return {
        "norad_id": norad_id,
        "target_time": target_dt.isoformat(),
        "position": pos["geodetic"],
        "tle_used": {
            "tle_epoch": tle_epoch_str,
            "line1": line1,
            "line2": line2,
            "age_hours": age_hours,
        },
        "source": "tle_history",
    }
