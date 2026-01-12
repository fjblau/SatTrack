#!/usr/bin/env python3

from pymongo import MongoClient

target = MongoClient('mongodb://localhost:27019')
target_col = target['kessler']['satellites']

sample = target_col.find_one({'sources.spacetrack': {'$exists': True}})
if sample:
    print(f'Sample satellite: {sample.get("identifier")}')
    print(f'\nCanonical TLE:')
    tle = sample.get('canonical', {}).get('tle', {})
    for key, value in tle.items():
        if isinstance(value, str) and len(value) > 60:
            print(f'  {key}: {value[:60]}...')
        else:
            print(f'  {key}: {value}')
    
    print(f'\nSpacetrack source:')
    spacetrack = sample.get('sources', {}).get('spacetrack', {})
    for key, value in spacetrack.items():
        if isinstance(value, str) and len(value) > 60:
            print(f'  {key}: {value[:60]}...')
        else:
            print(f'  {key}: {value}')
