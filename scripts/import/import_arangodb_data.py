#!/usr/bin/env python3
"""
Import satellite data from MongoDB JSON export to ArangoDB.
"""
import json
from datetime import datetime
from arango import ArangoClient
from arango.exceptions import DocumentInsertError
import os

ARANGO_HOST = os.getenv("ARANGO_HOST", "http://localhost:8529")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "kessler_dev_password")
DB_NAME = "kessler"
COLLECTION_NAME = "satellites"

def import_data(json_file="mongodb_export.json"):
    """Import data from JSON file to ArangoDB"""
    print("Connecting to ArangoDB...")
    client = ArangoClient(hosts=ARANGO_HOST)
    
    try:
        sys_db = client.db('_system', username=ARANGO_USER, password=ARANGO_PASSWORD)
        
        if not sys_db.has_database(DB_NAME):
            sys_db.create_database(DB_NAME)
            print(f"✓ Created database: {DB_NAME}")
        
        db = client.db(DB_NAME, username=ARANGO_USER, password=ARANGO_PASSWORD)
        
        if not db.has_collection(COLLECTION_NAME):
            collection = db.create_collection(COLLECTION_NAME)
            print(f"✓ Created collection: {COLLECTION_NAME}")
        else:
            collection = db.collection(COLLECTION_NAME)
        
        print(f"✓ Connected to ArangoDB: {DB_NAME}.{COLLECTION_NAME}")
        
        print(f"\nLoading data from {json_file}...")
        with open(json_file, 'r') as f:
            documents = json.load(f)
        
        print(f"Found {len(documents):,} documents to import")
        
        imported_count = 0
        error_count = 0
        batch_size = 500
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            batch_docs = []
            
            for doc in batch:
                if '_id' in doc:
                    del doc['_id']
                
                if 'identifier' in doc:
                    doc['_key'] = (doc['identifier']
                                   .replace('/', '_')
                                   .replace(':', '_')
                                   .replace('.', '_')
                                   .replace('*', '_STAR_')
                                   .replace(' ', '_')
                                   .replace('(', '_')
                                   .replace(')', '_'))
                
                batch_docs.append(doc)
            
            try:
                result = collection.import_bulk(batch_docs, on_duplicate="replace")
                imported_count += len(batch_docs)
                print(f"  Imported batch {i//batch_size + 1}/{(len(documents) + batch_size - 1)//batch_size}: {len(batch_docs)} documents", end='\r')
            except Exception as e:
                print(f"\n  ✗ Error importing batch: {e}")
                error_count += len(batch_docs)
        
        print(f"\n\n✓ Import complete!")
        print(f"  Successfully imported: {imported_count:,} documents")
        if error_count > 0:
            print(f"  Errors: {error_count:,} documents")
        
        actual_count = collection.count()
        print(f"  Total documents in collection: {actual_count:,}")
        
        print("\nCreating indexes...")
        try:
            collection.add_persistent_index(fields=['canonical.international_designator'], unique=False)
            collection.add_persistent_index(fields=['canonical.registration_number'], unique=False)
            collection.add_persistent_index(fields=['identifier'], unique=True)
            print("✓ Indexes created successfully")
        except Exception as e:
            print(f"  Note: Some indexes may already exist: {e}")
        
        print("\nSample document:")
        sample = collection.random()
        if sample:
            print(f"  identifier: {sample.get('identifier', 'N/A')}")
            print(f"  sources: {list(sample.get('sources', {}).keys())}")
            print(f"  canonical fields: {len(sample.get('canonical', {}))}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        client.close()

if __name__ == "__main__":
    success = import_data()
    exit(0 if success else 1)
