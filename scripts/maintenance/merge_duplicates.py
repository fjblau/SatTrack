#!/usr/bin/env python3
"""
Merge duplicate satellite entries that share the same NORAD ID.
This script identifies and merges satellites with the same NORAD ID but different identifiers.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import database.connection as db_conn
from database import connect_mongodb, get_satellites_collection, update_canonical

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def find_duplicates_by_norad_id(collection):
    """
    Find satellites with the same NORAD ID but different identifiers.
    Handles both string and numeric NORAD IDs.
    
    Returns:
        List of tuples (norad_id, [satellite_documents])
    """
    aql = """
    FOR sat IN @@collection
        FILTER sat.canonical.norad_cat_id != null
        LET norad_numeric = TO_NUMBER(sat.canonical.norad_cat_id)
        COLLECT norad_id = norad_numeric INTO groups
        FILTER LENGTH(groups) > 1
        SORT norad_id
        RETURN {
            norad_id: norad_id,
            satellites: groups[*].sat
        }
    """
    
    cursor = db_conn.db.aql.execute(
        aql,
        bind_vars={'@collection': collection.name}
    )
    
    results = []
    for group in cursor:
        results.append((group["norad_id"], group["satellites"]))
    
    return results


def merge_satellites(collection, satellites, dry_run=False):
    """
    Merge multiple satellite documents into one.
    
    Strategy:
    1. Prefer documents with international designator as the primary
    2. Merge all sources from all documents
    3. Keep the most complete metadata
    4. Update canonical fields
    5. Delete the duplicate documents
    
    Args:
        collection: MongoDB collection
        satellites: List of satellite documents to merge
        dry_run: If True, only print what would be done without making changes
        
    Returns:
        The identifier of the kept satellite, or None if no merge was performed
    """
    if len(satellites) < 2:
        return None
    
    satellites_sorted = sorted(
        satellites,
        key=lambda s: (
            s.get("identifier", "").startswith("NORAD-"),
            -len(s.get("sources", {})),
            -len(s.get("identifier", ""))
        )
    )
    
    primary = satellites_sorted[0].copy()
    duplicates = satellites_sorted[1:]
    
    norad_id = primary["canonical"]["norad_cat_id"]
    
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Merging {len(satellites)} satellites with NORAD ID {norad_id}:")
    print(f"  Primary: {primary['identifier']} (sources: {list(primary.get('sources', {}).keys())})")
    
    for dup in duplicates:
        print(f"  Merging in: {dup['identifier']} (sources: {list(dup.get('sources', {}).keys())})")
        
        for source_name, source_data in dup.get("sources", {}).items():
            if source_name not in primary["sources"]:
                primary["sources"][source_name] = source_data
            else:
                for key, value in source_data.items():
                    if key not in primary["sources"][source_name] or primary["sources"][source_name][key] is None:
                        primary["sources"][source_name][key] = value
    
    primary["metadata"]["sources_available"] = list(primary["sources"].keys())
    primary["metadata"]["last_updated_at"] = datetime.now(timezone.utc).isoformat()
    primary["metadata"]["merged_from"] = [dup["identifier"] for dup in duplicates]
    
    update_canonical(primary)
    
    if not dry_run:
        collection.update(primary)
        
        for dup in duplicates:
            collection.delete(dup)
        
        print(f"  ✓ Merged into {primary['identifier']}")
    else:
        print(f"  Would merge into {primary['identifier']}")
    
    return primary["identifier"]


def merge_all_duplicates(dry_run=False):
    """
    Find and merge all duplicate satellites.
    
    Args:
        dry_run: If True, only print what would be done without making changes
        
    Returns:
        Number of merges performed
    """
    if not connect_mongodb():
        print("Failed to connect to MongoDB")
        return 0
    
    collection = get_satellites_collection()
    
    print("Searching for duplicate satellites by NORAD ID...")
    duplicates = find_duplicates_by_norad_id(collection)
    
    if not duplicates:
        print("No duplicates found!")
        return 0
    
    print(f"\nFound {len(duplicates)} NORAD IDs with duplicate entries:")
    
    merged_count = 0
    for norad_id, satellites in duplicates:
        result = merge_satellites(collection, satellites, dry_run=dry_run)
        if result:
            merged_count += 1
    
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Summary:")
    print(f"  NORAD IDs with duplicates: {len(duplicates)}")
    print(f"  Merges performed: {merged_count}")
    
    return merged_count


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    
    if dry_run:
        print("Running in DRY RUN mode - no changes will be made\n")
    
    merge_all_duplicates(dry_run=dry_run)
