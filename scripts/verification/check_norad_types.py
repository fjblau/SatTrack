#!/usr/bin/env python3
"""
Check NORAD ID types for PRETTY satellites.
"""

import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import database.connection as db_conn
from database import connect_mongodb, get_satellites_collection

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def check_norad_types():
    """Check NORAD ID types"""
    if not connect_mongodb():
        print("Failed to connect to database")
        return
    
    collection = get_satellites_collection()
    
    aql = """
    FOR sat IN @@collection
        FILTER sat.canonical.name == "PRETTY"
        RETURN {
            identifier: sat.identifier,
            canonical_norad: sat.canonical.norad_cat_id,
            canonical_norad_type: TYPENAME(sat.canonical.norad_cat_id),
            full_canonical: sat.canonical
        }
    """
    
    cursor = db_conn.db.aql.execute(
        aql,
        bind_vars={'@collection': collection.name}
    )
    
    results = list(cursor)
    
    for sat in results:
        print(f"\n=== {sat['identifier']} ===")
        print(f"NORAD ID: {sat['canonical_norad']}")
        print(f"NORAD ID Type: {sat['canonical_norad_type']}")
        print(f"Full canonical:")
        print(json.dumps(sat['full_canonical'], indent=2))


if __name__ == "__main__":
    check_norad_types()
