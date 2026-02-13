#!/usr/bin/env python3
"""
Integration tests for collision risk API endpoints.

Tests the /v2/graphs/collision-risks endpoints with various
configurations including filtering, statistics, and network visualization.
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


class TestCollisionRiskAPI:
    """Test collision risk API endpoints"""
    
    def test_get_collision_risks_basic(self, api_available):
        """Test getting collision risks without filters"""
        url = f"{API_BASE}/v2/graphs/collision-risks"
        
        response = requests.get(url, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        assert "timestamp" in data
        assert "edges" in data["data"]
        assert "count" in data["data"]
        assert "parameters" in data["data"]
    
    def test_get_collision_risks_with_threshold(self, api_available):
        """Test filtering collision risks by risk threshold"""
        url = f"{API_BASE}/v2/graphs/collision-risks"
        params = {"risk_threshold": 0.7}
        
        response = requests.get(url, params=params, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["data"]["parameters"]["risk_threshold"] == 0.7
        
        if len(data["data"]["edges"]) > 0:
            for edge in data["data"]["edges"]:
                assert edge["risk_score"] >= 0.7
    
    def test_get_collision_risks_with_orbital_band(self, api_available):
        """Test filtering collision risks by orbital band"""
        url = f"{API_BASE}/v2/graphs/collision-risks"
        params = {"orbital_band": "LEO"}
        
        response = requests.get(url, params=params, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["data"]["parameters"]["orbital_band"] == "LEO"
        
        if len(data["data"]["edges"]) > 0:
            for edge in data["data"]["edges"]:
                assert edge["orbital_band"] == "LEO"
    
    def test_get_collision_risks_with_risk_level(self, api_available):
        """Test filtering collision risks by risk level"""
        url = f"{API_BASE}/v2/graphs/collision-risks"
        params = {"risk_level": "high"}
        
        response = requests.get(url, params=params, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["data"]["parameters"]["risk_level"] == "high"
        
        if len(data["data"]["edges"]) > 0:
            for edge in data["data"]["edges"]:
                assert edge["risk_level"] == "high"
    
    def test_get_collision_risks_with_limit(self, api_available):
        """Test limiting number of collision risk results"""
        url = f"{API_BASE}/v2/graphs/collision-risks"
        params = {"limit": 10}
        
        response = requests.get(url, params=params, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["data"]["edges"]) <= 10
    
    def test_get_collision_risks_combined_filters(self, api_available):
        """Test multiple filters together"""
        url = f"{API_BASE}/v2/graphs/collision-risks"
        params = {
            "risk_threshold": 0.6,
            "orbital_band": "LEO",
            "risk_level": "medium",
            "limit": 20
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["data"]["parameters"]["risk_threshold"] == 0.6
        assert data["data"]["parameters"]["orbital_band"] == "LEO"
        assert data["data"]["parameters"]["risk_level"] == "medium"
        assert len(data["data"]["edges"]) <= 20
    
    def test_get_collision_risks_invalid_risk_level(self, api_available):
        """Test invalid risk level parameter"""
        url = f"{API_BASE}/v2/graphs/collision-risks"
        params = {"risk_level": "invalid"}
        
        response = requests.get(url, params=params, timeout=10)
        
        assert response.status_code == 400
    
    def test_get_collision_risks_for_satellite(self, api_available):
        """Test getting collision risks for a specific satellite"""
        url = f"{API_BASE}/v2/graphs/collision-risks/2025-206B"
        
        response = requests.get(url, timeout=10)
        
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert "data" in data
            assert "satellite_id" in data["data"]
            assert "collision_risks" in data["data"]
            assert "count" in data["data"]
    
    def test_get_collision_risks_for_satellite_with_full_id(self, api_available):
        """Test with full document ID"""
        url = f"{API_BASE}/v2/graphs/collision-risks/satellites/2025-206B"
        
        response = requests.get(url, timeout=10)
        
        assert response.status_code in [200, 404]
    
    def test_get_collision_risks_for_satellite_with_threshold(self, api_available):
        """Test satellite collision risks with threshold filter"""
        url = f"{API_BASE}/v2/graphs/collision-risks/2025-206B"
        params = {"risk_threshold": 0.8}
        
        response = requests.get(url, params=params, timeout=10)
        
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            if len(data["data"]["collision_risks"]) > 0:
                for risk in data["data"]["collision_risks"]:
                    assert risk["risk_score"] >= 0.8
    
    def test_get_collision_risk_network(self, api_available):
        """Test getting collision risk network for visualization"""
        url = f"{API_BASE}/v2/graphs/collision-risks/network/graph"
        
        response = requests.get(url, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        assert "nodes" in data["data"]
        assert "edges" in data["data"]
        assert "stats" in data["data"]
    
    def test_get_collision_risk_network_with_filters(self, api_available):
        """Test collision risk network with filters"""
        url = f"{API_BASE}/v2/graphs/collision-risks/network/graph"
        params = {
            "orbital_band": "LEO",
            "risk_threshold": 0.7,
            "limit": 50
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["data"]["stats"]["risk_threshold"] == 0.7
        assert data["data"]["stats"]["orbital_band"] == "LEO"
        assert len(data["data"]["edges"]) <= 50
    
    def test_get_collision_risk_network_structure(self, api_available):
        """Test that network graph has proper structure"""
        url = f"{API_BASE}/v2/graphs/collision-risks/network/graph"
        params = {"limit": 10}
        
        response = requests.get(url, params=params, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data["data"]["edges"]) > 0:
            edge = data["data"]["edges"][0]
            assert "id" in edge
            assert "source" in edge
            assert "target" in edge
            assert "risk_score" in edge
            assert "risk_level" in edge
        
        if len(data["data"]["nodes"]) > 0:
            node = data["data"]["nodes"][0]
            assert "id" in node
            assert "identifier" in node
            assert "name" in node
            assert "orbital_band" in node
    
    def test_get_collision_risk_statistics(self, api_available):
        """Test collision risk statistics endpoint"""
        url = f"{API_BASE}/v2/graphs/collision-risks/statistics"
        
        response = requests.get(url, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        assert "timestamp" in data
    
    def test_get_collision_risk_statistics_structure(self, api_available):
        """Test statistics response structure"""
        url = f"{API_BASE}/v2/graphs/collision-risks/statistics"
        
        response = requests.get(url, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        if data["data"]:
            stats = data["data"]
            assert "total_edges" in stats or len(stats) == 0
    
    def test_get_collision_risk_statistics_with_orbital_band(self, api_available):
        """Test statistics filtered by orbital band"""
        url = f"{API_BASE}/v2/graphs/collision-risks/statistics"
        params = {"orbital_band": "LEO"}
        
        response = requests.get(url, params=params, timeout=10)
        
        assert response.status_code == 200
    
    def test_get_collision_clusters(self, api_available):
        """Test collision cluster detection endpoint"""
        url = f"{API_BASE}/v2/graphs/collision-risks/clusters"
        
        response = requests.get(url, timeout=15)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        assert "clusters" in data["data"]
        assert "count" in data["data"]
        assert "parameters" in data["data"]
    
    def test_get_collision_clusters_with_filters(self, api_available):
        """Test cluster detection with custom parameters"""
        url = f"{API_BASE}/v2/graphs/collision-risks/clusters"
        params = {
            "risk_threshold": 0.8,
            "min_cluster_size": 5,
            "orbital_band": "LEO"
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["data"]["parameters"]["risk_threshold"] == 0.8
        assert data["data"]["parameters"]["min_cluster_size"] == 5
        assert data["data"]["parameters"]["orbital_band"] == "LEO"
    
    def test_get_collision_clusters_structure(self, api_available):
        """Test cluster response structure"""
        url = f"{API_BASE}/v2/graphs/collision-risks/clusters"
        params = {"min_cluster_size": 3}
        
        response = requests.get(url, params=params, timeout=15)
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data["data"]["clusters"]) > 0:
            cluster = data["data"]["clusters"][0]
            assert "center_satellite" in cluster
            assert "cluster_size" in cluster
            assert "satellites" in cluster
            assert cluster["cluster_size"] >= 3
    
    def test_collision_risk_edge_data_completeness(self, api_available):
        """Test that collision risk edges have all required fields"""
        url = f"{API_BASE}/v2/graphs/collision-risks"
        params = {"limit": 1}
        
        response = requests.get(url, params=params, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data["data"]["edges"]) > 0:
            edge = data["data"]["edges"][0]
            assert "edge_id" in edge
            assert "from" in edge
            assert "to" in edge
            assert "risk_score" in edge
            assert "risk_level" in edge
            assert "orbital_band" in edge
            assert "differences" in edge
            
            assert "apogee_km" in edge["differences"]
            assert "perigee_km" in edge["differences"]
            assert "inclination_degrees" in edge["differences"]
            
            assert edge["risk_score"] >= 0.0
            assert edge["risk_score"] <= 1.0
            assert edge["risk_level"] in ["high", "medium", "low"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
