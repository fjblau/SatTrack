#!/usr/bin/env python3
"""
Integration tests for path finding API endpoints.

Tests the /v2/graphs/paths/{from_id}/{to_id} endpoint with various
configurations including caching, error handling, and different algorithms.
"""
import requests
import time
import pytest

API_BASE = "http://localhost:8000"


@pytest.fixture(scope="module")
def api_available():
    """Check if API is available before running tests"""
    try:
        response = requests.get(f"{API_BASE}/v2/health", timeout=2)
        return response.status_code == 200
    except Exception:
        pytest.skip("API server not available")


class TestPathFinding:
    """Test path finding endpoints"""
    
    def test_shortest_path_basic(self, api_available):
        """Test finding shortest path between two satellites"""
        url = f"{API_BASE}/v2/graphs/paths/2020-001A/2020-002A"
        
        response = requests.get(url, timeout=10)
        
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            assert "data" in data
            assert "timestamp" in data
            assert "cached" in data
            
            response_data = data["data"]
            assert "from_id" in response_data
            assert "to_id" in response_data
            assert "path_found" in response_data
            
            if response_data["path_found"]:
                assert "path" in response_data
                assert "vertices" in response_data["path"]
                assert "edges" in response_data["path"]
                assert "distance" in response_data["path"]
    
    def test_shortest_path_with_full_id(self, api_available):
        """Test shortest path with full document IDs"""
        url = f"{API_BASE}/v2/graphs/paths/satellites/2020-001A/satellites/2020-002A"
        
        response = requests.get(url, timeout=10)
        
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert data["data"]["from_id"] == "satellites/2020-001A"
            assert data["data"]["to_id"] == "satellites/2020-002A"
    
    def test_shortest_path_with_max_depth(self, api_available):
        """Test shortest path with custom max depth"""
        url = f"{API_BASE}/v2/graphs/paths/2020-001A/2020-002A?max_depth=5"
        
        response = requests.get(url, timeout=10)
        
        assert response.status_code in [200, 404]
    
    def test_shortest_path_with_edge_types(self, api_available):
        """Test shortest path with specific edge types"""
        url = f"{API_BASE}/v2/graphs/paths/2020-001A/2020-002A"
        params = {
            "edge_types": ["constellation_membership", "orbital_proximity"]
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        assert response.status_code in [200, 404]
    
    def test_all_paths_algorithm(self, api_available):
        """Test finding all paths between two satellites"""
        url = f"{API_BASE}/v2/graphs/paths/2020-001A/2020-002A"
        params = {
            "algorithm": "all",
            "max_depth": 3
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            response_data = data["data"]
            
            assert "algorithm" in response_data
            assert response_data["algorithm"] == "all"
            
            if response_data["path_found"]:
                assert "paths" in response_data
                assert "path_count" in response_data
                assert isinstance(response_data["paths"], list)
                assert response_data["path_count"] == len(response_data["paths"])
    
    def test_path_caching(self, api_available):
        """Test that path queries are cached correctly"""
        url = f"{API_BASE}/v2/graphs/paths/2020-001A/2020-002A?max_depth=5"
        
        response1 = requests.get(url, timeout=10)
        assert response1.status_code in [200, 404]
        
        if response1.status_code == 200:
            data1 = response1.json()
            assert data1["cached"] == False
            
            time.sleep(0.1)
            
            response2 = requests.get(url, timeout=10)
            assert response2.status_code == 200
            data2 = response2.json()
            
            assert data2["cached"] == True
            assert data1["data"] == data2["data"]
    
    def test_cache_stats_endpoint(self, api_available):
        """Test path cache statistics endpoint"""
        url = f"{API_BASE}/v2/graphs/paths/cache/stats"
        
        response = requests.get(url, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        stats = data["data"]
        
        assert "name" in stats
        assert stats["name"] == "path_queries"
        assert "size" in stats
        assert "max_size" in stats
        assert "ttl" in stats
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats
    
    def test_invalid_satellite_id(self, api_available):
        """Test error handling for invalid satellite IDs"""
        url = f"{API_BASE}/v2/graphs/paths/INVALID-ID-999/ANOTHER-INVALID-999"
        
        response = requests.get(url, timeout=10)
        
        assert response.status_code in [404, 500]
    
    def test_missing_satellite_id(self, api_available):
        """Test error handling for missing satellite IDs"""
        url = f"{API_BASE}/v2/graphs/paths//2020-002A"
        
        response = requests.get(url, timeout=10)
        
        assert response.status_code in [400, 404]
    
    def test_invalid_algorithm(self, api_available):
        """Test error handling for invalid algorithm parameter"""
        url = f"{API_BASE}/v2/graphs/paths/2020-001A/2020-002A"
        params = {"algorithm": "invalid_algorithm"}
        
        response = requests.get(url, params=params, timeout=10)
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "invalid" in data["detail"].lower()
    
    def test_max_depth_validation(self, api_available):
        """Test max_depth parameter validation"""
        url = f"{API_BASE}/v2/graphs/paths/2020-001A/2020-002A"
        
        response = requests.get(f"{url}?max_depth=0", timeout=10)
        assert response.status_code == 422
        
        response = requests.get(f"{url}?max_depth=25", timeout=10)
        assert response.status_code == 422
        
        response = requests.get(f"{url}?max_depth=10", timeout=10)
        assert response.status_code in [200, 404]
    
    def test_response_structure_shortest(self, api_available):
        """Test response structure for shortest path algorithm"""
        url = f"{API_BASE}/v2/graphs/paths/2020-001A/2020-002A?algorithm=shortest"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            assert "data" in data
            assert "timestamp" in data
            assert "cached" in data
            
            response_data = data["data"]
            assert "from_id" in response_data
            assert "to_id" in response_data
            assert "path_found" in response_data
            assert isinstance(response_data["path_found"], bool)
            
            if response_data["path_found"]:
                assert "path" in response_data
                assert "algorithm" in response_data
                assert response_data["algorithm"] == "shortest"
    
    def test_response_structure_all_paths(self, api_available):
        """Test response structure for all paths algorithm"""
        url = f"{API_BASE}/v2/graphs/paths/2020-001A/2020-002A?algorithm=all&max_depth=3"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            response_data = data["data"]
            assert "from_id" in response_data
            assert "to_id" in response_data
            assert "path_found" in response_data
            assert "paths" in response_data
            assert "path_count" in response_data
            assert "algorithm" in response_data
            assert response_data["algorithm"] == "all"
            assert isinstance(response_data["paths"], list)


def main():
    """Run tests manually (for non-pytest execution)"""
    print("=" * 60)
    print("Path Finding API Integration Tests")
    print("=" * 60)
    
    try:
        response = requests.get(f"{API_BASE}/v2/health", timeout=2)
        if response.status_code != 200:
            print("❌ API health check failed")
            return False
        print("✓ API is running\n")
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        return False
    
    test_suite = TestPathFinding()
    
    tests = [
        ("Shortest path - basic", test_suite.test_shortest_path_basic),
        ("Shortest path - with full ID", test_suite.test_shortest_path_with_full_id),
        ("Shortest path - with max depth", test_suite.test_shortest_path_with_max_depth),
        ("Shortest path - with edge types", test_suite.test_shortest_path_with_edge_types),
        ("All paths algorithm", test_suite.test_all_paths_algorithm),
        ("Path caching", test_suite.test_path_caching),
        ("Cache stats endpoint", test_suite.test_cache_stats_endpoint),
        ("Invalid satellite ID", test_suite.test_invalid_satellite_id),
        ("Invalid algorithm", test_suite.test_invalid_algorithm),
        ("Max depth validation", test_suite.test_max_depth_validation),
        ("Response structure - shortest", test_suite.test_response_structure_shortest),
        ("Response structure - all paths", test_suite.test_response_structure_all_paths),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            print(f"Testing: {test_name}...", end=" ")
            test_func(None)
            print("✓ PASS")
            passed += 1
        except AssertionError as e:
            print(f"❌ FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ ERROR: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Tests passed: {passed}/{len(tests)}")
    print(f"Tests failed: {failed}/{len(tests)}")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
