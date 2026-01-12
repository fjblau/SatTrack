#!/usr/bin/env python3
"""
Migration script to create graph structure in ArangoDB.

Creates:
- Edge collections: constellation_membership, registration_links, orbital_proximity
- Document collection: registration_documents
- Named graph: satellite_relationships
"""
import sys
import db as db_module

def migrate_graph_structure():
    """Create graph collections and named graph"""
    
    print("=" * 60)
    print("Graph Structure Migration")
    print("=" * 60)
    
    if not db_module.connect_mongodb():
        print("❌ Failed to connect to ArangoDB")
        return False
    
    print(f"\n✓ Connected to database: {db_module.DB_NAME}")
    
    success = True
    
    print("\n" + "=" * 60)
    print("Step 1: Create Edge Collections")
    print("=" * 60)
    
    edge_collections = [
        db_module.EDGE_COLLECTION_CONSTELLATION,
        db_module.EDGE_COLLECTION_REGISTRATION,
        db_module.EDGE_COLLECTION_PROXIMITY
    ]
    
    for edge_coll in edge_collections:
        if not db_module.create_edge_collection(edge_coll):
            success = False
            print(f"❌ Failed to create edge collection: {edge_coll}")
        else:
            print(f"✓ Edge collection ready: {edge_coll}")
    
    print("\n" + "=" * 60)
    print("Step 2: Create Document Collections")
    print("=" * 60)
    
    if not db_module.create_document_collection(db_module.COLLECTION_REG_DOCS):
        success = False
        print(f"❌ Failed to create document collection: {db_module.COLLECTION_REG_DOCS}")
    else:
        print(f"✓ Document collection ready: {db_module.COLLECTION_REG_DOCS}")
    
    print("\n" + "=" * 60)
    print("Step 3: Create Named Graph")
    print("=" * 60)
    
    edge_definitions = [
        {
            "edge_collection": db_module.EDGE_COLLECTION_CONSTELLATION,
            "from_vertex_collections": [db_module.COLLECTION_NAME],
            "to_vertex_collections": [db_module.COLLECTION_NAME]
        },
        {
            "edge_collection": db_module.EDGE_COLLECTION_REGISTRATION,
            "from_vertex_collections": [db_module.COLLECTION_NAME],
            "to_vertex_collections": [db_module.COLLECTION_REG_DOCS]
        },
        {
            "edge_collection": db_module.EDGE_COLLECTION_PROXIMITY,
            "from_vertex_collections": [db_module.COLLECTION_NAME],
            "to_vertex_collections": [db_module.COLLECTION_NAME]
        }
    ]
    
    if not db_module.create_graph(db_module.GRAPH_NAME, edge_definitions):
        success = False
        print(f"❌ Failed to create graph: {db_module.GRAPH_NAME}")
    else:
        print(f"✓ Named graph ready: {db_module.GRAPH_NAME}")
        print(f"\n  Graph definition:")
        print(f"    - Vertex collections: {db_module.COLLECTION_NAME}, {db_module.COLLECTION_REG_DOCS}")
        print(f"    - Edge collections: {', '.join(edge_collections)}")
    
    print("\n" + "=" * 60)
    print("Migration Summary")
    print("=" * 60)
    
    if success:
        print("✓ All graph structures created successfully!")
        print("\nYou can now:")
        print("  1. Populate constellation_membership edges")
        print("  2. Populate registration_links edges")
        print("  3. Calculate and populate orbital_proximity edges")
        print("  4. Query the graph using AQL traversals")
    else:
        print("❌ Some operations failed. Check logs above.")
    
    db_module.disconnect_mongodb()
    return success

if __name__ == "__main__":
    success = migrate_graph_structure()
    sys.exit(0 if success else 1)
