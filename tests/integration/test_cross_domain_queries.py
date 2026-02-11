#!/usr/bin/env python3
"""
Integration tests for cross-domain graph query endpoints.

Tests the multi-dimensional graph queries that combine multiple edge types:
- /v2/graphs/cross-constellation-proximity
- /v2/graphs/country-cooperation-network
- /v2/graphs/function-clusters
"""
import requests
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


class TestCrossConstellationProximity:
    """Test cross-constellation proximity endpoint"""
    
    def test_basic_query(self, api_available):
        """Test basic cross-constellation proximity query"""
        url = f"{API_BASE}/v2/graphs/cross-constellation-proximity"
        
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        assert "timestamp" in data
        
        result = data["data"]
        assert "nodes" in result
        assert "edges" in result
        assert "stats" in result
        
        assert isinstance(result["nodes"], list)
        assert isinstance(result["edges"], list)
        assert isinstance(result["stats"], dict)
    
    def test_with_limit_parameter(self, api_available):
        """Test cross-constellation proximity with custom limit"""
        url = f"{API_BASE}/v2/graphs/cross-constellation-proximity?limit=50"
        
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        result = data["data"]
        if result["edges"]:
            assert len(result["edges"]) <= 50
    
    def test_with_proximity_threshold(self, api_available):
        """Test cross-constellation proximity with threshold"""
        url = f"{API_BASE}/v2/graphs/cross-constellation-proximity"
        params = {"proximity_threshold": 0.8, "limit": 100}
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        result = data["data"]
        if result["edges"]:
            for edge in result["edges"]:
                assert edge["proximity_score"] >= 0.8
    
    def test_response_structure(self, api_available):
        """Test response structure for cross-constellation proximity"""
        url = f"{API_BASE}/v2/graphs/cross-constellation-proximity?limit=10"
        
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        result = data["data"]
        stats = result["stats"]
        
        assert "total_satellites" in stats
        assert "total_proximity_pairs" in stats
        assert "constellation_pairs" in stats
        assert "top_constellation_pairs" in stats
        
        if result["nodes"]:
            node = result["nodes"][0]
            assert "id" in node
            assert "identifier" in node
            assert "name" in node
            assert "constellation" in node
            assert "orbital_band" in node
        
        if result["edges"]:
            edge = result["edges"][0]
            assert "source" in edge
            assert "target" in edge
            assert "proximity_score" in edge
            assert "constellation_from" in edge
            assert "constellation_to" in edge
            assert edge["constellation_from"] != edge["constellation_to"]
    
    def test_limit_validation(self, api_available):
        """Test limit parameter validation"""
        url = f"{API_BASE}/v2/graphs/cross-constellation-proximity"
        
        response = requests.get(f"{url}?limit=0", timeout=10)
        assert response.status_code == 422
        
        response = requests.get(f"{url}?limit=600", timeout=10)
        assert response.status_code == 422
        
        response = requests.get(f"{url}?limit=100", timeout=30)
        assert response.status_code == 200


class TestCountryCooperationNetwork:
    """Test country cooperation network endpoint"""
    
    def test_basic_query(self, api_available):
        """Test basic country cooperation network query"""
        url = f"{API_BASE}/v2/graphs/country-cooperation-network"
        
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        assert "timestamp" in data
        
        result = data["data"]
        assert "nodes" in result
        assert "edges" in result
        assert "stats" in result
        
        assert isinstance(result["nodes"], list)
        assert isinstance(result["edges"], list)
        assert isinstance(result["stats"], dict)
    
    def test_with_limit_parameter(self, api_available):
        """Test country cooperation network with custom limit"""
        url = f"{API_BASE}/v2/graphs/country-cooperation-network?limit=20"
        
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        result = data["data"]
        if result["edges"]:
            assert len(result["edges"]) <= 20
    
    def test_with_min_shared_satellites(self, api_available):
        """Test country cooperation with minimum shared satellites filter"""
        url = f"{API_BASE}/v2/graphs/country-cooperation-network"
        params = {"min_shared_satellites": 5, "limit": 30}
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        result = data["data"]
        assert "edges" in result
    
    def test_response_structure(self, api_available):
        """Test response structure for country cooperation network"""
        url = f"{API_BASE}/v2/graphs/country-cooperation-network?limit=10"
        
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        result = data["data"]
        stats = result["stats"]
        
        assert "total_countries" in stats
        assert "total_cooperation_pairs" in stats
        assert "avg_cooperation_score" in stats
        assert "max_cooperation_score" in stats
        
        if result["nodes"]:
            node = result["nodes"][0]
            assert "id" in node
            assert "name" in node
            assert "type" in node
            assert node["type"] == "country"
            assert "satellite_count" in node
        
        if result["edges"]:
            edge = result["edges"][0]
            assert "source" in edge
            assert "target" in edge
            assert "shared_documents" in edge
            assert "proximity_connections" in edge
            assert "cooperation_score" in edge
            assert "cooperation_types" in edge
            
            coop_types = edge["cooperation_types"]
            assert "shared_registration" in coop_types
            assert "orbital_proximity" in coop_types
    
    def test_parameter_validation(self, api_available):
        """Test parameter validation"""
        url = f"{API_BASE}/v2/graphs/country-cooperation-network"
        
        response = requests.get(f"{url}?limit=0", timeout=10)
        assert response.status_code == 422
        
        response = requests.get(f"{url}?min_shared_satellites=0", timeout=10)
        assert response.status_code == 422
        
        response = requests.get(f"{url}?limit=50&min_shared_satellites=3", timeout=30)
        assert response.status_code == 200


