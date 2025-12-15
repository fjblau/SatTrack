import pandas as pd
import requests
import re
import io
import pdfplumber
import time

print("Scraping orbital parameters from UN documents...")

df = pd.read_csv("unoosa_registry.csv")

# Extract SER.E series numbers and map to registration numbers
doc_to_reg = {}
for idx, row in df.iterrows():
    reg_num = str(row['Registration Number']).strip()
    doc_url = str(row['Registration Document']).strip() if pd.notna(row['Registration Document']) else ""
    
    if doc_url and reg_num:
        match = re.search(r'stsgser\.e(\d+)', doc_url, re.IGNORECASE)
        if match:
            ser_e_num = match.group(1)
            if ser_e_num not in doc_to_reg:
                doc_to_reg[ser_e_num] = []
            doc_to_reg[ser_e_num].append(reg_num)

print(f"Found {len(doc_to_reg)} unique SER.E document identifiers")

# Known mappings of SER.E numbers to UN PDF URLs
known_urls = {
    "1301": "https://documents.un.org/doc/undoc/gen/v25/077/01/pdf/v2507701.pdf",
}

def extract_params_from_pdf_text(text):
    """Extract orbital parameters from PDF text using regex"""
    params = {}
    
    # Pattern to match registration numbers and orbital parameters
    # Format: XXXX-YYYY-ZZZ ... (numbers) ... description
    # The orbital parameters are: Apogee, Perigee, Inclination (degrees), Period (minutes)
    
    lines = text.split('\n')
    current_reg = None
    
    for line in lines:
        # Match registration number pattern at start of line
        reg_match = re.match(r'^(\d{4})-(\d{4})-(\d{3})\s', line)
        
        if reg_match:
            reg_num = f"{reg_match.group(1)}-{reg_match.group(2)}-{reg_match.group(3)}"
            
            # Extract orbital parameters from the same line
            # Look for sequence of 4 numbers separated by spaces
            # Pattern: date ... number number number number (followed by text)
            orbital_pattern = r'\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)'
            
            # Simpler approach: look for 4 consecutive numbers that look like orbital params
            # After the date (which has a number, space, some text, space, 4 numbers)
            # Match: (number) (number) (number) (number) where they're orbital parameters
            
            # Split to find the numbers after the date
            parts = line.split()
            
            try:
                # Find the date part and look for numbers after it
                # Format is usually: REG-NUM, Object Name, Date, Apogee, Perigee, Inclination, Period, ...
                
                # Count backwards from the orbital parameters - they should be 4 consecutive numbers
                for i in range(len(parts) - 4):
                    try:
                        a = float(parts[i].replace(',', '.'))
                        p = float(parts[i+1].replace(',', '.'))
                        inc = float(parts[i+2].replace(',', '.'))
                        per = float(parts[i+3].replace(',', '.'))
                        
                        # Sanity checks
                        if 0 <= a <= 50000 and 0 <= p <= 50000 and 0 <= inc <= 180 and 0 <= per <= 2000:
                            params[reg_num] = {
                                'Apogee (km)': a,
                                'Perigee (km)': p,
                                'Inclination (degrees)': inc,
                                'Period (minutes)': per
                            }
                            break
                    except:
                        pass
            except:
                pass
    
    return params

def extract_params_from_pdf_text_v2(text):
    """More robust extraction using line-by-line parsing"""
    params = {}
    
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        # Match registration number at start of line
        reg_match = re.match(r'^(\d{4})-(\d{4})-(\d{3})\s+', line)
        
        if reg_match:
            reg_num = f"{reg_match.group(1)}-{reg_match.group(2)}-{reg_match.group(3)}"
            
            # Pattern: REG-NUM ObjectName ... Date (Apogee Perigee Inclination Period) ...
            # Look for date pattern (e.g. "3 July 2025" or "25 July 2025")
            # followed by numbers that match orbital parameters
            
            date_pattern = r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})'
            date_match = re.search(date_pattern, line)
            
            if date_match:
                # Find all numbers after the date
                after_date_pos = date_match.end()
                after_date = line[after_date_pos:]
                
                # Extract numbers from the part after date
                numbers = re.findall(r'[\d.]+', after_date)
                
                # First 4 consecutive numbers should be orbital parameters
                if len(numbers) >= 4:
                    try:
                        a = float(numbers[0].replace(',', '.'))
                        p = float(numbers[1].replace(',', '.'))
                        inc = float(numbers[2].replace(',', '.'))
                        per = float(numbers[3].replace(',', '.'))
                        
                        # Check if they're in valid ranges
                        if (0 < a <= 50000 and 
                            0 < p <= 50000 and 
                            0 <= inc <= 180 and 
                            0 < per <= 2000 and
                            a >= p):  # Apogee should be >= Perigee
                            
                            params[reg_num] = {
                                'Apogee (km)': a,
                                'Perigee (km)': p,
                                'Inclination (degrees)': inc,
                                'Period (minutes)': per
                            }
                    except ValueError:
                        pass
    
    return params

# Extract orbital parameters from PDFs
extracted_params = {}
processed_docs = set()

for ser_e_num in sorted(known_urls.keys(), reverse=True):
    if ser_e_num in processed_docs:
        continue
    
    pdf_url = known_urls[ser_e_num]
    reg_numbers = doc_to_reg.get(ser_e_num, [])
    
    print(f"\nProcessing SER.E/{ser_e_num}")
    print(f"  URL: {pdf_url}")
    print(f"  Objects to find: {len(reg_numbers)}")
    
    try:
        response = requests.get(pdf_url, timeout=15)
        if response.status_code == 200:
            print(f"  ✓ Downloaded PDF ({len(response.content)} bytes)")
            
            try:
                pdf_file = io.BytesIO(response.content)
                with pdfplumber.open(pdf_file) as pdf:
                    full_text = ""
                    
                    # Extract text from all pages
                    for page in pdf.pages:
                        full_text += page.extract_text() + "\n"
                    
                    # Parse the text
                    page_params = extract_params_from_pdf_text_v2(full_text)
                    extracted_params.update(page_params)
                    
                    print(f"  ✓ Extracted {len(page_params)} orbital parameter sets")
                    
                    # Show sample
                    if page_params:
                        sample_reg = list(page_params.keys())[0]
                        sample_params = page_params[sample_reg]
                        print(f"    Sample: {sample_reg}")
                        for k, v in sample_params.items():
                            print(f"      {k}: {v}")
            
            except Exception as e:
                print(f"    ✗ Error parsing PDF: {str(e)[:100]}")
        else:
            print(f"  ✗ HTTP {response.status_code}")
    
    except Exception as e:
        print(f"  ✗ Error downloading: {str(e)[:100]}")
    
    processed_docs.add(ser_e_num)

print(f"\n{'='*60}")
print(f"✓ Extracted orbital parameters for {len(extracted_params)} objects")

# Update CSV with extracted parameters
updated_count = 0
for idx, row in df.iterrows():
    reg_num = str(row['Registration Number']).strip()
    if reg_num in extracted_params:
        params = extracted_params[reg_num]
        for param_name, param_value in params.items():
            df.at[idx, param_name] = param_value
        updated_count += 1

df.to_csv("unoosa_registry.csv", index=False)
print(f"✓ Updated {updated_count} records in unoosa_registry.csv")

# Summary statistics
print(f"\nOrbital Parameter Coverage:")
for col in ['Apogee (km)', 'Perigee (km)', 'Inclination (degrees)', 'Period (minutes)']:
    count = df[col].notna().sum()
    pct = 100 * count / len(df)
    print(f"  {col}: {count}/{len(df)} ({pct:.1f}%)")
