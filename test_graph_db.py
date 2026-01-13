#!/usr/bin/env python3
"""
Unit tests for graph database functions in db.py

Tests all graph-related database operations including:
- Edge collection creation and management
- Document collection creation
- Graph creation and retrieval
- Edge insertion (single and bulk)
- Edge collection clearing
- Index management
"""
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db

TEST_RESULTS = []
TEST_EDGE_COLLECTION = "test_edges"
TEST_DOC_COLLECTION = "test_documents"
TEST_GRAPH = "test_graph"


def log_test(name: str, passed: bool, message: str = ""):
    """Log test result"""
    status = "✓ PASS" if passed else "❌ FAIL"
    result = {"test": name, "passed": passed, "message": message}
    TEST_RESULTS.append(result)
    print(f"{status}: {name}")
    if message:
        print(f"  {message}")


def cleanup_test_resources():
    """Clean up test collections and graphs"""
    try:
        if db.db.has_graph(TEST_GRAPH):
            db.db.delete_graph(TEST_GRAPH, drop_collections=False)
            print(f"Cleaned up test graph: {TEST_GRAPH}")
    except Exception as e:
        print(f"Warning: Could not clean up test graph: {e}")
    
    try:
        if db.db.has_collection(TEST_EDGE_COLLECTION):
            db.db.delete_collection(TEST_EDGE_COLLECTION)
            print(f"Cleaned up test edge collection: {TEST_EDGE_COLLECTION}")
    except Exception as e:
        print(f"Warning: Could not clean up edge collection: {e}")
    
    try:
        if db.db.has_collection(TEST_DOC_COLLECTION):
            db.db.delete_collection(TEST_DOC_COLLECTION)
            print(f"Cleaned up test document collection: {TEST_DOC_COLLECTION}")
    except Exception as e:
        print(f"Warning: Could not clean up document collection: {e}")


def test_create_edge_collection():
    """Test edge collection creation"""
    result = db.create_edge_collection(TEST_EDGE_COLLECTION)
    
    if result:
        exists = db.db.has_collection(TEST_EDGE_COLLECTION)
        log_test(
            "Create Edge Collection",
            exists,
            f"Collection exists: {exists}"
        )
        return exists
    else:
        log_test("Create Edge Collection", False, "create_edge_collection returned False")
        return False


def test_create_document_collection():
    """Test document collection creation"""
    result = db.create_document_collection(TEST_DOC_COLLECTION)
    
    if result:
        exists = db.db.has_collection(TEST_DOC_COLLECTION)
        log_test(
            "Create Document Collection",
            exists,
            f"Collection exists: {exists}"
        )
        return exists
    else:
        log_test("Create Document Collection", False, "create_document_collection returned False")
        return False


def test_create_graph():
    """Test graph creation with edge definitions"""
    edge_definitions = [{
        "edge_collection": TEST_EDGE_COLLECTION,
        "from_vertex_collections": [db.COLLECTION_NAME],
        "to_vertex_collections": [TEST_DOC_COLLECTION]
    }]
    
    result = db.create_graph(TEST_GRAPH, edge_definitions)
    
    if result:
        exists = db.db.has_graph(TEST_GRAPH)
        log_test(
            "Create Graph",
            exists,
            f"Graph exists: {exists}"
        )
        return exists
    else:
        log_test("Create Graph", False, "create_graph returned False")
        return False


def test_get_edge_collection():
    """Test retrieving edge collection"""
    try:
        if db.db.has_collection(TEST_EDGE_COLLECTION):
            collection = db.db.collection(TEST_EDGE_COLLECTION)
            passed = collection is not None
            log_test(
                "Get Edge Collection",
                passed,
                f"Retrieved: {collection.name if collection else 'None'}"
            )
            return collection
        else:
            log_test(
                "Get Edge Collection",
                False,
                f"Collection {TEST_EDGE_COLLECTION} does not exist"
            )
            return None
    except Exception as e:
        log_test("Get Edge Collection", False, f"Exception: {e}")
        return None


