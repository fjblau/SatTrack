import pandas as pd
import requests
import re
import time

print("Discovering UN document URLs for SER.E series...")

df = pd.read_csv("unoosa_registry.csv")

# Extract unique SER.E numbers
doc_ids = set()
for idx, row in df.iterrows():
    doc_url = str(row['Registration Document']).strip() if pd.notna(row['Registration Document']) else ""
    if doc_url:
        match = re.search(r'stsgser\.e(\d+)', doc_url, re.IGNORECASE)
        if match:
            doc_ids.add(match.group(1))

doc_ids = sorted(list(doc_ids), reverse=True)
print(f"Found {len(doc_ids)} unique SER.E numbers")
print(f"Range: SER.E/{doc_ids[0]} to SER.E/{doc_ids[-1]}")

# Search for documents
found_urls = {}

# Try searching the UN documents API
print("\nSearching UN documents system...")

for ser_e_num in doc_ids[:50]:  # Start with top 50
    # Try direct search
    search_term = f"ST/SG/SER.E/{ser_e_num}"
    
    try:
        # Try documents.un.org search API
        url = f"https://documents.un.org/api/v1/search"
        params = {
            "query": search_term,
            "language": "EN",
            "pageSize": 5
        }
        
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('documents'):
                for doc in data['documents']:
                    if 'pdf' in doc.get('url', '').lower():
                        found_urls[ser_e_num] = doc['url']
                        print(f"  ✓ SER.E/{ser_e_num}: {doc['url'][:80]}...")
                        break
            elif data.get('results'):
                # Try alternate path
                for result in data['results']:
                    if 'url' in result and 'pdf' in result['url'].lower():
                        found_urls[ser_e_num] = result['url']
                        print(f"  ✓ SER.E/{ser_e_num}: {result['url'][:80]}...")
                        break
    
    except Exception as e:
        pass
    
    time.sleep(0.3)  # Rate limit

print(f"\n\nFound {len(found_urls)} document URLs")

# Save mapping
if found_urls:
    print("\nURL Mapping (add to scrape_orbital_params.py):")
    print("known_urls = {")
    for ser_e_num in sorted(found_urls.keys()):
        print(f'    "{ser_e_num}": "{found_urls[ser_e_num]}",')
    print("}")
    
    # Also save to JSON file
    import json
    with open("un_document_urls.json", "w") as f:
        json.dump(found_urls, f, indent=2)
    print("\nSaved to un_document_urls.json")
