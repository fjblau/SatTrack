#!/usr/bin/env python3
"""
Restore Railway production database from backup.
"""
import os
import json
from arango import ArangoClient
from pathlib import Path

RAILWAY_HOST = os.getenv("RAILWAY_HOST", "https://arangodb-production-d6fb.up.railway.app:443")
RAILWAY_PASSWORD = os.getenv("RAILWAY_PASSWORD")
DB_NAME = "kessler"

EDGE_COLLECTIONS = [
    "constellation_membership",
    "registration_links", 
    "orbital_proximity",
    "collision_risk_edges"
]

def restore_backup(backup_dir):
    if not RAILWAY_PASSWORD:
        print("Error: RAILWAY_PASSWORD environment variable not set")
        return False
    
    print(f"Restoring Railway database from backup: {backup_dir}")
    print(f"Host: {RAILWAY_HOST}")
    print()
    
    try:
        client = ArangoClient(hosts=RAILWAY_HOST)
        db = client.db(DB_NAME, username='root', password=RAILWAY_PASSWORD)
        
        print(f"✓ Connected to database: {DB_NAME}\n")
        
        backup_path = Path(backup_dir)
        if not backup_path.exists():
            print(f"Error: Backup directory '{backup_dir}' not found")
            return False
        
        # Load metadata
        metadata_file = backup_path / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            print(f"Backup metadata:")
            print(f"  Timestamp: {metadata['timestamp']}")
            print(f"  Total documents: {metadata['total_documents']:,}")
            print(f"  Collections: {len(metadata['collections'])}")
            print()
        
        jsonl_files = list(backup_path.glob("*.jsonl"))
        if not jsonl_files:
            print(f"Error: No .jsonl files found in '{backup_dir}'")
            return False
        
        print(f"Found {len(jsonl_files)} collections to restore\n")
        
        total_restored = 0
        
        for file_path in sorted(jsonl_files):
            collection_name = file_path.stem
            is_edge = collection_name in EDGE_COLLECTIONS
            
            print(f"{'='*60}")
            print(f"Restoring: {collection_name}")
            print(f"Type: {'Edge' if is_edge else 'Document'}")
            
            # Clear existing collection
            if db.has_collection(collection_name):
                print(f"  Clearing existing collection...")
                collection = db.collection(collection_name)
                collection.truncate()
            else:
                print(f"  Creating collection...")
                db.create_collection(collection_name, edge=is_edge)
            
            collection = db.collection(collection_name)
            
            # Count documents in backup
            with open(file_path, 'r') as f:
                doc_count = sum(1 for _ in f)
            
            print(f"  Documents to restore: {doc_count:,}")
            
            # Import in batches
            batch_size = 1000
            restored = 0
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
                                restored += len(batch)
                                if restored % 5000 == 0:
                                    print(f"    Progress: {restored:,}/{doc_count:,}")
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
                        restored += len(batch)
                    except Exception as e:
                        print(f"    Final batch error: {e}")
                        errors += len(batch)
            
            print(f"  ✓ Restored: {restored:,} documents")
            if errors > 0:
                print(f"  ⚠ Errors: {errors}")
            
            total_restored += restored
        
        print(f"\n{'='*60}")
        print(f"Restore Complete!")
        print(f"{'='*60}")
        print(f"Total documents restored: {total_restored:,}")
        
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
    import sys
    
    backup_dir = sys.argv[1] if len(sys.argv) > 1 else "railway_backup_20260217_175713"
    
    print("="*60)
    print("Railway Database Restore Script")
    print("="*60)
    print()
    print(f"⚠️  WARNING: This will REPLACE all data in the Railway database!")
    print(f"⚠️  Backup directory: {backup_dir}")
    print()
    
    response = input("Are you sure you want to proceed? (yes/no): ")
    if response.lower() != 'yes':
        print("Restore cancelled.")
        sys.exit(0)
    
    success = restore_backup(backup_dir)
    exit(0 if success else 1)