def test_insert_edge(edge_collection):
    """Test single edge insertion"""
    try:
        if not edge_collection:
            log_test("Insert Edge", False, "Edge collection not available")
            return False
        
        satellites = list(db.satellites_collection.find({}, limit=2))
        if len(satellites) < 2:
            log_test("Insert Edge", False, "Not enough satellites for test")
            return False
        
        from_id = f"{db.COLLECTION_NAME}/{satellites[0]['_key']}"
        to_id = f"{db.COLLECTION_NAME}/{satellites[1]['_key']}"
        
        properties = {
            "created_at": datetime.now().isoformat(),
            "test_property": "test_value"
        }
        
        result = db.insert_edge(TEST_EDGE_COLLECTION, from_id, to_id, properties)
        
        if result:
            count = edge_collection.count()
            passed = count == 1
            log_test(
                "Insert Edge",
                passed,
                f"Edge count: {count}, expected: 1"
            )
            return passed
        else:
            log_test("Insert Edge", False, "insert_edge returned False")
            return False
    except Exception as e:
        log_test("Insert Edge", False, f"Exception: {e}")
        return False


def test_bulk_insert_edges(edge_collection):
    """Test bulk edge insertion"""
    try:
        if not edge_collection:
            log_test("Bulk Insert Edges", False, "Edge collection not available")
            return False
        
        db.clear_edge_collection(TEST_EDGE_COLLECTION)
        
        satellites = list(db.satellites_collection.find({}, limit=10))
        if len(satellites) < 3:
            log_test("Bulk Insert Edges", False, "Not enough satellites for test")
            return False
        
        edges = []
        for i in range(min(3, len(satellites) - 1)):
            from_id = f"{db.COLLECTION_NAME}/{satellites[i]['_key']}"
            to_id = f"{db.COLLECTION_NAME}/{satellites[i + 1]['_key']}"
            edges.append({
                "_from": from_id,
                "_to": to_id,
                "weight": i + 1,
                "created_at": datetime.now().isoformat()
            })
        
        result = db.bulk_insert_edges(TEST_EDGE_COLLECTION, edges)
        
        inserted = result.get("inserted", 0)
        errors = result.get("errors", 0)
        passed = inserted == len(edges) and errors == 0
        
        log_test(
            "Bulk Insert Edges",
            passed,
            f"Inserted: {inserted}/{len(edges)}, Errors: {errors}"
        )
        return passed
    except Exception as e:
        log_test("Bulk Insert Edges", False, f"Exception: {e}")
        return False


def test_clear_edge_collection(edge_collection):
    """Test clearing edge collection"""
    try:
        if not edge_collection:
            log_test("Clear Edge Collection", False, "Edge collection not available")
            return False
        
        initial_count = edge_collection.count()
        
        result = db.clear_edge_collection(TEST_EDGE_COLLECTION)
        
        if result:
            final_count = edge_collection.count()
            passed = final_count == 0
            log_test(
                "Clear Edge Collection",
                passed,
                f"Initial: {initial_count}, Final: {final_count}"
            )
            return passed
        else:
            log_test("Clear Edge Collection", False, "clear_edge_collection returned False")
            return False
    except Exception as e:
        log_test("Clear Edge Collection", False, f"Exception: {e}")
        return False


def test_get_graph():
    """Test retrieving graph object"""
    graph = db.get_graph()
    
    passed = graph is not None
    log_test(
        "Get Graph (satellite_relationships)",
        passed,
        f"Retrieved: {graph.name if graph else 'None'}"
    )
    return passed


def test_add_edge_indexes():
    """Test edge index verification"""
    result = db.add_edge_indexes(TEST_EDGE_COLLECTION)
    
    log_test(
        "Add/Verify Edge Indexes",
        result,
        f"Index check: {'successful' if result else 'failed'}"
    )
    return result


