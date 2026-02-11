#!/usr/bin/env python3
"""
Populate satellite lineage network.

Creates edges representing satellite family relationships based on:
- Name patterns (e.g., GPS IIA-1, GPS IIA-2, GPS IIR-1, etc.)
- Launch date proximity within same family
- Manufacturer relationships
- International designator patterns

This enables tracking satellite evolution and family trees.
"""
import sys
import re
from collections import defaultdict
from datetime import datetime
import database as db_module

from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.services.lineage_service import detect_satellite_family, detect_lineage_relationships


def extract_satellite_family(name):
    """
    Extract satellite family name from satellite name.
    
    Examples:
    - "GPS IIA-1" -> "GPS IIA"
    - "Starlink-1234" -> "Starlink"
    - "Iridium 33" -> "Iridium"
    - "COSMOS 2251" -> "COSMOS"
    """
    if not name:
        return None
    
    patterns = [
        (r'^(GPS\s+[A-Z]+)', 'GPS family'),
        (r'^(Starlink)', 'Starlink'),
        (r'^(Iridium)', 'Iridium'),
        (r'^(COSMOS)', 'COSMOS'),
        (r'^(Galileo)', 'Galileo'),
        (r'^(GLONASS)', 'GLONASS'),
        (r'^(BeiDou)', 'BeiDou'),
        (r'^(O3B)', 'O3B'),
        (r'^(OneWeb)', 'OneWeb'),
        (r'^(GOES)', 'GOES'),
        (r'^(Landsat)', 'Landsat'),
        (r'^(Sentinel)', 'Sentinel'),
        (r'^(Planet)', 'Planet'),
        (r'^(Spire)', 'Spire'),
        (r'^([A-Z][A-Za-z]+)\s*[-\s]\d+', 'generic numbered'),
    ]
    
    for pattern, _ in patterns:
        match = re.match(pattern, name, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    words = name.split()
    if len(words) > 0:
        return words[0]
    
    return None


def extract_generation_info(name):
    """
    Extract generation or version info from satellite name.
    
    Examples:
    - "GPS IIA-1" -> "IIA"
    - "Starlink-1234" -> None (no generation marker)
    - "Galileo FOC 3" -> "FOC"
    """
    if not name:
        return None
    
    gen_patterns = [
        r'(I{1,3}[A-Z]*)',
        r'(Block\s+[A-Z0-9]+)',
        r'(Gen\s*\d+)',
        r'(FOC)',
        r'(IOV)',
        r'(M\d*)',
        r'(R\d*)',
    ]
    
    for pattern in gen_patterns:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return None


def populate_satellite_lineage(dry_run=False):
    """Create satellite lineage edges based on family relationships"""
    
    print("=" * 60)
    print("Satellite Lineage Network Population")
    print("=" * 60)
    
    if not db_module.connect_mongodb():
        print("❌ Failed to connect to ArangoDB")
        return False
    
    db = db_module.db
    
    print("\n" + "=" * 60)
    print("Step 1: Extract Satellites and Family Information")
    print("=" * 60)
    
    query = """
    FOR doc IN @@collection
        FILTER doc.canonical.name != null
        SORT doc.canonical.launch_date ASC
        RETURN {
            _key: doc._key,
            identifier: doc.identifier,
            name: doc.canonical.name,
            launch_date: doc.canonical.launch_date,
            manufacturer: doc.canonical.manufacturer,
            owner_country: doc.canonical.owner_country,
            international_designator: doc.canonical.international_designator
        }
    """
    
    cursor = db.aql.execute(
        query,
        bind_vars={'@collection': db_module.COLLECTION_NAME}
    )
    
    satellites = list(cursor)
    print(f"Found {len(satellites):,} satellites")
    
    print("\n" + "=" * 60)
    print("Step 2: Detect Satellite Families and Generations")
    print("=" * 60)
    
    satellites_with_family = []
    for sat in satellites:
        family_info = detect_satellite_family(sat['name'])
        if family_info:
            sat['_id'] = f"{db_module.COLLECTION_NAME}/{sat['_key']}"
            sat['family_name'] = family_info[0]
            sat['variant'] = family_info[1]
            sat['generation'] = family_info[2]
            satellites_with_family.append(sat)
    
    print(f"Identified {len(satellites_with_family)} satellites with family information")
    
    families = defaultdict(list)
    for sat in satellites_with_family:
        families[sat['family_name']].append(sat)
    
    families = {k: v for k, v in families.items() if len(v) >= 2}
    
    print(f"Found {len(families)} satellite families with 2+ members")
    print(f"\nTop 10 largest families:")
    sorted_families = sorted(families.items(), key=lambda x: len(x[1]), reverse=True)
    for family, members in sorted_families[:10]:
        print(f"  {family}: {len(members):,} satellites")
    
    print("\n" + "=" * 60)
    print("Step 3: Create Lineage Edges Using Detection Algorithm")
    print("=" * 60)
    
    all_edges = detect_lineage_relationships(satellites_with_family)
    
    edge_count_by_family = defaultdict(int)
    for edge in all_edges:
        family = edge.get('family_name', 'unknown')
        edge_count_by_family[family] += 1
    
    print(f"Total edges to create: {len(all_edges):,}")
    print(f"\nEdges by family (top 10):")
    sorted_edge_counts = sorted(edge_count_by_family.items(), key=lambda x: x[1], reverse=True)
    for family, count in sorted_edge_counts[:10]:
        print(f"  {family}: {count:,} edges")
    
    relationship_counts = defaultdict(int)
    for edge in all_edges:
        relationship_counts[edge.get('relationship_type', 'unknown')] += 1
    
    print(f"\nRelationship type distribution:")
    for rel_type, count in relationship_counts.items():
        print(f"  {rel_type}: {count:,} edges")
    
    if dry_run:
        print(f"\n[DRY-RUN] Would create {len(all_edges):,} lineage edges")
        
        if len(all_edges) > 0:
            print(f"\nSample successor edges:")
            sample_edges = all_edges[:5]
            for edge in sample_edges:
                print(f"  {edge['_from']} -> {edge['_to']}")
                print(f"    Family: {edge['family_name']}, Gen {edge.get('generation_from', '?')} -> Gen {edge.get('generation_to', '?')}")
        
        return True
    
    print("\n" + "=" * 60)
    print("Step 4: Create Satellite Lineage Edge Collection")
    print("=" * 60)
    
    if not db_module.create_edge_collection(db_module.EDGE_COLLECTION_SATELLITE_LINEAGE):
        print("❌ Failed to create satellite lineage edge collection")
        return False
    
    edge_collection = db.collection(db_module.EDGE_COLLECTION_SATELLITE_LINEAGE)
    
    existing_edge_query = f"RETURN LENGTH({db_module.EDGE_COLLECTION_SATELLITE_LINEAGE})"
    cursor = db.aql.execute(existing_edge_query)
    existing_edges = list(cursor)[0]
    
    if existing_edges > 0:
        print(f"Found {existing_edges:,} existing edges. Clearing...")
        edge_collection.truncate()
    
    print(f"Inserting {len(all_edges):,} lineage edges...")
    
    batch_size = 1000
    total_inserted = 0
    total_errors = 0
    
    for i in range(0, len(all_edges), batch_size):
        batch = all_edges[i:i + batch_size]
        results = edge_collection.insert_many(batch, return_new=False)
        
        batch_inserted = sum(1 for r in results if not isinstance(r, Exception))
        batch_errors = sum(1 for r in results if isinstance(r, Exception))
        
        total_inserted += batch_inserted
        total_errors += batch_errors
        
        if (i // batch_size + 1) % 10 == 0 or i + batch_size >= len(all_edges):
            print(f"  Progress: {total_inserted:,} / {len(all_edges):,} edges inserted")
    
    print(f"✓ Inserted {total_inserted:,} edges")
    if total_errors > 0:
        print(f"⚠ {total_errors} errors during edge insertion")
    
    print("\n" + "=" * 60)
    print("Step 5: Add Edge Indexes")
    print("=" * 60)
    
    db_module.add_edge_indexes(db_module.EDGE_COLLECTION_SATELLITE_LINEAGE)
    
    edge_collection.add_persistent_index(fields=['family_name'], unique=False)
    print("✓ Added family_name index")
    
    edge_collection.add_persistent_index(fields=['relationship_type'], unique=False)
    print("✓ Added relationship_type index")
    
    edge_collection.add_persistent_index(fields=['generation_from'], unique=False, sparse=True)
    print("✓ Added generation_from index")
    
    edge_collection.add_persistent_index(fields=['generation_to'], unique=False, sparse=True)
    print("✓ Added generation_to index")
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    print(f"✓ Total lineage edges created: {total_inserted:,}")
    print(f"✓ Families with lineage: {len(families)}")
    print(f"✓ Successor relationships: {relationship_counts.get('successor', 0):,}")
    print(f"\nSatellite lineage network is ready!")
    print(f"\nYou can now query satellite families and evolution via:")
    print(f"  - GET /v2/graphs/lineage/{{satellite_id}}")
    print(f"  - GET /v2/graphs/lineage/family/{{family_name}}")
    
    db_module.disconnect_mongodb()
    return True


if __name__ == "__main__":
    import sys
    
    dry_run = "--dry-run" in sys.argv
    
    success = populate_satellite_lineage(dry_run=dry_run)
    sys.exit(0 if success else 1)
