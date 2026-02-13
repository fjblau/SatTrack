#!/usr/bin/env python3
"""
Integration tests for centrality analysis API endpoints.

Tests the /v2/graphs/analytics/centrality endpoint with various
configurations including caching, error handling, and different metrics.
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


class TestCentralityAPI:
    """Test centrality analysis endpoints"""
    
    def test_degree_centrality_basic(self, api_available):
        """Test degree centrality calculation"""
        url = f"{API_BASE}/v2/graphs/analytics/centrality"
        params = {"metric": "degree", "limit": 10}
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        assert "timestamp" in data
        assert "cached" in data
        
        response_data = data["data"]
        assert "metric" in response_data
        assert response_data["metric"] == "degree"
        assert "satellites" in response_data
        assert "count" in response_data
        assert "parameters" in response_data
        
        assert isinstance(response_data["satellites"], list)
        assert response_data["count"] == len(response_data["satellites"])
        
        if len(response_data["satellites"]) > 0:
            sat = response_data["satellites"][0]
            assert "_id" in sat
            assert "identifier" in sat
            assert "name" in sat
            assert "degree" in sat
            assert "inbound" in sat
            assert "outbound" in sat
    
    def test_betweenness_centrality_basic(self, api_available):
        """Test betweenness centrality calculation"""
        url = f"{API_BASE}/v2/graphs/analytics/centrality"
        params = {
            "metric": "betweenness",
            "limit": 10,
            "sample_size": 50
        }
        
        response = requests.get(url, params=params, timeout=60)
        
        assert response.status_code == 200
        data = response.json()
        
        response_data = data["data"]
        assert response_data["metric"] == "betweenness"
        assert "satellites" in response_data
        assert "parameters" in response_data
        assert response_data["parameters"]["sample_size"] == 50
        
        if len(response_data["satellites"]) > 0:
            sat = response_data["satellites"][0]
            assert "betweenness_centrality" in sat
            assert "normalized_score" in sat
    
    def test_closeness_centrality_basic(self, api_available):
        """Test closeness centrality calculation"""
        url = f"{API_BASE}/v2/graphs/analytics/centrality"
        params = {
            "metric": "closeness",
            "limit": 10,
            "max_depth": 3
        }
        
        response = requests.get(url, params=params, timeout=60)
        
        assert response.status_code == 200
        data = response.json()
        
        response_data = data["data"]
        assert response_data["metric"] == "closeness"
        assert "satellites" in response_data
        assert "parameters" in response_data
        assert response_data["parameters"]["max_depth"] == 3
        
        if len(response_data["satellites"]) > 0:
            sat = response_data["satellites"][0]
            assert "closeness_centrality" in sat
            assert "reachable_nodes" in sat
            assert "avg_distance" in sat
    
    def test_centrality_with_edge_types(self, api_available):
        """Test centrality calculation with specific edge types"""
        url = f"{API_BASE}/v2/graphs/analytics/centrality"
        params = {
            "metric": "degree",
            "edge_types": ["constellation_membership"],
            "limit": 10
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        response_data = data["data"]
        assert response_data["parameters"]["edge_types"] == ["constellation_membership"]
    
    def test_centrality_caching(self, api_available):
        """Test that centrality queries are cached correctly"""
        url = f"{API_BASE}/v2/graphs/analytics/centrality"
        params = {"metric": "degree", "limit": 5}
        
        response1 = requests.get(url, params=params, timeout=30)
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["cached"] == False
        
        time.sleep(0.1)
        
        response2 = requests.get(url, params=params, timeout=30)
        assert response2.status_code == 200
        data2 = response2.json()
        
        assert data2["cached"] == True
        assert data1["data"]["satellites"] == data2["data"]["satellites"]
    
    def test_centrality_cache_stats(self, api_available):
        """Test centrality cache statistics endpoint"""
        url = f"{API_BASE}/v2/graphs/analytics/centrality/cache/stats"
        
        response = requests.get(url, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        stats = data["data"]
        
        assert "name" in stats
        assert stats["name"] == "centrality_queries"
        assert "size" in stats
        assert "max_size" in stats
        assert "ttl" in stats
        assert stats["ttl"] == 86400
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats
    
    def test_invalid_metric(self, api_available):
        """Test error handling for invalid metric"""
        url = f"{API_BASE}/v2/graphs/analytics/centrality"
        params = {"metric": "invalid_metric"}
        
        response = requests.get(url, params=params, timeout=10)
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "invalid" in data["detail"].lower()
    
    def test_limit_validation(self, api_available):
        """Test limit parameter validation"""
        url = f"{API_BASE}/v2/graphs/analytics/centrality"
        
        response = requests.get(f"{url}?metric=degree&limit=0", timeout=10)
        assert response.status_code == 422
        
        response = requests.get(f"{url}?metric=degree&limit=300", timeout=10)
        assert response.status_code == 422
        
        response = requests.get(f"{url}?metric=degree&limit=50", timeout=30)
        assert response.status_code == 200
    
    def test_sample_size_validation(self, api_available):
        """Test sample_size parameter validation for betweenness"""
        url = f"{API_BASE}/v2/graphs/analytics/centrality"
        
        response = requests.get(f"{url}?metric=betweenness&sample_size=5", timeout=10)
        assert response.status_code == 422
        
        response = requests.get(f"{url}?metric=betweenness&sample_size=600", timeout=10)
        assert response.status_code == 422
        
        response = requests.get(f"{url}?metric=betweenness&sample_size=50", timeout=60)
        assert response.status_code == 200
    
    def test_max_depth_validation(self, api_available):
        """Test max_depth parameter validation for closeness"""
        url = f"{API_BASE}/v2/graphs/analytics/centrality"
        
        response = requests.get(f"{url}?metric=closeness&max_depth=0", timeout=10)
        assert response.status_code == 422
        
        response = requests.get(f"{url}?metric=closeness&max_depth=15", timeout=10)
        assert response.status_code == 422
        
        response = requests.get(f"{url}?metric=closeness&max_depth=3", timeout=60)
        assert response.status_code == 200
    
    def test_response_structure_degree(self, api_available):
        """Test response structure for degree centrality"""
        url = f"{API_BASE}/v2/graphs/analytics/centrality"
        params = {"metric": "degree", "limit": 5}
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        assert "timestamp" in data
        assert "cached" in data
        
        response_data = data["data"]
        assert "metric" in response_data
        assert "satellites" in response_data
        assert "count" in response_data
        assert "parameters" in response_data
        
        params = response_data["parameters"]
        assert "edge_types" in params
        assert "limit" in params
        assert params["limit"] == 5
    
    def test_different_limits(self, api_available):
        """Test centrality with different limit values"""
        url = f"{API_BASE}/v2/graphs/analytics/centrality"
        
        for limit in [5, 10, 20, 50]:
            params = {"metric": "degree", "limit": limit}
            response = requests.get(url, params=params, timeout=30)
            
            assert response.status_code == 200
            data = response.json()
            
            satellites = data["data"]["satellites"]
            assert len(satellites) <= limit
    
    def test_sorting_order(self, api_available):
        """Test that results are sorted by centrality score descending"""
        url = f"{API_BASE}/v2/graphs/analytics/centrality"
        params = {"metric": "degree", "limit": 10}
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        satellites = data["data"]["satellites"]
        
        if len(satellites) > 1:
            for i in range(len(satellites) - 1):
                assert satellites[i]["degree"] >= satellites[i + 1]["degree"]


def main():
    """Run tests manually (for non-pytest execution)"""
    print("=" * 60)
    print("Centrality Analysis API Integration Tests")
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
    
    test_suite = TestCentralityAPI()
    
    tests = [
        ("Degree centrality - basic", test_suite.test_degree_centrality_basic),
        ("Betweenness centrality - basic", test_suite.test_betweenness_centrality_basic),
        ("Closeness centrality - basic", test_suite.test_closeness_centrality_basic),
        ("Centrality with edge types", test_suite.test_centrality_with_edge_types),
        ("Centrality caching", test_suite.test_centrality_caching),
        ("Centrality cache stats", test_suite.test_centrality_cache_stats),
        ("Invalid metric", test_suite.test_invalid_metric),
        ("Limit validation", test_suite.test_limit_validation),
        ("Sample size validation", test_suite.test_sample_size_validation),
        ("Max depth validation", test_suite.test_max_depth_validation),
        ("Response structure - degree", test_suite.test_response_structure_degree),
        ("Different limits", test_suite.test_different_limits),
        ("Sorting order", test_suite.test_sorting_order),
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
