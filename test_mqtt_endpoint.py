import sys
sys.path.insert(0, '.')

from database import get_mqtt_configuration, find_satellite

# Test with the satellite ID from the error
satellite_id = "satellites/2018-040E"
intl_desig = satellite_id.split('/')[-1]

print(f"Testing with satellite_id: {satellite_id}")
print(f"Extracted intl_desig: {intl_desig}")

# Test 1: Check if config exists
config = get_mqtt_configuration(satellite_id)
print(f"\n1. MQTT Config lookup: {'FOUND' if config else 'NOT FOUND'}")
if config:
    print(f"   Config _key: {config.get('_key')}")
    print(f"   Config satellite_id: {config.get('satellite_id')}")

# Test 2: Check if satellite exists
satellite = find_satellite(international_designator=intl_desig)
print(f"\n2. Satellite lookup: {'FOUND' if satellite else 'NOT FOUND'}")
if satellite:
    print(f"   Satellite _id: {satellite.get('_id')}")
    canonical = satellite.get('canonical', {})
    print(f"   International Designator: {canonical.get('international_designator')}")
    print(f"   NORAD ID: {canonical.get('norad_cat_id')}")
