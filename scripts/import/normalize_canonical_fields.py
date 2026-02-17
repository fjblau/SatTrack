#!/usr/bin/env python3
"""
Normalize canonical fields for satellites to ensure schema consistency.

This script ensures all satellites have required canonical fields populated:
- canonical.name (from sources or identifier)
- canonical.country (from sources)
- canonical.launch_date (from sources)

Run this AFTER importing new data to normalize the schema.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database import connect_arangodb
import database.connection as db_conn
from datetime import datetime, timezone

def normalize_canonical_fields(dry_run=True):
    """
    Normalize canonical fields for all satellites.
    
    Args:
        dry_run: If True, only show what would be changed without applying
    """
    connect_arangodb()
    
    print("="*70)
    print("Canonical Field Normalization")
    print("="*70)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
    print()
    
    # Find satellites missing canonical.name
    query = """
    FOR sat IN satellites
        FILTER sat.canonical.name == null OR sat.canonical.name == ""
        RETURN {
            _key: sat._key,
            identifier: sat.identifier,
            canonical: sat.canonical,
            sources: sat.sources
        }
    """
    
    satellites_to_fix = list(db_conn.db.aql.execute(query))
    
    print(f"Found {len(satellites_to_fix)} satellites with missing canonical.name")
    print()
    
    if len(satellites_to_fix) == 0:
        print("✓ All satellites have canonical.name populated")
        return
    
    # Show samples
    print("Sample satellites to fix:")
    for sat in satellites_to_fix[:5]:
        print(f"  {sat['identifier']}: missing canonical.name")
        # Try to find name in sources
        sources = sat.get('sources', {})
        for source_name in ['gcat', 'kaggle', 'satnogs', 'unoosa', 'spacetrack']:
            if source_name in sources and 'name' in sources[source_name]:
                print(f"    → Can use {source_name}.name: {sources[source_name]['name']}")
                break
        else:
            print(f"    → Will use identifier: {sat['identifier']}")
    
    if len(satellites_to_fix) > 5:
        print(f"  ... and {len(satellites_to_fix) - 5} more")
    print()
    
    if not dry_run:
        print("Applying normalization...")
        
        # Update query that sets canonical.name from sources or identifier
        update_query = """
        FOR sat IN satellites
            FILTER sat.canonical.name == null OR sat.canonical.name == ""
            
            // Try to get name from APPROVED sources only (GCAT and SatNOGS excluded)
            LET name = (
                sat.sources.unoosa.name ||
                sat.sources.spacetrack.name ||
                sat.sources.spacetrack.object_name ||
                sat.sources.kaggle.name ||
                sat.identifier
            )
            
            // Try to get country from APPROVED sources only
            LET country = (
                sat.canonical.country ||
                sat.sources.unoosa.country_of_origin ||
                sat.sources.unoosa.country ||
                sat.sources.spacetrack.country_of_origin ||
                sat.sources.kaggle.country ||
                sat.canonical.country_of_origin
            )
            
            // Try to get launch_date from APPROVED sources only
            LET launch_date = (
                sat.canonical.launch_date ||
                sat.sources.unoosa.date_of_launch ||
                sat.sources.spacetrack.date_of_launch ||
                sat.sources.kaggle.launch_date ||
                sat.canonical.date_of_launch
            )
            
            UPDATE sat WITH {
                canonical: MERGE(sat.canonical, {
                    name: name,
                    country: country,
                    launch_date: launch_date,
                    updated_at: @timestamp
                })
            } IN satellites
            
            RETURN {
                _key: sat._key,
                identifier: sat.identifier,
                updated: {
                    name: name,
                    country: country,
                    launch_date: launch_date
                }
            }
        """
        
        timestamp = datetime.now(timezone.utc).isoformat()
        results = list(db_conn.db.aql.execute(update_query, bind_vars={'timestamp': timestamp}))
        
        print(f"✓ Updated {len(results)} satellites")
        print()
        
        # Show samples of what was updated
        print("Sample updates:")
        for result in results[:5]:
            print(f"  {result['identifier']}:")
            print(f"    name: {result['updated']['name']}")
            print(f"    country: {result['updated']['country']}")
            print(f"    launch_date: {result['updated']['launch_date']}")
        
        if len(results) > 5:
            print(f"  ... and {len(results) - 5} more")
    else:
        print("ℹ️  This is a dry run. Use --apply to make changes.")
    
    print()
    print("="*70)
    print("Normalization complete" if not dry_run else "Dry run complete")
    print("="*70)


if __name__ == "__main__":
    import sys
    
    dry_run = "--apply" not in sys.argv
    
    if not dry_run:
        response = input("This will modify satellite records. Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            sys.exit(0)
    
    normalize_canonical_fields(dry_run=dry_run)
