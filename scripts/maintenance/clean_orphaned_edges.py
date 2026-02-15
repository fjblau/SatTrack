#!/usr/bin/env python3
"""
Clean up orphaned edges that reference deleted satellites.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import database.connection as db_conn
from database import connect_mongodb
from database.connection import (
    EDGE_COLLECTION_CONSTELLATION,
    EDGE_COLLECTION_REGISTRATION,
    EDGE_COLLECTION_PROXIMITY,
    EDGE_COLLECTION_COLLISION_RISK,
    EDGE_COLLECTION_SATELLITE_LINEAGE
)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def clean_orphaned_edges(dry_run=False):
    """Remove edges referencing deleted satellites"""
    if not connect_mongodb():
        print("Failed to connect to database")
        return 0
    
    edge_collections = [
        EDGE_COLLECTION_CONSTELLATION,
        EDGE_COLLECTION_REGISTRATION,
        EDGE_COLLECTION_PROXIMITY,
        EDGE_COLLECTION_COLLISION_RISK,
        EDGE_COLLECTION_SATELLITE_LINEAGE
    ]
    
    total_removed = 0
    
    for edge_coll_name in edge_collections:
        if not db_conn.db.has_collection(edge_coll_name):
            print(f"Skipping {edge_coll_name} (doesn't exist)")
            continue
        
        edge_coll = db_conn.db.collection(edge_coll_name)
        
        # Find orphaned edges
        aql = f"""
        FOR edge IN {edge_coll_name}
            LET from_exists = DOCUMENT(edge._from) != null
            LET to_exists = DOCUMENT(edge._to) != null
            FILTER !from_exists OR !to_exists
            RETURN edge._key
        """
        
        cursor = db_conn.db.aql.execute(aql)
        orphaned_keys = list(cursor)
        
        if orphaned_keys:
            print(f"\n{edge_coll_name}: Found {len(orphaned_keys)} orphaned edges")
            
            if not dry_run:
                # Delete in batches of 1000
                batch_size = 1000
                deleted = 0
                
                for i in range(0, len(orphaned_keys), batch_size):
                    batch = orphaned_keys[i:i + batch_size]
                    
                    delete_aql = f"""
                    FOR key IN @keys
                        REMOVE key IN {edge_coll_name}
                    """
                    
                    db_conn.db.aql.execute(delete_aql, bind_vars={'keys': batch})
                    deleted += len(batch)
                    
                    if deleted % 5000 == 0:
                        print(f"  Progress: {deleted}/{len(orphaned_keys)} deleted...")
                
                print(f"  ✓ Deleted {deleted} orphaned edges")
                total_removed += deleted
            else:
                print(f"  Would delete {len(orphaned_keys)} orphaned edges")
                total_removed += len(orphaned_keys)
        else:
            print(f"{edge_coll_name}: No orphaned edges")
    
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Total orphaned edges {'would be ' if dry_run else ''}removed: {total_removed}")
    return total_removed


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    
    if dry_run:
        print("Running in DRY RUN mode - no changes will be made\n")
    
    clean_orphaned_edges(dry_run=dry_run)
