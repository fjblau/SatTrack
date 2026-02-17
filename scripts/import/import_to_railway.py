#!/usr/bin/env python3
"""
Import exported ArangoDB data to Railway instance.
"""
import os
import json
from arango import ArangoClient
from pathlib import Path

RAILWAY_HOST = os.getenv("RAILWAY_HOST", "https://arangodb-production-d6fb.up.railway.app:443")
RAILWAY_PASSWORD = os.getenv("RAILWAY_PASSWORD")
DB_NAME = "kessler"
EXPORT_DIR = "arango_export"

EDGE_COLLECTIONS = [
    "constellation_membership",
    "registration_links", 
    "orbital_proximity",
    "collision_risk_edges"
]

def import_data():
    if not RAILWAY_PASSWORD:
        print("Error: RAILWAY_PASSWORD environment variable not set")
        print("Run: export RAILWAY_PASSWORD='your-password'")
        return False
    
    print(f"Connecting to Railway ArangoDB: {RAILWAY_HOST}")
    
    try:
        client = ArangoClient(hosts=RAILWAY_HOST)
        db = client.db(DB_NAME, username='root', password=RAILWAY_PASSWORD)
        
        print(f"✓ Connected to database: {DB_NAME}\n")
        
        export_path = Path(EXPORT_DIR)
        if not export_path.exists():
            print(f"Error: Export directory '{EXPORT_DIR}' not found")
            return False
        
        jsonl_files = list(export_path.glob("*.jsonl"))
        if not jsonl_files:
            print(f"Error: No .jsonl files found in '{EXPORT_DIR}'")
            return False
        
        print(f"Found {len(jsonl_files)} collections to import\n")
        
        total_imported = 0
        
        for file_path in sorted(jsonl_files):
            collection_name = file_path.stem
            is_edge = collection_name in EDGE_COLLECTIONS
            
            print(f"{'='*60}")
            print(f"Collection: {collection_name}")
            print(f"Type: {'Edge' if is_edge else 'Document'}")
            print(f"File: {file_path.name}")
            
            # Create collection if it doesn't exist
            if not db.has_collection(collection_name):
                print(f"  Creating collection...")
                db.create_collection(collection_name, edge=is_edge)
            else:
                print(f"  Collection exists")
            
            collection = db.collection(collection_name)
            
            # Count documents in file
            with open(file_path, 'r') as f:
                doc_count = sum(1 for _ in f)
            
            print(f"  Documents to import: {doc_count:,}")
            
            # Import in batches
            batch_size = 1000
            imported = 0
            errors = 0
            
            with open(file_path, 'r') as f:
                batch = []
                
                for line_num, line in enumerate(f, 1):
                    try:
                        doc = json.loads(line.strip())
                        batch.append(doc)
                        
                        if len(batch) >= batch_size:
                            try:
                                result = collection.import_bulk(batch, on_duplicate='replace')
                                imported += len(batch)
                                if imported % 5000 == 0:
                                    print(f"    Progress: {imported:,}/{doc_count:,}")
                                batch = []
                            except Exception as e:
                                print(f"    Batch error: {e}")
                                errors += len(batch)
                                batch = []
                    
                    except json.JSONDecodeError as e:
                        print(f"    Line {line_num}: JSON parse error - {e}")
                        errors += 1
                
                # Import remaining batch
                if batch:
                    try:
                        result = collection.import_bulk(batch, on_duplicate='replace')
                        imported += len(batch)
                    except Exception as e:
                        print(f"    Final batch error: {e}")
                        errors += len(batch)
            
            print(f"  ✓ Imported: {imported:,} documents")
            if errors > 0:
                print(f"  ⚠ Errors: {errors}")
            
            total_imported += imported
        
        print(f"\n{'='*60}")
        print(f"Import Complete!")
        print(f"{'='*60}")
        print(f"Total documents imported: {total_imported:,}")
        
        # Verify counts
        print(f"\nCollection counts:")
        for file_path in sorted(jsonl_files):
            collection_name = file_path.stem
            count = db.collection(collection_name).count()
            print(f"  {collection_name}: {count:,}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("="*60)
    print("Railway ArangoDB Import Script")
    print("="*60)
    print()
    
    success = import_data()
    exit(0 if success else 1)
