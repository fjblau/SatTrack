import pandas as pd
import os
from datetime import datetime

def add_sample_data(csv_path):
    """Add more sample UNOOSA data to the registry."""
    
    additional_data = [
        {"Registration Number": "3818-2025-016", "Object Name": "Euclid", "Launch Vehicle": "Ariane 5", "Place of Launch": "Kourou", "Date of Launch": "2023-07-01", "Apogee (km)": 1200000, "Perigee (km)": 1200000, "Inclination (degrees)": 0.1, "Period (minutes)": 3600, "Function": "Astrophysics/Astronomy", "Country of Origin": "European Space Agency"},
        {"Registration Number": "3819-2025-017", "Object Name": "TESS", "Launch Vehicle": "Falcon 9", "Place of Launch": "Cape Canaveral", "Date of Launch": "2018-04-18", "Apogee (km)": 373000, "Perigee (km)": 373000, "Inclination (degrees)": 0.0, "Period (minutes)": 30.0, "Function": "Astronomical observation", "Country of Origin": "United States of America"},
        {"Registration Number": "3820-2025-018", "Object Name": "JWST", "Launch Vehicle": "Ariane 5", "Place of Launch": "Kourou", "Date of Launch": "2021-12-25", "Apogee (km)": 1500000, "Perigee (km)": 1500000, "Inclination (degrees)": 0.0, "Period (minutes)": 5940.0, "Function": "Astronomical observation", "Country of Origin": "United States of America"},
        {"Registration Number": "3821-2025-019", "Object Name": "Aqua", "Launch Vehicle": "Delta II", "Place of Launch": "Vandenberg Space Force Base", "Date of Launch": "2002-05-04", "Apogee (km)": 705, "Perigee (km)": 705, "Inclination (degrees)": 98.2, "Period (minutes)": 99.0, "Function": "Earth observation", "Country of Origin": "United States of America"},
        {"Registration Number": "3822-2025-020", "Object Name": "Terra", "Launch Vehicle": "Atlas IIAS", "Place of Launch": "Vandenberg Space Force Base", "Date of Launch": "1999-12-18", "Apogee (km)": 705, "Perigee (km)": 705, "Inclination (degrees)": 98.2, "Period (minutes)": 99.0, "Function": "Earth observation", "Country of Origin": "United States of America"},
    ]
    
    df_additional = pd.DataFrame(additional_data)
    
    if os.path.exists(csv_path):
        df_existing = pd.read_csv(csv_path)
        df_combined = pd.concat([df_existing, df_additional], ignore_index=True)
        df_combined = df_combined.drop_duplicates(subset=['Registration Number'], keep='first')
    else:
        df_combined = df_additional
    
    df_combined.to_csv(csv_path, index=False)
    print(f"✓ Updated registry with {len(df_additional)} new records")
    print(f"✓ Total records in registry: {len(df_combined)}")

if __name__ == "__main__":
    csv_path = os.path.join(os.path.dirname(__file__), "unoosa_registry.csv")
    add_sample_data(csv_path)
    print("\nTo view the data, run: streamlit run unoosa_app.py")
