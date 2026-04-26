from typing import Optional, Dict
import math
import requests
import time
import logging
from datetime import datetime, timezone

from api.services.cache_service import get_tle_cache

logger = logging.getLogger(__name__)

_tle_cache_instance = get_tle_cache()

CELESTRAK_GP_URL = "https://celestrak.org/NORAD/elements/gp.php"
CELESTRAK_SATCAT_URL = "https://celestrak.org/satcat/records.php"

_CELESTRAK_GP_BASE = "https://celestrak.org/NORAD/elements/gp.php"

_CELESTRAK_BATCH_GROUPS = [
    "stations",          # ISS, CSS, and other space stations
    "iss",               # ISS supplemental — visiting vehicles, nearby objects
    "weather",           # weather satellites (GEO/LEO)
    "geo",               # GEO belt
    "starlink",          # Starlink constellation (inc ≈ 53°, alt 500–550 km)
    "iridium-NEXT",      # Iridium NEXT (inc ≈ 86°)
    "resource",          # Earth observation (inc varies)
    "sarsat",            # Search and rescue (inc varies)
    "dmc",               # Disaster monitoring (inc ≈ 98°)
]

_CELESTRAK_BATCH_URLS = [
    f"{_CELESTRAK_GP_BASE}?GROUP={g}&FORMAT=TLE" for g in _CELESTRAK_BATCH_GROUPS
] + [
    "https://celestrak.org/NORAD/elements/stations.txt",
    "https://celestrak.org/NORAD/elements/iss.txt",
]


def _parse_tle_text(text: str) -> list:
    """
    Parse a CelesTrak TLE text response (3-line format) into a list of dicts.

    Each dict contains: name, line1, line2, norad_cat_id, intl_designator.
    Returns an empty list if the text is empty or contains no valid TLE blocks.

    International designator year conversion: YY >= 57 → 19YY, YY < 57 → 20YY.
    """
    lines = [l.rstrip() for l in text.strip().splitlines() if l.strip()]
    results = []
    i = 0
    while i + 2 < len(lines):
        name_line = lines[i]
        l1 = lines[i + 1]
        l2 = lines[i + 2]
        if not l1.startswith("1 ") or not l2.startswith("2 "):
            i += 1
            continue
        try:
            norad_cat_id = l1[2:7].strip()
            intl_compact = l1[9:17].strip()
            year_2digit = int(intl_compact[:2])
            year_4digit = (1900 + year_2digit) if year_2digit >= 57 else (2000 + year_2digit)
            launch_num = intl_compact[2:5]
            piece = intl_compact[5:]
            intl_designator = f"{year_4digit}-{launch_num}{piece}"
            results.append({
                "name": name_line.strip(),
                "line1": l1,
                "line2": l2,
                "norad_cat_id": norad_cat_id,
                "intl_designator": intl_designator,
            })
            i += 3
        except (ValueError, IndexError):
            i += 1
    return results


def _fetch_from_celestrak_by_norad(norad_id: str) -> Optional[Dict]:
    """
    Attempt to fetch a fresh TLE from CelesTrak GP API.

    Tries TLE format first; on a non-200 or empty response also tries JSON format.
    Uses a short timeout (3s) with no retry so failures are fast.
    Returns None if CelesTrak is unavailable or the object is not listed.
    """
    for fmt in ("TLE", "JSON"):
        params = {"CATNR": norad_id, "FORMAT": fmt}
        try:
            response = requests.get(CELESTRAK_GP_URL, params=params, timeout=3)
            if response.status_code == 200:
                if fmt == "TLE":
                    entries = _parse_tle_text(response.text)
                    if entries:
                        e = entries[0]
                        logger.info(f"CelesTrak TLE hit for NORAD {norad_id}")
                        return {
                            "name": e["name"],
                            "line1": e["line1"],
                            "line2": e["line2"],
                            "source": "celestrak",
                            "date": None,
                            "norad_cat_id": e["norad_cat_id"],
                            "intl_designator": e["intl_designator"],
                        }
                else:
                    try:
                        records = response.json()
                        if records:
                            r = records[0]
                            line1 = r.get("TLE_LINE1", "")
                            line2 = r.get("TLE_LINE2", "")
                            if line1 and line2:
                                logger.info(f"CelesTrak JSON hit for NORAD {norad_id}")
                                return {
                                    "name": r.get("OBJECT_NAME", f"NORAD {norad_id}"),
                                    "line1": line1,
                                    "line2": line2,
                                    "source": "celestrak",
                                    "date": r.get("EPOCH"),
                                    "norad_cat_id": str(r.get("NORAD_CAT_ID", norad_id)),
                                    "intl_designator": r.get("INTLDES", ""),
                                }
                    except Exception:
                        pass
            elif response.status_code == 404:
                logger.info(f"CelesTrak 404 for NORAD {norad_id} ({fmt})")
            else:
                logger.warning(f"CelesTrak returned {response.status_code} for NORAD {norad_id} ({fmt})")
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            logger.warning(f"CelesTrak unavailable for NORAD {norad_id} ({fmt})")
        except Exception as e:
            logger.error(f"CelesTrak unexpected error for NORAD {norad_id}: {e}")
    return None


