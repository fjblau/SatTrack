#!/usr/bin/env python3
"""
Import TLE data from TLE API (tle.ivanstanojevic.me) for all satellites with NORAD IDs and store in MongoDB.
"""

import os
import sys
import requests
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from db import connect_mongodb, get_satellites_collection, update_canonical

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def fetch_tle_from_api(norad_id):
    """Fetch TLE data from TLE API."""
    try:
        url = f"https://tle.ivanstanojevic.me/api/tle/{norad_id}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "tle_line1": data.get("line1"),
                "tle_line2": data.get("line2"),
                "name": data.get("name"),
                "date": data.get("date")
            }
    except Exception as e:
        print(f"Error fetching TLE for NORAD {norad_id}: {e}")
    
    return None


def process_satellite(sat):
    """Process a single satellite (for parallel execution)."""
    norad_id = sat.get("canonical", {}).get("norad_cat_id")
    sat_name = sat.get("canonical", {}).get("object_name") or sat.get("identifier")
    
    tle_data = fetch_tle_from_api(norad_id)
    
    return {
        "sat": sat,
        "norad_id": norad_id,
        "sat_name": sat_name,
        "tle_data": tle_data
    }


def import_tle_api():
    """Import TLE data from TLE API for all satellites."""
    if not connect_mongodb():
        print("Failed to connect to MongoDB")
        return
    
    collection = get_satellites_collection()
    
    satellites = list(collection.find({"canonical.norad_cat_id": {"$exists": True, "$ne": None}}))
    total = len(satellites)
    
    print(f"Found {total} satellites with NORAD IDs")
    print(f"Fetching TLE data from TLE API (parallel, 10 concurrent)...\n")
    
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
                
                sat["sources"]["tleapi"] = tle_data
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
    import_tle_api()
