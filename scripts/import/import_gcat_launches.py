#!/usr/bin/env python3
"""
Import satellite data from GCAT (General Catalog) TSV file and merge with existing ArangoDB records.
Uses NORAD catalog ID and international designator for matching and merging data.

The GCAT catalog provides comprehensive launch and technical data from Jonathan McDowell's
General Catalog of Artificial Space Objects (https://planet4589.org/space/gcat/).
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database import (
    connect_arangodb,
    get_satellites_collection,
    create_satellite_document,
    update_canonical,
    find_satellite
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


def parse_gcat_date(date_str):
    """
    Parse GCAT date format "YYYY MMM DD" to ISO format
    Examples: "2025 Sep 13", "1957 Oct  4"
    """
    if not date_str or date_str.strip() == "-":
        return None
    
    try:
        date_str = date_str.strip()
        dt = datetime.strptime(date_str, "%Y %b %d")
        return dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        date_str_normalized = " ".join(date_str.split())
        try:
            dt = datetime.strptime(date_str_normalized, "%Y %b %d")
            return dt.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            return None


def is_after_date(launch_date, cutoff_date):
    """Check if launch_date is after cutoff_date"""
    if not launch_date or not cutoff_date:
        return False
    
    try:
        launch_dt = datetime.strptime(launch_date, "%Y-%m-%d")
        cutoff_dt = datetime.strptime(cutoff_date, "%Y-%m-%d")
        return launch_dt > cutoff_dt
    except (ValueError, TypeError):
        return False


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


def find_existing_by_intl_designator(intl_designator):
    """Find existing satellite by international designator"""
    if not intl_designator:
        return None
    
    collection = get_satellites_collection()
    
    aql = """
    FOR doc IN @@collection
        FILTER doc.canonical.international_designator == @intl_designator
           OR doc.sources.gcat.international_designator == @intl_designator
           OR doc.sources.unoosa.international_designator == @intl_designator
           OR doc.sources.celestrak.international_designator == @intl_designator
           OR doc.sources.spacetrack.object_id == @intl_designator
        LIMIT 1
        RETURN doc
    """
    
    cursor = db_conn.db.aql.execute(
        aql,
        bind_vars={
            '@collection': db_conn.COLLECTION_NAME,
            'intl_designator': intl_designator
        }
    )
    
    results = list(cursor)
    return results[0] if results else None


def import_gcat_launches(tsv_path, cutoff_date="2025-09-13", dry_run=False):
    """
    Import GCAT satellite data and merge with existing ArangoDB records.
    
    Args:
        tsv_path: Path to gcat_satcat.tsv file
        cutoff_date: Only import satellites launched after this date (YYYY-MM-DD)
        dry_run: If True, don't write to database, just show what would be done
    """
    if not os.path.exists(tsv_path):
        print(f"Error: File not found: {tsv_path}")
        return False
    
    if not dry_run:
        if not connect_arangodb():
            print("Failed to connect to ArangoDB")
            return False
    
    collection = get_satellites_collection() if not dry_run else None
    
    created = 0
    updated = 0
    skipped_old = 0
    skipped_invalid = 0
    
    print(f"Importing GCAT data from: {tsv_path}")
    print(f"Filtering for launches after: {cutoff_date}")
    if dry_run:
        print("DRY RUN MODE - No changes will be made to the database")
    print()
    
    try:
        with open(tsv_path, 'r', encoding='utf-8') as f:
            for row_num, line in enumerate(f, start=1):
                if row_num == 1:
                    continue
                
                if row_num == 2:
                    continue
                
                try:
                    fields = line.rstrip('\n').split('\t')
                    
                    if len(fields) < 42:
                        skipped_invalid += 1
                        continue
                    
                    jcat = normalize_string(fields[0])
                    satcat = normalize_string(fields[1])
                    launch_tag = normalize_string(fields[2])
                    piece = normalize_string(fields[3])
                    obj_type = normalize_string(fields[4])
                    name = normalize_string(fields[5])
                    plname = normalize_string(fields[6])
                    ldate = normalize_string(fields[7])
                    parent = normalize_string(fields[8])
                    sdate = normalize_string(fields[9])
                    primary = normalize_string(fields[10])
                    ddate = normalize_string(fields[11])
                    status = normalize_string(fields[12])
                    dest = normalize_string(fields[13])
                    owner = normalize_string(fields[14])
                    state = normalize_string(fields[15])
                    manufacturer = normalize_string(fields[16])
                    bus = normalize_string(fields[17])
                    motor = normalize_string(fields[18])
                    mass = convert_float(fields[19])
                    perigee = convert_float(fields[33])
                    apogee = convert_float(fields[35])
                    inclination = convert_float(fields[37])
                    
                    norad_id = convert_int(satcat)
                    
                    launch_date = parse_gcat_date(ldate)
                    
                    if not is_after_date(launch_date, cutoff_date):
                        skipped_old += 1
                        continue
                    
                    gcat_data = {
                        "jcat": jcat,
                        "norad_cat_id": norad_id,
                        "international_designator": launch_tag,
                        "piece": piece,
                        "object_type": obj_type,
                        "name": name or plname,
                        "payload_name": plname,
                        "date_of_launch": launch_date,
                        "launch_date": launch_date,
                        "parent": parent,
                        "separation_date": parse_gcat_date(sdate),
                        "primary": primary,
                        "decay_date": parse_gcat_date(ddate),
                        "status": status,
                        "destination": dest,
                        "owner": owner,
                        "country_of_origin": state,
                        "manufacturer": manufacturer,
                        "bus": bus,
                        "motor": motor,
                        "mass_kg": mass,
                        "perigee_km": perigee,
                        "apogee_km": apogee,
                        "inclination_degrees": inclination,
                    }
                    
                    gcat_data = {k: v for k, v in gcat_data.items() if v is not None}
                    
                    if dry_run:
                        print(f"[DRY RUN] Would process: {name or plname} ({launch_date}) - NORAD: {norad_id}")
                        created += 1
                        continue
                    
                    existing = None
                    if norad_id:
                        existing = find_existing_by_norad(norad_id)
                    
                    if not existing and launch_tag:
                        existing = find_existing_by_intl_designator(launch_tag)
                    
                    if existing:
                        existing["sources"]["gcat"] = {
                            **gcat_data,
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        }
                        existing["metadata"]["sources_available"] = list(existing["sources"].keys())
                        existing["metadata"]["last_updated_at"] = datetime.now(timezone.utc).isoformat()
                        
                        # DO NOT call update_canonical - GCAT is not an approved source
                        # Data stays in sources.gcat only
                        
                        collection.update(existing)
                        updated += 1
                        
                        if updated % 100 == 0:
                            print(f"Progress: {updated} records updated, {created} created, {skipped_old} old skipped")
                    else:
                        identifier = f"GCAT-{jcat}" if jcat else f"NORAD-{norad_id}" if norad_id else f"INTL-{launch_tag}"
                        
                        doc = {
                            "_key": (identifier
                                     .replace('/', '_')
                                     .replace(':', '_')
                                     .replace('.', '_')
                                     .replace('*', '_STAR_')
                                     .replace(' ', '_')
                                     .replace('(', '_')
                                     .replace(')', '_')),
                            "identifier": identifier,
                            "canonical": {
                                "name": gcat_data.get("name") or identifier,
                                "updated_at": datetime.now(timezone.utc).isoformat()
                            },
                            "sources": {
                                "gcat": {
                                    **gcat_data,
                                    "updated_at": datetime.now(timezone.utc).isoformat()
                                }
                            },
                            "metadata": {
                                "created_at": datetime.now(timezone.utc).isoformat(),
                                "last_updated_at": datetime.now(timezone.utc).isoformat(),
                                "sources_available": ["gcat"],
                                "source_priority": ["unoosa", "spacetrack", "celestrak", "tleapi", "kaggle"]
                            }
                        }
                        
                        # DO NOT call update_canonical - GCAT is not an approved source
                        # For new satellites, set minimal canonical.name to prevent graph errors
                        # Full canonical data will be populated when approved sources are added
                        
                        collection.insert(doc)
                        created += 1
                        
                        if created % 100 == 0:
                            print(f"Progress: {created} records created, {updated} updated, {skipped_old} old skipped")
                
                except Exception as e:
                    print(f"Error processing row {row_num}: {e}")
                    skipped_invalid += 1
                    continue
        
        print(f"\n✓ Import complete!")
        print(f"  Created: {created}")
        print(f"  Updated: {updated}")
        print(f"  Skipped (before {cutoff_date}): {skipped_old}")
        print(f"  Skipped (invalid): {skipped_invalid}")
        print(f"  Total processed: {created + updated}")
        
        if not dry_run:
            total_in_db = collection.count()
            print(f"\nTotal satellites in database: {total_in_db}")
        
        return True
    
    except Exception as e:
        print(f"Error reading TSV file: {e}")
        return False


if __name__ == "__main__":
    tsv_path = "gcat_satcat.tsv"
    cutoff_date = "2025-09-13"
    dry_run = False
    
    if len(sys.argv) > 1:
        tsv_path = sys.argv[1]
    
    if len(sys.argv) > 2:
        cutoff_date = sys.argv[2]
    
    if "--dry-run" in sys.argv:
        dry_run = True
    
    success = import_gcat_launches(tsv_path, cutoff_date, dry_run)
    sys.exit(0 if success else 1)
