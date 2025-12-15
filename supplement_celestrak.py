import pandas as pd
import requests
import re
import math
import time

print("Supplementing orbital parameters with CelesTrak TLE data...")

df = pd.read_csv("unoosa_registry.csv")

# Get records with International Designators
records_with_designator = df[df['International Designator'].notna() & (df['International Designator'] != '')]
print(f"\nRecords with International Designator: {len(records_with_designator)}/{len(df)}")

# Fetch TLE data from CelesTrak
print("\nFetching TLE data from CelesTrak...")

try:
    # CelesTrak provides TLE data in text format
    # Format: https://celestrak.com/NORAD/elements/active.txt (or other categories)
    
    tle_urls = [
        "https://celestrak.org/NORAD/elements/stations.txt",
        "https://celestrak.org/NORAD/elements/resource.txt",
        "https://celestrak.org/NORAD/elements/sarsat.txt",
        "https://celestrak.org/NORAD/elements/dmc.txt",
        "https://celestrak.org/NORAD/elements/tdrss.txt",
        "https://celestrak.org/NORAD/elements/weather.txt",
        "https://celestrak.org/NORAD/elements/landsat.txt",
        "https://celestrak.org/NORAD/elements/iridium.txt",
        "https://celestrak.org/NORAD/elements/geo.txt",
        "https://celestrak.org/NORAD/elements/military.txt",
        "https://celestrak.org/NORAD/elements/imaging.txt",
        "https://celestrak.org/NORAD/elements/other-comm.txt",
        "https://celestrak.org/NORAD/elements/iss.txt",
    ]
    
    # Dictionary to store TLE by International Designator
    tle_dict = {}
    
    for tle_url in tle_urls:
        print(f"  Fetching {tle_url.split('/')[-1]}...", end=" ")
        try:
            response = requests.get(tle_url, timeout=10)
            if response.status_code == 200:
                lines = response.text.split('\n')
                
                # Parse TLE format:
                # Line 0: Satellite name
                # Line 1: TLE line 1
                # Line 2: TLE line 2
                
                i = 0
                while i < len(lines) - 2:
                    sat_name = lines[i].strip()
                    tle_line1 = lines[i + 1].strip()
                    tle_line2 = lines[i + 2].strip()
                    
                    # Extract International Designator from TLE line 1
                    # Format: 1 ZZZZZU ZZZZZZZZ ZZZZZZZ ...
                    # Position 9-17: YYNCCCL (Year, Julian day, ID number)
                    # Actually, we need to match by satellite name or extract from TLE
                    
                    # TLE line 1 format: 1 SSSSSU ZZZZZ ZZZZZZZ Z ZZZZZZZZZZZZZZZZ ZZZZZZZZZZZZZZZZ Z Z
                    # Positions: [25:32] is International Designator (YYYYNNNL format)
                    
                    if tle_line1.startswith('1 ') and len(tle_line1) >= 69:
                        try:
                            intl_desig = tle_line1[9:17].strip()  # International Designator
                            tle_dict[intl_desig] = (sat_name, tle_line1, tle_line2)
                        except:
                            pass
                    
                    i += 3
                
                print(f"✓ ({len([k for k in tle_dict.keys()])}) unique designators")
            else:
                print(f"HTTP {response.status_code}")
        except Exception as e:
            print(f"Error: {str(e)[:50]}")
        
        time.sleep(0.5)
    
    print(f"\nTotal TLE records: {len(tle_dict)}")

except Exception as e:
    print(f"Error fetching TLE data: {str(e)}")
    tle_dict = {}

