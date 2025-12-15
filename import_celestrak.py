import pandas as pd
import requests
import json

print("Fetching satellite data from CelesTrak...")

try:
    url = "https://celestrak.org/NORAD/elements/stations.json"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    satellites = response.json()
    
    print(f"Retrieved {len(satellites)} satellites from CelesTrak")
    
    records = []
    for sat in satellites:
        record = {
            'Registration Number': sat.get('NORAD_CAT_ID', sat.get('CATNR', '')),
            'Object Name': sat.get('SATNAME', ''),
            'Launch Vehicle': '',
            'Place of Launch': '',
            'Date of Launch': sat.get('LAUNCH_DATE', ''),
            'Apogee (km)': sat.get('APOGEE', ''),
            'Perigee (km)': sat.get('PERIGEE', ''),
            'Inclination (degrees)': sat.get('INCLINATION', ''),
            'Period (minutes)': sat.get('PERIOD', ''),
            'Function': sat.get('OBJECT_TYPE', ''),
            'Country of Origin': sat.get('COUNTRY', '')
        }
        if record['Object Name'] and record['Registration Number']:
            records.append(record)
    
    df = pd.DataFrame(records)
    
    df = df.drop_duplicates(subset=['Registration Number'], keep='first')
    
    df.to_csv('unoosa_registry.csv', index=False)
    
    print(f"\n✓ Imported {len(df)} satellite records from CelesTrak")
    print(f"✓ Saved to unoosa_registry.csv")
    print(f"\nData preview:")
    print(df.head(10)[['Registration Number', 'Object Name', 'Country of Origin', 'Apogee (km)', 'Perigee (km)']].to_string())
    
except requests.exceptions.RequestException as e:
    print(f"Error fetching CelesTrak data: {e}")
    print("\nTrying alternative endpoint (active satellites)...")
    
    try:
        url = "https://celestrak.org/NORAD/elements/active.json"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        satellites = response.json()
        
        print(f"Retrieved {len(satellites)} satellites")
        
        records = []
        for sat in satellites:
            record = {
                'Registration Number': sat.get('NORAD_CAT_ID', sat.get('CATNR', '')),
                'Object Name': sat.get('SATNAME', ''),
                'Launch Vehicle': '',
                'Place of Launch': '',
                'Date of Launch': sat.get('LAUNCH_DATE', ''),
                'Apogee (km)': sat.get('APOGEE', ''),
                'Perigee (km)': sat.get('PERIGEE', ''),
                'Inclination (degrees)': sat.get('INCLINATION', ''),
                'Period (minutes)': sat.get('PERIOD', ''),
                'Function': sat.get('OBJECT_TYPE', ''),
                'Country of Origin': sat.get('COUNTRY', '')
            }
            if record['Object Name'] and record['Registration Number']:
                records.append(record)
        
        df = pd.DataFrame(records)
        df = df.drop_duplicates(subset=['Registration Number'], keep='first')
        df.to_csv('unoosa_registry.csv', index=False)
        
        print(f"✓ Imported {len(df)} satellite records")
        print(f"✓ Saved to unoosa_registry.csv")
        
    except Exception as e2:
        print(f"Alternative endpoint also failed: {e2}")
