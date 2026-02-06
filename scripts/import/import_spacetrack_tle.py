#!/usr/bin/env python3
"""
Import TLE data from Space-Track for all satellites with NORAD IDs and store in MongoDB.
"""

import os
import sys
import requests
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database import connect_mongodb, get_satellites_collection, update_canonical

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def get_space_track_session():
    """Create authenticated Space-Track session."""
    space_track_user = os.getenv("SPACE_TRACK_USER")
    space_track_pass = os.getenv("SPACE_TRACK_PASS")
    
    if not space_track_user or not space_track_pass:
        print("Error: SPACE_TRACK_USER and SPACE_TRACK_PASS environment variables required")
        return None
    
    session = requests.Session()
    
    try:
        login_url = "https://www.space-track.org/ajaxauth/login"
        login_payload = {"identity": space_track_user, "password": space_track_pass}
        login_response = session.post(login_url, data=login_payload, timeout=10)
        
        if login_response.status_code == 200:
            return session
        else:
            print(f"Space-Track login failed: {login_response.status_code}")
            return None
    except Exception as e:
        print(f"Error creating Space-Track session: {e}")
        return None


def fetch_tle_from_space_track(session, norad_id):
    """Fetch TLE data from Space-Track."""
    try:
        url = f"https://www.space-track.org/basicspacedata/query/class/gp/NORAD_CAT_ID/{norad_id}/orderby/TLE_LINE1%20ASC/format/tle"
        response = session.get(url, timeout=10)
        
        if response.status_code == 200 and response.text.strip():
            lines = [line.strip() for line in response.text.strip().split('\n') if line.strip()]
            
            if len(lines) >= 2:
                tle_line1 = lines[0]
                tle_line2 = lines[1]
                
                if tle_line1.startswith('1 ') and len(tle_line1) >= 69:
                    return {
                        "tle_line1": tle_line1,
                        "tle_line2": tle_line2
                    }
    except Exception as e:
        print(f"Error fetching TLE for NORAD {norad_id}: {e}")
    
    return None


def process_satellite(sat):
    """Process a single satellite (for parallel execution)."""
    norad_id = sat.get("canonical", {}).get("norad_cat_id")
    sat_name = sat.get("canonical", {}).get("object_name") or sat.get("identifier")
    
    session = get_space_track_session()
    if not session:
        return {
            "sat": sat,
            "norad_id": norad_id,
            "sat_name": sat_name,
            "tle_data": None
        }
    
    tle_data = fetch_tle_from_space_track(session, norad_id)
    
    return {
        "sat": sat,
        "norad_id": norad_id,
        "sat_name": sat_name,
        "tle_data": tle_data
    }


def import_space_track_tle():
    """Import TLE data from Space-Track for all satellites."""
    if not connect_mongodb():
        print("Failed to connect to MongoDB")
        return
    
    collection = get_satellites_collection()
    
    satellites = list(collection.find({"canonical.norad_cat_id": {"$exists": True, "$ne": None}}))
    total = len(satellites)
    
    print(f"Found {total} satellites with NORAD IDs")
    print(f"Fetching TLE data from Space-Track (parallel, 10 concurrent)...\n")
    
    updated = 0
    failed = 0
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_satellite, sat) for sat in satellites]
        
        for idx, future in enumerate(as_completed(futures), 1):
            result = future.result()
            sat = result["sat"]
            tle_data = result["tle_data"]
            sat_name = result["sat_name"]
            norad_id = result["norad_id"]
            
            print(f"[{idx}/{total}] {sat_name} (NORAD {norad_id})...", end=" ", flush=True)
            
            if tle_data:
                tle_data["updated_at"] = datetime.now(timezone.utc).isoformat()
                
                sat["sources"]["spacetrack"] = tle_data
                sat["metadata"]["sources_available"] = list(sat["sources"].keys())
                sat["metadata"]["last_updated_at"] = datetime.now(timezone.utc).isoformat()
                
                update_canonical(sat)
                
                collection.replace_one({"identifier": sat["identifier"]}, sat)
                print("✓ Updated")
                updated += 1
            else:
                print("✗ Not found")
                failed += 1
    
    print(f"\n{'='*60}")
    print(f"Import complete:")
    print(f"  Updated: {updated}")
    print(f"  Failed:  {failed}")
    print(f"  Total:   {total}")
    print(f"{'='*60}")


if __name__ == "__main__":
    import_space_track_tle()
