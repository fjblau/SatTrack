from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Optional, List, Dict
import json
from datetime import datetime, timezone
import math
import os
import requests
import time
import re
from bs4 import BeautifulSoup
import pdfplumber
import io
from db import (
    connect_mongodb, disconnect_mongodb, find_satellite, search_satellites,
    count_satellites, get_all_countries, get_all_statuses, get_all_orbital_bands, 
    get_all_congestion_risks, create_satellite_document
)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not connect_mongodb():
        raise RuntimeError("Failed to connect to MongoDB. MongoDB is required.")
    yield
    disconnect_mongodb()

app = FastAPI(lifespan=lifespan)

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



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





@app.get("/v2/health")
def health_check():
    """Check API and database health"""
    return {
        "status": "ok",
        "api_version": "v2"
    }


@app.get("/v2/search")
def search_satellites_v2(
    q: Optional[str] = Query(None, description="Search query (name, designator, registration number)"),
    country: Optional[str] = Query(None, description="Filter by country"),
    status: Optional[str] = Query(None, description="Filter by status"),
    orbital_band: Optional[str] = Query(None, description="Filter by orbital band"),
    congestion_risk: Optional[str] = Query(None, description="Filter by congestion risk"),
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0)
):
    """
    Search satellites in MongoDB.
    Supports filtering by country, status, orbital band, and congestion risk.
    """
    results = search_satellites(
        query=q or "",
        country=country,
        status=status,
        orbital_band=orbital_band,
        congestion_risk=congestion_risk,
        limit=limit,
        skip=skip
    )
    
    total_count = count_satellites(
        query=q or "",
        country=country,
        status=status,
        orbital_band=orbital_band,
        congestion_risk=congestion_risk
    )
    
    # Convert MongoDB documents to JSON-safe format
    data = []
    for r in results:
        canonical = r.get("canonical", {})
        # Filter out MongoDB special fields and NaN values
        safe_canonical = {}
        for k, v in canonical.items():
            if k != '_id' and not (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
                safe_canonical[k] = v
        
        data.append({
            "identifier": r.get("identifier"),
            "canonical": safe_canonical,
            "sources_available": r.get("metadata", {}).get("sources_available", [])
        })
    
    return {
        "count": total_count,
        "skip": skip,
        "limit": limit,
        "data": data
    }


@app.get("/v2/satellite/{identifier}")
def get_satellite_v2(identifier: str):
    """
    Get detailed satellite information from MongoDB.
    Identifier can be international designator or registration number.
    """
    sat = find_satellite(international_designator=identifier) or find_satellite(registration_number=identifier)
    
    if sat:
        # Filter out MongoDB special fields and NaN values
        canonical = sat.get("canonical", {})
        safe_canonical = {}
        for k, v in canonical.items():
            if k != '_id':
                if isinstance(v, dict):
                    # Handle nested orbit dict
                    safe_v = {}
                    for kk, vv in v.items():
                        if not (isinstance(vv, float) and (math.isnan(vv) or math.isinf(vv))):
                            safe_v[kk] = vv
                    safe_canonical[k] = safe_v
                elif not (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
                    safe_canonical[k] = v
        
        sources = sat.get("sources", {})
        safe_sources = {}
        for k, v in sources.items():
            if k != '_id' and isinstance(v, dict):
                safe_v = {}
                for kk, vv in v.items():
                    if kk != '_id' and not (isinstance(vv, float) and (math.isnan(vv) or math.isinf(vv))):
                        safe_v[kk] = vv
                safe_sources[k] = safe_v
        
        return {
            "data": {
                "identifier": sat.get("identifier"),
                "canonical": safe_canonical,
                "sources": safe_sources,
                "metadata": sat.get("metadata", {})
            }
        }
    else:
        return {"error": "Satellite not found"}, 404


@app.get("/v2/countries")
def get_countries_v2():
    """Get list of all countries with satellite registrations"""
    countries = get_all_countries()
    return {
        "count": len(countries),
        "countries": sorted([c for c in countries if c and c.strip()])
    }


@app.get("/v2/statuses")
def get_statuses_v2():
    """Get list of all satellite statuses"""
    statuses = get_all_statuses()
    return {
        "count": len(statuses),
        "statuses": sorted([s for s in statuses if s and s.strip()])
    }


@app.get("/v2/orbital-bands")
def get_orbital_bands_v2():
    """Get list of all orbital bands"""
    orbital_bands = get_all_orbital_bands()
    return {
        "count": len(orbital_bands),
        "orbital_bands": sorted([b for b in orbital_bands if b and b.strip()])
    }


@app.get("/v2/congestion-risks")
def get_congestion_risks_v2():
    """Get list of all congestion risks"""
    congestion_risks = get_all_congestion_risks()
    return {
        "count": len(congestion_risks),
        "congestion_risks": sorted([r for r in congestion_risks if r and r.strip()])
    }


@app.get("/v2/stats")
def get_stats_v2(country: Optional[str] = Query(None), status: Optional[str] = Query(None)):
    """Get statistics about satellites"""
    total = count_satellites()
    filtered = count_satellites(country=country, status=status) if (country or status) else total
    
    return {
        "total_satellites": total,
        "filtered_count": filtered,
        "filters_applied": {
            "country": country,
            "status": status
        }
    }


def fetch_tle_by_norad_id(norad_id: str) -> Optional[Dict]:
    """Fetch fresh TLE data by NORAD ID from TLE API"""
    url = f"https://tle.ivanstanojevic.me/api/tle/{norad_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # Retry logic for transient failures
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "name": data.get("name", f"NORAD {norad_id}"),
                    "line1": data.get("line1"),
                    "line2": data.get("line2"),
                    "source": "tle-api",
                    "date": data.get("date")
                }
            elif response.status_code == 404:
                return None
            else:
                print(f"Error fetching from TLE API: {response.status_code}")
                return None
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < max_retries - 1:
                wait_time = 0.5 * (2 ** attempt)  # Exponential backoff: 0.5s, 1s, 2s
                print(f"Connection error fetching TLE for NORAD {norad_id}, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                print(f"Error fetching from TLE API after {max_retries} attempts: {e}")
                return None
        except Exception as e:
            print(f"Error fetching from TLE API: {e}")
            return None
    
    return None


@app.get("/v2/tle/{norad_id}")
def get_current_tle(norad_id: str):
    """Get current TLE data from TLE API for a satellite by NORAD ID"""
    tle = fetch_tle_by_norad_id(norad_id)
    
    if tle:
        return {
            "data": tle,
            "source": tle.get("source", "tle-api"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": None,
            "message": f"TLE data not found for NORAD ID {norad_id}.",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, 200
