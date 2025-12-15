import pandas as pd
import requests
import json
import os

print("Attempting to fetch UCS Satellite Database...")

try:
    print("Method 1: UCS Satellite Database...")
    
    ucs_url = "https://www.ucsusa.org/sites/default/files/attach/2024/02/UCS_Satellite_Database.csv"
    response = requests.get(ucs_url, timeout=30)
    response.raise_for_status()
    
    from io import StringIO
    df = pd.read_csv(StringIO(response.text))
    
    print(f"Retrieved {len(df)} satellites from UCS database")
    
    records = []
    for idx, row in df.iterrows():
        record = {
            'Registration Number': str(row.get('NORAD Number', '')).strip() if pd.notna(row.get('NORAD Number')) else '',
            'Object Name': str(row.get('Satellite Name', '')).strip() if pd.notna(row.get('Satellite Name')) else '',
            'Launch Vehicle': str(row.get('Launch Vehicle', '')).strip() if pd.notna(row.get('Launch Vehicle')) else '',
            'Place of Launch': str(row.get('Country of Operator', '')).strip() if pd.notna(row.get('Country of Operator')) else '',
            'Date of Launch': str(row.get('Date of Launch', '')).strip() if pd.notna(row.get('Date of Launch')) else '',
            'Apogee (km)': row.get('Apogee (km)', ''),
            'Perigee (km)': row.get('Perigee (km)', ''),
            'Inclination (degrees)': row.get('Inclination (degrees)', ''),
            'Period (minutes)': row.get('Period (minutes)', ''),
            'Function': str(row.get('Class of Orbit', '')).strip() if pd.notna(row.get('Class of Orbit')) else '',
            'Country of Origin': str(row.get('Country of Operator', '')).strip() if pd.notna(row.get('Country of Operator')) else ''
        }
        if record['Object Name'] and record['Registration Number']:
            records.append(record)
    
    if len(records) > 0:
        df_final = pd.DataFrame(records)
        df_final = df_final.drop_duplicates(subset=['Registration Number'], keep='first')
        df_final.to_csv('unoosa_registry.csv', index=False)
        
        print(f"\n✓ Successfully imported {len(df_final)} satellite records from UCS Database")
        print(f"✓ Saved to unoosa_registry.csv")
        print(f"\nSample data:")
        print(df_final.head(10)[['Registration Number', 'Object Name', 'Country of Origin']].to_string())
    else:
        raise Exception("No valid records found")

except Exception as e:
    print(f"Method 1 failed: {e}\n")
    print("Falling back to local UNOOSA data...")
    
    if os.path.exists('unoosa_registry_import.csv'):
        df = pd.read_csv('unoosa_registry_import.csv')
        df = df.drop_duplicates(subset=['Registration Number'], keep='first')
        df.to_csv('unoosa_registry.csv', index=False)
        print(f"✓ Restored {len(df)} records from UNOOSA backup")
    else:
        print("No backup found. Please provide data file.")
