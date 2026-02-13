#!/usr/bin/env python3
"""
Integration tests for graph recommendations API endpoint.

Tests the /v2/graphs/recommendations/{satellite_id} endpoint with various
strategies including caching, error handling, and different recommendation types.
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


@pytest.fixture(scope="module")
def sample_satellite_id(api_available):
    """Get a sample satellite ID for testing"""
    try:
        response = requests.get(
            f"{API_BASE}/v2/satellites",
            params={"limit": 1},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if "data" in data and len(data["data"]) > 0:
                return data["data"][0]["identifier"]
        return "2025-001A"
    except Exception:
        return "2025-001A"


class TestRecommendationsAPI:
    """Test graph recommendations endpoints"""
    
    def test_collaborative_filtering_basic(self, api_available, sample_satellite_id):
        """Test collaborative filtering recommendations"""
        url = f"{API_BASE}/v2/graphs/recommendations/{sample_satellite_id}"
        params = {
            "strategy": "collaborative_filtering",
            "limit": 10
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        assert "timestamp" in data
        assert "cached" in data
        
        response_data = data["data"]
        assert "satellite_id" in response_data
        assert response_data["satellite_id"] == sample_satellite_id
        assert "strategy" in response_data
        assert response_data["strategy"] == "collaborative_filtering"
        assert "recommendations" in response_data
        assert "count" in response_data
        assert "parameters" in response_data
        
        assert isinstance(response_data["recommendations"], list)
        assert response_data["count"] == len(response_data["recommendations"])
        
        if len(response_data["recommendations"]) > 0:
            rec = response_data["recommendations"][0]
            assert "_id" in rec
            assert "identifier" in rec
            assert "name" in rec
            assert "relevance_score" in rec
            assert "common_connections" in rec
            assert rec["recommendation_type"] == "collaborative_filtering"
    
    def test_similarity_strategy(self, api_available, sample_satellite_id):
        """Test similarity-based recommendations"""
        url = f"{API_BASE}/v2/graphs/recommendations/{sample_satellite_id}"
        params = {
            "strategy": "similarity",
            "limit": 5,
            "min_similarity": 0.2
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        response_data = data["data"]
        assert response_data["strategy"] == "similarity"
        assert response_data["parameters"]["min_similarity"] == 0.2
        
        if len(response_data["recommendations"]) > 0:
            rec = response_data["recommendations"][0]
            assert "similarity_score" in rec
            assert rec["similarity_score"] >= 0.2
            assert "common_neighbors" in rec
            assert "total_neighbors" in rec
    
    def test_similar_neighbors_strategy(self, api_available, sample_satellite_id):
        """Test similar neighbors recommendations"""
        url = f"{API_BASE}/v2/graphs/recommendations/{sample_satellite_id}"
        params = {
            "strategy": "similar_neighbors",
            "limit": 10
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        response_data = data["data"]
        assert response_data["strategy"] == "similar_neighbors"
        
        if len(response_data["recommendations"]) > 0:
            rec = response_data["recommendations"][0]
            assert rec["recommendation_type"] == "similar_neighbors"
            assert "relevance_score" in rec
    
    def test_second_degree_strategy(self, api_available, sample_satellite_id):
        """Test second degree (friends of friends) recommendations"""
        url = f"{API_BASE}/v2/graphs/recommendations/{sample_satellite_id}"
        params = {
            "strategy": "second_degree",
            "limit": 10
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        response_data = data["data"]
        assert response_data["strategy"] == "second_degree"
        
        if len(response_data["recommendations"]) > 0:
            rec = response_data["recommendations"][0]
            assert rec["recommendation_type"] == "second_degree"
    
    def test_common_neighbors_strategy(self, api_available, sample_satellite_id):
        """Test common neighbors recommendations"""
        url = f"{API_BASE}/v2/graphs/recommendations/{sample_satellite_id}"
        params = {
            "strategy": "common_neighbors",
            "limit": 10
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        response_data = data["data"]
        assert response_data["strategy"] == "common_neighbors"
        
        if len(response_data["recommendations"]) > 0:
            rec = response_data["recommendations"][0]
            assert rec["recommendation_type"] == "common_neighbors"
    
    def test_recommendations_with_edge_types(self, api_available, sample_satellite_id):
        """Test recommendations with specific edge types"""
        url = f"{API_BASE}/v2/graphs/recommendations/{sample_satellite_id}"
        params = {
            "strategy": "collaborative_filtering",
            "edge_types": ["constellation_membership"],
            "limit": 10
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        response_data = data["data"]
        assert "constellation_membership" in response_data["parameters"]["edge_types"]
    
    def test_recommendations_limit_parameter(self, api_available, sample_satellite_id):
        """Test recommendations limit parameter"""
        url = f"{API_BASE}/v2/graphs/recommendations/{sample_satellite_id}"
        params = {
            "strategy": "collaborative_filtering",
            "limit": 3
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        response_data = data["data"]
        assert len(response_data["recommendations"]) <= 3
        assert response_data["parameters"]["limit"] == 3
    
    def test_recommendations_caching(self, api_available, sample_satellite_id):
        """Test that recommendations are cached properly"""
        url = f"{API_BASE}/v2/graphs/recommendations/{sample_satellite_id}"
        params = {
            "strategy": "collaborative_filtering",
            "limit": 5
        }
        
        response1 = requests.get(url, params=params, timeout=30)
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["cached"] == False
        
        time.sleep(0.5)
        
        response2 = requests.get(url, params=params, timeout=30)
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["cached"] == True
        
        assert data1["data"]["count"] == data2["data"]["count"]
    
    def test_recommendations_invalid_strategy(self, api_available, sample_satellite_id):
        """Test error handling for invalid strategy"""
        url = f"{API_BASE}/v2/graphs/recommendations/{sample_satellite_id}"
        params = {
            "strategy": "invalid_strategy",
            "limit": 10
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Invalid strategy" in data["detail"]
    
    def test_recommendations_min_common_connections(self, api_available, sample_satellite_id):
        """Test collaborative filtering with min_common_connections parameter"""
        url = f"{API_BASE}/v2/graphs/recommendations/{sample_satellite_id}"
        params = {
            "strategy": "collaborative_filtering",
            "min_common_connections": 3,
            "limit": 10
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        response_data = data["data"]
        assert response_data["parameters"]["min_common_connections"] == 3
        
        for rec in response_data["recommendations"]:
            assert rec["common_connections"] >= 3
    
    def test_recommendations_min_similarity(self, api_available, sample_satellite_id):
        """Test similarity strategy with min_similarity parameter"""
        url = f"{API_BASE}/v2/graphs/recommendations/{sample_satellite_id}"
        params = {
            "strategy": "similarity",
            "min_similarity": 0.3,
            "limit": 10
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        response_data = data["data"]
        assert response_data["parameters"]["min_similarity"] == 0.3
        
        for rec in response_data["recommendations"]:
            assert rec["similarity_score"] >= 0.3
    
    def test_recommendations_sorted_by_relevance(self, api_available, sample_satellite_id):
        """Test that recommendations are sorted by relevance score"""
        url = f"{API_BASE}/v2/graphs/recommendations/{sample_satellite_id}"
        params = {
            "strategy": "collaborative_filtering",
            "limit": 10
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        recommendations = data["data"]["recommendations"]
        if len(recommendations) > 1:
            for i in range(len(recommendations) - 1):
                assert recommendations[i]["relevance_score"] >= recommendations[i + 1]["relevance_score"]
    
    def test_recommendations_different_strategies_different_results(self, api_available, sample_satellite_id):
        """Test that different strategies produce different results"""
        url = f"{API_BASE}/v2/graphs/recommendations/{sample_satellite_id}"
        
        response1 = requests.get(
            url,
            params={"strategy": "collaborative_filtering", "limit": 5},
            timeout=30
        )
        response2 = requests.get(
            url,
            params={"strategy": "second_degree", "limit": 5},
            timeout=30
        )
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        data1 = response1.json()
        data2 = response2.json()
        
        if len(data1["data"]["recommendations"]) > 0 and len(data2["data"]["recommendations"]) > 0:
            rec_type1 = data1["data"]["recommendations"][0]["recommendation_type"]
            rec_type2 = data2["data"]["recommendations"][0]["recommendation_type"]
            assert rec_type1 == "collaborative_filtering"
            assert rec_type2 == "second_degree"
    
    def test_recommendations_limit_boundaries(self, api_available, sample_satellite_id):
        """Test recommendations limit boundary conditions"""
        url = f"{API_BASE}/v2/graphs/recommendations/{sample_satellite_id}"
        
        response_min = requests.get(
            url,
            params={"strategy": "collaborative_filtering", "limit": 1},
            timeout=30
        )
        assert response_min.status_code == 200
        data_min = response_min.json()
        assert len(data_min["data"]["recommendations"]) <= 1
        
        response_max = requests.get(
            url,
            params={"strategy": "collaborative_filtering", "limit": 100},
            timeout=30
        )
        assert response_max.status_code == 200
        data_max = response_max.json()
        assert len(data_max["data"]["recommendations"]) <= 100
        
        response_invalid = requests.get(
            url,
            params={"strategy": "collaborative_filtering", "limit": 0},
            timeout=30
        )
        assert response_invalid.status_code == 422
    
    def test_recommendations_returns_metadata(self, api_available, sample_satellite_id):
        """Test that recommendations include proper metadata"""
        url = f"{API_BASE}/v2/graphs/recommendations/{sample_satellite_id}"
        params = {
            "strategy": "collaborative_filtering",
            "limit": 5
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "timestamp" in data
        assert "cached" in data
        
        response_data = data["data"]
        assert "satellite_id" in response_data
        assert "strategy" in response_data
        assert "count" in response_data
        assert "parameters" in response_data
        
        params_returned = response_data["parameters"]
        assert "strategy" in params_returned
        assert "edge_types" in params_returned
        assert "limit" in params_returned


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
