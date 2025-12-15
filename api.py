from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
from typing import Optional, List, Dict
import json
from datetime import datetime, timezone
import math
import requests
import time
import re
from bs4 import BeautifulSoup
import pdfplumber
import io

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

df = pd.read_csv("unoosa_registry.csv")

norad_id_map = {
    "2023-155H": "58023",
}

tle_cache = {}
tle_cache_time = {}
CACHE_TTL = 3600


def fetch_tle_data():
    """Fetch TLE data from CelesTrak with caching"""
    global tle_cache, tle_cache_time
    current_time = time.time()
    
    if tle_cache and all(current_time - tle_cache_time.get(cat, 0) < CACHE_TTL for cat in tle_cache):
        return tle_cache
    
    tle_urls = [
        "https://celestrak.org/NORAD/elements/stations.txt",
        "https://celestrak.org/NORAD/elements/resource.txt",
        "https://celestrak.org/NORAD/elements/sarsat.txt",
        "https://celestrak.org/NORAD/elements/dmc.txt",
        "https://celestrak.org/NORAD/elements/weather.txt",
        "https://celestrak.org/NORAD/elements/geo.txt",
        "https://celestrak.org/NORAD/elements/iss.txt",
    ]
    
    for tle_url in tle_urls:
        try:
            response = requests.get(tle_url, timeout=5)
            if response.status_code == 200:
                lines = response.text.split('\n')
                i = 0
                while i < len(lines) - 2:
                    sat_name = lines[i].strip()
                    tle_line1 = lines[i + 1].strip()
                    tle_line2 = lines[i + 2].strip()
                    
                    if tle_line1.startswith('1 ') and len(tle_line1) >= 69:
                        try:
                            intl_desig = tle_line1[9:17].strip()
                            tle_cache[intl_desig] = (sat_name, tle_line1, tle_line2)
                            tle_cache_time[intl_desig] = current_time
                        except:
                            pass
                    i += 3
        except Exception as e:
            print(f"Error fetching {tle_url}: {e}")
    
    return tle_cache


def convert_to_norad_format(designator):
    """Convert YYYY-NNNSSS format to YYNNNSSG format"""
    try:
        parts = designator.split('-')
        if len(parts) >= 2:
            year = parts[0]
            rest = '-'.join(parts[1:])
            yy = year[-2:]
            
            if '-' in rest:
                seq, piece = rest.split('-')
            else:
                if rest[-1].isalpha():
                    seq = rest[:-1]
                    piece = rest[-1]
                else:
                    seq = rest
                    piece = ""
            
            if piece:
                return f"{yy}{int(seq):0>3}{piece}"
            else:
                return f"{yy}{int(seq):0>3}"
    except:
        pass
    return None


