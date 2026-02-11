#!/usr/bin/env python3
"""
Integration tests for community detection API endpoints.

Tests the /v2/graphs/communities endpoint with various
algorithms, configurations, and caching behavior.
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


class TestCommunitiesAPI:
    """Integration tests for communities API endpoint"""
    
    def test_get_communities_default_algorithm(self, api_available):
        """Test getting communities with default algorithm (label_propagation)"""
        url = f"{API_BASE}/v2/graphs/communities"
        
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        assert "timestamp" in data
        assert "cached" in data
        
        result = data["data"]
        assert "communities" in result
        assert "algorithm" in result
        assert "stats" in result
        
        assert result["algorithm"] == "label_propagation"
        assert isinstance(result["communities"], list)
        assert isinstance(result["stats"], dict)
    
    def test_get_communities_label_propagation(self, api_available):
        """Test getting communities with label propagation algorithm"""
        url = f"{API_BASE}/v2/graphs/communities"
        params = {"algorithm": "label_propagation", "min_size": 2}
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        result = data["data"]
        
        assert result["algorithm"] == "label_propagation"
        assert result["stats"]["min_community_size"] == 2
        
        if result["communities"]:
            community = result["communities"][0]
            assert "community_id" in community
            assert "size" in community
            assert "members" in community
            assert "algorithm" in community
            assert community["algorithm"] == "label_propagation"
            assert community["size"] >= 2
    
    def test_get_communities_connected_components(self, api_available):
        """Test getting communities with connected components algorithm"""
        url = f"{API_BASE}/v2/graphs/communities"
        params = {"algorithm": "connected_components", "min_size": 3}
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        result = data["data"]
        
        assert result["algorithm"] == "connected_components"
        assert result["stats"]["min_community_size"] == 3
        
        if result["communities"]:
            community = result["communities"][0]
            assert "community_id" in community
            assert "size" in community
            assert "members" in community
            assert "algorithm" in community
            assert community["algorithm"] == "connected_components"
            assert community["size"] >= 3
    
    def test_get_communities_invalid_algorithm(self, api_available):
        """Test getting communities with invalid algorithm"""
        url = f"{API_BASE}/v2/graphs/communities"
        params = {"algorithm": "invalid_algorithm"}
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 400
        assert "Invalid algorithm" in response.json()["detail"]
    
    def test_get_communities_with_min_size(self, api_available):
        """Test getting communities with custom minimum size"""
        url = f"{API_BASE}/v2/graphs/communities"
        params = {"min_size": 5}
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        result = data["data"]
        
        assert result["stats"]["min_community_size"] == 5
        
        for community in result["communities"]:
            assert community["size"] >= 5
    
    def test_get_communities_min_size_validation(self, api_available):
        """Test minimum size validation"""
        url = f"{API_BASE}/v2/graphs/communities"
        params = {"min_size": 1}
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 422
    
    def test_get_communities_max_min_size_validation(self, api_available):
        """Test maximum min_size validation"""
        url = f"{API_BASE}/v2/graphs/communities"
        params = {"min_size": 101}
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 422
    
    def test_get_communities_with_edge_types(self, api_available):
        """Test getting communities with specific edge types"""
        url = f"{API_BASE}/v2/graphs/communities"
        params = {
            "algorithm": "label_propagation",
            "edge_types": ["constellation_membership", "orbital_proximity"]
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        result = data["data"]
        
        assert "edge_types" in result["stats"]
    
    def test_get_communities_caching(self, api_available):
        """Test that communities endpoint uses caching"""
        url = f"{API_BASE}/v2/graphs/communities"
        params = {"algorithm": "label_propagation", "min_size": 2}
        
        response1 = requests.get(url, params=params, timeout=30)
        assert response1.status_code == 200
        data1 = response1.json()
        
        response2 = requests.get(url, params=params, timeout=30)
        assert response2.status_code == 200
        data2 = response2.json()
        
        assert data2["cached"] == True
        assert data1["data"] == data2["data"]
    
    def test_get_communities_response_structure(self, api_available):
        """Test that response has correct structure"""
        url = f"{API_BASE}/v2/graphs/communities"
        
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        assert "timestamp" in data
        assert "cached" in data
        
        result = data["data"]
        assert "communities" in result
        assert "algorithm" in result
        assert "stats" in result
        
        stats = result["stats"]
        assert "total_communities" in stats
        assert "total_satellites" in stats
        assert "min_community_size" in stats
        assert "edge_types" in stats
    
    def test_get_communities_statistics(self, api_available):
        """Test that statistics are calculated correctly"""
        url = f"{API_BASE}/v2/graphs/communities"
        
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        result = data["data"]
        
        stats = result["stats"]
        communities = result["communities"]
        
        assert stats["total_communities"] == len(communities)
        
        actual_total = sum(c.get("size", 0) for c in communities)
        assert stats["total_satellites"] == actual_total


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
