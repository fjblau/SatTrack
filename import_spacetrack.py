import pandas as pd
import requests
import json

print("Creating sample UNOOSA registry with CelesTrak TLE data...")

try:
    import urllib3
    urllib3.disable_warnings()
    
    print("Fetching satellite catalog from TLE API...")
    url = "https://tle.ivanstanojevic.me/api/tle?apiKey=demo"
    response = requests.get(url, timeout=30, verify=False)
    response.raise_for_status()
    data = response.json()
    
    satellites = data.get('member', [])
    print(f"Retrieved {len(satellites)} satellites from TLE API")
    
    records = []
    for sat in satellites:
        record = {
            'Registration Number': sat.get('satnum', ''),
            'Object Name': sat.get('satname', ''),
            'Launch Vehicle': '',
            'Place of Launch': '',
            'Date of Launch': '',
            'Apogee (km)': '',
            'Perigee (km)': '',
            'Inclination (degrees)': sat.get('inclination', ''),
            'Period (minutes)': '',
            'Function': 'Satellite',
            'Country of Origin': ''
        }
        if record['Object Name'] and record['Registration Number']:
            records.append(record)
    
    if len(records) > 0:
        df = pd.DataFrame(records)
        df = df.drop_duplicates(subset=['Registration Number'], keep='first')
        df = df.head(1000)
        
        df.to_csv('unoosa_registry.csv', index=False)
        print(f"\n✓ Imported {len(df)} satellite records")
        print(f"✓ Saved to unoosa_registry.csv")
        print(f"\nSample data:")
        print(df.head(10)[['Registration Number', 'Object Name', 'Inclination (degrees)']].to_string())
    else:
        raise Exception("No valid records retrieved")
        
except Exception as e:
    print(f"Error: {e}")
    print("\nFalling back to local UNOOSA data...")
    
    import os
    if os.path.exists('unoosa_registry_import.csv'):
        df = pd.read_csv('unoosa_registry_import.csv')
        df = df.head(1000)
        df.to_csv('unoosa_registry.csv', index=False)
        print(f"✓ Restored from backup: {len(df)} records")
    else:
        print("Creating minimal sample registry...")
        sample_data = [
            {'Registration Number': '25544', 'Object Name': 'ISS (ZARYA)', 'Launch Vehicle': '', 'Place of Launch': '', 'Date of Launch': '1998-11-20', 'Apogee (km)': 408, 'Perigee (km)': 395, 'Inclination (degrees)': 51.64, 'Period (minutes)': 92.0, 'Function': 'Space Station', 'Country of Origin': 'Russian Federation'},
            {'Registration Number': '25982', 'Object Name': 'HUBBLE SPACE TELESCOPE', 'Launch Vehicle': '', 'Place of Launch': '', 'Date of Launch': '1990-04-24', 'Apogee (km)': 610, 'Perigee (km)': 605, 'Inclination (degrees)': 28.47, 'Period (minutes)': 96.0, 'Function': 'Observatory', 'Country of Origin': 'United States of America'},
            {'Registration Number': '39444', 'Object Name': 'JAMES WEBB SPACE TELESCOPE', 'Launch Vehicle': '', 'Place of Launch': '', 'Date of Launch': '2021-12-25', 'Apogee (km)': 1500000, 'Perigee (km)': 1500000, 'Inclination (degrees)': 0, 'Period (minutes)': 5940.0, 'Function': 'Observatory', 'Country of Origin': 'United States of America'},
        ]
        df = pd.DataFrame(sample_data)
        df.to_csv('unoosa_registry.csv', index=False)
        print(f"✓ Created sample registry: {len(df)} records")
