#!/usr/bin/env python3
"""
Analyze registration document data in the satellite collection.
"""
import sys
import db as db_module
from collections import Counter

def analyze_registration_docs():
    """Analyze registration documents in satellite data"""
    
    if not db_module.connect_mongodb():
        print("Failed to connect to ArangoDB")
        return False
    
    db = db_module.db
    
    print("=" * 60)
    print("Registration Document Analysis")
    print("=" * 60)
    
    query = """
    FOR doc IN @@collection
        FILTER doc.canonical.registration_document != null
        RETURN {
            identifier: doc.identifier,
            registration_document: doc.canonical.registration_document,
            registration_number: doc.canonical.registration_number,
            country: doc.canonical.country_of_origin,
            name: doc.canonical.name
        }
    """
    
    cursor = db.aql.execute(
        query,
        bind_vars={'@collection': db_module.COLLECTION_NAME}
    )
    
    satellites_with_reg_doc = list(cursor)
    
    print(f"\nTotal satellites with registration_document: {len(satellites_with_reg_doc):,}")
    
    if len(satellites_with_reg_doc) == 0:
        print("\nNo registration documents found in the dataset.")
        db_module.disconnect_mongodb()
        return True
    
    reg_doc_counter = Counter(sat['registration_document'] for sat in satellites_with_reg_doc)
    
    print(f"\nUnique registration documents: {len(reg_doc_counter):,}")
    
    print("\nTop 20 registration documents by satellite count:")
    for reg_doc, count in reg_doc_counter.most_common(20):
        print(f"  {reg_doc}: {count} satellites")
    
    print("\nSample satellites with registration documents:")
    for sat in satellites_with_reg_doc[:10]:
        print(f"  {sat['identifier']}: {sat['name']}")
        print(f"    Reg Doc: {sat['registration_document']}")
        print(f"    Reg Number: {sat['registration_number']}")
        print(f"    Country: {sat['country']}")
    
    country_counter = Counter(sat['country'] for sat in satellites_with_reg_doc if sat['country'])
    print(f"\nCountries with registered satellites (top 10):")
    for country, count in country_counter.most_common(10):
        print(f"  {country}: {count} satellites")
    
    db_module.disconnect_mongodb()
    return True

if __name__ == "__main__":
    success = analyze_registration_docs()
    sys.exit(0 if success else 1)
