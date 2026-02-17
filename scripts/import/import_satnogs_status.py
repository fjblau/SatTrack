#!/usr/bin/env python3
"""
Import satellite operational status from SatNOGS database and merge with existing ArangoDB records.
Uses NORAD catalog ID for matching.

SatNOGS (Satellite Networked Open Ground Station) is a global network of satellite ground stations
that provides real-time operational status and telemetry data for thousands of satellites.
"""

import os
import sys
import time
import requests
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database import (
    connect_arangodb,
    get_satellites_collection,
    update_canonical
)
import database.connection as db_conn

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


SATNOGS_API_URL = "https://db.satnogs.org/api/satellites/"


def normalize_string(value):
    """Normalize string values for comparison and storage"""
    if value is None or value == "":
        return None
    value_str = str(value).strip()
    if value_str.lower() in ["nan", "n/a", "none", "", "-"]:
        return None
    return value_str


def get_all_norad_ids():
    """Get all NORAD IDs from the database"""
    collection = get_satellites_collection()
    
    aql = """
    FOR doc IN @@collection
        LET norad_id = doc.canonical.norad_cat_id 
                    OR doc.sources.gcat.norad_cat_id 
                    OR doc.sources.celestrak.norad_id 
                    OR doc.sources.spacetrack.norad_catalog_number 
                    OR doc.sources.kaggle.norad_cat_id
        FILTER norad_id != null
        RETURN DISTINCT norad_id
    """
    
    cursor = db_conn.db.aql.execute(
        aql,
        bind_vars={'@collection': db_conn.COLLECTION_NAME}
    )
    
    norad_ids = list(cursor)
    norad_ids_int = []
    for nid in norad_ids:
        try:
            norad_ids_int.append(int(nid))
        except (ValueError, TypeError):
            pass
    
    return sorted(norad_ids_int)


def fetch_satnogs_satellites(page_size=100):
    """
    Fetch all satellites from SatNOGS API with pagination.
    
    Args:
        page_size: Number of satellites per page (default 100)
        
    Yields:
        Dictionary containing satellite data from SatNOGS
    """
    page = 1
    total_fetched = 0
    
    while True:
        try:
            print(f"Fetching SatNOGS page {page}...", flush=True)
            response = requests.get(
                SATNOGS_API_URL,
                params={"page": page, "page_size": page_size},
                timeout=30
            )
            response.raise_for_status()
            
            satellites = response.json()
            
            if not satellites or len(satellites) == 0:
                print(f"Finished fetching from SatNOGS. Total satellites: {total_fetched}", flush=True)
                break
            
            for sat in satellites:
                total_fetched += 1
                yield sat
            
            print(f"Fetched {len(satellites)} satellites (total: {total_fetched})", flush=True)
            
            if len(satellites) < page_size:
                print(f"Finished fetching from SatNOGS. Total satellites: {total_fetched}", flush=True)
                break
            
            page += 1
            time.sleep(0.5)
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching SatNOGS data on page {page}: {e}", flush=True)
            print(f"Retrying in 5 seconds...", flush=True)
            time.sleep(5)
            continue
        except Exception as e:
            print(f"Unexpected error fetching SatNOGS data: {e}", flush=True)
            break


def find_existing_by_norad(norad_id):
    """Find existing satellite by NORAD ID"""
    if not norad_id:
        return None
    
    collection = get_satellites_collection()
    
    aql = """
    FOR doc IN @@collection
        FILTER doc.canonical.norad_cat_id == @norad_id
           OR doc.sources.gcat.norad_cat_id == @norad_id
           OR doc.sources.celestrak.norad_id == @norad_id
           OR doc.sources.spacetrack.norad_catalog_number == @norad_id
           OR doc.sources.kaggle.norad_cat_id == @norad_id
           OR doc.sources.satnogs.norad_cat_id == @norad_id
        LIMIT 1
        RETURN doc
    """
    
    cursor = db_conn.db.aql.execute(
        aql,
        bind_vars={
            '@collection': db_conn.COLLECTION_NAME,
            'norad_id': norad_id
        }
    )
    
    results = list(cursor)
    return results[0] if results else None


