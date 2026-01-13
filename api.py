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
import db as db_module
from db import (
    connect_mongodb, disconnect_mongodb, find_satellite, search_satellites,
    count_satellites, get_all_countries, get_all_statuses, get_all_orbital_bands, 
    get_all_congestion_risks, create_satellite_document,
    COLLECTION_NAME, COLLECTION_REG_DOCS, EDGE_COLLECTION_CONSTELLATION,
    EDGE_COLLECTION_REGISTRATION, EDGE_COLLECTION_PROXIMITY, GRAPH_NAME
)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not connect_mongodb():
        raise RuntimeError("Failed to connect to ArangoDB. ArangoDB is required.")
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


@app.get("/v2/graphs/constellation/{constellation_name}")
def get_constellation_graph(
    constellation_name: str,
    limit: Optional[int] = Query(default=None, description="Limit number of satellites returned")
):
    """
    Get constellation membership graph for a specific constellation.
    
    Returns nodes (satellites) and edges (constellation membership) in graph format.
    Uses star topology where all satellites connect to a constellation hub.
    """
    query = f"""
    LET hub = FIRST(
        FOR edge IN {EDGE_COLLECTION_CONSTELLATION}
            FILTER edge.constellation_name == @constellation_name
            LIMIT 1
            RETURN edge._to
    )
    
    LET members = (
        FOR v, e IN 1..1 INBOUND hub
        {EDGE_COLLECTION_CONSTELLATION}
        FILTER e.constellation_name == @constellation_name
        {f"LIMIT {limit}" if limit else ""}
        RETURN {{
            id: v._id,
            key: v._key,
            identifier: v.identifier,
            name: v.canonical.name,
            country: v.canonical.country_of_origin,
            orbital_band: v.canonical.orbital_band,
            status: v.canonical.status,
            launch_date: v.canonical.date_of_launch
        }}
    )
    
    LET hub_doc = hub ? DOCUMENT(hub) : null
    
    LET hub_node = hub_doc ? {{
        id: hub_doc._id,
        key: hub_doc._key,
        identifier: hub_doc.identifier,
        name: hub_doc.canonical.name,
        country: hub_doc.canonical.country_of_origin,
        orbital_band: hub_doc.canonical.orbital_band,
        status: hub_doc.canonical.status,
        launch_date: hub_doc.canonical.date_of_launch,
        is_hub: true
    }} : null
    
    LET edges = (
        FOR v IN members
            RETURN {{
                id: CONCAT(v.id, "_to_hub"),
                source: v.id,
                target: hub,
                constellation: @constellation_name,
                relationship: "member_to_hub"
            }}
    )
    
    RETURN {{
        constellation: @constellation_name,
        hub: hub_node,
        nodes: hub_node ? APPEND(members, [hub_node]) : members,
        edges: edges,
        stats: {{
            total_satellites: hub_node ? LENGTH(members) + 1 : LENGTH(members),
            members: LENGTH(members),
            has_hub: hub_node != null
        }}
    }}
    """
    
    cursor = db_module.db.aql.execute(
        query,
        bind_vars={'constellation_name': constellation_name}
    )
    
    results = list(cursor)
    
    if results and results[0]['nodes']:
        return {
            "data": results[0],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": {
                "constellation": constellation_name,
                "hub": None,
                "nodes": [],
                "edges": [],
                "stats": {
                    "total_satellites": 0,
                    "members": 0,
                    "has_hub": False
                }
            },
            "message": f"No satellites found for constellation '{constellation_name}'",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@app.get("/v2/graphs/registration-document/{doc_key}")
