#!/usr/bin/env python3
"""
Check for PRETTY satellites in the database.
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


def check_pretty_satellites():
    """Find all satellites named PRETTY"""
    if not connect_mongodb():
        print("Failed to connect to database")
        return
    
    collection = get_satellites_collection()
    
    aql = """
    FOR sat IN @@collection
        FILTER sat.canonical.name == "PRETTY" OR 
               sat.sources.kaggle.name == "PRETTY" OR
               sat.sources.unoosa.name == "PRETTY" OR
               sat.sources.spacetrack.name == "PRETTY"
        RETURN sat
    """
    
    cursor = db_conn.db.aql.execute(
        aql,
        bind_vars={'@collection': collection.name}
    )
    
    satellites = list(cursor)
    
    print(f"Found {len(satellites)} satellite(s) named PRETTY:\n")
    
    for i, sat in enumerate(satellites, 1):
        print(f"=== PRETTY Satellite {i}: {sat['identifier']} ===")
        print(f"Sources: {list(sat.get('sources', {}).keys())}")
        print(f"Canonical NORAD ID: {sat.get('canonical', {}).get('norad_cat_id', 'N/A')}")
        
        if 'kaggle' in sat.get('sources', {}):
            print(f"Kaggle data:")
            print(f"  norad_cat_id: {sat['sources']['kaggle'].get('norad_cat_id', 'N/A')}")
            print(f"  name: {sat['sources']['kaggle'].get('name', 'N/A')}")
        
        if 'unoosa' in sat.get('sources', {}):
            print(f"UNOOSA data:")
            print(f"  international_designator: {sat['sources']['unoosa'].get('international_designator', 'N/A')}")
        
        if 'spacetrack' in sat.get('sources', {}):
            print(f"SpaceTrack data:")
            print(f"  international_designator: {sat['sources']['spacetrack'].get('international_designator', 'N/A')}")
        
        print()


if __name__ == "__main__":
    check_pretty_satellites()
