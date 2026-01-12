#!/usr/bin/env python3
"""
Promote orbital parameters from Kaggle source to canonical fields.

Kaggle has:
- inclination (degrees)
- altitude_km (single value - average altitude)
- eccentricity
- mean_motion (rev/day)

We need to calculate and promote to canonical.orbit:
- inclination_degrees (direct copy)
- apogee_km (calculate from altitude + eccentricity)
- perigee_km (calculate from altitude + eccentricity)
- period_minutes (calculate from mean_motion)

Note: altitude_km in Kaggle is average altitude, so:
- semi_major_axis = altitude_km + Earth_radius (6378.137 km)
- apogee = semi_major_axis * (1 + ecc) - Earth_radius
- perigee = semi_major_axis * (1 - ecc) - Earth_radius
"""
import sys
import math
from datetime import datetime, timezone
import db as db_module

EARTH_RADIUS_KM = 6378.137

def calculate_apogee_perigee(altitude_km, eccentricity):
    """
    Calculate apogee and perigee from average altitude and eccentricity.
    
    Args:
        altitude_km: Average altitude above Earth's surface
        eccentricity: Orbital eccentricity
    
    Returns:
        tuple: (apogee_km, perigee_km)
    """
    if altitude_km is None or eccentricity is None:
        return None, None
    
    # Semi-major axis = altitude + Earth radius
    semi_major_axis = altitude_km + EARTH_RADIUS_KM
    
    # Calculate apogee and perigee
    apogee = semi_major_axis * (1 + eccentricity) - EARTH_RADIUS_KM
    perigee = semi_major_axis * (1 - eccentricity) - EARTH_RADIUS_KM
    
    return round(apogee, 2), round(perigee, 2)

def calculate_period(mean_motion_rev_day):
    """
    Calculate orbital period in minutes from mean motion.
    
    Args:
        mean_motion_rev_day: Mean motion in revolutions per day
    
    Returns:
        float: Period in minutes
    """
    if mean_motion_rev_day is None or mean_motion_rev_day <= 0:
        return None
    
    period_minutes = 1440.0 / mean_motion_rev_day  # 1440 minutes in a day
    return round(period_minutes, 2)