def import_satnogs_status(dry_run=False, use_db_filter=True):
    """
    Import SatNOGS operational status data and merge with existing ArangoDB records.
    
    Args:
        dry_run: If True, don't write to database, just show what would be done
        use_db_filter: If True, only fetch satellites that exist in the database
    """
    if not dry_run:
        if not connect_arangodb():
            print("Failed to connect to ArangoDB")
            return False
    
    collection = get_satellites_collection() if not dry_run else None
    
    norad_ids_in_db = set()
    if use_db_filter and not dry_run:
        print("Getting NORAD IDs from database...", flush=True)
        norad_ids_in_db = set(get_all_norad_ids())
        print(f"Found {len(norad_ids_in_db)} satellites with NORAD IDs in database", flush=True)
    
    updated = 0
    skipped_no_norad = 0
    skipped_not_found = 0
    
    print(f"Importing SatNOGS operational status data...", flush=True)
    if dry_run:
        print("DRY RUN MODE - No changes will be made to the database", flush=True)
    print(flush=True)
    
    try:
        for sat_data in fetch_satnogs_satellites():
            try:
                norad_id = sat_data.get("norad_cat_id")
                
                if not norad_id or norad_id == 0:
                    skipped_no_norad += 1
                    continue
                
                if use_db_filter and not dry_run and norad_id not in norad_ids_in_db:
                    skipped_not_found += 1
                    continue
                
                satnogs_data = {
                    "norad_cat_id": norad_id,
                    "sat_id": normalize_string(sat_data.get("sat_id")),
                    "name": normalize_string(sat_data.get("name")),
                    "names": normalize_string(sat_data.get("names")),
                    "status": normalize_string(sat_data.get("status")),
                    "decayed": normalize_string(sat_data.get("decayed")),
                    "launched": normalize_string(sat_data.get("launched")),
                    "deployed": normalize_string(sat_data.get("deployed")),
                    "operator": normalize_string(sat_data.get("operator")),
                    "countries": normalize_string(sat_data.get("countries")),
                    "website": normalize_string(sat_data.get("website")),
                    "image": normalize_string(sat_data.get("image")),
                    "updated": normalize_string(sat_data.get("updated")),
                    "citation": normalize_string(sat_data.get("citation")),
                    "is_frequency_violator": sat_data.get("is_frequency_violator", False),
                }
                
                if sat_data.get("telemetries"):
                    satnogs_data["telemetries"] = sat_data["telemetries"]
                
                if sat_data.get("associated_satellites"):
                    satnogs_data["associated_satellites"] = sat_data["associated_satellites"]
                
                satnogs_data = {k: v for k, v in satnogs_data.items() if v is not None}
                
                if dry_run:
                    status = satnogs_data.get("status", "unknown")
                    name = satnogs_data.get("name", "Unknown")
                    print(f"[DRY RUN] Would update: {name} (NORAD: {norad_id}) - Status: {status}", flush=True)
                    updated += 1
                    continue
                
                existing = find_existing_by_norad(norad_id)
                
                if existing:
                    existing["sources"]["satnogs"] = {
                        **satnogs_data,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                    existing["metadata"]["sources_available"] = list(existing["sources"].keys())
                    existing["metadata"]["last_updated_at"] = datetime.now(timezone.utc).isoformat()
                    
                    # DO NOT call update_canonical - SatNOGS is not an approved source
                    # Data stays in sources.satnogs only
                    
                    collection.update(existing)
                    updated += 1
                    
                    if updated % 100 == 0:
                        print(f"Progress: {updated} records updated, {skipped_not_found} not found, {skipped_no_norad} skipped (no NORAD)", flush=True)
                else:
                    skipped_not_found += 1
                    if skipped_not_found % 500 == 0:
                        print(f"Progress: {updated} records updated, {skipped_not_found} not found in database", flush=True)
            
            except Exception as e:
                print(f"Error processing satellite {sat_data.get('name', 'Unknown')}: {e}", flush=True)
                continue
        
        print(f"\n✓ Import complete!", flush=True)
        print(f"  Updated: {updated}", flush=True)
        print(f"  Skipped (no NORAD ID): {skipped_no_norad}", flush=True)
        print(f"  Skipped (not found in DB): {skipped_not_found}", flush=True)
        print(f"  Total processed: {updated + skipped_no_norad + skipped_not_found}", flush=True)
        
        if not dry_run:
            total_in_db = collection.count()
            print(f"\nTotal satellites in database: {total_in_db}", flush=True)
            
            aql = """
            FOR doc IN @@collection
                FILTER doc.sources.satnogs != null
                COLLECT WITH COUNT INTO count
                RETURN count
            """
            cursor = db_conn.db.aql.execute(
                aql,
                bind_vars={'@collection': db_conn.COLLECTION_NAME}
            )
            satnogs_count = list(cursor)[0] if list(cursor) else 0
            print(f"Records with SatNOGS data: {satnogs_count}", flush=True)
        
        return True
    
    except Exception as e:
        print(f"Error during import: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    
    success = import_satnogs_status(dry_run)
    sys.exit(0 if success else 1)
