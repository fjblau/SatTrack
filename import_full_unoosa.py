import pandas as pd
import os

print("Importing complete UNOOSA data with registration documents...")

input_file = "United Nations_Outer Space Objects Index_Retrieved 12.10.2025 by laurenainsleyhaines.csv"

df = pd.read_csv(input_file, on_bad_lines='skip')

print(f"Total records: {len(df)}")

records = []
for idx, row in df.iterrows():
    record = {
        'Registration Number': row.get('National Designator', ''),
        'International Designator': row.get('International Designator', ''),
        'Object Name': row.get('Name of Space Object', ''),
        'Country of Origin': row.get('State/Organization', ''),
        'Date of Launch': row.get('Date of Launch', ''),
        'Function': row.get('Function of Space Object', ''),
        'Status': row.get('Status', ''),
        'Registration Document': row.get('Registration Document', ''),
        'UN Registered': row.get('UN Registered', ''),
        'GSO Location': row.get('GSO Location', ''),
        'Date of Decay or Change': row.get('Date of Decay or Change', ''),
        'Secretariat Remarks': row.get('Secretariat`s Remarks', ''),
        'External Website': row.get('External website', ''),
        'Launch Vehicle': '',
        'Place of Launch': '',
        'Apogee (km)': '',
        'Perigee (km)': '',
        'Inclination (degrees)': '',
        'Period (minutes)': '',
    }
    if record['Registration Number'] and record['Object Name']:
        records.append(record)

df_final = pd.DataFrame(records)
df_final = df_final.drop_duplicates(subset=['Registration Number'], keep='first')

output_file = 'unoosa_registry.csv'
df_final.to_csv(output_file, index=False)

print(f"\n✓ Imported {len(df_final)} space objects with complete metadata")
print(f"✓ Saved to {output_file}")
print(f"\nColumns available:")
for col in df_final.columns:
    print(f"  - {col}")
print(f"\nSample record:")
print(df_final.iloc[0])
