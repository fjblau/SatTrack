#!/usr/bin/env python3
"""
Populate collision risk network.

Creates edges between satellites with collision risk based on:
- Same orbital band
- Close orbital parameters (apogee, perigee, inclination)
- Calculates risk score based on proximity
- Includes timestamp for temporal analysis

This network enables analysis of potential collision scenarios.
"""
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import database as db_module

APOGEE_RISK_THRESHOLD_KM = 20
PERIGEE_RISK_THRESHOLD_KM = 20
INCLINATION_RISK_THRESHOLD_DEG = 2
MIN_RISK_SCORE = 0.3
MAX_EDGES_PER_SATELLITE = 20


def calculate_collision_risk_score(sat1, sat2):
    """
    Calculate collision risk score based on orbital parameter proximity.
    
    Higher score = higher collision risk (0-1 range).
    Based on inverse of orbital differences.
    """
    apogee_diff = abs(sat1['apogee_km'] - sat2['apogee_km'])
    perigee_diff = abs(sat1['perigee_km'] - sat2['perigee_km'])
    inclination_diff = abs(sat1['inclination_degrees'] - sat2['inclination_degrees'])
    
    apogee_score = max(0, 1 - (apogee_diff / APOGEE_RISK_THRESHOLD_KM))
    perigee_score = max(0, 1 - (perigee_diff / PERIGEE_RISK_THRESHOLD_KM))
    inclination_score = max(0, 1 - (inclination_diff / INCLINATION_RISK_THRESHOLD_DEG))
    
    risk_score = (apogee_score + perigee_score + inclination_score) / 3
    
    return round(risk_score, 4)


