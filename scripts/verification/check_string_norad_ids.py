#!/usr/bin/env python3
"""
Check for satellites with string NORAD IDs.
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


def check_string_norad_ids():
    """Check for satellites with string NORAD IDs"""
    if not connect_mongodb():
        print("Failed to connect to database")
        return
    
    collection = get_satellites_collection()
    
    aql = """
    FOR sat IN @@collection
        FILTER sat.canonical.norad_cat_id != null
        FILTER TYPENAME(sat.canonical.norad_cat_id) == "string"
        RETURN {
            identifier: sat.identifier,
            norad_cat_id: sat.canonical.norad_cat_id,
            norad_type: TYPENAME(sat.canonical.norad_cat_id),
            name: sat.canonical.name
        }
    """
    
    cursor = db_conn.db.aql.execute(
        aql,
        bind_vars={'@collection': collection.name}
    )
    
    results = list(cursor)
    
    print(f"Found {len(results)} satellite(s) with string NORAD IDs:\n")
    
    for i, sat in enumerate(results[:20], 1):  # Show first 20
        print(f"{i}. {sat['identifier']}: {sat['norad_cat_id']} ({sat['name']})")
    
    if len(results) > 20:
        print(f"\n... and {len(results) - 20} more")


if __name__ == "__main__":
    check_string_norad_ids()
