#!/usr/bin/env python3
"""
Debug duplicate detection query.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import database.connection as db_conn
from database import connect_mongodb, get_satellites_collection

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def debug_duplicates():
    """Debug duplicate detection"""
    if not connect_mongodb():
        print("Failed to connect to database")
        return
    
    collection = get_satellites_collection()
    
    aql = """
    FOR sat IN @@collection
        FILTER sat.canonical.norad_cat_id != null
        COLLECT norad_id = sat.canonical.norad_cat_id INTO groups
        FILTER LENGTH(groups) > 1
        SORT norad_id
        RETURN {
            norad_id: norad_id,
            count: LENGTH(groups),
            identifiers: groups[*].sat.identifier
        }
    """
    
    cursor = db_conn.db.aql.execute(
        aql,
        bind_vars={'@collection': collection.name}
    )
    
    results = list(cursor)
    
    print(f"Found {len(results)} NORAD IDs with duplicates:\n")
    
    for group in results:
        print(f"NORAD ID: {group['norad_id']}")
        print(f"  Count: {group['count']}")
        print(f"  Identifiers: {group['identifiers']}")
        print()


if __name__ == "__main__":
    debug_duplicates()