def calculate_orbital_state(tle_line1: str, tle_line2: str, timestamp: datetime = None) -> Dict:
    """
    Calculate orbital state from TLE
    Returns: position (lat/lon/alt), velocity, and orbital parameters
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    
    try:
        inclination = float(tle_line2[8:16])
        eccentricity = float('0.' + tle_line2[26:33])
        mean_motion_rev_day = float(tle_line2[52:63])
        
        period_minutes = 1440.0 / mean_motion_rev_day
        
        GM = 398600.4418
        n_rad_per_sec = (mean_motion_rev_day * 2 * math.pi) / 86400.0
        a = (GM / (n_rad_per_sec * n_rad_per_sec)) ** (1.0/3.0)
        
        earth_radius = 6378.137
        apogee = a * (1 + eccentricity) - earth_radius
        perigee = a * (1 - eccentricity) - earth_radius
        
        return {
            'apogee_km': round(apogee, 2),
            'perigee_km': round(perigee, 2),
            'inclination_degrees': round(inclination, 2),
            'period_minutes': round(period_minutes, 2),
            'semi_major_axis_km': round(a, 2),
            'eccentricity': round(eccentricity, 6),
            'mean_motion_rev_day': round(mean_motion_rev_day, 6),
            'timestamp': timestamp.isoformat(),
            'data_source': 'TLE (CelesTrak)'
        }
    except Exception as e:
        return {'error': str(e)}


orbital_state_cache = {}
orbital_state_cache_time = {}

doc_link_cache = {}
doc_link_cache_time = {}

doc_metadata_cache = {}
doc_metadata_cache_time = {}


def extract_document_metadata(url: str) -> Optional[Dict]:
    """
    Extract structured metadata from a registration document PDF.
    Handles direct PDF URLs. UN documents API URLs are not directly processable by pdfplumber.
    """
    actual_url = url
    
    if 'daccess-ods.un.org' in url:
        return None
    
    try:
        response = requests.get(actual_url, timeout=15)
        if response.status_code != 200:
            return None
        
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            if len(pdf.pages) == 0:
                return None
            
            text = ""
            for page in pdf.pages[:5]:
                text += page.extract_text() or ""
            
            metadata = {}
            
            owner_match = re.search(r'Space object owner or operator[:;]?\s+([^\n]+?)(?:\n|$)', text, re.IGNORECASE)
            if owner_match:
                owner = owner_match.group(1).strip()
                if owner and len(owner) < 200 and owner.lower() not in ['website', 'launch vehicle', 'place of launch']:
                    metadata['owner_operator'] = owner
            
            website_match = re.search(r'Website[:;]?\s+(https?://[^\s\n]+|www\.[^\s\n/]+(?:/[^\s\n]*)?)', text, re.IGNORECASE)
            if website_match:
                website = website_match.group(1).strip()
                if website and len(website) < 300:
                    metadata['website'] = website
            
            launch_vehicle_match = re.search(r'Launch vehicle[:;]?\s+([^\n]+?)(?:\n|$)', text, re.IGNORECASE)
            if launch_vehicle_match:
                vehicle = launch_vehicle_match.group(1).strip()
                if vehicle and len(vehicle) < 150 and vehicle.lower() not in ['website', 'owner', 'operator']:
                    metadata['launch_vehicle'] = vehicle
            
            place_match = re.search(r'Place of launch[:;]?\s+([^\n]+?)(?:\n|$)', text, re.IGNORECASE)
            if place_match:
                place = place_match.group(1).strip()
                if place and len(place) < 150:
                    metadata['place_of_launch'] = place
            
            nodal_period_match = re.search(r'Nodal period[:;]?\s+([\d.]+)\s*minutes?', text, re.IGNORECASE)
            if nodal_period_match:
                period = nodal_period_match.group(1).strip()
                if period:
                    metadata['nodal_period_minutes'] = period
            
            inclination_match = re.search(r'Inclination[:;]?\s+([\d.]+)\s*degrees?', text, re.IGNORECASE)
            if inclination_match:
                incl = inclination_match.group(1).strip()
                if incl:
                    metadata['inclination_degrees'] = incl
            
            apogee_match = re.search(r'Apogee[:;]?\s+([\d.]+)\s*(?:km|kilometres)', text, re.IGNORECASE)
            if apogee_match:
                apogee = apogee_match.group(1).strip()
                if apogee:
                    metadata['apogee_km'] = apogee
            
            perigee_match = re.search(r'Perigee[:;]?\s+([\d.]+)\s*(?:km|kilometres)', text, re.IGNORECASE)
            if perigee_match:
                perigee = perigee_match.group(1).strip()
                if perigee:
                    metadata['perigee_km'] = perigee
            
            return metadata if metadata else None
    except Exception as e:
        return None


def fetch_english_doc_link(registry_doc_path: str) -> Optional[str]:
    """
    Fetch the actual English document link from UNOOSA registry page.
    Registry URLs often point to HTML pages that have links to PDFs.
    Also tries to correct common document ID errors.
    """
    if not registry_doc_path:
        return None
    
    current_time = time.time()
    cache_key = f"doc_{registry_doc_path}"
    
    if cache_key in doc_link_cache:
        cache_age = current_time - doc_link_cache_time.get(cache_key, 0)
        if cache_age < CACHE_TTL:
            return doc_link_cache[cache_key]
    
    def try_fetch(path: str) -> Optional[str]:
        try:
            url = f"https://www.unoosa.org{path}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 404:
                url_with_oosa = f"https://www.unoosa.org/oosa{path}"
                response = requests.get(url_with_oosa, timeout=5)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                all_links = soup.find_all('a', href=True)
                
                for link in all_links:
                    href = link.get('href', '')
                    link_text = link.get_text(strip=True).lower()
                    
                    if link_text == 'english':
                        full_url = href if href.startswith('http') else (f"https://www.unoosa.org{href}" if href.startswith('/') else href)
                        
                        if 'daccess-ods.un.org' in full_url:
                            pdf_url = convert_un_doc_to_pdf_url(full_url)
                            if pdf_url:
                                return pdf_url
                        
                        return full_url
                    
                    if ('documents.un.org' in href or 'undoc' in href or 'daccess-ods.un.org' in href) and ('Lang=E' in href or 'English' in href):
                        full_url = href if href.startswith('http') else (f"https://www.unoosa.org{href}" if href.startswith('/') else href)
                        
                        if 'daccess-ods.un.org' in full_url:
                            pdf_url = convert_un_doc_to_pdf_url(full_url)
                            if pdf_url:
                                return pdf_url
                        
                        return full_url
            
            return None
        except Exception as e:
            return None
    
    result = try_fetch(registry_doc_path)
    if result:
        doc_link_cache[cache_key] = result
        doc_link_cache_time[cache_key] = current_time
        return result
    
    match = re.search(r'stsgser\.e(\d{4})', registry_doc_path)
    if match:
        doc_id = int(match.group(1))
        
        pdf_path = f'/res/osoindex/data/documents/at/st/stsgser_e{doc_id:04d}_html/sere_{doc_id:04d}E.pdf'
        pdf_url = f"https://www.unoosa.org{pdf_path}"
        try:
            response = requests.head(pdf_url, timeout=5)
            if response.status_code == 200:
                doc_link_cache[cache_key] = pdf_url
                doc_link_cache_time[cache_key] = current_time
                return pdf_url
        except:
            pass
        
        for offset in [-10, -8, -6, -4, -2, -1, 1, 2, 4, 6, 8, 10]:
            corrected_id = doc_id + offset
            corrected_path = registry_doc_path.replace(f'stsgser.e{doc_id:04d}', f'stsgser.e{corrected_id:04d}')
            result = try_fetch(corrected_path)
            if result:
                doc_link_cache[cache_key] = result
                doc_link_cache_time[cache_key] = current_time
                return result
            
            pdf_path = f'/res/osoindex/data/documents/at/st/stsgser_e{corrected_id:04d}_html/sere_{corrected_id:04d}E.pdf'
            pdf_url = f"https://www.unoosa.org{pdf_path}"
            try:
                response = requests.head(pdf_url, timeout=5)
                if response.status_code == 200:
                    doc_link_cache[cache_key] = pdf_url
                    doc_link_cache_time[cache_key] = current_time
                    return pdf_url
            except:
                pass
    
    doc_link_cache[cache_key] = None
    doc_link_cache_time[cache_key] = current_time
    return None



@app.get("/api/documents/resolve")
def resolve_document_link(path: str) -> Dict:
    """
    Resolve a registry document path to the actual accessible document link.
    Handles the common issue where registry paths point to Russian pages
    with English links hidden.
    """
    if not path:
        return {"error": "No path provided", "original_path": path}
    
    english_link = fetch_english_doc_link(path)
    
    return {
        "original_path": path,
        "original_url": f"https://www.unoosa.org{path}",
        "english_link": english_link,
        "found": english_link is not None
    }


@app.get("/api/documents/metadata")
def get_document_metadata(url: str) -> Dict:
    """
    Extract and return metadata from a registration document PDF.
    Caches results to avoid repeated PDF processing.
    """
    if not url:
        return {"error": "No URL provided"}
    
    current_time = time.time()
    cache_key = url
    
    if cache_key in doc_metadata_cache:
        cache_age = current_time - doc_metadata_cache_time.get(cache_key, 0)
        if cache_age < CACHE_TTL:
            result = doc_metadata_cache[cache_key]
            result['cached'] = True
            return result
    
    metadata = extract_document_metadata(url)
    
    result = {
        "url": url,
        "metadata": metadata,
        "found": metadata is not None,
        "cached": False
    }
    
    doc_metadata_cache[cache_key] = result
    doc_metadata_cache_time[cache_key] = current_time
    
    return result


@app.get("/api/objects")
def get_objects(
    search: Optional[str] = None,
    country: Optional[str] = None,
    function: Optional[str] = None,
    apogee_min: Optional[float] = None,
    apogee_max: Optional[float] = None,
    perigee_min: Optional[float] = None,
    perigee_max: Optional[float] = None,
    inclination_min: Optional[float] = None,
    inclination_max: Optional[float] = None,
    skip: int = 0,
    limit: int = 100,
):
    result = df.copy()
    
    print(f"DEBUG: country={country}, function={function}, search={search}")
    
    if search and search.strip():
        result = result[
            result["Registration Number"].str.contains(search, case=False, na=False) |
            result["Object Name"].str.contains(search, case=False, na=False)
        ]
    
    if country and country.strip():
        print(f"DEBUG: Filtering by country: '{country.strip()}'")
        print(f"DEBUG: Available countries: {result['Country of Origin'].unique()[:5]}")
        result = result[result["Country of Origin"].str.strip() == country.strip()]
        print(f"DEBUG: After country filter: {len(result)} records")
    
    if function and function.strip():
        result = result[result["Function"].str.strip() == function.strip()]
    
    if apogee_min is not None:
        result = result[(result["Apogee (km)"].isna()) | (result["Apogee (km)"] >= apogee_min)]
    
    if apogee_max is not None:
        result = result[(result["Apogee (km)"].isna()) | (result["Apogee (km)"] <= apogee_max)]
    
    if perigee_min is not None:
        result = result[(result["Perigee (km)"].isna()) | (result["Perigee (km)"] >= perigee_min)]
    
    if perigee_max is not None:
        result = result[(result["Perigee (km)"].isna()) | (result["Perigee (km)"] <= perigee_max)]
    
    if inclination_min is not None:
        result = result[(result["Inclination (degrees)"].isna()) | (result["Inclination (degrees)"] >= inclination_min)]
    
    if inclination_max is not None:
        result = result[(result["Inclination (degrees)"].isna()) | (result["Inclination (degrees)"] <= inclination_max)]
    
    total = len(result)
    
    records = result.iloc[skip:skip+limit].to_dict(orient="records")
    for record in records:
        for key, value in record.items():
            if pd.isna(value):
                record[key] = None
    
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": records
    }

@app.get("/api/filters")
def get_filters():
    filters_data = {
        "countries": sorted(list(set([str(x).strip() for x in df["Country of Origin"].unique() if pd.notna(x)]))),
        "functions": sorted(list(set([str(x).strip() for x in df["Function"].unique() if pd.notna(x)]))),
    }
    
    apogee_vals = df[df["Apogee (km)"].notna()]["Apogee (km)"]
    if len(apogee_vals) > 0:
        filters_data["apogee_range"] = [float(apogee_vals.min()), float(apogee_vals.max())]
    else:
        filters_data["apogee_range"] = [0, 1000]
    
    perigee_vals = df[df["Perigee (km)"].notna()]["Perigee (km)"]
    if len(perigee_vals) > 0:
        filters_data["perigee_range"] = [float(perigee_vals.min()), float(perigee_vals.max())]
    else:
        filters_data["perigee_range"] = [0, 1000]
    
    inclination_vals = df[df["Inclination (degrees)"].notna()]["Inclination (degrees)"]
    if len(inclination_vals) > 0:
        filters_data["inclination_range"] = [float(inclination_vals.min()), float(inclination_vals.max())]
    else:
        filters_data["inclination_range"] = [0, 180]
    
    return filters_data

@app.get("/api/objects/{registration_number}")
def get_object(registration_number: str):
    obj = df[df["Registration Number"] == registration_number]
    if len(obj) == 0:
        return {"error": "Not found"}
    record = obj.iloc[0].to_dict()
    for key, value in record.items():
        if pd.isna(value):
            record[key] = None
    return record


@app.get("/api/objects/{registration_number}/orbital-state")
def get_orbital_state(registration_number: str):
    """
    Get current orbital state for an object using TLE data
    Includes orbital parameters and links to live tracking data
    """
    current_time = time.time()
    
    if registration_number in orbital_state_cache:
        cache_age = current_time - orbital_state_cache_time.get(registration_number, 0)
        if cache_age < CACHE_TTL:
            return orbital_state_cache[registration_number]
    
    obj = df[df["Registration Number"] == registration_number]
    if len(obj) == 0:
        return {"error": "Object not found"}
    
    obj_data = obj.iloc[0]
    intl_designator = str(obj_data['International Designator']).strip() if pd.notna(obj_data['International Designator']) else ""
    
    if not intl_designator:
        return {
            "registration_number": registration_number,
            "object_name": None if pd.isna(obj_data['Object Name']) else obj_data['Object Name'],
            "error": "No International Designator available for TLE lookup",
            "data_source": "Static registry only"
        }
    
    def get_value(val):
        return None if pd.isna(val) else val
    
    response = {
        "registration_number": registration_number,
        "object_name": get_value(obj_data['Object Name']),
        "international_designator": intl_designator,
        "country_of_origin": get_value(obj_data['Country of Origin']),
        "function": get_value(obj_data['Function']),
        "date_of_launch": get_value(obj_data['Date of Launch']),
        "status": get_value(obj_data['Status']),
    }
    
    doc_metadata = None
    has_complete_orbital_params = False
    
    if pd.notna(obj_data['Registration Document']) and obj_data['Registration Document']:
        doc_link_result = resolve_document_link(obj_data['Registration Document'])
        if doc_link_result.get('english_link'):
            doc_metadata = extract_document_metadata(doc_link_result['english_link'])
            if doc_metadata and all(k in doc_metadata for k in ['apogee_km', 'perigee_km', 'inclination_degrees', 'nodal_period_minutes']):
                has_complete_orbital_params = True
                response["orbital_state"] = {
                    "apogee_km": float(doc_metadata['apogee_km']),
                    "perigee_km": float(doc_metadata['perigee_km']),
                    "inclination_degrees": float(doc_metadata['inclination_degrees']),
                    "period_minutes": float(doc_metadata['nodal_period_minutes']),
                    "data_source": "Registration document"
                }
    
    if not has_complete_orbital_params:
        tle_data = fetch_tle_data()
        found_tle = None
        norad_id = None
        
        norad_format = convert_to_norad_format(intl_designator)
        if norad_format:
            if norad_format in tle_data:
                found_tle = tle_data[norad_format]
                norad_id = norad_format
            elif not norad_format[-1].isalpha():
                for piece in 'ABCDEFGH':
                    candidate = norad_format + piece
                    if candidate in tle_data:
                        found_tle = tle_data[candidate]
                        norad_id = candidate
                        break
        
        if not found_tle and intl_designator in tle_data:
            found_tle = tle_data[intl_designator]
            norad_id = intl_designator
        
        if found_tle:
            sat_name, tle_line1, tle_line2 = found_tle
            orbital_params = calculate_orbital_state(tle_line1, tle_line2)
            response["orbital_state"] = orbital_params
            response["tle_source"] = "CelesTrak"
            response["tracking_available"] = True
            response["norad_id"] = norad_id
            if norad_id:
                response["n2yo_url"] = f"https://www.n2yo.com/satellite/?s={norad_id}"
        else:
            response["error"] = "TLE data not found (satellite may be inactive/decayed)"
            response["tracking_available"] = False
            if pd.notna(obj_data['Apogee (km)']):
                response["orbital_state"] = {
                    "apogee_km": float(obj_data['Apogee (km)']),
                    "perigee_km": float(obj_data['Perigee (km)']),
                    "inclination_degrees": float(obj_data['Inclination (degrees)']),
                    "period_minutes": float(obj_data['Period (minutes)']),
                    "data_source": "Static registry"
                }
            
            if intl_designator in norad_id_map:
                norad_id = norad_id_map[intl_designator]
                response["norad_id"] = norad_id
                response["n2yo_url"] = f"https://www.n2yo.com/satellite/?s={norad_id}"
                response["tracking_available"] = True
    else:
        if intl_designator in norad_id_map:
            norad_id = norad_id_map[intl_designator]
            response["norad_id"] = norad_id
            response["n2yo_url"] = f"https://www.n2yo.com/satellite/?s={norad_id}"
            response["tracking_available"] = True
    
    orbital_state_cache[registration_number] = response
    orbital_state_cache_time[registration_number] = current_time
    
    return response
