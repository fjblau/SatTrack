#!/usr/bin/env python3
"""
Test script for graph API endpoints.
"""
import requests
import json
import subprocess
import time
import signal
import os

API_BASE = "http://localhost:8000"
TEST_RESULTS = []

def test_endpoint(name, url, expected_keys=None):
    """Test an API endpoint"""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"URL: {url}")
    print(f"{'='*60}")
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"\nResponse keys: {list(data.keys())}")
            
            if 'data' in data:
                if isinstance(data['data'], dict):
                    print(f"Data keys: {list(data['data'].keys())}")
                    
                    if expected_keys:
                        missing = [k for k in expected_keys if k not in data['data']]
                        if missing:
                            print(f"❌ Missing expected keys: {missing}")
                            TEST_RESULTS.append({"test": name, "status": "FAIL", "reason": f"Missing keys: {missing}"})
                            return False
                    
                    if 'stats' in data['data']:
                        print(f"Stats: {json.dumps(data['data']['stats'], indent=2)}")
                    
                    if 'nodes' in data['data']:
                        print(f"Nodes count: {len(data['data']['nodes'])}")
                        if data['data']['nodes']:
                            print(f"Sample node: {json.dumps(data['data']['nodes'][0], indent=2)}")
                    
                    if 'edges' in data['data']:
                        print(f"Edges count: {len(data['data']['edges'])}")
                        if data['data']['edges']:
                            print(f"Sample edge: {json.dumps(data['data']['edges'][0], indent=2)}")
                
                print(f"\n✓ Test passed: {name}")
                TEST_RESULTS.append({"test": name, "status": "PASS"})
                return True
            else:
                print(f"❌ Response missing 'data' key")
                TEST_RESULTS.append({"test": name, "status": "FAIL", "reason": "Missing data key"})
                return False
        else:
            print(f"❌ HTTP {response.status_code}")
            print(f"Response: {response.text[:200]}")
            TEST_RESULTS.append({"test": name, "status": "FAIL", "reason": f"HTTP {response.status_code}"})
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        TEST_RESULTS.append({"test": name, "status": "FAIL", "reason": str(e)})
        return False


def main():
    """Run API tests"""
    print("=" * 60)
    print("Graph API Endpoint Tests")
    print("=" * 60)
    
    print("\nChecking if API is running...")
    try:
        response = requests.get(f"{API_BASE}/v2/health", timeout=2)
        if response.status_code == 200:
            print("✓ API is running")
        else:
            print("❌ API health check failed")
            print("Please start the API server first:")
            print("  uvicorn api:app --reload")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        print("Please start the API server first:")
        print("  uvicorn api:app --reload")
        return False
    
    test_endpoint(
        "Graph Stats",
        f"{API_BASE}/v2/graphs/stats",
        expected_keys=['nodes', 'edges', 'constellations', 'graph_name']
    )
    
    test_endpoint(
        "Starlink Gen 1 Constellation (limited)",
        f"{API_BASE}/v2/graphs/constellation/Starlink Gen 1?limit=50",
        expected_keys=['constellation', 'hub', 'nodes', 'edges', 'stats']
    )
    
    test_endpoint(
        "OneWeb Constellation (limited)",
        f"{API_BASE}/v2/graphs/constellation/OneWeb?limit=20",
        expected_keys=['constellation', 'hub', 'nodes', 'edges', 'stats']
    )
    
    test_endpoint(
        "Glonass Constellation (full)",
        f"{API_BASE}/v2/graphs/constellation/Glonass",
        expected_keys=['constellation', 'hub', 'nodes', 'edges', 'stats']
    )
    
    test_endpoint(
        "Registration Document",
        f"{API_BASE}/v2/graphs/registration-document/_osoindex_data_documents_gb_st_stsgser_e1020_html",
        expected_keys=['registration_document', 'nodes', 'edges', 'stats']
    )
    
    test_endpoint(
        "Non-existent Constellation",
        f"{API_BASE}/v2/graphs/constellation/FakeConstellation",
        expected_keys=['constellation', 'nodes', 'edges', 'stats']
    )
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for r in TEST_RESULTS if r['status'] == 'PASS')
    failed = sum(1 for r in TEST_RESULTS if r['status'] == 'FAIL')
    
    print(f"\nTotal tests: {len(TEST_RESULTS)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed > 0:
        print("\nFailed tests:")
        for result in TEST_RESULTS:
            if result['status'] == 'FAIL':
                print(f"  - {result['test']}: {result.get('reason', 'Unknown')}")
    
    if failed == 0:
        print("\n✓ All tests passed!")
        return True
    else:
        print(f"\n❌ {failed} test(s) failed")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