_IVANSTANOJEVIC_BASE = "https://tle.ivanstanojevic.me/api/tle"


def _fetch_from_ivanstanojevic_by_norad(norad_id: str) -> Optional[Dict]:
    """
    Fallback TLE source: tle.ivanstanojevic.me — mirrors CelesTrak data.
    Used when CelesTrak is unreachable (outage, rate-limit, or cloud-IP block).
    """
    try:
        response = requests.get(f"{_IVANSTANOJEVIC_BASE}/{norad_id}", timeout=4)
        if response.status_code == 200:
            data = response.json()
            line1 = data.get("line1", "")
            line2 = data.get("line2", "")
            if line1 and line2:
                logger.info(f"tle.ivanstanojevic.me hit for NORAD {norad_id}")
                return {
                    "name": data.get("name", f"NORAD {norad_id}"),
                    "line1": line1,
                    "line2": line2,
                    "source": "ivanstanojevic",
                    "date": data.get("date"),
                    "norad_cat_id": str(norad_id),
                    "intl_designator": "",
                }
        logger.info(f"tle.ivanstanojevic.me: no record for NORAD {norad_id} (status {response.status_code})")
    except Exception as e:
        logger.warning(f"tle.ivanstanojevic.me error for NORAD {norad_id}: {e}")
    return None


def _fetch_tle_by_norad_id_uncached(norad_id: str) -> Optional[Dict]:
    """
    Fetch fresh TLE data by NORAD ID.

    Chain: CelesTrak (TLE then JSON format) → tle.ivanstanojevic.me mirror
           → last known TLE from satellite DB.
    """
    result = _fetch_from_celestrak_by_norad(norad_id)
    if result:
        return result

    logger.info(f"CelesTrak miss for NORAD {norad_id}, trying tle.ivanstanojevic.me mirror")
    result = _fetch_from_ivanstanojevic_by_norad(norad_id)
    if result:
        return result

    logger.info(f"All live sources failed for NORAD {norad_id}, trying satellite DB for last known TLE")
    try:
        from database.operations import get_satellite_tle_by_norad_id
        db_tle = get_satellite_tle_by_norad_id(norad_id)
        if db_tle and db_tle.get("line1") and db_tle.get("line2"):
            logger.info(f"Using last known DB TLE for NORAD {norad_id} (fetched {db_tle.get('fetched_at', 'unknown')})")
            return {
                "name": db_tle["name"],
                "line1": db_tle["line1"],
                "line2": db_tle["line2"],
                "source": "db_cached",
                "date": db_tle.get("fetched_at"),
                "norad_cat_id": norad_id,
                "intl_designator": "",
            }
    except Exception as e:
        logger.error(f"DB TLE lookup failed for NORAD {norad_id}: {e}")

    logger.warning(f"No TLE found anywhere for NORAD {norad_id}")
    return None


def _fetch_tle_by_intl_des_uncached(intl_des: str) -> Optional[Dict]:
    """
    Fetch fresh TLE data by International Designator from CelesTrak.

    CelesTrak returns all objects associated with the launch designator (e.g. 1999-025
    returns all fragments). This returns the best match — the entry whose intl_designator
    exactly matches intl_des, or the first entry if no exact match.
    SpaceTrack is intentionally not used due to rate limits.
    """
    params = {"INTDES": intl_des, "FORMAT": "TLE"}
    for attempt in range(2):
        try:
            response = requests.get(CELESTRAK_GP_URL, params=params, timeout=5)
            if response.status_code == 200:
                entries = _parse_tle_text(response.text)
                if not entries:
                    logger.info(f"CelesTrak: no TLE for intl des {intl_des}")
                    return None
                normalized = intl_des.replace(" ", "").upper()
                exact = next(
                    (e for e in entries if e["intl_designator"].replace(" ", "").upper() == normalized),
                    None
                )
                entry = exact or entries[0]
                logger.info(f"CelesTrak hit for intl des {intl_des}")
                return {
                    "name": entry["name"],
                    "line1": entry["line1"],
                    "line2": entry["line2"],
                    "source": "celestrak",
                    "date": None,
                    "norad_cat_id": entry["norad_cat_id"],
                    "intl_designator": entry["intl_designator"],
                }
            elif response.status_code == 404:
                logger.info(f"CelesTrak 404 for intl des {intl_des}")
                return None
            else:
                logger.warning(f"CelesTrak returned {response.status_code} for intl des {intl_des}")
                return None
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if attempt == 0:
                logger.warning(f"CelesTrak timeout for intl des {intl_des}, retrying once...")
                time.sleep(0.5)
            else:
                logger.warning(f"CelesTrak still unavailable for intl des {intl_des}")
        except Exception as e:
            logger.error(f"CelesTrak error for intl des {intl_des}: {e}")
            break
    return None


