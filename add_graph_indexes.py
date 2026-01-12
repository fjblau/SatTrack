#!/usr/bin/env python3
"""
Add indexes to edge collections for better graph traversal performance.
"""
import sys
import db as db_module

def add_graph_indexes():
    """Add indexes to all edge collections"""
    
    print("=" * 60)
    print("Add Graph Indexes")
    print("=" * 60)
    
    if not db_module.connect_mongodb():
        print("❌ Failed to connect to ArangoDB")
        return False
    
    print(f"\n✓ Connected to database: {db_module.DB_NAME}")
    
    edge_collections = [
        db_module.EDGE_COLLECTION_CONSTELLATION,
        db_module.EDGE_COLLECTION_REGISTRATION,
        db_module.EDGE_COLLECTION_PROXIMITY
    ]
    
    print("\nAdding indexes to edge collections...")
    print("(Indexes: _from, _to for traversal performance)\n")
    
    success = True
    for edge_coll in edge_collections:
        if not db_module.add_edge_indexes(edge_coll):
            success = False
            print(f"❌ Failed to add indexes to: {edge_coll}")
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    if success:
        print("✓ All edge collections indexed successfully!")
        print("\nIndexes added:")
        for edge_coll in edge_collections:
            print(f"  - {edge_coll}: _from, _to")
        print("\nGraph queries will now have improved performance.")
    else:
        print("❌ Some index operations failed.")
    
    db_module.disconnect_mongodb()
    return success

if __name__ == "__main__":
    success = add_graph_indexes()
    sys.exit(0 if success else 1)
