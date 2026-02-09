#!/usr/bin/env python3
"""
Simple verification script to test Skyfield installation and basic functionality.
"""

from skyfield.api import load, wgs84, EarthSatellite
from datetime import datetime, timezone
import sys


def test_skyfield_installation():
    """Test basic Skyfield functionality"""
    print("="*60)
    print("SKYFIELD INSTALLATION VERIFICATION")
    print("="*60)
    
    print("\n1. Loading timescale...")
    try:
        ts = load.timescale()
        print("   ✅ Timescale loaded successfully")
    except Exception as e:
        print(f"   ❌ Failed to load timescale: {e}")
        return False
    
    print("\n2. Creating time object...")
    try:
        t = ts.now()
        print(f"   ✅ Current time: {t.utc_datetime()}")
    except Exception as e:
        print(f"   ❌ Failed to create time: {e}")
        return False
    
    print("\n3. Testing WGS84 ellipsoid...")
    try:
        location = wgs84.latlon(40.7128, -74.0060)
        print(f"   ✅ Created location: {location}")
    except Exception as e:
        print(f"   ❌ Failed to create WGS84 location: {e}")
        return False
    
    print("\n4. Testing TLE satellite creation...")
    try:
        line1 = "1 25544U 98067A   08264.51782528 -.00002182  00000-0 -11606-4 0  2927"
        line2 = "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.72125391563537"
        
        satellite = EarthSatellite(line1, line2, "ISS (TEST)", ts)
        print(f"   ✅ Created satellite: {satellite.name}")
    except Exception as e:
        print(f"   ❌ Failed to create satellite: {e}")
        return False
    
    print("\n5. Testing satellite position calculation...")
    try:
        geocentric = satellite.at(t)
        print(f"   ✅ Geocentric position calculated")
        
        subpoint = wgs84.subpoint(geocentric)
        print(f"   ✅ Subpoint: lat={subpoint.latitude.degrees:.2f}°, lon={subpoint.longitude.degrees:.2f}°, alt={subpoint.elevation.km:.2f} km")
    except Exception as e:
        print(f"   ❌ Failed to calculate position: {e}")
        return False
    
    print("\n" + "="*60)
    print("✅ ALL TESTS PASSED - Skyfield is working correctly!")
    print("="*60)
    
    return True


if __name__ == "__main__":
    try:
        success = test_skyfield_installation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
