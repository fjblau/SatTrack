#!/usr/bin/env python3
"""
Comparison script to validate coordinate transformation accuracy.

Compares three methods:
1. Current implementation (simplified ECI to geodetic)
2. Skyfield library (accurate WGS84 conversion)
3. N2YO API (external reference - optional)

Tests with multiple satellites:
- PRETTY (NORAD 58023) - Low Earth Orbit
- ISS (NORAD 25544) - Low Earth Orbit
- GOES-16 (NORAD 41866) - Geostationary
"""

import math
from datetime import datetime, timezone
from typing import Dict, List, Tuple
import sys

from sgp4.api import Satrec, jday
from skyfield.api import EarthSatellite, load, wgs84
from skyfield.toposlib import GeographicPosition

from api.services.tle_service import fetch_tle_by_norad_id


def current_eci_to_geodetic(x_km: float, y_km: float, z_km: float) -> Dict[str, float]:
    """Current implementation from propagation_service.py"""
    EARTH_RADIUS_KM = 6371.0
    r = math.sqrt(x_km**2 + y_km**2 + z_km**2)
    
    longitude_rad = math.atan2(y_km, x_km)
    latitude_rad = math.asin(z_km / r)
    
    altitude_km = r - EARTH_RADIUS_KM
    
    return {
        'latitude': math.degrees(latitude_rad),
        'longitude': math.degrees(longitude_rad),
        'altitude_km': altitude_km
    }


def skyfield_eci_to_geodetic(x_km: float, y_km: float, z_km: float, dt: datetime, ts) -> Dict[str, float]:
    """Skyfield-based accurate conversion using WGS84 ellipsoid"""
    from skyfield.positionlib import Geocentric
    from skyfield.units import Distance
    import numpy as np
    
    t = ts.from_datetime(dt)
    
    position_km = Distance(km=np.array([x_km, y_km, z_km]))
    velocity_km_s = Distance(km=np.array([0.0, 0.0, 0.0]))
    
    position = Geocentric(position_km.au, velocity_km_s.au, t)
    
    subpoint = wgs84.subpoint(position)
    
    return {
        'latitude': subpoint.latitude.degrees,
        'longitude': subpoint.longitude.degrees,
        'altitude_km': subpoint.elevation.km
    }