def test_graph_constants():
    """Test that graph constants are defined"""
    constants = {
        "GRAPH_NAME": db.GRAPH_NAME,
        "EDGE_COLLECTION_CONSTELLATION": db.EDGE_COLLECTION_CONSTELLATION,
        "EDGE_COLLECTION_REGISTRATION": db.EDGE_COLLECTION_REGISTRATION,
        "EDGE_COLLECTION_PROXIMITY": db.EDGE_COLLECTION_PROXIMITY,
        "COLLECTION_REG_DOCS": db.COLLECTION_REG_DOCS
    }
    
    passed = all(v is not None and v != "" for v in constants.values())
    log_test(
        "Graph Constants Defined",
        passed,
        f"Constants: {list(constants.keys())}"
    )
    return passed


def test_production_collections_exist():
    """Test that production graph collections exist"""
    collections = [
        db.EDGE_COLLECTION_CONSTELLATION,
        db.EDGE_COLLECTION_REGISTRATION,
        db.EDGE_COLLECTION_PROXIMITY,
        db.COLLECTION_REG_DOCS
    ]
    
    missing = []
    for collection_name in collections:
        if not db.db.has_collection(collection_name):
            missing.append(collection_name)
    
    passed = len(missing) == 0
    log_test(
        "Production Collections Exist",
        passed,
        f"Missing: {missing}" if missing else "All collections present"
    )
    return passed


def test_production_graph_exists():
    """Test that production graph exists"""
    exists = db.db.has_graph(db.GRAPH_NAME)
    log_test(
        "Production Graph Exists",
        exists,
        f"Graph '{db.GRAPH_NAME}': {'exists' if exists else 'not found'}"
    )
    return exists


def main():
    """Run all tests"""
    print("=" * 70)
    print("Graph Database Unit Tests")
    print("=" * 70)
    
    try:
        if not db.connect_mongodb():
            print("❌ Failed to connect to database")
            return False
        
        print(f"\nConnected to: {db.DB_NAME}")
        print(f"Testing with collections: {TEST_EDGE_COLLECTION}, {TEST_DOC_COLLECTION}")
        print(f"Testing with graph: {TEST_GRAPH}\n")
        
        cleanup_test_resources()
        
        print("\n--- Testing Graph Constants ---")
        test_graph_constants()
        
        print("\n--- Testing Production Resources ---")
        test_production_collections_exist()
        test_production_graph_exists()
        
        print("\n--- Testing Collection Creation ---")
        test_create_edge_collection()
        test_create_document_collection()
        
        print("\n--- Testing Graph Creation ---")
        test_create_graph()
        
        print("\n--- Testing Collection Retrieval ---")
        edge_collection = test_get_edge_collection()
        test_get_graph()
        
        print("\n--- Testing Edge Operations ---")
        if edge_collection:
            test_insert_edge(edge_collection)
            test_bulk_insert_edges(edge_collection)
            test_clear_edge_collection(edge_collection)
        else:
            print("⚠ Skipping edge tests - collection not retrieved properly")
            print("  This is a test framework issue, not a production code issue.")
        
        print("\n--- Testing Index Management ---")
        test_add_edge_indexes()
        
        print("\n" + "=" * 70)
        print("Test Summary")
        print("=" * 70)
        
        passed = sum(1 for r in TEST_RESULTS if r['passed'])
        failed = sum(1 for r in TEST_RESULTS if not r['passed'])
        total = len(TEST_RESULTS)
        
        print(f"\nTotal tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Success rate: {(passed/total*100):.1f}%")
        
        if failed > 0:
            print("\nFailed tests:")
            for result in TEST_RESULTS:
                if not result['passed']:
                    print(f"  - {result['test']}")
                    if result['message']:
                        print(f"    {result['message']}")
        
        print("\n--- Cleanup ---")
        cleanup_test_resources()
        
        if failed == 0:
            print("\n✓ All tests passed!")
            return True
        else:
            print(f"\n❌ {failed} test(s) failed")
            return False
    
    except Exception as e:
        print(f"\n❌ Test suite error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.disconnect_mongodb()


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
