from typing import Optional, Dict
import math
import requests
import time
import logging
from datetime import datetime, timezone

from api.services.cache_service import get_tle_cache

logger = logging.getLogger(__name__)

_tle_cache_instance = get_tle_cache()


def _fetch_tle_data_uncached():
    """
    Internal function to fetch fresh TLE data from CelesTrak.
    Use fetch_tle_data() instead for cached results.
    """
    tle_urls = [
        "https://celestrak.org/NORAD/elements/stations.txt",
        "https://celestrak.org/NORAD/elements/resource.txt",
        "https://celestrak.org/NORAD/elements/sarsat.txt",
        "https://celestrak.org/NORAD/elements/dmc.txt",
        "https://celestrak.org/NORAD/elements/weather.txt",
        "https://celestrak.org/NORAD/elements/geo.txt",
        "https://celestrak.org/NORAD/elements/iss.txt",
    ]
    
    tle_data = {}
    
    for tle_url in tle_urls:
        try:
            response = requests.get(tle_url, timeout=5)
            if response.status_code == 200:
                lines = response.text.split('\n')
                i = 0
                while i < len(lines) - 2:
                    sat_name = lines[i].strip()
                    tle_line1 = lines[i + 1].strip()
                    tle_line2 = lines[i + 2].strip()
                    
                    if tle_line1.startswith('1 ') and len(tle_line1) >= 69:
                        try:
                            intl_desig = tle_line1[9:17].strip()
                            tle_data[intl_desig] = (sat_name, tle_line1, tle_line2)
                        except:
                            pass
                    i += 3
        except Exception as e:
            logger.warning(f"Error fetching {tle_url}: {e}")
    
    logger.info(f"Fetched TLE data for {len(tle_data)} satellites from CelesTrak")
    return tle_data


def fetch_tle_data():
    """
    Fetch TLE data from CelesTrak with caching.
    
    Returns a dictionary mapping international designator to (name, line1, line2) tuples.
    Results are cached for the configured TTL (default 1 hour).
    """
    cache_key = "celestrak_tle_data"
    
    def fetch_func():
        return _fetch_tle_data_uncached()
    
    return _tle_cache_instance.get_or_fetch(cache_key, fetch_func)


def _fetch_tle_by_norad_id_uncached(norad_id: str) -> Optional[Dict]:
    """
    Internal function to fetch fresh TLE data by NORAD ID from TLE API.
    Use fetch_tle_by_norad_id() instead for cached results.
    """
    url = f"https://tle.ivanstanojevic.me/api/tle/{norad_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                result = {
                    "name": data.get("name", f"NORAD {norad_id}"),
                    "line1": data.get("line1"),
                    "line2": data.get("line2"),
                    "source": "tle-api",
                    "date": data.get("date")
                }
                logger.info(f"Successfully fetched TLE for NORAD ID {norad_id}")
                return result
            elif response.status_code == 404:
                logger.info(f"TLE not found for NORAD ID {norad_id}")
                return None
            else:
                logger.warning(f"Error fetching from TLE API: {response.status_code}")
                return None
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < max_retries - 1:
                wait_time = 0.5 * (2 ** attempt)
                logger.warning(f"Connection error fetching TLE for NORAD {norad_id}, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                logger.error(f"Error fetching from TLE API after {max_retries} attempts: {e}")
                return None
        except Exception as e:
            logger.error(f"Error fetching from TLE API: {e}")
            return None
    
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
    Fetch TLE data by NORAD ID from TLE API with caching.
    
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
