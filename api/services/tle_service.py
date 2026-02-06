from typing import Optional, Dict
import requests
import time


def fetch_tle_data():
    """
    Fetch TLE data from CelesTrak.
    
    Note: This function returns raw TLE data without caching.
    Caching should be handled at the router level using CacheService.
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
    
    tle_cache = {}
    
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
                            tle_cache[intl_desig] = (sat_name, tle_line1, tle_line2)
                        except:
                            pass
                    i += 3
        except Exception as e:
            print(f"Error fetching {tle_url}: {e}")
    
    return tle_cache


def fetch_tle_by_norad_id(norad_id: str) -> Optional[Dict]:
    """
    Fetch fresh TLE data by NORAD ID from TLE API.
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
                return {
                    "name": data.get("name", f"NORAD {norad_id}"),
                    "line1": data.get("line1"),
                    "line2": data.get("line2"),
                    "source": "tle-api",
                    "date": data.get("date")
                }
            elif response.status_code == 404:
                return None
            else:
                print(f"Error fetching from TLE API: {response.status_code}")
                return None
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < max_retries - 1:
                wait_time = 0.5 * (2 ** attempt)
                print(f"Connection error fetching TLE for NORAD {norad_id}, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                print(f"Error fetching from TLE API after {max_retries} attempts: {e}")
                return None
        except Exception as e:
            print(f"Error fetching from TLE API: {e}")
            return None
    
    return None
