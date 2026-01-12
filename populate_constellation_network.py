#!/usr/bin/env python3
"""
Populate constellation membership network.

Creates a star topology for each constellation:
- One satellite per constellation is designated as the "hub" (first alphabetically)
- All other satellites in that constellation connect to the hub
- This allows efficient querying of constellation members via graph traversal
"""
import sys
from collections import defaultdict
import db as db_module

def populate_constellation_network(dry_run=False):
    """Create constellation membership edges"""
    
    print("=" * 60)
    print("Constellation Membership Network Population")
    print("=" * 60)
    
    if not db_module.connect_mongodb():
        print("❌ Failed to connect to ArangoDB")
        return False
    
    db = db_module.db
    
    print("\n" + "=" * 60)
    print("Step 1: Extract Constellation Data")
    print("=" * 60)
    
    query = """
    FOR doc IN @@collection
        FILTER doc.sources.kaggle.satellite_constellation != null
        SORT doc.identifier ASC
        RETURN {
            _key: doc._key,
            identifier: doc.identifier,
            constellation: doc.sources.kaggle.satellite_constellation,
            name: doc.canonical.name
        }
    """
    
    cursor = db.aql.execute(
        query,
        bind_vars={'@collection': db_module.COLLECTION_NAME}
    )
    
    satellites_with_const = list(cursor)
    print(f"Found {len(satellites_with_const):,} satellites with constellation data")
    
    constellation_members = defaultdict(list)
    for sat in satellites_with_const:
        constellation_members[sat['constellation']].append(sat)
    
    print(f"\nConstellation breakdown:")
    for const_name in sorted(constellation_members.keys()):
        count = len(constellation_members[const_name])
        print(f"  {const_name}: {count:,} satellites")
    
    print("\n" + "=" * 60)
    print("Step 2: Select Constellation Hubs")
    print("=" * 60)
    
    constellation_hubs = {}
    for const_name, members in constellation_members.items():
        hub = members[0]
        constellation_hubs[const_name] = hub
        print(f"  {const_name}: Hub = {hub['identifier']} ({hub['name']})")
    
    if dry_run:
        total_edges = sum(len(members) - 1 for members in constellation_members.values())
        print(f"\n[DRY-RUN] Would create {total_edges:,} constellation membership edges")
        print(f"[DRY-RUN] Edge pattern: All satellites → constellation hub (star topology)")
        return True
    
    print("\n" + "=" * 60)
    print("Step 3: Create Constellation Membership Edges")
    print("=" * 60)
    
    edge_collection = db.collection(db_module.EDGE_COLLECTION_CONSTELLATION)
    
    existing_edge_query = f"RETURN LENGTH({db_module.EDGE_COLLECTION_CONSTELLATION})"
    cursor = db.aql.execute(existing_edge_query)
    existing_edges = list(cursor)[0]
    
    if existing_edges > 0:
        print(f"Found {existing_edges} existing edges. Clearing...")
        edge_collection.truncate()
    
    edges = []
    for const_name, members in constellation_members.items():
        hub = constellation_hubs[const_name]
        hub_id = f"{db_module.COLLECTION_NAME}/{hub['_key']}"
        
        for sat in members:
            if sat['_key'] == hub['_key']:
                continue
            
            sat_id = f"{db_module.COLLECTION_NAME}/{sat['_key']}"
            edges.append({
                "_from": sat_id,
                "_to": hub_id,
                "constellation_name": const_name,
                "relationship": "member_to_hub"
            })
    
    print(f"Creating {len(edges):,} constellation membership edges...")
    
    batch_size = 1000
    total_inserted = 0
    total_errors = 0
    
    for i in range(0, len(edges), batch_size):
        batch = edges[i:i + batch_size]
        results = edge_collection.insert_many(batch, return_new=False)
        
        batch_inserted = sum(1 for r in results if not isinstance(r, Exception))
        batch_errors = sum(1 for r in results if isinstance(r, Exception))
        
        total_inserted += batch_inserted
        total_errors += batch_errors
        
        if (i // batch_size + 1) % 10 == 0 or i + batch_size >= len(edges):
            print(f"  Progress: {total_inserted:,} / {len(edges):,} edges inserted")
    
    print(f"✓ Inserted {total_inserted:,} edges")
    if total_errors > 0:
        print(f"⚠ {total_errors} errors during edge insertion")
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    print(f"✓ Constellation hubs designated: {len(constellation_hubs)}")
    print(f"✓ Edges created: {total_inserted:,}")
    print(f"\nConstellation network is ready!")
    print(f"\nTopology: Star network (all satellites → hub)")
    print(f"Query example: Find all Starlink Gen 1 satellites via hub traversal")
    
    db_module.disconnect_mongodb()
    return True

if __name__ == "__main__":
    import sys
    
    dry_run = "--dry-run" in sys.argv
    success = populate_constellation_network(dry_run=dry_run)
    sys.exit(0 if success else 1)
