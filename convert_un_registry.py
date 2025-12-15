import pandas as pd
import os
import sys

input_file = "United Nations_Outer Space Objects Index_Retrieved 12.10.2025 by laurenainsleyhaines.csv"
output_file = "unoosa_registry_import.csv"

print(f"Reading {input_file}...")

df = pd.read_csv(input_file, on_bad_lines='skip')

print(f"Total rows: {len(df)}")
print(f"Columns: {list(df.columns)}")

subset = df[[
    'National Designator',
    'Name of Space Object', 
    'State/Organization',
    'Date of Launch',
    'Function of Space Object'
]].copy()

subset.columns = [
    'Registration Number',
    'Object Name',
    'Country of Origin',
    'Date of Launch',
    'Function'
]

subset['Launch Vehicle'] = ''
subset['Place of Launch'] = ''
subset['Apogee (km)'] = ''
subset['Perigee (km)'] = ''
subset['Inclination (degrees)'] = ''
subset['Period (minutes)'] = ''

subset = subset[
    ['Registration Number', 'Object Name', 'Launch Vehicle', 'Place of Launch',
     'Date of Launch', 'Apogee (km)', 'Perigee (km)', 'Inclination (degrees)',
     'Period (minutes)', 'Function', 'Country of Origin']
]

subset = subset.drop_duplicates(subset='Registration Number', keep='first')

subset = subset[subset['Registration Number'].notna() & (subset['Registration Number'] != '')]

print(f"Unique records after dedup: {len(subset)}")

subset.to_csv(output_file, index=False)

print(f"\n✓ Converted to {output_file}")
print(f"✓ {len(subset)} records ready for import")
print("\nUpload this file in the Streamlit app sidebar to add all records.")
