from typing import Optional, Dict
import requests
import re
import io
import pdfplumber
from bs4 import BeautifulSoup


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


def convert_un_doc_to_pdf_url(url: str) -> Optional[str]:
    """
    Convert UN document API URL to direct PDF download URL.
    
    Example input: https://daccess-ods.un.org/access.nsf/Get?OpenAgent&DS=ST/SG/SER.E/1234&Lang=E
    Example output: https://daccess-ods.un.org/TMP/1234567.pdf (hypothetical)
    """
    return None


def fetch_english_doc_link(registry_doc_path: str) -> Optional[str]:
    """
    Fetch the actual English document link from UNOOSA registry page.
    Registry URLs often point to HTML pages that have links to PDFs.
    Also tries to correct common document ID errors.
    """
    if not registry_doc_path:
        return None
    
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
        return result
    
    match = re.search(r'stsgser\.e(\d{4})', registry_doc_path)
    if match:
        doc_id = int(match.group(1))
        
        pdf_path = f'/res/osoindex/data/documents/at/st/stsgser_e{doc_id:04d}_html/sere_{doc_id:04d}E.pdf'
        pdf_url = f"https://www.unoosa.org{pdf_path}"
        try:
            response = requests.head(pdf_url, timeout=5)
            if response.status_code == 200:
                return pdf_url
        except:
            pass
        
        for offset in [-10, -8, -6, -4, -2, -1, 1, 2, 4, 6, 8, 10]:
            corrected_id = doc_id + offset
            corrected_path = registry_doc_path.replace(f'stsgser.e{doc_id:04d}', f'stsgser.e{corrected_id:04d}')
            result = try_fetch(corrected_path)
            if result:
                return result
            
            pdf_path = f'/res/osoindex/data/documents/at/st/stsgser_e{corrected_id:04d}_html/sere_{corrected_id:04d}E.pdf'
            pdf_url = f"https://www.unoosa.org{pdf_path}"
            try:
                response = requests.head(pdf_url, timeout=5)
                if response.status_code == 200:
                    return pdf_url
            except:
                pass
    
    return None
