#!/usr/bin/env python3
"""
Direct test of graph API endpoints (without HTTP server).
"""
import sys
from api import get_graph_stats, get_constellation_graph, get_registration_document_graph
import db as db_module

def test_direct():
    """Test endpoints by calling functions directly"""
    
    print("=" * 60)
    print("Direct Graph Endpoint Tests")
    print("=" * 60)
    
    print("\nTest 1: Graph Stats")
    print("=" * 60)
    try:
        result = get_graph_stats()
        print(f"✓ get_graph_stats() returned successfully")
        print(f"  Nodes: {result['data']['nodes']}")
        print(f"  Edges: {result['data']['edges']}")
        print(f"  Constellations: {len(result['data']['constellations'])}")
        for const in result['data']['constellations'][:3]:
            print(f"    - {const['name']}: {const['member_count']} members")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n\nTest 2: Constellation Graph (OneWeb, limited)")
    print("=" * 60)
    try:
        result = get_constellation_graph("OneWeb", limit=10)
        print(f"✓ get_constellation_graph('OneWeb', limit=10) returned successfully")
        print(f"  Constellation: {result['data']['constellation']}")
        print(f"  Total satellites: {result['data']['stats']['total_satellites']}")
        print(f"  Nodes: {len(result['data']['nodes'])}")
        print(f"  Edges: {len(result['data']['edges'])}")
        if result['data']['hub']:
            print(f"  Hub: {result['data']['hub']['identifier']}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n\nTest 3: Registration Document Graph")
    print("=" * 60)
    try:
        result = get_registration_document_graph("_osoindex_data_documents_gb_st_stsgser_e1020_html")
        print(f"✓ get_registration_document_graph() returned successfully")
        if result['data']['registration_document']:
            print(f"  Document: {result['data']['registration_document']['url']}")
            print(f"  Total nodes: {result['data']['stats']['total_nodes']}")
            print(f"  Satellites: {result['data']['stats']['satellites']}")
        else:
            print(f"  ⚠ Document not found (this is ok for testing)")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print("✓ All direct function calls successful!")
    print("\nNote: The HTTP server needs to be restarted to serve these endpoints.")
    print("Restart command: pkill -f uvicorn && uvicorn api:app --host 127.0.0.1 --port 8000")
    return True

if __name__ == "__main__":
    if not db_module.connect_mongodb():
        print("❌ Failed to connect to ArangoDB")
        sys.exit(1)
    
    success = test_direct()
    db_module.disconnect_mongodb()
    sys.exit(0 if success else 1)
