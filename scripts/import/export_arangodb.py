#!/usr/bin/env python3
"""
Export ArangoDB data to JSONL format for cloud migration.
Creates one file per collection for easier import.
"""
import json
from arango import ArangoClient
import os

# Local ArangoDB connection
ARANGO_HOST = os.getenv("ARANGO_HOST", "http://localhost:8529")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "kessler_dev_password")
DB_NAME = "kessler"

def export_collection(db, collection_name, output_file):
    """Export a single collection to JSONL file"""
    try:
        collection = db.collection(collection_name)
        count = collection.count()
        
        if count == 0:
            print(f"  {collection_name}: 0 documents (skipped)")
            return 0
        
        print(f"  {collection_name}: Exporting {count:,} documents...")
        
        # Export in batches to handle large collections
        batch_size = 1000
        exported = 0
        
        with open(output_file, 'w') as f:
            cursor = db.aql.execute(f"""
                FOR doc IN {collection_name}
                RETURN doc
            """, batch_size=batch_size)
            
            for doc in cursor:
                # Remove _rev field (not needed for import)
                if '_rev' in doc:
                    del doc['_rev']
                
                # Write as JSONL (one JSON object per line)
                f.write(json.dumps(doc) + '\n')
                exported += 1
                
                if exported % 1000 == 0:
                    print(f"    Exported {exported:,}/{count:,}...")
        
        print(f"  ✓ {collection_name}: {exported:,} documents → {output_file}")
        return exported
        
    except Exception as e:
        print(f"  ✗ {collection_name}: Error - {e}")
        return 0


def export_database():
    """Export all collections from ArangoDB"""
    print(f"Connecting to ArangoDB: {ARANGO_HOST}")
    
    try:
        client = ArangoClient(hosts=ARANGO_HOST)
        db = client.db(DB_NAME, username=ARANGO_USER, password=ARANGO_PASSWORD)
        
        print(f"✓ Connected to database: {DB_NAME}\n")
        
        # Get all collections (excluding system collections)
        collections = [c['name'] for c in db.collections() if not c['name'].startswith('_')]
        
        print(f"Found {len(collections)} collections:\n")
        
        total_docs = 0
        export_dir = "arango_export"
        os.makedirs(export_dir, exist_ok=True)
        
        for collection_name in collections:
            output_file = f"{export_dir}/{collection_name}.jsonl"
            count = export_collection(db, collection_name, output_file)
            total_docs += count
        
        print(f"\n{'='*60}")
        print(f"Export Complete!")
        print(f"{'='*60}")
        print(f"Total documents exported: {total_docs:,}")
        print(f"Output directory: {export_dir}/")
        print(f"\nFiles created:")
        for collection_name in collections:
            output_file = f"{export_dir}/{collection_name}.jsonl"
            if os.path.exists(output_file):
                size = os.path.getsize(output_file) / (1024 * 1024)  # MB
                print(f"  - {collection_name}.jsonl ({size:.2f} MB)")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = export_database()
    
    if success:
        print("\n" + "="*60)
        print("Next Steps:")
        print("="*60)
        print("1. Sign up at https://cloud.arangodb.com (free tier)")
        print("2. Create a new deployment (Free tier, select nearest region)")
        print("3. Create database named 'kessler'")
        print("4. Import data:")
        print("   - Go to your deployment → Import")
        print("   - Upload each .jsonl file to its collection")
        print("   - Or use arangoimport CLI (faster for large datasets)")
        print("\nCLI Import command (after installing arangodb3-client):")
        print("  for file in arango_export/*.jsonl; do")
        print("    collection=$(basename $file .jsonl)")
        print("    arangoimport \\")
        print("      --server.endpoint https://YOUR-INSTANCE.arangodb.cloud:8529 \\")
        print("      --server.username root \\")
        print("      --server.password YOUR_PASSWORD \\")
        print("      --server.database kessler \\")
        print("      --collection $collection \\")
        print("      --type jsonl \\")
        print("      --file $file")
        print("  done")
    
    exit(0 if success else 1)