def populate_collision_risks(dry_run=False, orbital_band_filter=None):
    """Create collision risk edges between satellites"""
    
    print("=" * 60)
    print("Collision Risk Network Population")
    print("=" * 60)
    
    if not db_module.connect_mongodb():
        print("❌ Failed to connect to ArangoDB")
        return False
    
    db = db_module.db
    
    print(f"\nRisk Thresholds:")
    print(f"  Apogee: ±{APOGEE_RISK_THRESHOLD_KM} km")
    print(f"  Perigee: ±{PERIGEE_RISK_THRESHOLD_KM} km")
    print(f"  Inclination: ±{INCLINATION_RISK_THRESHOLD_DEG}°")
    print(f"  Minimum risk score: {MIN_RISK_SCORE}")
    print(f"  Max edges per satellite: {MAX_EDGES_PER_SATELLITE}")
    if orbital_band_filter:
        print(f"  Orbital band filter: {orbital_band_filter}")
    
    print("\n" + "=" * 60)
    print("Step 1: Extract Active Satellites with Orbital Data")
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
        FILTER doc.canonical.status IN ["Active", "Unknown"]
        {filter_clause}
        SORT doc.identifier ASC
        RETURN {{
            _key: doc._key,
            identifier: doc.identifier,
            name: doc.canonical.name,
            orbital_band: doc.canonical.orbital_band,
            apogee_km: doc.canonical.orbit.apogee_km,
            perigee_km: doc.canonical.orbit.perigee_km,
            inclination_degrees: doc.canonical.orbit.inclination_degrees,
            launch_date: doc.canonical.launch_date
        }}
    """
    
    cursor = db.aql.execute(
        query,
        bind_vars={'@collection': db_module.COLLECTION_NAME}
    )
    
    satellites = list(cursor)
    print(f"Found {len(satellites):,} active satellites with complete orbital data")
    
    satellites_by_band = defaultdict(list)
    for sat in satellites:
        satellites_by_band[sat['orbital_band']].append(sat)
    
    print(f"\nSatellites by orbital band:")
    for band in sorted(satellites_by_band.keys()):
        count = len(satellites_by_band[band])
        print(f"  {band}: {count:,} satellites")
    
    print("\n" + "=" * 60)
    print("Step 2: Calculate Collision Risk Edges")
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
                
                if (apogee_diff <= APOGEE_RISK_THRESHOLD_KM and
                    perigee_diff <= PERIGEE_RISK_THRESHOLD_KM and
                    inclination_diff <= INCLINATION_RISK_THRESHOLD_DEG):
                    
                    risk_score = calculate_collision_risk_score(sat1, sat2)
                    
                    if risk_score >= MIN_RISK_SCORE:
                        satellite_edges[sat1['_key']].append({
                            'target': sat2['_key'],
                            'risk_score': risk_score,
                            'apogee_diff': apogee_diff,
                            'perigee_diff': perigee_diff,
                            'inclination_diff': inclination_diff
                        })
                        
                        satellite_edges[sat2['_key']].append({
                            'target': sat1['_key'],
                            'risk_score': risk_score,
                            'apogee_diff': apogee_diff,
                            'perigee_diff': perigee_diff,
                            'inclination_diff': inclination_diff
                        })
        
        for sat_key, edges in satellite_edges.items():
            edges.sort(key=lambda x: x['risk_score'], reverse=True)
            top_edges = edges[:MAX_EDGES_PER_SATELLITE]
            
            for edge in top_edges:
                all_edges.append({
                    '_from': f"{db_module.COLLECTION_NAME}/{sat_key}",
                    '_to': f"{db_module.COLLECTION_NAME}/{edge['target']}",
                    'orbital_band': band,
                    'risk_score': edge['risk_score'],
                    'apogee_diff_km': round(edge['apogee_diff'], 2),
                    'perigee_diff_km': round(edge['perigee_diff'], 2),
                    'inclination_diff_degrees': round(edge['inclination_diff'], 2),
                    'risk_level': 'high' if edge['risk_score'] >= 0.8 else 'medium' if edge['risk_score'] >= 0.5 else 'low'
                })
                edge_count_by_band[band] += 1
        
        print(f"  Created {edge_count_by_band[band]:,} collision risk edges for {band}")
    
    print(f"\nTotal edges to create: {len(all_edges):,}")
    print(f"\nEdges by orbital band:")
    for band in sorted(edge_count_by_band.keys()):
        print(f"  {band}: {edge_count_by_band[band]:,} edges")
    
    risk_level_counts = defaultdict(int)
    for edge in all_edges:
        risk_level_counts[edge['risk_level']] += 1
    
    print(f"\nRisk level distribution:")
    for level in ['high', 'medium', 'low']:
        if level in risk_level_counts:
            print(f"  {level}: {risk_level_counts[level]:,} edges")
    
    if dry_run:
        print(f"\n[DRY-RUN] Would create {len(all_edges):,} collision risk edges")
        
        if len(all_edges) > 0:
            print(f"\nSample high-risk edges:")
            high_risk = [e for e in all_edges if e['risk_level'] == 'high'][:5]
            for edge in high_risk:
                print(f"  {edge['_from']} <-> {edge['_to']}")
                print(f"    Risk score: {edge['risk_score']} ({edge['risk_level']})")
                print(f"    Differences: apogee={edge['apogee_diff_km']}km, perigee={edge['perigee_diff_km']}km, incl={edge['inclination_diff_degrees']}°")
        
        return True
    
    print("\n" + "=" * 60)
    print("Step 3: Create Collision Risk Edge Collection")
    print("=" * 60)
    
    if not db_module.create_edge_collection(db_module.EDGE_COLLECTION_COLLISION_RISK):
        print("❌ Failed to create collision risk edge collection")
        return False
    
    edge_collection = db.collection(db_module.EDGE_COLLECTION_COLLISION_RISK)
    
    existing_edge_query = f"RETURN LENGTH({db_module.EDGE_COLLECTION_COLLISION_RISK})"
    cursor = db.aql.execute(existing_edge_query)
    existing_edges = list(cursor)[0]
    
    if existing_edges > 0:
        print(f"Found {existing_edges:,} existing edges. Clearing...")
        edge_collection.truncate()
    
    print(f"Inserting {len(all_edges):,} collision risk edges...")
    
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
    print("Step 4: Add Edge Indexes")
    print("=" * 60)
    
    db_module.add_edge_indexes(db_module.EDGE_COLLECTION_COLLISION_RISK)
    
    edge_collection.add_persistent_index(fields=['risk_score'], unique=False)
    print("✓ Added risk_score index")
    
    edge_collection.add_persistent_index(fields=['risk_level'], unique=False)
    print("✓ Added risk_level index")
    
    edge_collection.add_persistent_index(fields=['orbital_band'], unique=False)
    print("✓ Added orbital_band index")
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    print(f"✓ Total collision risk edges created: {total_inserted:,}")
    print(f"✓ Risk levels: high={risk_level_counts.get('high', 0):,}, medium={risk_level_counts.get('medium', 0):,}, low={risk_level_counts.get('low', 0):,}")
    print(f"\nCollision risk network is ready!")
    print(f"\nYou can now query collision risks via graph traversal")
    
    db_module.disconnect_mongodb()
    return True


if __name__ == "__main__":
    import sys
    
    dry_run = "--dry-run" in sys.argv
    
    orbital_band = None
    for arg in sys.argv:
        if arg.startswith("--band="):
            orbital_band = arg.split("=")[1]
    
    success = populate_collision_risks(dry_run=dry_run, orbital_band_filter=orbital_band)
    sys.exit(0 if success else 1)