def get_registration_document_graph(
    doc_key: str,
    limit: Optional[int] = Query(default=None, description="Limit number of satellites returned")
):
    """
    Get satellites linked to a specific registration document.
    
    Returns nodes (satellites + registration document) and edges in graph format.
    """
    doc_id = f"{COLLECTION_REG_DOCS}/{doc_key}"
    
    limit_clause = f"LIMIT {limit}" if limit else ""
    
    query = f"""
    LET reg_doc = DOCUMENT(@doc_id)
    
    LET satellites = reg_doc ? (
        FOR v, e IN 1..1 INBOUND @doc_id
        {EDGE_COLLECTION_REGISTRATION}
        {limit_clause}
        RETURN {{
            id: v._id,
            key: v._key,
            identifier: v.identifier,
            name: v.canonical.name,
            country: v.canonical.country_of_origin,
            orbital_band: v.canonical.orbital_band,
            status: v.canonical.status,
            registration_number: v.canonical.registration_number
        }}
    ) : []
    
    LET reg_doc_node = reg_doc ? {{
        id: reg_doc._id,
        key: reg_doc._key,
        url: reg_doc.url,
        satellite_count: reg_doc.satellite_count,
        countries: reg_doc.countries,
        type: "registration_document"
    }} : null
    
    LET edges = (
        FOR sat IN satellites
            RETURN {{
                id: CONCAT(sat.id, "_to_", reg_doc._id),
                source: sat.id,
                target: reg_doc._id,
                relationship: "registered_in"
            }}
    )
    
    RETURN {{
        registration_document: reg_doc_node,
        nodes: reg_doc_node ? APPEND(satellites, [reg_doc_node]) : satellites,
        edges: edges,
        stats: {{
            total_nodes: reg_doc_node ? LENGTH(satellites) + 1 : LENGTH(satellites),
            satellites: LENGTH(satellites),
            has_document: reg_doc_node != null
        }}
    }}
    """
    
    cursor = db_module.db.aql.execute(
        query,
        bind_vars={'doc_id': doc_id}
    )
    
    results = list(cursor)
    
    if results and results[0]['registration_document']:
        return {
            "data": results[0],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": {
                "registration_document": None,
                "nodes": [],
                "edges": [],
                "stats": {
                    "total_nodes": 0,
                    "satellites": 0,
                    "has_document": False
                }
            },
            "message": f"Registration document not found: {doc_key}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@app.get("/v2/graphs/stats")
