import pandas as pd
import requests
import re
import time

print("Discovering UN document URLs for SER.E series...")

df = pd.read_csv("unoosa_registry.csv")

# Extract all unique SER.E numbers
doc_ids = set()
for idx, row in df.iterrows():
    doc_url = str(row['Registration Document']).strip() if pd.notna(row['Registration Document']) else ""
    if doc_url:
        match = re.search(r'stsgser\.e(\d+)', doc_url, re.IGNORECASE)
        if match:
            doc_ids.add(match.group(1))

doc_ids = sorted(list(doc_ids), reverse=True)
print(f"Found {len(doc_ids)} unique SER.E numbers")
print(f"SER.E range: {doc_ids[0]} to {doc_ids[-1]}")

# Try to search for these documents on the UN website
# The documents.un.org site allows searching by document symbol/number
found_urls = {}

for ser_e_num in doc_ids[:20]:  # Start with first 20
    # Try searching for the document
    search_url = f"https://documents.un.org/api/v1/search?query=ST/SG/SER.E/{ser_e_num}&language=EN"
    
    try:
        print(f"\nSearching for SER.E/{ser_e_num}...", end=" ")
        response = requests.get(search_url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('results'):
                for result in data['results']:
                    if 'pdf_url' in result or 'url' in result:
                        url = result.get('pdf_url') or result.get('url')
                        if url:
                            print(f"✓ Found")
                            found_urls[ser_e_num] = url
                            print(f"  {url}")
                            break
                else:
                    print(f"No PDF URL in results")
            else:
                print(f"No results")
        else:
            print(f"HTTP {response.status_code}")
    except Exception as e:
        print(f"Error: {str(e)[:50]}")
    
    time.sleep(0.5)  # Rate limit

print(f"\n\nFound URLs for {len(found_urls)} documents")
if found_urls:
    print("\nMapping:")
    for ser_e_num, url in sorted(found_urls.items()):
        print(f"  {ser_e_num}: {url}")
