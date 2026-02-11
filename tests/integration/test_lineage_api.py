#!/usr/bin/env python3
"""
Integration tests for satellite lineage API endpoints.

Tests the /v2/graphs/lineage endpoints with various configurations
including ancestor/descendant traversal, family trees, and statistics.
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


@pytest.fixture(scope="module")
def sample_satellite_id(api_available):
    """Get a sample satellite ID for testing"""
    url = f"{API_BASE}/v2/satellites"
    params = {"limit": 1}
    
    response = requests.get(url, params=params, timeout=10)
    if response.status_code == 200:
        data = response.json()
        if "data" in data and len(data["data"]) > 0:
            sat = data["data"][0]
            return sat.get("identifier") or sat.get("_key")
    
    return "2020-001A"


class TestLineageAPI:
    """Test satellite lineage API endpoints"""
    
    def test_get_lineage_basic(self, api_available, sample_satellite_id):
        """Test getting lineage for a satellite"""
        url = f"{API_BASE}/v2/graphs/lineage/{sample_satellite_id}"
        
        response = requests.get(url, timeout=10)
        
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            
            assert "data" in data
            assert "timestamp" in data
            assert "root" in data["data"]
            assert "ancestors" in data["data"]
            assert "descendants" in data["data"]
            assert "stats" in data["data"]
    
    def test_get_lineage_ancestors_only(self, api_available, sample_satellite_id):
        """Test getting only ancestors"""
        url = f"{API_BASE}/v2/graphs/lineage/{sample_satellite_id}"
        params = {"direction": "ancestors"}
        
        response = requests.get(url, params=params, timeout=10)
        
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert data["data"]["stats"]["direction"] == "ancestors"
    
    def test_get_lineage_descendants_only(self, api_available, sample_satellite_id):
        """Test getting only descendants"""
        url = f"{API_BASE}/v2/graphs/lineage/{sample_satellite_id}"
        params = {"direction": "descendants"}
        
        response = requests.get(url, params=params, timeout=10)
        
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert data["data"]["stats"]["direction"] == "descendants"
    
    def test_get_lineage_both_directions(self, api_available, sample_satellite_id):
        """Test getting both ancestors and descendants"""
        url = f"{API_BASE}/v2/graphs/lineage/{sample_satellite_id}"
        params = {"direction": "both"}
        
        response = requests.get(url, params=params, timeout=10)
        
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert data["data"]["stats"]["direction"] == "both"
    
    def test_get_lineage_with_max_depth(self, api_available, sample_satellite_id):
        """Test controlling lineage traversal depth"""
        url = f"{API_BASE}/v2/graphs/lineage/{sample_satellite_id}"
        params = {"max_depth": 3}
        
        response = requests.get(url, params=params, timeout=10)
        
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert data["data"]["stats"]["max_depth"] == 3
    
    def test_get_lineage_invalid_direction(self, api_available, sample_satellite_id):
        """Test invalid direction parameter"""
        url = f"{API_BASE}/v2/graphs/lineage/{sample_satellite_id}"
        params = {"direction": "invalid"}
        
        response = requests.get(url, params=params, timeout=10)
        
        assert response.status_code == 400
    
    def test_get_lineage_nonexistent_satellite(self, api_available):
        """Test getting lineage for non-existent satellite"""
        url = f"{API_BASE}/v2/graphs/lineage/NONEXISTENT-9999"
        
        response = requests.get(url, timeout=10)
        
        assert response.status_code == 404
    
    def test_get_lineage_with_depth_validation(self, api_available, sample_satellite_id):
        """Test depth parameter validation"""
        url = f"{API_BASE}/v2/graphs/lineage/{sample_satellite_id}"
        params = {"max_depth": 15}
        
        response = requests.get(url, params=params, timeout=10)
        
        assert response.status_code == 422


class TestFamilyTreeAPI:
    """Test satellite family tree API endpoints"""
    
    def test_get_family_tree_gps(self, api_available):
        """Test getting GPS family tree"""
        url = f"{API_BASE}/v2/graphs/lineage/family/GPS"
        
        response = requests.get(url, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        assert "timestamp" in data
        assert "family_name" in data["data"]
        assert "nodes" in data["data"]
        assert "edges" in data["data"]
        assert "stats" in data["data"]
    
    def test_get_family_tree_iridium(self, api_available):
        """Test getting IRIDIUM family tree"""
        url = f"{API_BASE}/v2/graphs/lineage/family/IRIDIUM"
        
        response = requests.get(url, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["data"]["family_name"] == "IRIDIUM"
    
    def test_get_family_tree_starlink(self, api_available):
        """Test getting STARLINK family tree"""
        url = f"{API_BASE}/v2/graphs/lineage/family/STARLINK"
        
        response = requests.get(url, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["data"]["family_name"] == "STARLINK"
    
    def test_get_family_tree_glonass(self, api_available):
        """Test getting GLONASS family tree"""
        url = f"{API_BASE}/v2/graphs/lineage/family/GLONASS"
        
        response = requests.get(url, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["data"]["family_name"] == "GLONASS"
    
    def test_get_family_tree_galileo(self, api_available):
        """Test getting GALILEO family tree"""
        url = f"{API_BASE}/v2/graphs/lineage/family/GALILEO"
        
        response = requests.get(url, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["data"]["family_name"] == "GALILEO"
    
    def test_get_family_tree_with_limit(self, api_available):
        """Test limiting family tree results"""
        url = f"{API_BASE}/v2/graphs/lineage/family/GPS"
        params = {"limit": 10}
        
        response = requests.get(url, params=params, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data["data"]["nodes"]) > 0:
            assert len(data["data"]["nodes"]) <= 10
    
    def test_get_family_tree_nonexistent_family(self, api_available):
        """Test getting tree for non-existent family"""
        url = f"{API_BASE}/v2/graphs/lineage/family/NONEXISTENT_FAMILY"
        
        response = requests.get(url, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["data"]["nodes"]) == 0
        assert "message" in data
    
    def test_get_family_tree_case_insensitive(self, api_available):
        """Test family name is case-insensitive"""
        url_upper = f"{API_BASE}/v2/graphs/lineage/family/GPS"
        url_lower = f"{API_BASE}/v2/graphs/lineage/family/gps"
        
        response_upper = requests.get(url_upper, timeout=10)
        response_lower = requests.get(url_lower, timeout=10)
        
        assert response_upper.status_code == 200
        assert response_lower.status_code == 200
    
    def test_family_tree_structure(self, api_available):
        """Test family tree has correct structure"""
        url = f"{API_BASE}/v2/graphs/lineage/family/GPS"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if len(data["data"]["nodes"]) > 0:
                node = data["data"]["nodes"][0]
                assert "id" in node
                assert "identifier" in node
                assert "name" in node
            
            if len(data["data"]["edges"]) > 0:
                edge = data["data"]["edges"][0]
                assert "id" in edge
                assert "source" in edge
                assert "target" in edge
                assert "relationship_type" in edge


class TestLineageStatistics:
    """Test lineage statistics endpoint"""
    
    def test_get_lineage_statistics(self, api_available):
        """Test getting lineage statistics"""
        url = f"{API_BASE}/v2/graphs/lineage/statistics"
        
        response = requests.get(url, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        assert "timestamp" in data
    
    def test_lineage_statistics_structure(self, api_available):
        """Test statistics have expected structure"""
        url = f"{API_BASE}/v2/graphs/lineage/statistics"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data["data"]:
                assert "total_edges" in data["data"]


class TestLineageIntegration:
    """Integration tests combining multiple lineage endpoints"""
    
    def test_lineage_and_family_tree_consistency(self, api_available):
        """Test consistency between lineage and family tree endpoints"""
        family_url = f"{API_BASE}/v2/graphs/lineage/family/GPS"
        family_response = requests.get(family_url, timeout=10)
        
        if family_response.status_code == 200:
            family_data = family_response.json()
            
            if len(family_data["data"]["nodes"]) > 0:
                satellite_id = family_data["data"]["nodes"][0]["identifier"]
                
                lineage_url = f"{API_BASE}/v2/graphs/lineage/{satellite_id}"
                lineage_response = requests.get(lineage_url, timeout=10)
                
                if lineage_response.status_code == 200:
                    lineage_data = lineage_response.json()
                    
                    if lineage_data["data"]["root"]:
                        assert lineage_data["data"]["root"]["family"] == "GPS"
    
    def test_statistics_reflect_population(self, api_available):
        """Test statistics reflect actual data"""
        stats_url = f"{API_BASE}/v2/graphs/lineage/statistics"
        stats_response = requests.get(stats_url, timeout=10)
        
        if stats_response.status_code == 200:
            stats_data = stats_response.json()
            
            if stats_data["data"] and "families" in stats_data["data"]:
                families = stats_data["data"]["families"]
                
                for family_info in families[:3]:
                    family_name = family_info["family"]
                    
                    family_url = f"{API_BASE}/v2/graphs/lineage/family/{family_name}"
                    family_response = requests.get(family_url, timeout=10)
                    
                    assert family_response.status_code == 200


class TestLineagePerformance:
    """Performance tests for lineage endpoints"""
    
    def test_lineage_response_time(self, api_available, sample_satellite_id):
        """Test lineage endpoint responds within reasonable time"""
        import time
        
        url = f"{API_BASE}/v2/graphs/lineage/{sample_satellite_id}"
        
        start_time = time.time()
        response = requests.get(url, timeout=10)
        elapsed_time = time.time() - start_time
        
        assert elapsed_time < 5.0
    
    def test_family_tree_response_time(self, api_available):
        """Test family tree endpoint responds within reasonable time"""
        import time
        
        url = f"{API_BASE}/v2/graphs/lineage/family/GPS"
        
        start_time = time.time()
        response = requests.get(url, timeout=10)
        elapsed_time = time.time() - start_time
        
        assert elapsed_time < 5.0
    
    def test_statistics_response_time(self, api_available):
        """Test statistics endpoint responds within reasonable time"""
        import time
        
        url = f"{API_BASE}/v2/graphs/lineage/statistics"
        
        start_time = time.time()
        response = requests.get(url, timeout=10)
        elapsed_time = time.time() - start_time
        
        assert elapsed_time < 3.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
