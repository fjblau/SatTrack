#!/usr/bin/env python3
"""
Populate orbital proximity network.

Creates edges between satellites with similar orbital parameters:
- Same orbital band
- Apogee within ±50km
- Perigee within ±50km
- Inclination within ±5 degrees

Limits to top N closest satellites per node to keep graph manageable.
"""
import sys
from collections import defaultdict
import db as db_module

APOGEE_THRESHOLD_KM = 50
PERIGEE_THRESHOLD_KM = 50
INCLINATION_THRESHOLD_DEG = 5
MAX_EDGES_PER_SATELLITE = 10

def calculate_proximity_score(sat1, sat2):
    """
    Calculate proximity score based on orbital parameter similarity.
    Lower score = more similar (closer proximity).
    """
    apogee_diff = abs(sat1['apogee_km'] - sat2['apogee_km'])
    perigee_diff = abs(sat1['perigee_km'] - sat2['perigee_km'])
    inclination_diff = abs(sat1['inclination_degrees'] - sat2['inclination_degrees'])
    
    score = (
        (apogee_diff / APOGEE_THRESHOLD_KM) ** 2 +
        (perigee_diff / PERIGEE_THRESHOLD_KM) ** 2 +
        (inclination_diff / INCLINATION_THRESHOLD_DEG) ** 2
    )
    
    return score

