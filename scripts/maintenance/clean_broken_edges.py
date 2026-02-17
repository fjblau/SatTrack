#!/usr/bin/env python3
"""
Clean broken edges from edge collections.

Run this if you get errors like:
  "Cannot create edge with nonexistent target satellites/NORAD-XXXXX"

This happens when satellite _keys change but edges still reference old _keys.
"""
import os
import sys
from arango import ArangoClient

RAILWAY_HOST = os.getenv("RAILWAY_HOST", "https://arangodb-production-d6fb.up.railway.app:443")
RAILWAY_PASSWORD = os.getenv("RAILWAY_PASSWORD")
DB_NAME = "kessler"

EDGE_COLLECTIONS = [
    "orbital_proximity",
    "constellation_membership",
    "registration_links",
    "collision_risk_edges"
]


def clean_broken_edges(collection_name, db, dry_run=True):
    """Clean broken edges from a collection."""
    
    print(f"\nCleaning {collection_name}...")
    
    # Find broken edges
    query = f'''
    FOR edge IN {collection_name}
        LET from_exists = DOCUMENT(edge._from) != null
        LET to_exists = DOCUMENT(edge._to) != null
        FILTER !from_exists OR !to_exists
        RETURN {{
            _key: edge._key,
            _from: edge._from,
            _to: edge._to,
            from_exists: from_exists,
            to_exists: to_exists
        }}
    '''
    
    broken = list(db.aql.execute(query))
    
    if not broken:
        print(f"  ✓ No broken edges in {collection_name}")
        return 0
    
    print(f"  Found {len(broken)} broken edges")
    
    if dry_run:
        print(f"  [DRY RUN] Would delete {len(broken)} edges")
        print(f"  Sample broken edges:")
        for edge in broken[:5]:
            print(f"    {edge['_from']} -> {edge['_to']}")
            if not edge['from_exists']:
                print(f"      (source doesn't exist)")
            if not edge['to_exists']:
                print(f"      (target doesn't exist)")
        return len(broken)
    
    # Delete broken edges
    delete_query = f'''
    FOR edge IN {collection_name}
        LET from_exists = DOCUMENT(edge._from) != null
        LET to_exists = DOCUMENT(edge._to) != null
        FILTER !from_exists OR !to_exists
        REMOVE edge IN {collection_name}
        RETURN 1
    '''
    
    result = list(db.aql.execute(delete_query))
    deleted = len(result)
    
    print(f"  ✓ Deleted {deleted} broken edges from {collection_name}")
    return deleted


def main(railway=False, dry_run=True):
    """Clean broken edges from all edge collections."""
    
    if railway:
        if not RAILWAY_PASSWORD:
            print("❌ Error: RAILWAY_PASSWORD environment variable not set")
            return False
        
        client = ArangoClient(hosts=RAILWAY_HOST)
        db = client.db(DB_NAME, username='root', password=RAILWAY_PASSWORD)
        location = "Railway Production"
    else:
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from database import connect_arangodb
        import database.connection as db_conn
        connect_arangodb()
        db = db_conn.db
        location = "Local"
    
    print("="*70)
    print(f"CLEANING BROKEN EDGES - {location}")
    print("="*70)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE DELETE'}")
    print()
    
    total_broken = 0
    
    for collection_name in EDGE_COLLECTIONS:
        if not db.has_collection(collection_name):
            print(f"  ⚠️  Collection {collection_name} not found")
            continue
        
        broken = clean_broken_edges(collection_name, db, dry_run)
        total_broken += broken
    
    print()
    print("="*70)
    
    if dry_run:
        print(f"DRY RUN: Would delete {total_broken} broken edges total")
        print("Run with --apply to actually delete")
    else:
        print(f"✓ Deleted {total_broken} broken edges total")
    
    print("="*70)
    
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean broken edges from edge collections")
    parser.add_argument("--railway", action="store_true", help="Clean Railway production database")
    parser.add_argument("--apply", action="store_true", help="Actually delete (default is dry run)")
    
    args = parser.parse_args()
    
    dry_run = not args.apply
    
    if not dry_run:
        location = "Railway Production" if args.railway else "Local"
        response = input(f"⚠️  This will DELETE broken edges from {location}. Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            sys.exit(0)
    
    success = main(railway=args.railway, dry_run=dry_run)
    sys.exit(0 if success else 1)
