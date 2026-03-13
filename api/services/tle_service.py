from typing import Optional, Dict
import math
import requests
import time
import logging
from datetime import datetime, timezone

from api.services.cache_service import get_tle_cache
from api.services.spacetrack_service import (
    fetch_tle_from_spacetrack_by_norad_id,
    fetch_tle_from_spacetrack_by_intl_des,
)

logger = logging.getLogger(__name__)

_tle_cache_instance = get_tle_cache()

CELESTRAK_GP_URL = "https://celestrak.org/NORAD/elements/gp.php"


def _celestrak_gp_to_tle_dict(entry: dict, fallback_id: str = "") -> Optional[Dict]:
    """Convert a CelesTrak GP JSON entry to the internal TLE dict format."""
    line1 = entry.get("TLE_LINE1")
    line2 = entry.get("TLE_LINE2")
    if not line1 or not line2:
        return None
    return {
        "name": entry.get("OBJECT_NAME", fallback_id),
        "line1": line1,
        "line2": line2,
        "source": "celestrak",
        "date": entry.get("EPOCH"),
        "norad_cat_id": entry.get("NORAD_CAT_ID"),
        "intl_designator": entry.get("OBJECT_ID"),
    }


def _fetch_tle_by_norad_id_uncached(norad_id: str) -> Optional[Dict]:
    """
    Fetch fresh TLE data by NORAD ID.

    First attempts CelesTrak GP API; if the object is not found there, falls
    back to SpaceTrack which covers all catalogued objects including debris.
    Use fetch_tle_by_norad_id() instead for cached results.
    """
    params = {"CATNR": norad_id, "FORMAT": "JSON"}
    max_retries = 3
    celestrak_found = False
    for attempt in range(max_retries):
        try:
            response = requests.get(CELESTRAK_GP_URL, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and data:
                    result = _celestrak_gp_to_tle_dict(data[0], fallback_id=f"NORAD {norad_id}")
                    if result:
                        logger.info(f"Successfully fetched TLE for NORAD ID {norad_id} from CelesTrak")
                        celestrak_found = True
                        return result
                logger.info(f"TLE not found for NORAD ID {norad_id} on CelesTrak")
                break
            elif response.status_code == 404:
                logger.info(f"TLE not found for NORAD ID {norad_id} on CelesTrak (404)")
                break
            else:
                logger.warning(f"CelesTrak GP API returned {response.status_code} for NORAD {norad_id}")
                break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < max_retries - 1:
                wait_time = 0.5 * (2 ** attempt)
                logger.warning(f"Connection error fetching TLE for NORAD {norad_id}, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                logger.error(f"Error fetching from CelesTrak after {max_retries} attempts: {e}")
        except Exception as e:
            logger.error(f"Error fetching from CelesTrak GP API: {e}")
            break
    if not celestrak_found:
        logger.info(f"Falling back to SpaceTrack for NORAD ID {norad_id}")
        return fetch_tle_from_spacetrack_by_norad_id(norad_id)
    return None


def _fetch_tle_by_intl_des_uncached(intl_des: str) -> Optional[Dict]:
    """
    Fetch fresh TLE data by International Designator.

    First attempts CelesTrak GP API; if the object is not found there, falls
    back to SpaceTrack which covers all catalogued objects including debris.
    Use fetch_tle_by_intl_des() instead for cached results.

    CelesTrak returns all objects associated with the launch designator (e.g. 1999-025
    returns all fragments). This returns the best match — the entry whose OBJECT_ID
    exactly matches intl_des, or the first entry if no exact match.
    """
    params = {"INTDES": intl_des, "FORMAT": "JSON"}
    max_retries = 3
    celestrak_found = False
    for attempt in range(max_retries):
        try:
            response = requests.get(CELESTRAK_GP_URL, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if not isinstance(data, list) or not data:
                    logger.info(f"TLE not found for international designator {intl_des} on CelesTrak")
                    break
                normalized = intl_des.replace(" ", "").upper()
                exact = next(
                    (e for e in data if e.get("OBJECT_ID", "").replace(" ", "").upper() == normalized),
                    None
                )
                entry = exact or data[0]
                result = _celestrak_gp_to_tle_dict(entry, fallback_id=intl_des)
                if result:
                    logger.info(f"Successfully fetched TLE for intl des {intl_des} from CelesTrak")
                    celestrak_found = True
                    return result
                break
            elif response.status_code == 404:
                logger.info(f"TLE not found for intl des {intl_des} on CelesTrak (404)")
                break
            else:
                logger.warning(f"CelesTrak GP API returned {response.status_code} for intl des {intl_des}")
                break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < max_retries - 1:
                wait_time = 0.5 * (2 ** attempt)
                logger.warning(f"Connection error fetching TLE for intl des {intl_des}, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                logger.error(f"Error fetching from CelesTrak after {max_retries} attempts: {e}")
        except Exception as e:
            logger.error(f"Error fetching from CelesTrak GP API: {e}")
            break
    if not celestrak_found:
        logger.info(f"Falling back to SpaceTrack for intl des {intl_des}")
        return fetch_tle_from_spacetrack_by_intl_des(intl_des)
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