def get_graph_stats():
    """
    Get overall graph statistics including node and edge counts.
    """
    query = f"""
    LET satellite_count = LENGTH({COLLECTION_NAME})
    LET reg_doc_count = LENGTH({COLLECTION_REG_DOCS})
    LET constellation_edges = LENGTH({EDGE_COLLECTION_CONSTELLATION})
    LET registration_edges = LENGTH({EDGE_COLLECTION_REGISTRATION})
    LET proximity_edges = LENGTH({EDGE_COLLECTION_PROXIMITY})
    
    LET constellations = (
        FOR edge IN {EDGE_COLLECTION_CONSTELLATION}
            COLLECT constellation = edge.constellation_name WITH COUNT INTO count
            SORT count DESC
            RETURN {{
                name: constellation,
                member_count: count
            }}
    )
    
    LET top_reg_docs = (
        FOR doc IN {COLLECTION_REG_DOCS}
            SORT doc.satellite_count DESC
            LIMIT 10
            RETURN {{
                key: doc._key,
                url: doc.url,
                satellite_count: doc.satellite_count,
                countries: doc.countries
            }}
    )
    
    LET proximity_by_band = (
        FOR edge IN {EDGE_COLLECTION_PROXIMITY}
            COLLECT band = edge.orbital_band WITH COUNT INTO count
            SORT count DESC
            RETURN {{
                orbital_band: band,
                edge_count: count
            }}
    )
    
    LET launches_by_year = (
        FOR doc IN {COLLECTION_NAME}
            FILTER doc.canonical.launch_date != null
            LET year = TO_NUMBER(SUBSTRING(doc.canonical.launch_date, 0, 4))
            COLLECT launch_year = year WITH COUNT INTO sat_count
            SORT launch_year DESC
            LIMIT 10
            RETURN {{
                year: launch_year,
                satellite_count: sat_count
            }}
    )
    
    RETURN {{
        nodes: {{
            satellites: satellite_count,
            registration_documents: reg_doc_count,
            total: satellite_count + reg_doc_count
        }},
        edges: {{
            constellation_membership: constellation_edges,
            registration_links: registration_edges,
            orbital_proximity: proximity_edges,
            total: constellation_edges + registration_edges + proximity_edges
        }},
        constellations: constellations,
        top_registration_documents: top_reg_docs,
        proximity_by_orbital_band: proximity_by_band,
        recent_launch_years: launches_by_year,
        graph_name: '{GRAPH_NAME}',
        collections: {{
            satellites: '{COLLECTION_NAME}',
            registration_documents: '{COLLECTION_REG_DOCS}',
            constellation_edges: '{EDGE_COLLECTION_CONSTELLATION}',
            registration_edges: '{EDGE_COLLECTION_REGISTRATION}',
            proximity_edges: '{EDGE_COLLECTION_PROXIMITY}'
        }}
    }}
    """
    
    cursor = db_module.db.aql.execute(query)
    results = list(cursor)
    
    return {
        "data": results[0] if results else {},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/v2/graphs/orbital-proximity/{orbital_band}")
def get_orbital_proximity_graph(
    orbital_band: str,
    limit: Optional[int] = Query(default=50, description="Limit number of satellites returned")
):
    """
    Get orbital proximity graph for a specific orbital band.
    
    Returns satellites and their proximity relationships (satellites with similar orbits).
    """
    query = f"""
    LET proximity_edges = (
        FOR edge IN {EDGE_COLLECTION_PROXIMITY}
            FILTER edge.orbital_band == @orbital_band
            LIMIT @limit
            RETURN edge
    )
    
    LET satellite_ids = UNIQUE(FLATTEN(
        FOR edge IN proximity_edges
            RETURN [edge._from, edge._to]
    ))
    
    LET satellites = (
        FOR sat_id IN satellite_ids
            LET sat = DOCUMENT(sat_id)
            RETURN {{
                id: sat._id,
                key: sat._key,
                identifier: sat.identifier,
                name: sat.canonical.name,
                orbital_band: sat.canonical.orbital_band,
                apogee_km: sat.canonical.orbit.apogee_km,
                perigee_km: sat.canonical.orbit.perigee_km,
                inclination_degrees: sat.canonical.orbit.inclination_degrees,
                congestion_risk: sat.canonical.congestion_risk
            }}
    )
    
    LET edges = (
        FOR edge IN proximity_edges
            RETURN {{
                id: edge._key,
                source: edge._from,
                target: edge._to,
                proximity_score: edge.proximity_score,
                apogee_diff_km: edge.apogee_diff_km,
                perigee_diff_km: edge.perigee_diff_km,
                inclination_diff_degrees: edge.inclination_diff_degrees
            }}
    )
    
    LET total_proximity_edges = LENGTH(
        FOR edge IN {EDGE_COLLECTION_PROXIMITY}
            FILTER edge.orbital_band == @orbital_band
            RETURN 1
    )
    
    RETURN {{
        orbital_band: @orbital_band,
        nodes: satellites,
        edges: edges,
        stats: {{
            total_satellites: LENGTH(satellites),
            total_proximity_edges: total_proximity_edges,
            edges_shown: LENGTH(edges)
        }}
    }}
    """
    
    cursor = db_module.db.aql.execute(
        query,
        bind_vars={'orbital_band': orbital_band, 'limit': limit}
    )
    
    results = list(cursor)
    
    if results and results[0]['nodes']:
        return {
            "data": results[0],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": {
                "orbital_band": orbital_band,
                "nodes": [],
                "edges": [],
                "stats": {
                    "total_satellites": 0,
                    "total_proximity_edges": 0,
                    "edges_shown": 0
                }
            },
            "message": f"No proximity data found for orbital band '{orbital_band}'",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

@app.get("/v2/graphs/timeline/filter-options")
def get_timeline_filter_options():
    """
    Get available filter options for timeline view (countries and orbital bands).
    """
    
    query = f"""
    LET countries = (
        FOR doc IN {db_module.COLLECTION_NAME}
            FILTER doc.canonical.country != null
            COLLECT country = doc.canonical.country WITH COUNT INTO count
            FILTER count >= 10
            SORT country ASC
            RETURN country
    )
    
    LET orbital_bands = (
        FOR doc IN {db_module.COLLECTION_NAME}
            FILTER doc.canonical.orbital_band != null
            COLLECT band = doc.canonical.orbital_band WITH COUNT INTO count
            FILTER count >= 10
            SORT band ASC
            RETURN band
    )
    
    RETURN {{
        countries: countries,
        orbital_bands: orbital_bands
    }}
    """
    
    cursor = db_module.db.aql.execute(query)
    results = list(cursor)
    
    if results:
        return {
            "data": results[0],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": {
                "countries": [],
                "orbital_bands": []
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

@app.get("/v2/graphs/timeline/yearly")
def get_yearly_launch_data_filtered(
    country: Optional[str] = Query(default=None, description="Filter by country"),
    orbital_band: Optional[str] = Query(default=None, description="Filter by orbital band")
):
    """
    Get yearly launch data with optional filters.
    Returns satellite counts grouped by year.
    """
    
    filters = []
    bind_vars = {}
    
    if country:
        filters.append("doc.canonical.country == @country")
        bind_vars['country'] = country
    
    if orbital_band:
        filters.append("doc.canonical.orbital_band == @orbital_band")
        bind_vars['orbital_band'] = orbital_band
    
    filter_clause = " AND ".join(filters) if filters else "true"
    
    query = f"""
    FOR doc IN {db_module.COLLECTION_NAME}
        FILTER doc.canonical.launch_date != null
        FILTER {filter_clause}
        LET launch_year = TO_NUMBER(SUBSTRING(doc.canonical.launch_date, 0, 4))
        FILTER launch_year != null AND launch_year >= 1957
        COLLECT year = launch_year WITH COUNT INTO sat_count
        SORT year ASC
        RETURN {{
            year: year,
            satellite_count: sat_count
        }}
    """
    
    cursor = db_module.db.aql.execute(query, bind_vars=bind_vars)
    results = list(cursor)
    
    return {
        "data": {
            "recent_launch_years": results
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/v2/graphs/launch-timeline/monthly/{year}")
def get_monthly_launch_data(
    year: int,
    country: Optional[str] = Query(default=None, description="Filter by country"),
    orbital_band: Optional[str] = Query(default=None, description="Filter by orbital band")
):
    """
    Get monthly launch data for a specific year with optional filters.
    Returns satellite counts grouped by month.
    """
    
    filters = []
    bind_vars = {'year': year}
    
    if country:
        filters.append("doc.canonical.country == @country")
        bind_vars['country'] = country
    
    if orbital_band:
        filters.append("doc.canonical.orbital_band == @orbital_band")
        bind_vars['orbital_band'] = orbital_band
    
    filter_clause = " AND ".join(filters) if filters else "true"
    
    query = f"""
    FOR doc IN {db_module.COLLECTION_NAME}
        FILTER doc.canonical.launch_date != null
        FILTER {filter_clause}
        LET launch_year = TO_NUMBER(SUBSTRING(doc.canonical.launch_date, 0, 4))
        FILTER launch_year == @year
        LET launch_month = TO_NUMBER(SUBSTRING(doc.canonical.launch_date, 5, 2))
        COLLECT month = launch_month WITH COUNT INTO sat_count
        SORT month ASC
        RETURN {{
            month: month,
            satellite_count: sat_count
        }}
    """
    
    cursor = db_module.db.aql.execute(query, bind_vars=bind_vars)
    results = list(cursor)
    
    return {
        "data": {
            "year": year,
            "monthly_data": results,
            "total_satellites": sum(r['satellite_count'] for r in results)
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/v2/graphs/launch-timeline/breakdown/{year}")
def get_launch_timeline_breakdown(
    year: int,
    country: Optional[str] = Query(default=None, description="Filter by country"),
    orbital_band: Optional[str] = Query(default=None, description="Filter by orbital band")
):
    """
    Get breakdown statistics for a specific year including:
    - Orbital band distribution
    - Country distribution  
    - Constellation distribution
    """
    
    filters = []
    bind_vars = {'year': year}
    
    if country:
        filters.append("sat.canonical.country == @country")
        bind_vars['country'] = country
    
    if orbital_band:
        filters.append("sat.canonical.orbital_band == @orbital_band")
        bind_vars['orbital_band'] = orbital_band
    
    filter_clause = " AND ".join(filters) if filters else "true"
    
    query = f"""
    LET year_satellites = (
        FOR doc IN {db_module.COLLECTION_NAME}
            FILTER doc.canonical.launch_date != null
            LET sat_year = TO_NUMBER(SUBSTRING(doc.canonical.launch_date, 0, 4))
            FILTER sat_year == @year
            RETURN doc
    )
    
    LET filtered_satellites = (
        FOR sat IN year_satellites
            FILTER {filter_clause}
            RETURN sat
    )
    
    LET by_orbital_band = (
        FOR sat IN filtered_satellites
            COLLECT band = sat.canonical.orbital_band WITH COUNT INTO band_count
            SORT band_count DESC
            RETURN {{orbital_band: band, count: band_count}}
    )
    
    LET by_country = (
        FOR sat IN filtered_satellites
            COLLECT country = sat.canonical.country WITH COUNT INTO country_count
            SORT country_count DESC
            LIMIT 10
            RETURN {{country: country, count: country_count}}
    )
    
    LET by_constellation = (
        FOR sat IN filtered_satellites
            FILTER sat.canonical.constellation != null
            COLLECT constellation = sat.canonical.constellation WITH COUNT INTO const_count
            SORT const_count DESC
            LIMIT 10
            RETURN {{constellation: constellation, count: const_count}}
    )
    
    RETURN {{
        year: @year,
        total_satellites: LENGTH(filtered_satellites),
        by_orbital_band: by_orbital_band,
        by_country: by_country,
        by_constellation: by_constellation
    }}
    """
    
    cursor = db_module.db.aql.execute(query, bind_vars=bind_vars)
    results = list(cursor)
    
    if results:
        return {
            "data": results[0],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": {
                "year": year,
                "total_satellites": 0,
                "by_orbital_band": [],
                "by_country": [],
                "by_constellation": []
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

@app.get("/v2/graphs/launch-timeline/breakdown/monthly/{year}/{month}")
def get_monthly_launch_breakdown(
    year: int,
    month: int,
    country: Optional[str] = Query(default=None, description="Filter by country"),
    orbital_band: Optional[str] = Query(default=None, description="Filter by orbital band")
):
    """
    Get breakdown statistics for a specific month including:
    - Orbital band distribution
    - Country distribution  
    - Constellation distribution
    """
    
    filters = []
    bind_vars = {'year': year, 'month': month}
    
    if country:
        filters.append("sat.canonical.country == @country")
        bind_vars['country'] = country
    
    if orbital_band:
        filters.append("sat.canonical.orbital_band == @orbital_band")
        bind_vars['orbital_band'] = orbital_band
    
    filter_clause = " AND ".join(filters) if filters else "true"
    
    query = f"""
    LET month_satellites = (
        FOR doc IN {db_module.COLLECTION_NAME}
            FILTER doc.canonical.launch_date != null
            LET sat_year = TO_NUMBER(SUBSTRING(doc.canonical.launch_date, 0, 4))
            LET sat_month = TO_NUMBER(SUBSTRING(doc.canonical.launch_date, 5, 2))
            FILTER sat_year == @year AND sat_month == @month
            RETURN doc
    )
    
    LET filtered_satellites = (
        FOR sat IN month_satellites
            FILTER {filter_clause}
            RETURN sat
    )
    
    LET by_orbital_band = (
        FOR sat IN filtered_satellites
            COLLECT band = sat.canonical.orbital_band WITH COUNT INTO band_count
            SORT band_count DESC
            RETURN {{orbital_band: band, count: band_count}}
    )
    
    LET by_country = (
        FOR sat IN filtered_satellites
            COLLECT country = sat.canonical.country WITH COUNT INTO country_count
            SORT country_count DESC
            LIMIT 10
            RETURN {{country: country, count: country_count}}
    )
    
    LET by_constellation = (
        FOR sat IN filtered_satellites
            FILTER sat.canonical.constellation != null
            COLLECT constellation = sat.canonical.constellation WITH COUNT INTO const_count
            SORT const_count DESC
            LIMIT 10
            RETURN {{constellation: constellation, count: const_count}}
    )
    
    RETURN {{
        year: @year,
        month: @month,
        total_satellites: LENGTH(filtered_satellites),
        by_orbital_band: by_orbital_band,
        by_country: by_country,
        by_constellation: by_constellation
    }}
    """
    
    cursor = db_module.db.aql.execute(query, bind_vars=bind_vars)
    results = list(cursor)
    
    if results:
        return {
            "data": results[0],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": {
                "year": year,
                "month": month,
                "total_satellites": 0,
                "by_orbital_band": [],
                "by_country": [],
                "by_constellation": []
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

@app.get("/v2/graphs/launch-timeline/{time_period}")
def get_launch_timeline_graph(
    time_period: str,
    limit: Optional[int] = Query(default=50, description="Limit number of satellites returned")
):
    """
    Get launch timeline graph for a specific time period.
    
    Returns satellites grouped by launch time period (year, decade, era).
    Time periods can be specific years (e.g., "2024") or ranges (e.g., "2020-2024").
    """
    
    start_year = None
    end_year = None
    
    if '-' in time_period:
        try:
            parts = time_period.split('-')
            start_year = int(parts[0])
            end_year = int(parts[1])
        except (ValueError, IndexError):
            raise HTTPException(status_code=400, detail=f"Invalid time period format: {time_period}")
    else:
        try:
            start_year = int(time_period)
            end_year = start_year
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid time period format: {time_period}")
    
    query = f"""
    LET satellites_in_period = (
        FOR doc IN {db_module.COLLECTION_NAME}
            FILTER doc.canonical.launch_date != null
            LET year = TO_NUMBER(SUBSTRING(doc.canonical.launch_date, 0, 4))
            FILTER year >= @start_year AND year <= @end_year
            LIMIT @limit
            RETURN {{
                _key: doc._key,
                _id: doc._id,
                identifier: doc.identifier,
                name: doc.canonical.name,
                launch_date: doc.canonical.launch_date,
                launch_year: year,
                country: doc.canonical.country,
                constellation: doc.canonical.constellation,
                orbital_band: doc.canonical.orbital_band,
                congestion_risk: doc.canonical.congestion_risk
            }}
    )
    
    LET year_groups = (
        FOR sat IN satellites_in_period
            COLLECT year = sat.launch_year INTO year_sats
            RETURN {{
                year: year,
                satellite_count: LENGTH(year_sats),
                satellites: year_sats[*].sat
            }}
    )
    
    LET total_in_period = LENGTH(
        FOR doc IN {db_module.COLLECTION_NAME}
            FILTER doc.canonical.launch_date != null
            LET year = TO_NUMBER(SUBSTRING(doc.canonical.launch_date, 0, 4))
            FILTER year >= @start_year AND year <= @end_year
            RETURN 1
    )
    
    RETURN {{
        time_period: @time_period,
        start_year: @start_year,
        end_year: @end_year,
        year_groups: year_groups,
        nodes: satellites_in_period,
        stats: {{
            total_in_period: total_in_period,
            satellites_shown: LENGTH(satellites_in_period),
            years_covered: LENGTH(year_groups)
        }}
    }}
    """
    
    cursor = db_module.db.aql.execute(
        query,
        bind_vars={
            'time_period': time_period,
            'start_year': start_year,
            'end_year': end_year,
            'limit': limit
        }
    )
    
    results = list(cursor)
    
    if results and results[0]['nodes']:
        return {
            "data": results[0],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": {
                "time_period": time_period,
                "start_year": start_year,
                "end_year": end_year,
                "year_groups": [],
                "nodes": [],
                "stats": {
                    "total_in_period": 0,
                    "satellites_shown": 0,
                    "years_covered": 0
                }
            },
            "message": f"No satellites found for time period '{time_period}'",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

@app.get("/v2/graphs/function-similarity")
def get_function_similarity_graph(limit: Optional[int] = Query(default=100, description="Limit satellites per category")):
    """
    Get function similarity graph showing satellites grouped by function categories.
    
    Categories are derived from function keywords:
    - Communications: satellites for telecommunications
    - Earth Observation: remote sensing, earth resources
    - Scientific Research: space/atmosphere investigation
    - Navigation: GPS, GLONASS, positioning
    - Military-Defense: defense, military assignments
    - Space Station: ISS, Mir supply and operations
    - Technology-Testing: tech demonstration, experimental
    """
    
    query = f"""
    LET satellites_with_function = (
        FOR doc IN {db_module.COLLECTION_NAME}
            FILTER doc.canonical.function != null
            LET func_lower = LOWER(doc.canonical.function)
            LET category = (
                func_lower LIKE '%communicat%' OR func_lower LIKE '%telecom%' ? 'Communications' :
                func_lower LIKE '%earth%' OR func_lower LIKE '%observation%' OR func_lower LIKE '%remote sens%' OR func_lower LIKE '%resources%' ? 'Earth Observation' :
                func_lower LIKE '%investigation%' OR func_lower LIKE '%scientific%' OR func_lower LIKE '%atmosphere%' OR func_lower LIKE '%space%' ? 'Scientific Research' :
                func_lower LIKE '%navigation%' OR func_lower LIKE '%glonass%' OR func_lower LIKE '%gps%' OR func_lower LIKE '%position%' ? 'Navigation' :
                func_lower LIKE '%defense%' OR func_lower LIKE '%defence%' OR func_lower LIKE '%military%' ? 'Military-Defense' :
                func_lower LIKE '%station%' OR func_lower LIKE '%mir%' OR func_lower LIKE '%iss%' OR func_lower LIKE '%delivery%' ? 'Space Station' :
                func_lower LIKE '%technolog%' OR func_lower LIKE '%experiment%' OR func_lower LIKE '%test%' OR func_lower LIKE '%demonstration%' ? 'Technology-Testing' :
                'Other'
            )
            RETURN {{
                _id: doc._id,
                _key: doc._key,
                identifier: doc.identifier,
                name: doc.canonical.name,
                function: doc.canonical.function,
                function_category: category,
                country: doc.canonical.country,
                launch_date: doc.canonical.launch_date,
                orbital_band: doc.canonical.orbital_band,
                congestion_risk: doc.canonical.congestion_risk
            }}
    )
    
    LET category_stats = (
        FOR sat IN satellites_with_function
            COLLECT category = sat.function_category WITH COUNT INTO count
            SORT count DESC
            RETURN {{
                category: category,
                satellite_count: count
            }}
    )
    
    LET limited_satellites = (
        FOR sat IN satellites_with_function
            COLLECT category = sat.function_category INTO category_sats
            LET limited_sats = SLICE(category_sats[*].sat, 0, @limit)
            FOR s IN limited_sats
                RETURN s
    )
    
    LET satellite_ids = limited_satellites[*]._id
    
    LET constellation_edges = (
        FOR edge IN {db_module.EDGE_COLLECTION_CONSTELLATION}
            FILTER edge._from IN satellite_ids AND edge._to IN satellite_ids
            RETURN {{
                id: edge._key,
                source: edge._from,
                target: edge._to,
                relationship_type: 'constellation_membership',
                constellation_name: edge.constellation_name
            }}
    )
    
    LET registration_edges = (
        FOR edge IN {db_module.EDGE_COLLECTION_REGISTRATION}
            FILTER (edge._from IN satellite_ids OR edge._to IN satellite_ids)
            RETURN {{
                id: edge._key,
                source: edge._from,
                target: edge._to,
                relationship_type: 'registration_link',
                registration_document: edge.registration_document
            }}
    )
    
    LET proximity_edges = (
        FOR edge IN {db_module.EDGE_COLLECTION_PROXIMITY}
            FILTER edge._from IN satellite_ids AND edge._to IN satellite_ids
            LIMIT 500
            RETURN {{
                id: edge._key,
                source: edge._from,
                target: edge._to,
                relationship_type: 'orbital_proximity',
                proximity_score: edge.proximity_score,
                orbital_band: edge.orbital_band
            }}
    )
    
    LET edges = UNION(constellation_edges, registration_edges, proximity_edges)
    
    RETURN {{
        nodes: limited_satellites,
        edges: edges,
        categories: category_stats,
        stats: {{
            total_with_function: LENGTH(satellites_with_function),
            nodes_shown: LENGTH(limited_satellites),
            edges_shown: LENGTH(edges),
            categories_count: LENGTH(category_stats)
        }}
    }}
    """
    
    cursor = db_module.db.aql.execute(query, bind_vars={'limit': limit})
    results = list(cursor)
    
    if results:
        return {
            "data": results[0],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": {
                "nodes": [],
                "edges": [],
                "categories": [],
                "stats": {
                    "total_with_function": 0,
                    "nodes_shown": 0,
                    "edges_shown": 0,
                    "categories_count": 0
                }
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

@app.get("/v2/graphs/function-similarity/category/{category}")
def get_function_category_graph(
    category: str,
    limit: Optional[int] = Query(default=100, description="Limit number of satellites")
):
    """
    Get satellites for a specific function category.
    """
    
    query = f"""
    LET satellites_with_function = (
        FOR doc IN {db_module.COLLECTION_NAME}
            FILTER doc.canonical.function != null
            LET func_lower = LOWER(doc.canonical.function)
            LET detected_category = (
                func_lower LIKE '%communicat%' OR func_lower LIKE '%telecom%' ? 'Communications' :
                func_lower LIKE '%earth%' OR func_lower LIKE '%observation%' OR func_lower LIKE '%remote sens%' OR func_lower LIKE '%resources%' ? 'Earth Observation' :
                func_lower LIKE '%investigation%' OR func_lower LIKE '%scientific%' OR func_lower LIKE '%atmosphere%' OR func_lower LIKE '%space%' ? 'Scientific Research' :
                func_lower LIKE '%navigation%' OR func_lower LIKE '%glonass%' OR func_lower LIKE '%gps%' OR func_lower LIKE '%position%' ? 'Navigation' :
                func_lower LIKE '%defense%' OR func_lower LIKE '%defence%' OR func_lower LIKE '%military%' ? 'Military-Defense' :
                func_lower LIKE '%station%' OR func_lower LIKE '%mir%' OR func_lower LIKE '%iss%' OR func_lower LIKE '%delivery%' ? 'Space Station' :
                func_lower LIKE '%technolog%' OR func_lower LIKE '%experiment%' OR func_lower LIKE '%test%' OR func_lower LIKE '%demonstration%' ? 'Technology-Testing' :
                'Other'
            )
            FILTER detected_category == @category
            LIMIT @limit
            RETURN {{
                _id: doc._id,
                _key: doc._key,
                identifier: doc.identifier,
                name: doc.canonical.name,
                function: doc.canonical.function,
                function_category: detected_category,
                country: doc.canonical.country,
                launch_date: doc.canonical.launch_date,
                orbital_band: doc.canonical.orbital_band,
                congestion_risk: doc.canonical.congestion_risk,
                norad_cat_id: doc.canonical.norad_cat_id
            }}
    )
    
    LET satellite_ids = satellites_with_function[*]._id
    
    LET constellation_edges = (
        FOR edge IN {db_module.EDGE_COLLECTION_CONSTELLATION}
            FILTER edge._from IN satellite_ids AND edge._to IN satellite_ids
            RETURN {{
                id: edge._key,
                source: edge._from,
                target: edge._to,
                relationship_type: 'constellation_membership',
                constellation_name: edge.constellation_name
            }}
    )
    
    LET registration_edges = (
        FOR edge IN {db_module.EDGE_COLLECTION_REGISTRATION}
            FILTER (edge._from IN satellite_ids OR edge._to IN satellite_ids)
            RETURN {{
                id: edge._key,
                source: edge._from,
                target: edge._to,
                relationship_type: 'registration_link',
                registration_document: edge.registration_document
            }}
    )
    
    LET proximity_edges = (
        FOR edge IN {db_module.EDGE_COLLECTION_PROXIMITY}
            FILTER edge._from IN satellite_ids AND edge._to IN satellite_ids
            LIMIT 300
            RETURN {{
                id: edge._key,
                source: edge._from,
                target: edge._to,
                relationship_type: 'orbital_proximity',
                proximity_score: edge.proximity_score,
                orbital_band: edge.orbital_band
            }}
    )
    
    LET edges = UNION(constellation_edges, registration_edges, proximity_edges)
    
    RETURN {{
        category: @category,
        nodes: satellites_with_function,
        edges: edges,
        stats: {{
            satellites_shown: LENGTH(satellites_with_function),
            edges_shown: LENGTH(edges)
        }}
    }}
    """
    
    cursor = db_module.db.aql.execute(query, bind_vars={'category': category, 'limit': limit})
    results = list(cursor)
    
    if results:
        return {
            "data": results[0],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": {
                "category": category,
                "nodes": [],
                "edges": [],
                "stats": {
                    "satellites_shown": 0,
                    "edges_shown": 0
                }
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

@app.get("/v2/graphs/country-relations")
def get_country_relations_graph(
    min_satellites: Optional[int] = Query(default=50, description="Minimum satellites per country"),
    limit_countries: Optional[int] = Query(default=10, description="Limit number of countries")
):
    """
    Get country relations graph showing international cooperation and shared interests.
    
    Relationships are based on:
    - Shared registration documents (direct collaboration)
    - Satellites in similar orbital bands (coordination)
    """
    
    query = f"""
    LET countries_with_sats = (
        FOR doc IN {db_module.COLLECTION_NAME}
            FILTER doc.canonical.country != null
            COLLECT c = doc.canonical.country WITH COUNT INTO count
            FILTER count >= @min_satellites
            SORT count DESC
            LIMIT @limit_countries
            RETURN {{
                country: c,
                satellite_count: count
            }}
    )
    
    LET country_names = countries_with_sats[*].country
    
    LET by_orbital_band = (
        FOR doc IN {db_module.COLLECTION_NAME}
            FILTER doc.canonical.country IN country_names
            FILTER doc.canonical.orbital_band != null
            COLLECT country_name = doc.canonical.country, band = doc.canonical.orbital_band WITH COUNT INTO count
            RETURN {{
                country: country_name,
                orbital_band: band,
                count: count
            }}
    )
    
    LET orbital_edges = (
        FOR b1 IN by_orbital_band
            FOR b2 IN by_orbital_band
                FILTER b1.country < b2.country
                FILTER b1.orbital_band == b2.orbital_band
                FILTER b1.count + b2.count >= 10
                RETURN {{
                    country1: b1.country,
                    country2: b2.country,
                    orbital_band: b1.orbital_band,
                    shared_count: b1.count + b2.count
                }}
    )
    
    LET by_registration_doc = (
        FOR doc IN {db_module.COLLECTION_NAME}
            FILTER doc.canonical.country IN country_names
            FILTER doc.canonical.registration_document != null
            COLLECT country_name = doc.canonical.country, reg_doc = doc.canonical.registration_document WITH COUNT INTO count
            RETURN {{
                country: country_name,
                reg_doc: reg_doc,
                count: count
            }}
    )
    
    LET collab_edges = (
        FOR r1 IN by_registration_doc
            FOR r2 IN by_registration_doc
                FILTER r1.country < r2.country
                FILTER r1.reg_doc == r2.reg_doc
                RETURN {{
                    country1: r1.country,
                    country2: r2.country,
                    collaboration_count: r1.count + r2.count
                }}
    )
    
    LET edges = UNION_DISTINCT(
        (FOR edge IN orbital_edges
            RETURN {{
                id: CONCAT(edge.country1, '_', edge.country2, '_', edge.orbital_band),
                source: edge.country1,
                target: edge.country2,
                relationship_type: 'shared_orbital_band',
                orbital_band: edge.orbital_band,
                strength: edge.shared_count,
                weight: edge.shared_count
            }}),
        (FOR edge IN collab_edges
            RETURN {{
                id: CONCAT(edge.country1, '_', edge.country2, '_collab'),
                source: edge.country1,
                target: edge.country2,
                relationship_type: 'collaboration',
                strength: edge.collaboration_count * 10,
                weight: edge.collaboration_count * 10
            }})
    )
    
    RETURN {{
        nodes: countries_with_sats,
        edges: edges,
        stats: {{
            countries_shown: LENGTH(countries_with_sats),
            relationships_found: LENGTH(edges)
        }}
    }}
    """
    
    cursor = db_module.db.aql.execute(
        query,
        bind_vars={'min_satellites': min_satellites, 'limit_countries': limit_countries}
    )
    results = list(cursor)
    
    if results:
        return {
            "data": results[0],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": {
                "nodes": [],
                "edges": [],
                "stats": {
                    "countries_shown": 0,
                    "relationships_found": 0
                }
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
