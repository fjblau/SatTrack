#!/usr/bin/env python3
"""
Import satellite data from Kaggle current_catalog.csv and merge with existing ArangoDB records.
Uses NORAD ID as the primary identifier for matching and merging data.

The Kaggle catalog provides orbital analytics data including altitude categories,
congestion risk assessments, and orbit lifetime predictions.
"""

import os
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database import (
    connect_arangodb,
    get_satellites_collection,
    update_canonical,
)
import database.connection as db_conn

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
    if value_str.lower() in ["nan", "n/a", "none", "", "-"]:
        return None
    return value_str


def convert_float(value):
    """Convert string to float, return None if invalid"""
    if value is None or value == "":
        return None
    try:
        val_str = str(value).strip()
        if val_str.lower() in ["nan", "n/a", "none", "-"]:
            return None
        return float(val_str)
    except (ValueError, TypeError):
        return None


def convert_int(value):
    """Convert string to int, return None if invalid"""
    if value is None or value == "":
        return None
    try:
        val_str = str(value).strip()
        if val_str.lower() in ["nan", "n/a", "none", "-"]:
            return None
        return int(val_str)
    except (ValueError, TypeError):
        return None


def find_existing_by_norad(norad_id):
    """Find existing satellite by NORAD ID (handles both int and string)"""
    if not norad_id:
        return None
    
    collection = get_satellites_collection()
    
    norad_str = str(norad_id)
    
    aql = """
    FOR doc IN @@collection
        FILTER doc.canonical.norad_cat_id == @norad_id
           OR doc.canonical.norad_cat_id == @norad_str
           OR doc.sources.gcat.norad_cat_id == @norad_id
           OR doc.sources.gcat.norad_cat_id == @norad_str
           OR doc.sources.celestrak.norad_id == @norad_id
           OR doc.sources.celestrak.norad_id == @norad_str
           OR doc.sources.spacetrack.norad_catalog_number == @norad_id
           OR doc.sources.spacetrack.norad_catalog_number == @norad_str
           OR doc.sources.kaggle.norad_cat_id == @norad_id
           OR doc.sources.kaggle.norad_cat_id == @norad_str
           OR doc.identifier == @identifier
        LIMIT 1
        RETURN doc
    """
    
    cursor = db_conn.db.aql.execute(
        aql,
        bind_vars={
            '@collection': db_conn.COLLECTION_NAME,
            'norad_id': norad_id,
            'norad_str': norad_str,
            'identifier': f'NORAD-{norad_id}'
        }
    )
    
    results = list(cursor)
    return results[0] if results else None


def import_kaggle_catalog(csv_path, dry_run=False):
    """
    Import Kaggle catalog data and merge with existing ArangoDB records.
    
    Args:
        csv_path: Path to current_catalog.csv file
        dry_run: If True, don't write to database, just show what would be done
    """
    if not os.path.exists(csv_path):
        print(f"Error: File not found: {csv_path}")
        return False
    
    if not dry_run:
        if not connect_arangodb():
            print("Failed to connect to ArangoDB")
            return False
    
    collection = get_satellites_collection() if not dry_run else None
    
    created = 0
    updated = 0
    skipped = 0
    
    print(f"Importing Kaggle catalog from: {csv_path}")
    if dry_run:
        print("DRY RUN MODE - No changes will be made to the database")
    print()
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row_num, row in enumerate(reader, start=2):
                try:
                    norad_id_str = normalize_string(row.get('norad_id'))
                    
                    if not norad_id_str:
                        skipped += 1
                        continue
                    
                    norad_id = convert_int(norad_id_str)
                    if not norad_id:
                        skipped += 1
                        continue
                    
                    # Extract Kaggle data fields
                    kaggle_data = {
                        "norad_cat_id": norad_id,
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
                    
                    # Remove None values
                    kaggle_data = {k: v for k, v in kaggle_data.items() if v is not None}
                    
                    if dry_run:
                        print(f"[DRY RUN] Would process: {kaggle_data.get('name')} - NORAD: {norad_id}")
                        created += 1
                        continue
                    
                    # Find existing record by NORAD ID
                    existing = find_existing_by_norad(norad_id)
                    
                    if existing:
                        # Update existing record
                        existing["sources"]["kaggle"] = {
                            **kaggle_data,
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        }
                        existing["metadata"]["sources_available"] = list(existing["sources"].keys())
                        existing["metadata"]["last_updated_at"] = datetime.now(timezone.utc).isoformat()
                        
                        # Update canonical fields with new data
                        update_canonical(existing)
                        
                        # Save to database
                        collection.update(existing)
                        updated += 1
                        
                        if updated % 1000 == 0:
                            print(f"Progress: {updated} updated, {created} created, {skipped} skipped")
                    
                    else:
                        # Create new record
                        identifier = f"NORAD-{norad_id}"
                        
                        doc = {
                            "_key": f"NORAD_{norad_id}",
                            "identifier": identifier,
                            "canonical": {},
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
                                "source_priority": ["unoosa", "gcat", "celestrak", "tleapi", "kaggle"]
                            }
                        }
                        
                        # Populate canonical fields
                        update_canonical(doc)
                        
                        # Insert into database
                        collection.insert(doc)
                        created += 1
                        
                        if created % 1000 == 0:
                            print(f"Progress: {created} created, {updated} updated, {skipped} skipped")
                
                except Exception as e:
                    print(f"Error processing row {row_num}: {e}")
                    skipped += 1
                    continue
        
        print(f"\n✓ Import complete!")
        print(f"  Created: {created}")
        print(f"  Updated: {updated}")
        print(f"  Skipped: {skipped}")
        print(f"  Total processed: {created + updated}")
        
        if not dry_run:
            total_in_db = collection.count()
            print(f"\nTotal satellites in database: {total_in_db}")
            
            # Count records with Kaggle data
            aql_count = """
            FOR doc IN @@collection
                FILTER doc.sources.kaggle != null
                COLLECT WITH COUNT INTO count
                RETURN count
            """
            cursor = db_conn.db.aql.execute(
                aql_count,
                bind_vars={'@collection': db_conn.COLLECTION_NAME}
            )
            kaggle_count = list(cursor)[0]
            print(f"Records with Kaggle data: {kaggle_count}")
        
        return True
    
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return False


if __name__ == "__main__":
    csv_path = "/Users/frankblau/Downloads/current_catalog.csv"
    dry_run = False
    
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    
    if "--dry-run" in sys.argv:
        dry_run = True
    
    success = import_kaggle_catalog(csv_path, dry_run)
    sys.exit(0 if success else 1)