def promote_kaggle_orbital(dry_run=False):
    """Promote Kaggle orbital parameters to canonical.orbit"""
    
    if not db_module.connect_mongodb():
        print("Failed to connect to ArangoDB")
        return False
    
    # Access db after connection is established
    db = db_module.db
    COLLECTION_NAME = db_module.COLLECTION_NAME
    
    try:
        # Count satellites with Kaggle orbital data but missing canonical orbit data
        count_query = """
        FOR doc IN @@collection
            FILTER doc.sources.kaggle.altitude_km != null
            FILTER doc.sources.kaggle.inclination != null
            FILTER (
                doc.canonical.orbit.apogee_km == null OR
                doc.canonical.orbit.perigee_km == null OR
                doc.canonical.orbit.inclination_degrees == null
            )
            COLLECT WITH COUNT INTO count
            RETURN count
        """
        
        cursor = db.aql.execute(
            count_query,
            bind_vars={'@collection': COLLECTION_NAME}
        )
        total_count = list(cursor)[0]
        
        print(f"\n=== Kaggle Orbital Parameters Promotion ===")
        print(f"Found {total_count:,} satellites with Kaggle orbital data missing from canonical")
        
        if total_count == 0:
            print("No satellites to process.")
            return True
        
        # Sample a few to show what will be promoted
        sample_query = """
        FOR doc IN @@collection
            FILTER doc.sources.kaggle.altitude_km != null
            FILTER doc.sources.kaggle.inclination != null
            FILTER (
                doc.canonical.orbit.apogee_km == null OR
                doc.canonical.orbit.perigee_km == null OR
                doc.canonical.orbit.inclination_degrees == null
            )
            LIMIT 5
            RETURN {
                identifier: doc.identifier,
                kaggle_altitude: doc.sources.kaggle.altitude_km,
                kaggle_inclination: doc.sources.kaggle.inclination,
                kaggle_eccentricity: doc.sources.kaggle.eccentricity,
                kaggle_mean_motion: doc.sources.kaggle.mean_motion,
                current_orbit: doc.canonical.orbit
            }
        """
        
        cursor = db.aql.execute(
            sample_query,
            bind_vars={'@collection': COLLECTION_NAME}
        )
        samples = list(cursor)
        
        print("\nSample documents:")
        for s in samples:
            apogee, perigee = calculate_apogee_perigee(
                s.get('kaggle_altitude'),
                s.get('kaggle_eccentricity')
            )
            period = calculate_period(s.get('kaggle_mean_motion'))
            
            print(f"  {s['identifier']}:")
            print(f"    Kaggle: alt={s.get('kaggle_altitude'):.2f}km, inc={s.get('kaggle_inclination'):.2f}°, ecc={s.get('kaggle_eccentricity')}")
            print(f"    → Calculated: apogee={apogee}km, perigee={perigee}km, period={period}min")
            current = s.get('current_orbit', {})
            if current:
                print(f"    Current canonical: apogee={current.get('apogee_km')}, perigee={current.get('perigee_km')}, inc={current.get('inclination_degrees')}")
        
        if dry_run:
            print(f"\n[DRY-RUN] Would promote Kaggle orbital parameters for {total_count:,} satellites")
            return True
        
        # Confirm
        response = input(f"\nProceed with promoting orbital parameters for {total_count:,} satellites? (y/N): ").strip().lower()
        if response not in ['y', 'yes']:
            print("Operation cancelled")
            return False
        
        # Perform the promotion using AQL UPDATE
        update_query = """
        FOR doc IN @@collection
            FILTER doc.sources.kaggle.altitude_km != null
            FILTER doc.sources.kaggle.inclination != null
            FILTER (
                doc.canonical.orbit.apogee_km == null OR
                doc.canonical.orbit.perigee_km == null OR
                doc.canonical.orbit.inclination_degrees == null
            )
            
            LET altitude_km = doc.sources.kaggle.altitude_km
            LET eccentricity = doc.sources.kaggle.eccentricity || 0
            LET mean_motion = doc.sources.kaggle.mean_motion
            LET inclination = doc.sources.kaggle.inclination
            
            LET semi_major_axis = altitude_km + @earth_radius
            LET apogee = semi_major_axis * (1 + eccentricity) - @earth_radius
            LET perigee = semi_major_axis * (1 - eccentricity) - @earth_radius
            LET period = mean_motion > 0 ? 1440.0 / mean_motion : null
            
            LET transformations = [
                {
                    timestamp: @timestamp,
                    source_field: "sources.kaggle.inclination",
                    target_field: "canonical.orbit.inclination_degrees",
                    value: inclination,
                    promoted_by: "promote_kaggle_orbital_script"
                },
                {
                    timestamp: @timestamp,
                    source_field: "sources.kaggle.altitude_km+eccentricity",
                    target_field: "canonical.orbit.apogee_km",
                    value: apogee,
                    promoted_by: "promote_kaggle_orbital_script",
                    reason: "Calculated from altitude_km and eccentricity"
                },
                {
                    timestamp: @timestamp,
                    source_field: "sources.kaggle.altitude_km+eccentricity",
                    target_field: "canonical.orbit.perigee_km",
                    value: perigee,
                    promoted_by: "promote_kaggle_orbital_script",
                    reason: "Calculated from altitude_km and eccentricity"
                },
                period != null ? {
                    timestamp: @timestamp,
                    source_field: "sources.kaggle.mean_motion",
                    target_field: "canonical.orbit.period_minutes",
                    value: period,
                    promoted_by: "promote_kaggle_orbital_script",
                    reason: "Calculated from mean_motion"
                } : null
            ]
            
            UPDATE doc WITH {
                canonical: MERGE(doc.canonical, {
                    orbit: MERGE(doc.canonical.orbit || {}, {
                        inclination_degrees: doc.canonical.orbit.inclination_degrees || ROUND(inclination * 100) / 100,
                        apogee_km: doc.canonical.orbit.apogee_km || ROUND(apogee * 100) / 100,
                        perigee_km: doc.canonical.orbit.perigee_km || ROUND(perigee * 100) / 100,
                        period_minutes: doc.canonical.orbit.period_minutes || (period != null ? ROUND(period * 100) / 100 : null)
                    })
                }),
                metadata: MERGE(doc.metadata, {
                    transformations: APPEND(
                        doc.metadata.transformations || [],
                        transformations[* FILTER CURRENT != null]
                    ),
                    last_updated_at: @timestamp
                })
            } IN @@collection
            
            COLLECT WITH COUNT INTO updated
            RETURN updated
        """
        
        timestamp = datetime.now(timezone.utc).isoformat()
        
        print(f"\nUpdating {total_count:,} documents...")
        cursor = db.aql.execute(
            update_query,
            bind_vars={
                '@collection': COLLECTION_NAME,
                'timestamp': timestamp,
                'earth_radius': EARTH_RADIUS_KM
            }
        )
        
        updated = list(cursor)[0]
        
        print(f"✓ Successfully promoted orbital parameters for {updated:,} satellites")
        
        # Verify
        verify_query = """
        FOR doc IN @@collection
            FILTER doc.canonical.orbit.apogee_km != null
            FILTER doc.canonical.orbit.perigee_km != null
            COLLECT WITH COUNT INTO count
            RETURN count
        """
        
        cursor = db.aql.execute(
            verify_query,
            bind_vars={'@collection': COLLECTION_NAME}
        )
        verified = list(cursor)[0]
        
        print(f"✓ Verification: {verified:,} satellites now have complete orbital parameters")
        
        # Show coverage improvement
        total_sats_query = """
        FOR doc IN @@collection
            COLLECT WITH COUNT INTO count
            RETURN count
        """
        cursor = db.aql.execute(total_sats_query, bind_vars={'@collection': COLLECTION_NAME})
        total_sats = list(cursor)[0]
        
        coverage_pct = (verified / total_sats) * 100
        print(f"✓ Orbital parameter coverage: {coverage_pct:.1f}% ({verified:,}/{total_sats:,})")
        
        return True
        
    except Exception as e:
        print(f"Error during promotion: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db_module.disconnect_mongodb()

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    success = promote_kaggle_orbital(dry_run=dry_run)
    sys.exit(0 if success else 1)