def parse_tle_fields(name: str, line1: str, line2: str) -> Dict:
    """
    Parse a TLE (Two-Line Element set) into individual orbital parameter fields.

    Args:
        name: Satellite name (TLE header line)
        line1: TLE line 1
        line2: TLE line 2

    Returns:
        Dictionary of parsed TLE fields with human-readable units.
    """
    from sgp4.api import Satrec
    sat = Satrec.twoline2rv(line1, line2)

    RAD_TO_DEG = 180.0 / math.pi
    RAD_PER_MIN_TO_REV_PER_DAY = (1440.0) / (2.0 * math.pi)

    return {
        "line1": line1,
        "line2": line2,
        "name": name,
        "epoch_year": sat.epochyr,
        "epoch_day": sat.epochdays,
        "bstar": sat.bstar,
        "inclination_deg": sat.inclo * RAD_TO_DEG,
        "raan_deg": sat.nodeo * RAD_TO_DEG,
        "eccentricity": sat.ecco,
        "arg_of_perigee_deg": sat.argpo * RAD_TO_DEG,
        "mean_anomaly_deg": sat.mo * RAD_TO_DEG,
        "mean_motion_rev_per_day": sat.no_kozai * RAD_PER_MIN_TO_REV_PER_DAY,
        "rev_number": sat.revnum,
        "ndot": sat.ndot,
        "nddot": sat.nddot,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_tle_by_norad_id(norad_id: str) -> Optional[Dict]:
    """
    Fetch TLE data by NORAD ID from CelesTrak GP API with caching.

    Args:
        norad_id: NORAD catalog ID

    Returns:
        Dictionary with TLE data (name, line1, line2, source, date) or None if not found.
        Results are cached for the configured TTL (default 1 hour).
    """
    cache_key = f"tle_norad_{norad_id}"

    def fetch_func():
        return _fetch_tle_by_norad_id_uncached(norad_id)

    return _tle_cache_instance.get_or_fetch(cache_key, fetch_func)


def warm_tle_cache() -> int:
    """
    Pre-populate the TLE cache from CelesTrak batch files.

    Called once at application startup in a background thread. Ensures that
    well-known objects (ISS, space stations, GEO, weather) are always
    available in the individual NORAD lookup cache even if CelesTrak GP API
    is temporarily unavailable.

    Returns the number of new TLE entries loaded.
    """
    loaded = 0
    for url in _CELESTRAK_BATCH_URLS:
        try:
            response = requests.get(url, timeout=15)
            if response.status_code != 200:
                logger.warning(f"TLE warm-up: HTTP {response.status_code} for {url}")
                continue
            entries = _parse_tle_text(response.text)
            for e in entries:
                cache_key = f"tle_norad_{e['norad_cat_id']}"
                if _tle_cache_instance.get(cache_key) is None:
                    _tle_cache_instance.set(cache_key, {
                        "name": e["name"],
                        "line1": e["line1"],
                        "line2": e["line2"],
                        "source": "celestrak_batch",
                        "date": None,
                        "norad_cat_id": e["norad_cat_id"],
                        "intl_designator": e.get("intl_designator", ""),
                    })
                    loaded += 1
        except Exception as exc:
            logger.warning(f"TLE warm-up failed for {url}: {exc}")
    logger.info(f"TLE cache warmed with {loaded} new entries from batch files")
    return loaded


def check_decay_from_celestrak(norad_id: str) -> Optional[Dict]:
    """
    Query CelesTrak satellite catalog for decay status of a specific object.

    Returns a dict with 'decay_date' (str, YYYY-MM-DD) and 'ops_status_code'
    if the record is found, or None if CelesTrak does not have data for the ID.

    This is intentionally not cached — it is called at most once per UI page
    open for objects whose canonical status is "in orbit", so rate impact is low.
    """
    try:
        response = requests.get(
            CELESTRAK_SATCAT_URL,
            params={"CATNR": norad_id, "FORMAT": "JSON"},
            timeout=10,
        )
        if response.status_code != 200:
            logger.warning(f"CelesTrak satcat returned {response.status_code} for NORAD {norad_id}")
            return None
        records = response.json()
        if not records:
            return None
        rec = records[0]
        return {
            "decay_date": rec.get("DECAY_DATE"),
            "ops_status_code": rec.get("OPS_STATUS_CODE"),
            "object_name": rec.get("OBJECT_NAME"),
        }
    except Exception as e:
        logger.error(f"Error fetching CelesTrak satcat for NORAD {norad_id}: {e}")
        return None


def fetch_tle_by_intl_des(intl_des: str) -> Optional[Dict]:
    """
    Fetch TLE data by International Designator from CelesTrak GP API with caching.

    Useful for debris objects that have an international designator but no NORAD ID
    stored in the local database.

    Args:
        intl_des: International designator (e.g. "1999-025DEB", "1986-017GV")

    Returns:
        Dictionary with TLE data (name, line1, line2, source, date, norad_cat_id,
        intl_designator) or None if not found.
        Results are cached for the configured TTL (default 1 hour).
    """
    cache_key = f"tle_intldes_{intl_des}"

    def fetch_func():
        return _fetch_tle_by_intl_des_uncached(intl_des)

    return _tle_cache_instance.get_or_fetch(cache_key, fetch_func)
