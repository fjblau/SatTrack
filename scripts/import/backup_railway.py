#!/usr/bin/env python3
"""
Backup Railway production database before deployment.
"""
import json
import os
from arango import ArangoClient
from datetime import datetime

RAILWAY_HOST = os.getenv("RAILWAY_HOST", "https://arangodb-production-d6fb.up.railway.app:443")
RAILWAY_PASSWORD = os.getenv("RAILWAY_PASSWORD")
DB_NAME = "kessler"

def backup_production():
    if not RAILWAY_PASSWORD:
        print("Error: RAILWAY_PASSWORD environment variable not set")
        return False
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"railway_backup_{timestamp}"
    
    print(f"Backing up Railway production database")
    print(f"Host: {RAILWAY_HOST}")
    print(f"Backup directory: {backup_dir}/\n")
    
    try:
        client = ArangoClient(hosts=RAILWAY_HOST)
        db = client.db(DB_NAME, username='root', password=RAILWAY_PASSWORD)
        
        print(f"✓ Connected to database: {DB_NAME}\n")
        
        collections = [c['name'] for c in db.collections() if not c['name'].startswith('_')]
        
        print(f"Found {len(collections)} collections to backup\n")
        
        os.makedirs(backup_dir, exist_ok=True)
        
        total_docs = 0
        
        for collection_name in collections:
            collection = db.collection(collection_name)
            count = collection.count()
            
            if count == 0:
                print(f"  {collection_name}: 0 documents (skipped)")
                continue
            
            print(f"  {collection_name}: Backing up {count:,} documents...")
            
            output_file = f"{backup_dir}/{collection_name}.jsonl"
            exported = 0
            
            with open(output_file, 'w') as f:
                cursor = db.aql.execute(f"""
                    FOR doc IN {collection_name}
                    RETURN doc
                """, batch_size=1000)
                
                for doc in cursor:
                    if '_rev' in doc:
                        del doc['_rev']
                    
                    f.write(json.dumps(doc) + '\n')
                    exported += 1
                    
                    if exported % 5000 == 0:
                        print(f"    {exported:,}/{count:,}...")
            
            print(f"  ✓ {collection_name}: {exported:,} documents")
            total_docs += exported
        
        print(f"\n{'='*60}")
        print(f"Backup Complete!")
        print(f"{'='*60}")
        print(f"Total documents backed up: {total_docs:,}")
        print(f"Backup directory: {backup_dir}/")
        
        # Save metadata
        metadata = {
            "timestamp": timestamp,
            "host": RAILWAY_HOST,
            "database": DB_NAME,
            "total_documents": total_docs,
            "collections": collections
        }
        
        with open(f"{backup_dir}/metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"\nMetadata saved: {backup_dir}/metadata.json")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = backup_production()
    exit(0 if success else 1)