def populate_orbital_proximity(dry_run=False, orbital_band_filter=None):
    """Create orbital proximity edges"""
    
    print("=" * 60)
    print("Orbital Proximity Network Population")
    print("=" * 60)
    
    if not db_module.connect_mongodb():
        print("❌ Failed to connect to ArangoDB")
        return False
    
    db = db_module.db
    
    print(f"\nThresholds:")
    print(f"  Apogee: ±{APOGEE_THRESHOLD_KM} km")
    print(f"  Perigee: ±{PERIGEE_THRESHOLD_KM} km")
    print(f"  Inclination: ±{INCLINATION_THRESHOLD_DEG}°")
    print(f"  Max edges per satellite: {MAX_EDGES_PER_SATELLITE}")
    if orbital_band_filter:
        print(f"  Orbital band filter: {orbital_band_filter}")
    
    print("\n" + "=" * 60)
    print("Step 1: Extract Satellites with Orbital Data")
    print("=" * 60)
    
    filter_clause = ""
    if orbital_band_filter:
        filter_clause = f"FILTER doc.canonical.orbital_band == '{orbital_band_filter}'"
    
    query = f"""
    FOR doc IN @@collection
        FILTER doc.canonical.orbit.apogee_km != null
        FILTER doc.canonical.orbit.perigee_km != null
        FILTER doc.canonical.orbit.inclination_degrees != null
        FILTER doc.canonical.orbital_band != null
        {filter_clause}
        SORT doc.identifier ASC
        RETURN {{
            _key: doc._key,
            identifier: doc.identifier,
            name: doc.canonical.name,
            orbital_band: doc.canonical.orbital_band,
            apogee_km: doc.canonical.orbit.apogee_km,
            perigee_km: doc.canonical.orbit.perigee_km,
            inclination_degrees: doc.canonical.orbit.inclination_degrees
        }}
    """
    
    cursor = db.aql.execute(
        query,
        bind_vars={'@collection': db_module.COLLECTION_NAME}
    )
    
    satellites = list(cursor)
    print(f"Found {len(satellites):,} satellites with complete orbital data")
    
    satellites_by_band = defaultdict(list)
    for sat in satellites:
        satellites_by_band[sat['orbital_band']].append(sat)
    
    print(f"\nSatellites by orbital band:")
    for band in sorted(satellites_by_band.keys()):
        count = len(satellites_by_band[band])
        print(f"  {band}: {count:,} satellites")
    
    print("\n" + "=" * 60)
    print("Step 2: Calculate Proximity Edges")
    print("=" * 60)
    
    all_edges = []
    edge_count_by_band = defaultdict(int)
    
    for band, band_satellites in satellites_by_band.items():
        print(f"\nProcessing {band} ({len(band_satellites):,} satellites)...")
        
        satellite_edges = defaultdict(list)
        
        for i, sat1 in enumerate(band_satellites):
            if (i + 1) % 500 == 0:
                print(f"  Progress: {i + 1:,} / {len(band_satellites):,}")
            
            for sat2 in band_satellites[i + 1:]:
                apogee_diff = abs(sat1['apogee_km'] - sat2['apogee_km'])
                perigee_diff = abs(sat1['perigee_km'] - sat2['perigee_km'])
                inclination_diff = abs(sat1['inclination_degrees'] - sat2['inclination_degrees'])
                
                if (apogee_diff <= APOGEE_THRESHOLD_KM and
                    perigee_diff <= PERIGEE_THRESHOLD_KM and
                    inclination_diff <= INCLINATION_THRESHOLD_DEG):
                    
                    score = calculate_proximity_score(sat1, sat2)
                    
                    satellite_edges[sat1['_key']].append({
                        'target': sat2['_key'],
                        'score': score,
                        'apogee_diff': apogee_diff,
                        'perigee_diff': perigee_diff,
                        'inclination_diff': inclination_diff
                    })
                    
                    satellite_edges[sat2['_key']].append({
                        'target': sat1['_key'],
                        'score': score,
                        'apogee_diff': apogee_diff,
                        'perigee_diff': perigee_diff,
                        'inclination_diff': inclination_diff
                    })
        
        for sat_key, edges in satellite_edges.items():
            edges.sort(key=lambda x: x['score'])
            top_edges = edges[:MAX_EDGES_PER_SATELLITE]
            
            for edge in top_edges:
                all_edges.append({
                    '_from': f"{db_module.COLLECTION_NAME}/{sat_key}",
                    '_to': f"{db_module.COLLECTION_NAME}/{edge['target']}",
                    'orbital_band': band,
                    'proximity_score': round(edge['score'], 4),
                    'apogee_diff_km': round(edge['apogee_diff'], 2),
                    'perigee_diff_km': round(edge['perigee_diff'], 2),
                    'inclination_diff_degrees': round(edge['inclination_diff'], 2)
                })
                edge_count_by_band[band] += 1
        
        print(f"  Created {edge_count_by_band[band]:,} edges for {band}")
    
    print(f"\nTotal edges to create: {len(all_edges):,}")
    print(f"\nEdges by orbital band:")
    for band in sorted(edge_count_by_band.keys()):
        print(f"  {band}: {edge_count_by_band[band]:,} edges")
    
    if dry_run:
        print(f"\n[DRY-RUN] Would create {len(all_edges):,} proximity edges")
        
        if len(all_edges) > 0:
            print(f"\nSample edges:")
            for edge in all_edges[:5]:
                print(f"  {edge['_from']} -> {edge['_to']}")
                print(f"    Proximity score: {edge['proximity_score']}")
                print(f"    Differences: apogee={edge['apogee_diff_km']}km, perigee={edge['perigee_diff_km']}km, incl={edge['inclination_diff_degrees']}°")
        
        return True
    
    print("\n" + "=" * 60)
    print("Step 3: Populate Orbital Proximity Edges")
    print("=" * 60)
    
    edge_collection = db.collection(db_module.EDGE_COLLECTION_PROXIMITY)
    
    existing_edge_query = f"RETURN LENGTH({db_module.EDGE_COLLECTION_PROXIMITY})"
    cursor = db.aql.execute(existing_edge_query)
    existing_edges = list(cursor)[0]
    
    if existing_edges > 0:
        print(f"Found {existing_edges:,} existing edges. Clearing...")
        edge_collection.truncate()
    
    print(f"Inserting {len(all_edges):,} proximity edges...")
    
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
    print("Summary")
    print("=" * 60)
    
    print(f"✓ Total proximity edges created: {total_inserted:,}")
    print(f"\nOrbital proximity network is ready!")
    print(f"\nYou can now query proximity relationships via graph traversal")
    
    db_module.disconnect_mongodb()
    return True

if __name__ == "__main__":
    import sys
    
    dry_run = "--dry-run" in sys.argv
    
    orbital_band = None
    for arg in sys.argv:
        if arg.startswith("--band="):
            orbital_band = arg.split("=")[1]
    
    success = populate_orbital_proximity(dry_run=dry_run, orbital_band_filter=orbital_band)
    sys.exit(0 if success else 1)
