"""
SpaceTrack TLE fetching service.

SpaceTrack (https://www.space-track.org) is the authoritative US Space Command
catalog covering all catalogued objects including debris and rocket bodies.
This service is used as a fallback when CelesTrak does not have TLE data for
a given NORAD ID or international designator.

Authentication uses SpaceTrack's session-based login. A single session is reused
across requests within its lifetime to avoid repeated logins.
"""
from typing import Optional, Dict, List
import logging
import time
import requests

from config import config

logger = logging.getLogger(__name__)

_BASE_URL = config.external.SPACETRACK_BASE_URL
_LOGIN_URL = f"{_BASE_URL}/ajaxauth/login"
_GP_NORAD_URL = "{base}/basicspacedata/query/class/gp/NORAD_CAT_ID/{norad_id}/orderby/EPOCH desc/limit/1/format/json"
_GP_INTLDES_URL = "{base}/basicspacedata/query/class/gp/INTLDES/{intl_des}/orderby/EPOCH desc/limit/10/format/json"
_GP_HISTORY_URL = "{base}/basicspacedata/query/class/gp_history/NORAD_CAT_ID/{norad_id}/EPOCH/{from_date}--{to_date}/orderby/EPOCH asc/format/json"

_SESSION_TTL = 7200

_session: Optional[requests.Session] = None
_session_created_at: float = 0.0


def _credentials_configured() -> bool:
    return bool(config.external.SPACETRACK_USERNAME and config.external.SPACETRACK_PASSWORD)


def _get_session() -> Optional[requests.Session]:
    global _session, _session_created_at

    if not _credentials_configured():
        return None

    now = time.monotonic()
    if _session is not None and (now - _session_created_at) < _SESSION_TTL:
        return _session

    sess = requests.Session()
    try:
        resp = sess.post(
            _LOGIN_URL,
            data={
                "identity": config.external.SPACETRACK_USERNAME,
                "password": config.external.SPACETRACK_PASSWORD,
            },
            timeout=10,
        )
        if resp.status_code != 200:
            logger.warning(f"SpaceTrack login failed with status {resp.status_code}")
            return None
        _session = sess
        _session_created_at = now
        logger.info("SpaceTrack session established")
        return _session
    except Exception as e:
        logger.error(f"SpaceTrack login error: {e}")
        return None


def _invalidate_session() -> None:
    global _session, _session_created_at
    _session = None
    _session_created_at = 0.0


def _gp_entry_to_tle_dict(entry: dict) -> Optional[Dict]:
    """Convert a SpaceTrack GP JSON entry to the internal TLE dict format."""
    line1 = entry.get("TLE_LINE1")
    line2 = entry.get("TLE_LINE2")
    if not line1 or not line2:
        return None
    return {
        "name": entry.get("OBJECT_NAME", ""),
        "line1": line1,
        "line2": line2,
        "source": "spacetrack",
        "date": entry.get("EPOCH"),
        "norad_cat_id": entry.get("NORAD_CAT_ID"),
        "intl_designator": entry.get("OBJECT_ID"),
    }


def _do_get(url: str) -> Optional[list]:
    """Perform an authenticated GET to SpaceTrack; re-authenticates on 401."""
    sess = _get_session()
    if sess is None:
        return None

    for attempt in range(2):
        try:
            resp = sess.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return data
                logger.warning(f"SpaceTrack returned unexpected format for {url}")
                return None
            elif resp.status_code == 401:
                logger.info("SpaceTrack session expired, re-authenticating")
                _invalidate_session()
                sess = _get_session()
                if sess is None:
                    return None
            else:
                logger.warning(f"SpaceTrack returned {resp.status_code} for {url}")
                return None
        except Exception as e:
            logger.error(f"SpaceTrack request error: {e}")
            return None
    return None


def fetch_tle_from_spacetrack_by_norad_id(norad_id: str) -> Optional[Dict]:
    """
    Fetch TLE data for a NORAD catalog ID from SpaceTrack.

    Returns None if credentials are not configured or if no TLE is found.
    """
    if not _credentials_configured():
        logger.debug("SpaceTrack credentials not configured, skipping")
        return None

    url = _GP_NORAD_URL.format(base=_BASE_URL, norad_id=norad_id)
    data = _do_get(url)
    if not data:
        logger.info(f"TLE not found on SpaceTrack for NORAD ID {norad_id}")
        return None

    result = _gp_entry_to_tle_dict(data[0])
    if result:
        logger.info(f"Successfully fetched TLE for NORAD ID {norad_id} from SpaceTrack")
    return result


def fetch_tle_from_spacetrack_by_intl_des(intl_des: str) -> Optional[Dict]:
    """
    Fetch TLE data by international designator from SpaceTrack.

    SpaceTrack can return multiple objects for a launch designator (e.g. all
    fragments of 1999-025). This returns the entry whose OBJECT_ID exactly
    matches intl_des, or the first entry if no exact match.

    Returns None if credentials are not configured or if no TLE is found.
    """
    if not _credentials_configured():
        logger.debug("SpaceTrack credentials not configured, skipping")
        return None

    url = _GP_INTLDES_URL.format(base=_BASE_URL, intl_des=requests.utils.quote(intl_des, safe=""))
    data = _do_get(url)
    if not data:
        logger.info(f"TLE not found on SpaceTrack for intl des {intl_des}")
        return None

    normalized = intl_des.replace(" ", "").upper()
    exact = next(
        (e for e in data if e.get("OBJECT_ID", "").replace(" ", "").upper() == normalized),
        None,
    )
    entry = exact or data[0]
    result = _gp_entry_to_tle_dict(entry)
    if result:
        logger.info(f"Successfully fetched TLE for intl des {intl_des} from SpaceTrack")
    return result


def fetch_tle_history_range(norad_id: str, from_date: str, to_date: str) -> List[Dict]:
    """
    Fetch all historical TLE records for a NORAD ID within a date range from SpaceTrack
    gp_history. This is a single bulk API call — no per-TLE requests are made.

    from_date / to_date: "YYYY-MM-DD" strings (inclusive on both ends).

    Returns a list of dicts, each containing:
        gp_id, tle_epoch, line1, line2, object_name

    Returns an empty list if credentials are not configured or no data is found.
    SpaceTrack counts this as one API request regardless of how many TLEs are returned.
    """
    if not _credentials_configured():
        logger.debug("SpaceTrack credentials not configured, skipping history fetch")
        return []

    url = _GP_HISTORY_URL.format(
        base=_BASE_URL,
        norad_id=norad_id,
        from_date=from_date,
        to_date=to_date,
    )
    data = _do_get(url)
    if not data:
        logger.info(f"No historical TLEs on SpaceTrack for NORAD {norad_id} [{from_date} – {to_date}]")
        return []

    results = []
    for entry in data:
        line1 = entry.get("TLE_LINE1", "")
        line2 = entry.get("TLE_LINE2", "")
        epoch = entry.get("EPOCH", "")
        if not (line1 and line2 and epoch):
            continue
        results.append({
            "gp_id": str(entry.get("GP_ID", "")),
            "tle_epoch": epoch,
            "line1": line1,
            "line2": line2,
            "object_name": entry.get("OBJECT_NAME", ""),
        })

    logger.info(
        f"SpaceTrack gp_history returned {len(results)} TLEs for NORAD {norad_id} "
        f"[{from_date} – {to_date}]"
    )
    return results
