#!/usr/bin/env python3

from pymongo import MongoClient

target = MongoClient('mongodb://localhost:27019')
target_col = target['kessler']['satellites']

target_with_tle = target_col.count_documents({'canonical.tle.line1': {'$exists': True, '$ne': None}})
target_total = target_col.count_documents({})

print(f'Total satellites: {target_total}')
print(f'Satellites with TLE data: {target_with_tle}')

sample = target_col.find_one({'canonical.tle.line1': {'$exists': True}})
if sample:
    print(f'\nSample satellite: {sample.get("identifier")}')
    tle = sample.get('canonical', {}).get('tle', {})
    print(f'TLE Line 1: {tle.get("line1", "N/A")[:50]}...')
    print(f'TLE updated: {tle.get("updated_at", "N/A")}')
    print(f'Sources: {list(sample.get("sources", {}).keys())}')
    
sources_with_tle = target_col.count_documents({'sources.spacetrack.tle_line1': {'$exists': True}})
print(f'\nSatellites with spacetrack TLE source: {sources_with_tle}')