def compare_satellite(norad_id: str, satellite_name: str, ts) -> Dict:
    """
    Compare coordinate conversions for a specific satellite.
    
    Returns comparison results with errors.
    """
    print(f"\n{'='*80}")
    print(f"Testing: {satellite_name} (NORAD {norad_id})")
    print(f"{'='*80}")
    
    tle_data = fetch_tle_by_norad_id(norad_id)
    
    if not tle_data:
        print(f"❌ TLE data not found for NORAD ID {norad_id}")
        return None
    
    line1 = tle_data['line1']
    line2 = tle_data['line2']
    
    print(f"\nTLE Data:")
    print(f"  Source: {tle_data.get('source', 'unknown')}")
    print(f"  Date: {tle_data.get('date', 'unknown')}")
    print(f"  Line 1: {line1}")
    print(f"  Line 2: {line2}")
    
    satellite_sgp4 = Satrec.twoline2rv(line1, line2)
    satellite_skyfield = EarthSatellite(line1, line2, satellite_name, ts)
    
    test_time = datetime.now(timezone.utc)
    
    print(f"\nCalculation Time: {test_time.isoformat()}")
    
    jd, fr = jday(test_time.year, test_time.month, test_time.day, 
                   test_time.hour, test_time.minute, test_time.second)
    
    error_code, position, velocity = satellite_sgp4.sgp4(jd, fr)
    
    if error_code != 0:
        print(f"❌ SGP4 error code: {error_code}")
        return None
    
    x_km, y_km, z_km = position
    
    print(f"\nECI Position (km):")
    print(f"  X: {x_km:12.3f}")
    print(f"  Y: {y_km:12.3f}")
    print(f"  Z: {z_km:12.3f}")
    print(f"  R: {math.sqrt(x_km**2 + y_km**2 + z_km**2):12.3f}")
    
    current_geo = current_eci_to_geodetic(x_km, y_km, z_km)
    
    skyfield_geo = skyfield_eci_to_geodetic(x_km, y_km, z_km, test_time, ts)
    
    print(f"\n{'Method':<20} {'Latitude':<15} {'Longitude':<15} {'Altitude (km)':<15}")
    print(f"{'-'*65}")
    print(f"{'Current':<20} {current_geo['latitude']:>14.6f}° {current_geo['longitude']:>14.6f}° {current_geo['altitude_km']:>14.2f}")
    print(f"{'Skyfield (accurate)':<20} {skyfield_geo['latitude']:>14.6f}° {skyfield_geo['longitude']:>14.6f}° {skyfield_geo['altitude_km']:>14.2f}")
    
    lat_error = abs(current_geo['latitude'] - skyfield_geo['latitude'])
    lon_error = abs(current_geo['longitude'] - skyfield_geo['longitude'])
    
    if lon_error > 180:
        lon_error = 360 - lon_error
    
    alt_error = abs(current_geo['altitude_km'] - skyfield_geo['altitude_km'])
    
    print(f"\n{'Error Analysis:':<20} {'Latitude':<15} {'Longitude':<15} {'Altitude (km)':<15}")
    print(f"{'-'*65}")
    print(f"{'Absolute Error':<20} {lat_error:>14.6f}° {lon_error:>14.6f}° {alt_error:>14.2f}")
    
    if lat_error > 0.1:
        print(f"  ⚠️  Latitude error exceeds 0.1° threshold")
    if lon_error > 0.1:
        print(f"  ⚠️  Longitude error exceeds 0.1° threshold")
    if alt_error > 1.0:
        print(f"  ⚠️  Altitude error exceeds 1 km threshold")
    
    return {
        'norad_id': norad_id,
        'name': satellite_name,
        'timestamp': test_time.isoformat(),
        'eci': {
            'x_km': x_km,
            'y_km': y_km,
            'z_km': z_km
        },
        'current': current_geo,
        'skyfield': skyfield_geo,
        'errors': {
            'latitude_deg': lat_error,
            'longitude_deg': lon_error,
            'altitude_km': alt_error
        }
    }


def main():
    """Run comparison tests on multiple satellites"""
    print("="*80)
    print("COORDINATE TRANSFORMATION VALIDATION")
    print("Comparing: Current Implementation vs Skyfield (WGS84)")
    print("="*80)
    
    ts = load.timescale()
    
    test_satellites = [
        ("58023", "PRETTY"),
        ("25544", "ISS (ZARYA)"),
        ("41866", "GOES-16"),
    ]
    
    results = []
    
    for norad_id, name in test_satellites:
        result = compare_satellite(norad_id, name, ts)
        if result:
            results.append(result)
    
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"\n{'Satellite':<20} {'Lat Error (°)':<15} {'Lon Error (°)':<15} {'Alt Error (km)':<15}")
    print(f"{'-'*65}")
    
    for result in results:
        errors = result['errors']
        print(f"{result['name']:<20} {errors['latitude_deg']:>14.6f} {errors['longitude_deg']:>14.6f} {errors['altitude_km']:>14.2f}")
    
    if results:
        avg_lat_error = sum(r['errors']['latitude_deg'] for r in results) / len(results)
        avg_lon_error = sum(r['errors']['longitude_deg'] for r in results) / len(results)
        avg_alt_error = sum(r['errors']['altitude_km'] for r in results) / len(results)
        
        print(f"{'-'*65}")
        print(f"{'Average':<20} {avg_lat_error:>14.6f} {avg_lon_error:>14.6f} {avg_alt_error:>14.2f}")
        
        print(f"\n{'='*80}")
        print("VALIDATION CRITERIA")
        print(f"{'='*80}")
        print(f"  Latitude error < 0.1°:  {'✅ PASS' if avg_lat_error < 0.1 else '❌ FAIL'}")
        print(f"  Longitude error < 0.1°: {'✅ PASS' if avg_lon_error < 0.1 else '❌ FAIL'}")
        print(f"  Altitude error < 1 km:  {'✅ PASS' if avg_alt_error < 1.0 else '❌ FAIL'}")
    
    return results


if __name__ == "__main__":
    try:
        results = main()
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
