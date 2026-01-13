#!/usr/bin/env python3
"""
Verify registration document network with graph traversal queries.
"""
import sys
import db as db_module

def verify_registration_network():
    """Verify registration document network"""
    
    print("=" * 60)
    print("Registration Document Network Verification")
    print("=" * 60)
    
    if not db_module.connect_mongodb():
        print("❌ Failed to connect to ArangoDB")
        return False
    
    db = db_module.db
    all_passed = True
    
    print("\n" + "=" * 60)
    print("Test 1: Verify Collection Counts")
    print("=" * 60)
    
    reg_docs_count = db.collection(db_module.COLLECTION_REG_DOCS).count()
    edges_count = db.collection(db_module.EDGE_COLLECTION_REGISTRATION).count()
    
    print(f"Registration documents: {reg_docs_count:,}")
    print(f"Registration edges: {edges_count:,}")
    
    if reg_docs_count == 0:
        print("❌ No registration documents found")
        all_passed = False
    else:
        print(f"✓ {reg_docs_count:,} registration documents created")
    
    if edges_count == 0:
        print("❌ No registration edges found")
        all_passed = False
    else:
        print(f"✓ {edges_count:,} registration edges created")
    
    print("\n" + "=" * 60)
    print("Test 2: Query Registration Document with Most Satellites")
    print("=" * 60)
    
    query = """
    FOR doc IN @@reg_docs
        SORT doc.satellite_count DESC
        LIMIT 1
        RETURN doc
    """
    
    cursor = db.aql.execute(
        query,
        bind_vars={'@reg_docs': db_module.COLLECTION_REG_DOCS}
    )
    top_doc = list(cursor)
    
    if top_doc:
        doc = top_doc[0]
        print(f"✓ Top registration document: {doc['url']}")
        print(f"  Satellites: {doc['satellite_count']}")
        print(f"  Countries: {', '.join(doc['countries'])}")
    else:
        print("❌ Failed to query top registration document")
        all_passed = False
    
    print("\n" + "=" * 60)
    print("Test 3: Graph Traversal - Find Satellites by Registration Doc")
    print("=" * 60)
    
    if top_doc:
        doc_id = f"{db_module.COLLECTION_REG_DOCS}/{top_doc[0]['_key']}"
        
        query = """
        FOR v, e, p IN 1..1 INBOUND @doc_id
        @@edge_collection
        LIMIT 10
        RETURN {
            identifier: v.identifier,
            name: v.canonical.name,
            country: v.canonical.country_of_origin
        }
        """
        
        cursor = db.aql.execute(
            query,
            bind_vars={
                'doc_id': doc_id,
                '@edge_collection': db_module.EDGE_COLLECTION_REGISTRATION
            }
        )
        satellites = list(cursor)
        
        if satellites:
            print(f"✓ Found {len(satellites)} satellites linked to registration document")
            print(f"\nSample satellites:")
            for sat in satellites[:5]:
                print(f"  - {sat['identifier']}: {sat['name']} ({sat['country']})")
        else:
            print("❌ No satellites found for registration document")
            all_passed = False
    
    print("\n" + "=" * 60)
    print("Test 4: Reverse Traversal - Find Registration Doc for Satellite")
    print("=" * 60)
    
    query = """
    FOR sat IN @@satellites
        FILTER sat.canonical.registration_document != null
        LIMIT 1
        RETURN sat
    """
    
    cursor = db.aql.execute(
        query,
        bind_vars={'@satellites': db_module.COLLECTION_NAME}
    )
    sample_sat = list(cursor)
    
    if sample_sat:
        sat_id = f"{db_module.COLLECTION_NAME}/{sample_sat[0]['_key']}"
        
        query = """
        FOR v, e, p IN 1..1 OUTBOUND @sat_id
        @@edge_collection
        RETURN v
        """
        
        cursor = db.aql.execute(
            query,
            bind_vars={
                'sat_id': sat_id,
                '@edge_collection': db_module.EDGE_COLLECTION_REGISTRATION
            }
        )
        reg_docs = list(cursor)
        
        if reg_docs:
            print(f"✓ Found registration document for satellite {sample_sat[0]['identifier']}")
            print(f"  URL: {reg_docs[0]['url']}")
            print(f"  Satellite count: {reg_docs[0]['satellite_count']}")
        else:
            print("❌ No registration document found for satellite")
            all_passed = False
    
    print("\n" + "=" * 60)
    print("Test 5: Named Graph Traversal")
    print("=" * 60)
    
    if sample_sat:
        sat_id = f"{db_module.COLLECTION_NAME}/{sample_sat[0]['_key']}"
        
        query = f"""
        FOR v, e, p IN 1..1 OUTBOUND @sat_id
        GRAPH '{db_module.GRAPH_NAME}'
        FILTER IS_SAME_COLLECTION(@reg_docs_collection, v)
        RETURN v
        """
        
        cursor = db.aql.execute(
            query,
            bind_vars={
                'sat_id': sat_id,
                'reg_docs_collection': db_module.COLLECTION_REG_DOCS
            }
        )
        results = list(cursor)
        
        if results:
            print(f"✓ Named graph traversal successful")
            print(f"  Found registration document via graph: {results[0]['url']}")
        else:
            print("❌ Named graph traversal failed")
            all_passed = False
    
    print("\n" + "=" * 60)
    print("Verification Summary")
    print("=" * 60)
    
    if all_passed:
        print("✓ All verification tests passed!")
        print("\nRegistration document network statistics:")
        print(f"  - {reg_docs_count:,} unique registration documents")
        print(f"  - {edges_count:,} satellite-to-document links")
        print(f"  - Graph traversals working correctly")
        print(f"\nGraph is ready for use!")
    else:
        print("❌ Some verification tests failed")
    
    db_module.disconnect_mongodb()
    return all_passed

if __name__ == "__main__":
    success = verify_registration_network()
    sys.exit(0 if success else 1)