# Function to calculate orbital parameters from TLE
def calculate_orbital_params_from_tle(tle_line1, tle_line2):
    """
    Calculate orbital parameters from TLE data
    """
    
    try:
        # Extract key parameters from TLE line 2
        # Position [8:16]: Inclination (degrees)
        # Position [26:33]: Eccentricity (0.XXXXXXX format)
        # Position [52:63]: Mean Motion (revolutions per day)
        
        inclination = float(tle_line2[8:16])  # degrees
        eccentricity = float('0.' + tle_line2[26:33])  # dimensionless
        mean_motion_rev_day = float(tle_line2[52:63])  # revolutions per day
        
        # Calculate orbital period
        period_minutes = 1440.0 / mean_motion_rev_day
        
        # Calculate semi-major axis using Kepler's third law
        # For TLE mean motion: a = ((GM / (2π * n_rad)^2)^(1/3)
        # Where n_rad is in radians per second
        # Simplified: a_km = 6.6293e3 * ((1440 / mean_motion_rev_day)^(2/3))
        # But we'll use the more direct formula
        
        GM = 398600.4418  # Earth's standard gravitational parameter (km^3/s^2)
        
        # Convert mean motion from revolutions per day to radians per second
        # 1 revolution = 2π radians
        # 1 day = 86400 seconds
        n_rad_per_sec = (mean_motion_rev_day * 2 * math.pi) / 86400.0
        
        # Kepler's third law: a = (GM / n^2)^(1/3)
        a = (GM / (n_rad_per_sec * n_rad_per_sec)) ** (1.0/3.0)  # Semi-major axis in km
        
        # Calculate apogee and perigee (altitude above Earth's surface)
        earth_radius = 6378.137  # km (WGS84 mean radius)
        
        apogee = a * (1 + eccentricity) - earth_radius
        perigee = a * (1 - eccentricity) - earth_radius
        
        return {
            'Apogee (km)': round(apogee, 2),
            'Perigee (km)': round(perigee, 2),
            'Inclination (degrees)': round(inclination, 2),
            'Period (minutes)': round(period_minutes, 2)
        }
    except Exception as e:
        return None

# Function to convert registry designator to NORAD format
def convert_to_norad_format(designator):
    """
    Convert YYYY-NNNSSS format (e.g., 2025-206B) to YYNNNSSG format (e.g., 25206B)
    """
    try:
        # Handle format: YYYY-NNNSSS or YYYY-NNN-P or YYYY-NNN
        parts = designator.split('-')
        if len(parts) >= 2:
            year = parts[0]
            rest = '-'.join(parts[1:])
            
            # Get last 2 digits of year
            yy = year[-2:]
            
            # Extract sequence and piece
            # Format could be: "206B", "206-B", or just "180"
            if '-' in rest:
                seq, piece = rest.split('-')
            else:
                # Check if last character is a letter
                if rest[-1].isalpha():
                    seq = rest[:-1]
                    piece = rest[-1]
                else:
                    # No piece letter, assume primary payload
                    seq = rest
                    piece = ""
            
            if piece:
                norad_format = f"{yy}{int(seq):0>3}{piece}"
            else:
                # No piece - try both with and without suffix
                norad_format = f"{yy}{int(seq):0>3}"
            
            return norad_format
    except Exception as e:
        pass
    
    return None

# Match and update records
updated_count = 0
matched_count = 0

print("\nMatching designators and calculating orbital parameters...")

for idx, row in df.iterrows():
    intl_designator = str(row['International Designator']).strip() if pd.notna(row['International Designator']) else ""
    
    if not intl_designator or intl_designator == "":
        continue
    
    # Try converting to NORAD format and matching
    norad_format = convert_to_norad_format(intl_designator)
    found_tle = None
    
    if norad_format:
        # Try exact match
        if norad_format in tle_dict:
            found_tle = tle_dict[norad_format]
        # If no piece letter, try matching with common piece letters (A-H)
        elif not norad_format[-1].isalpha():
            for piece in 'ABCDEFGH':
                candidate = norad_format + piece
                if candidate in tle_dict:
                    found_tle = tle_dict[candidate]
                    break
    
    # Try exact match as well
    if not found_tle and intl_designator in tle_dict:
        found_tle = tle_dict[intl_designator]
    
    if found_tle:
        sat_name, tle_line1, tle_line2 = found_tle
        params = calculate_orbital_params_from_tle(tle_line1, tle_line2)
        
        if params:
            # Only update if we don't already have values
            if pd.isna(df.at[idx, 'Apogee (km)']):
                df.at[idx, 'Apogee (km)'] = params['Apogee (km)']
                df.at[idx, 'Perigee (km)'] = params['Perigee (km)']
                df.at[idx, 'Inclination (degrees)'] = params['Inclination (degrees)']
                df.at[idx, 'Period (minutes)'] = params['Period (minutes)']
                updated_count += 1
            
            matched_count += 1

print(f"\n{'='*60}")
print(f"✓ Matched: {matched_count} International Designators")
print(f"✓ Updated: {updated_count} records with orbital parameters")

# Save updated registry
df.to_csv("unoosa_registry.csv", index=False)
print(f"✓ Saved to unoosa_registry.csv")

# Summary statistics
print(f"\nOrbital Parameter Coverage:")
for col in ['Apogee (km)', 'Perigee (km)', 'Inclination (degrees)', 'Period (minutes)']:
    count = df[col].notna().sum()
    pct = 100 * count / len(df)
    print(f"  {col}: {count}/{len(df)} ({pct:.1f}%)")