class TestFunctionClusters:
    """Test function-based clusters endpoint"""
    
    def test_basic_query(self, api_available):
        """Test basic function clusters query"""
        url = f"{API_BASE}/v2/graphs/function-clusters"
        
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        assert "timestamp" in data
        
        result = data["data"]
        assert "nodes" in result
        assert "edges" in result
        assert "clusters" in result
        assert "stats" in result
        
        assert isinstance(result["nodes"], list)
        assert isinstance(result["edges"], list)
        assert isinstance(result["clusters"], list)
        assert isinstance(result["stats"], dict)
    
    def test_with_orbital_band_filter(self, api_available):
        """Test function clusters with orbital band filter"""
        url = f"{API_BASE}/v2/graphs/function-clusters"
        params = {"orbital_band": "LEO"}
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        result = data["data"]
        if result["clusters"]:
            for cluster in result["clusters"]:
                assert cluster["orbital_band"] == "LEO"
    
    def test_with_limit_parameter(self, api_available):
        """Test function clusters with custom limit"""
        url = f"{API_BASE}/v2/graphs/function-clusters?limit=10"
        
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        result = data["data"]
        if result["clusters"]:
            assert len(result["clusters"]) <= 10
    
    def test_with_min_cluster_size(self, api_available):
        """Test function clusters with minimum cluster size"""
        url = f"{API_BASE}/v2/graphs/function-clusters"
        params = {"min_cluster_size": 5, "limit": 15}
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        result = data["data"]
        if result["clusters"]:
            for cluster in result["clusters"]:
                assert cluster["size"] >= 5
    
    def test_response_structure(self, api_available):
        """Test response structure for function clusters"""
        url = f"{API_BASE}/v2/graphs/function-clusters?limit=5"
        
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        result = data["data"]
        stats = result["stats"]
        
        assert "total_clusters" in stats
        assert "total_satellites" in stats
        assert "total_proximity_edges" in stats
        assert "avg_cluster_size" in stats
        assert "avg_density" in stats
        
        if result["nodes"]:
            node = result["nodes"][0]
            assert "id" in node
            assert "identifier" in node
            assert "name" in node
            assert "function" in node
            assert "orbital_band" in node
        
        if result["edges"]:
            edge = result["edges"][0]
            assert "source" in edge
            assert "target" in edge
            assert "proximity_score" in edge
            assert "function_cluster" in edge
            assert "orbital_band" in edge
        
        if result["clusters"]:
            cluster = result["clusters"][0]
            assert "function" in cluster
            assert "orbital_band" in cluster
            assert "size" in cluster
            assert "density" in cluster
            assert "countries" in cluster
            assert "country_count" in cluster
    
    def test_parameter_validation(self, api_available):
        """Test parameter validation"""
        url = f"{API_BASE}/v2/graphs/function-clusters"
        
        response = requests.get(f"{url}?limit=0", timeout=10)
        assert response.status_code == 422
        
        response = requests.get(f"{url}?min_cluster_size=1", timeout=10)
        assert response.status_code == 422
        
        response = requests.get(f"{url}?limit=20&min_cluster_size=3", timeout=30)
        assert response.status_code == 200


class TestCrossDomainIntegration:
    """Test integration between different cross-domain endpoints"""
    
    def test_all_endpoints_available(self, api_available):
        """Test that all cross-domain endpoints are available"""
        endpoints = [
            "/v2/graphs/cross-constellation-proximity",
            "/v2/graphs/country-cooperation-network",
            "/v2/graphs/function-clusters"
        ]
        
        for endpoint in endpoints:
            url = f"{API_BASE}{endpoint}"
            response = requests.get(url, timeout=30)
            assert response.status_code == 200, f"Endpoint {endpoint} failed"
    
    def test_consistent_response_format(self, api_available):
        """Test that all endpoints return consistent response format"""
        endpoints = [
            "/v2/graphs/cross-constellation-proximity?limit=5",
            "/v2/graphs/country-cooperation-network?limit=5",
            "/v2/graphs/function-clusters?limit=5"
        ]
        
        for endpoint in endpoints:
            url = f"{API_BASE}{endpoint}"
            response = requests.get(url, timeout=30)
            assert response.status_code == 200
            
            data = response.json()
            assert "data" in data
            assert "timestamp" in data
            
            result = data["data"]
            assert "nodes" in result or "clusters" in result
            assert "stats" in result


def main():
    """Run tests manually (for non-pytest execution)"""
    print("=" * 60)
    print("Cross-Domain Graph Queries Integration Tests")
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
    
    test_suites = [
        ("Cross-Constellation Proximity", TestCrossConstellationProximity()),
        ("Country Cooperation Network", TestCountryCooperationNetwork()),
        ("Function-Based Clusters", TestFunctionClusters()),
        ("Cross-Domain Integration", TestCrossDomainIntegration())
    ]
    
    total_passed = 0
    total_failed = 0
    
    for suite_name, suite in test_suites:
        print(f"\n{suite_name} Tests:")
        print("-" * 60)
        
        test_methods = [method for method in dir(suite) if method.startswith("test_")]
        
        for test_name in test_methods:
            try:
                print(f"  {test_name}...", end=" ")
                test_func = getattr(suite, test_name)
                test_func(None)
                print("✓ PASS")
                total_passed += 1
            except AssertionError as e:
                print(f"❌ FAIL: {e}")
                total_failed += 1
            except Exception as e:
                print(f"❌ ERROR: {e}")
                total_failed += 1
    
    print("\n" + "=" * 60)
    print(f"Total tests passed: {total_passed}")
    print(f"Total tests failed: {total_failed}")
    print("=" * 60)
    
    return total_failed == 0


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
