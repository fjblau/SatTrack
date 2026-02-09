#!/usr/bin/env python3
"""
Manual validation script to compare our coordinate calculations with N2YO.

This script calculates current positions for test satellites and provides
N2YO links for manual comparison.

Usage:
    python3 manual_validation.py
"""

from datetime import datetime, timezone
from api.services.propagation_service import PropagationService
from api.services.tle_service import fetch_tle_by_norad_id


SATELLITES = [
    {
        'name': 'PRETTY',
        'norad_id': 58023,
        'type': 'LEO',
        'description': 'Low Earth Orbit satellite used in discrepancy screenshot'
    },
    {
        'name': 'ISS',
        'norad_id': 25544,
        'type': 'LEO',
        'description': 'International Space Station'
    },
    {
        'name': 'GOES-16',
        'norad_id': 41866,
        'type': 'GEO',
        'description': 'Geostationary weather satellite'
    }
]


def calculate_position(norad_id: int) -> dict:
    """Calculate current position for a satellite"""
    tle = fetch_tle_by_norad_id(str(norad_id))
    
    if not tle:
        raise ValueError(f"Could not fetch TLE for NORAD {norad_id}")
    
    current_time = datetime.now(timezone.utc)
    
    result = PropagationService.propagate_orbit(
        line1=tle['line1'],
        line2=tle['line2'],
        start_time=current_time,
        interval_minutes=1
    )
    
    return {
        'timestamp': current_time,
        'position': result['current_position']['geodetic'],
        'tle_epoch': result['tle_epoch']
    }


def format_position(position: dict) -> str:
    """Format position for display"""
    return (
        f"  Latitude:  {position['latitude']:>10.6f}°\n"
        f"  Longitude: {position['longitude']:>10.6f}°\n"
        f"  Altitude:  {position['altitude_km']:>10.2f} km"
    )


def main():
    print("=" * 80)
    print("SATELLITE POSITION VALIDATION - Compare with N2YO")
    print("=" * 80)
    print()
    
    for sat in SATELLITES:
        print(f"{sat['name']} (NORAD {sat['norad_id']}) - {sat['description']}")
        print("-" * 80)
        
        try:
            result = calculate_position(sat['norad_id'])
            
            print(f"Timestamp:  {result['timestamp'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"TLE Epoch:  {result['tle_epoch'][:19]}")
            print()
            print("Our Position:")
            print(format_position(result['position']))
            print()
            print(f"Compare with N2YO: https://www.n2yo.com/satellite/?s={sat['norad_id']}")
            print()
            print("Validation Checklist:")
            print("  [ ] Latitude matches N2YO (within ~0.1°)")
            print("  [ ] Longitude matches N2YO (within ~0.1°)")
            print("  [ ] Altitude matches N2YO (within ~1 km)")
            print()
            
        except Exception as e:
            print(f"ERROR: {e}")
            print()
        
        print("=" * 80)
        print()


if __name__ == '__main__':
    main()
