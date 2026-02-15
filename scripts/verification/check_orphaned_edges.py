#!/usr/bin/env python3
"""
Check for orphaned edges that reference deleted satellites.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import database.connection as db_conn
from database import connect_mongodb, get_satellites_collection
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


def check_orphaned_edges():
    """Check for edges referencing deleted satellites"""
    if not connect_mongodb():
        print("Failed to connect to database")
        return
    
    edge_collections = [
        EDGE_COLLECTION_CONSTELLATION,
        EDGE_COLLECTION_REGISTRATION,
        EDGE_COLLECTION_PROXIMITY,
        EDGE_COLLECTION_COLLISION_RISK,
        EDGE_COLLECTION_SATELLITE_LINEAGE
    ]
    
    for edge_coll_name in edge_collections:
        if not db_conn.db.has_collection(edge_coll_name):
            print(f"Skipping {edge_coll_name} (doesn't exist)")
            continue
        
        aql = f"""
        FOR edge IN {edge_coll_name}
            LET from_exists = DOCUMENT(edge._from) != null
            LET to_exists = DOCUMENT(edge._to) != null
            FILTER !from_exists OR !to_exists
            RETURN {{
                edge_id: edge._id,
                from: edge._from,
                to: edge._to,
                from_exists: from_exists,
                to_exists: to_exists
            }}
        """
        
        cursor = db_conn.db.aql.execute(aql)
        orphaned = list(cursor)
        
        if orphaned:
            print(f"\n{edge_coll_name}: {len(orphaned)} orphaned edges")
            for edge in orphaned[:5]:  # Show first 5
                print(f"  {edge['edge_id']}: {edge['from']} -> {edge['to']}")
                if not edge['from_exists']:
                    print(f"    _from document missing: {edge['from']}")
                if not edge['to_exists']:
                    print(f"    _to document missing: {edge['to']}")
            if len(orphaned) > 5:
                print(f"  ... and {len(orphaned) - 5} more")
        else:
            print(f"{edge_coll_name}: No orphaned edges")


if __name__ == "__main__":
    check_orphaned_edges()
