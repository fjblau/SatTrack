#!/usr/bin/env python3
"""
Import satellite data from Kaggle current_catalog.csv and merge with existing MongoDB records.
Uses NORAD ID as the primary identifier for matching and merging data.
"""

import os
import csv
import sys
from datetime import datetime, timezone
from db import connect_mongodb, get_satellites_collection, create_satellite_document, update_canonical

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def normalize_string(value):
    """Normalize string values for comparison and storage"""
    if value is None or value == "":
        return None
    value_str = str(value).strip()
    if value_str.lower() in ["nan", "n/a", "none", ""]:
        return None
    return value_str


def convert_float(value):
    """Convert string to float, return None if invalid"""
    if value is None or value == "":
        return None
    try:
        val_str = str(value).strip()
        if val_str.lower() in ["nan", "n/a", "none"]:
            return None
        return float(val_str)
    except (ValueError, TypeError):
        return None


def import_kaggle_catalog(csv_path):
    """
    Import Kaggle catalog data and merge with existing MongoDB records.
    
    Args:
        csv_path: Path to current_catalog.csv file
    """
    if not os.path.exists(csv_path):
        print(f"Error: File not found: {csv_path}")
        return False
    
    if not connect_mongodb():
        print("Failed to connect to MongoDB")
        return False
    
    collection = get_satellites_collection()
    
    created = 0
    updated = 0
    skipped = 0
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row_num, row in enumerate(reader, start=2):
                try:
                    norad_id_str = normalize_string(row.get('norad_id'))
                    
                    if not norad_id_str:
                        skipped += 1
                        continue
                    
                    try:
                        norad_id = int(norad_id_str)
                    except (ValueError, TypeError):
                        skipped += 1
                        continue
                    
                    kaggle_data = {
                        "name": normalize_string(row.get('name')),
                        "object_type": normalize_string(row.get('object_type')),
                        "country": normalize_string(row.get('country')),
                        "satellite_constellation": normalize_string(row.get('satellite_constellation')),
                        "altitude_km": convert_float(row.get('altitude_km')),
                        "altitude_category": normalize_string(row.get('altitude_category')),
                        "orbital_band": normalize_string(row.get('orbital_band')),
                        "congestion_risk": normalize_string(row.get('congestion_risk')),
                        "inclination": convert_float(row.get('inclination')),
                        "eccentricity": convert_float(row.get('eccentricity')),
                        "launch_year_estimate": normalize_string(row.get('launch_year_estimate')),
                        "days_in_orbit_estimate": normalize_string(row.get('days_in_orbit_estimate')),
                        "orbit_lifetime_category": normalize_string(row.get('orbit_lifetime_category')),
                        "mean_motion": convert_float(row.get('mean_motion')),
                        "epoch": normalize_string(row.get('epoch')),
                        "data_source": normalize_string(row.get('data_source')),
                        "snapshot_date": normalize_string(row.get('snapshot_date')),
                        "last_seen": normalize_string(row.get('last_seen')),
                    }
                    
                    kaggle_data["norad_cat_id"] = norad_id
                    
                    existing = collection.find_one({"canonical.norad_cat_id": norad_id})
                    
                    if existing:
                        existing["sources"]["kaggle"] = {
                            **kaggle_data,
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        }
                        existing["metadata"]["sources_available"] = list(existing["sources"].keys())
                        existing["metadata"]["last_updated_at"] = datetime.now(timezone.utc).isoformat()
                        
                        update_canonical(existing)
                        
                        collection.replace_one(
                            {"_id": existing["_id"]},
                            existing
                        )
                        updated += 1
                    else:
                        identifier = f"NORAD-{norad_id}"
                        doc = {
                            "identifier": identifier,
                            "canonical": {
                                "name": kaggle_data["name"],
                                "object_type": kaggle_data["object_type"],
                                "norad_cat_id": norad_id,
                            },
                            "sources": {
                                "kaggle": {
                                    **kaggle_data,
                                    "updated_at": datetime.now(timezone.utc).isoformat()
                                }
                            },
                            "metadata": {
                                "created_at": datetime.now(timezone.utc).isoformat(),
                                "last_updated_at": datetime.now(timezone.utc).isoformat(),
                                "sources_available": ["kaggle"],
                                "source_priority": ["unoosa", "celestrak", "spacetrack", "kaggle"]
                            }
                        }
                        
                        update_canonical(doc)
                        collection.insert_one(doc)
                        created += 1
                    
                    if (created + updated + skipped) % 1000 == 0:
                        print(f"Progress: {created + updated + skipped} rows processed "
                              f"({created} created, {updated} updated, {skipped} skipped)")
                
                except Exception as e:
                    print(f"Error processing row {row_num}: {e}")
                    skipped += 1
                    continue
        
        print(f"\n✓ Import complete!")
        print(f"  Created: {created}")
        print(f"  Updated: {updated}")
        print(f"  Skipped: {skipped}")
        print(f"  Total processed: {created + updated + skipped}")
        
        total_in_db = collection.count_documents({})
        print(f"\nTotal satellites in database: {total_in_db}")
        
        return True
    
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return False


if __name__ == "__main__":
    csv_path = "/Users/frankblau/Downloads/archive (3)/current_catalog.csv"
    
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    
    success = import_kaggle_catalog(csv_path)
    sys.exit(0 if success else 1)
