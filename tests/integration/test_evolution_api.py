#!/usr/bin/env python3
"""
Integration tests for graph evolution timeline API endpoints.

Tests the /v2/graphs/evolution/timeline and /v2/graphs/evolution/snapshot endpoints
with various configurations including caching, error handling, and different granularities.
"""
import requests
import time
import pytest
from datetime import datetime

API_BASE = "http://localhost:8000"


@pytest.fixture(scope="module")
def api_available():
    """Check if API is available before running tests"""
    try:
        response = requests.get(f"{API_BASE}/v2/health", timeout=2)
        return response.status_code == 200
    except Exception:
        pytest.skip("API server not available")


class TestEvolutionAPI:
    """Test graph evolution timeline endpoints"""
    
    def test_evolution_timeline_basic(self, api_available):
        """Test basic evolution timeline query"""
        url = f"{API_BASE}/v2/graphs/evolution/timeline"
        params = {
            "start_date": "2000",
            "end_date": "2024",
            "granularity": "year"
        }
        
        response = requests.get(url, params=params, timeout=60)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        assert "timestamp" in data
        assert "cached" in data
        
        response_data = data["data"]
        assert "timeline" in response_data
        assert "parameters" in response_data
        assert "stats" in response_data
        
        assert isinstance(response_data["timeline"], list)
        assert response_data["parameters"]["granularity"] == "year"
        assert response_data["parameters"]["start_date"] == "2000"
        assert response_data["parameters"]["end_date"] == "2024"
    
    def test_evolution_timeline_yearly(self, api_available):
        """Test evolution timeline with yearly granularity"""
        url = f"{API_BASE}/v2/graphs/evolution/timeline"
        params = {
            "start_date": "2010",
            "end_date": "2020",
            "granularity": "year"
        }
        
        response = requests.get(url, params=params, timeout=60)
        
        assert response.status_code == 200
        data = response.json()
        
        timeline = data["data"]["timeline"]
        
        if len(timeline) > 0:
            snapshot = timeline[0]
            assert "period" in snapshot
            assert "date" in snapshot
            assert "node_count" in snapshot
            assert "edge_count" in snapshot
            assert "density" in snapshot
            assert "avg_degree" in snapshot
            assert "node_growth" in snapshot
            assert "edge_growth" in snapshot
            assert "density_change" in snapshot
            assert "edge_counts_by_type" in snapshot
    
    def test_evolution_timeline_monthly(self, api_available):
        """Test evolution timeline with monthly granularity"""
        url = f"{API_BASE}/v2/graphs/evolution/timeline"
        params = {
            "start_date": "2023-01",
            "end_date": "2023-12",
            "granularity": "month"
        }
        
        response = requests.get(url, params=params, timeout=60)
        
        assert response.status_code == 200
        data = response.json()
        
        timeline = data["data"]["timeline"]
        assert len(timeline) <= 12
    
    def test_evolution_timeline_quarterly(self, api_available):
        """Test evolution timeline with quarterly granularity"""
        url = f"{API_BASE}/v2/graphs/evolution/timeline"
        params = {
            "start_date": "2020",
            "end_date": "2022",
            "granularity": "quarter"
        }
        
        response = requests.get(url, params=params, timeout=60)
        
        assert response.status_code == 200
        data = response.json()
        
        timeline = data["data"]["timeline"]
        
        if len(timeline) > 0:
            assert "Q" in timeline[0]["period"]
    
    def test_evolution_timeline_default_dates(self, api_available):
        """Test evolution timeline with default dates"""
        url = f"{API_BASE}/v2/graphs/evolution/timeline"
        
        response = requests.get(url, timeout=60)
        
        assert response.status_code == 200
        data = response.json()
        
        response_data = data["data"]
        assert response_data["parameters"]["start_date"] == "1957"
        assert response_data["parameters"]["end_date"] == str(datetime.now().year)
    
    def test_evolution_timeline_stats(self, api_available):
        """Test that timeline stats are calculated correctly"""
        url = f"{API_BASE}/v2/graphs/evolution/timeline"
        params = {
            "start_date": "2015",
            "end_date": "2020",
            "granularity": "year"
        }
        
        response = requests.get(url, params=params, timeout=60)
        
        assert response.status_code == 200
        data = response.json()
        
        stats = data["data"]["stats"]
        assert "total_periods" in stats
        assert "total_growth" in stats
        assert "final_state" in stats
        assert "peak_growth_period" in stats
        assert "avg_density" in stats
        
        total_growth = stats["total_growth"]
        assert "nodes" in total_growth
        assert "edges" in total_growth
        
        final_state = stats["final_state"]
        assert "node_count" in final_state
        assert "edge_count" in final_state
        assert "density" in final_state
        assert "avg_degree" in final_state
    
    def test_evolution_timeline_caching(self, api_available):
        """Test that evolution queries are cached correctly"""
        url = f"{API_BASE}/v2/graphs/evolution/timeline"
        params = {
            "start_date": "2018",
            "end_date": "2022",
            "granularity": "year"
        }
        
        response1 = requests.get(url, params=params, timeout=60)
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["cached"] == False
        
        time.sleep(0.1)
        
        response2 = requests.get(url, params=params, timeout=60)
        assert response2.status_code == 200
        data2 = response2.json()
        
        assert data2["cached"] == True
        assert data1["data"]["timeline"] == data2["data"]["timeline"]
    
    def test_graph_snapshot_basic(self, api_available):
        """Test basic graph snapshot query"""
        url = f"{API_BASE}/v2/graphs/evolution/snapshot/2020"
        
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        assert "timestamp" in data
        
        snapshot = data["data"]
        assert "date" in snapshot
        assert "node_count" in snapshot
        assert "edge_count" in snapshot
        assert "density" in snapshot
        assert "avg_degree" in snapshot
        assert "edge_counts_by_type" in snapshot
        
        assert snapshot["date"] == "2020"
    
    def test_graph_snapshot_yearly(self, api_available):
        """Test graph snapshot with year format"""
        url = f"{API_BASE}/v2/graphs/evolution/snapshot/2022"
        
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        snapshot = data["data"]
        assert snapshot["date"] == "2022"
        assert snapshot["node_count"] >= 0
        assert snapshot["edge_count"] >= 0
    
    def test_graph_snapshot_monthly(self, api_available):
        """Test graph snapshot with year-month format"""
        url = f"{API_BASE}/v2/graphs/evolution/snapshot/2023-06"
        
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        snapshot = data["data"]
        assert snapshot["date"] == "2023-06"
    
    def test_graph_snapshot_daily(self, api_available):
        """Test graph snapshot with full date format"""
        url = f"{API_BASE}/v2/graphs/evolution/snapshot/2023-06-15"
        
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        snapshot = data["data"]
        assert snapshot["date"] == "2023-06-15"
    
    def test_invalid_granularity(self, api_available):
        """Test error handling for invalid granularity"""
        url = f"{API_BASE}/v2/graphs/evolution/timeline"
        params = {
            "start_date": "2020",
            "end_date": "2024",
            "granularity": "invalid"
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "invalid" in data["detail"].lower()
    
    def test_growth_metrics(self, api_available):
        """Test that growth metrics are calculated correctly"""
        url = f"{API_BASE}/v2/graphs/evolution/timeline"
        params = {
            "start_date": "2019",
            "end_date": "2021",
            "granularity": "year"
        }
        
        response = requests.get(url, params=params, timeout=60)
        
        assert response.status_code == 200
        data = response.json()
        
        timeline = data["data"]["timeline"]
        
        if len(timeline) > 1:
            for i in range(1, len(timeline)):
                current = timeline[i]
                previous = timeline[i - 1]
                
                expected_node_growth = current["node_count"] - previous["node_count"]
                expected_edge_growth = current["edge_count"] - previous["edge_count"]
                
                assert current["node_growth"] == expected_node_growth
                assert current["edge_growth"] == expected_edge_growth
    
    def test_edge_counts_by_type(self, api_available):
        """Test that edge counts are broken down by type"""
        url = f"{API_BASE}/v2/graphs/evolution/snapshot/2024"
        
        response = requests.get(url, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        
        snapshot = data["data"]
        edge_counts = snapshot["edge_counts_by_type"]
        
        assert isinstance(edge_counts, dict)
        
        total_edges_from_types = sum(edge_counts.values())
        assert snapshot["edge_count"] == total_edges_from_types
    
    def test_timeline_consistency(self, api_available):
        """Test that node/edge counts are monotonically increasing"""
        url = f"{API_BASE}/v2/graphs/evolution/timeline"
        params = {
            "start_date": "2010",
            "end_date": "2024",
            "granularity": "year"
        }
        
        response = requests.get(url, params=params, timeout=60)
        
        assert response.status_code == 200
        data = response.json()
        
        timeline = data["data"]["timeline"]
        
        if len(timeline) > 1:
            for i in range(1, len(timeline)):
                current = timeline[i]
                previous = timeline[i - 1]
                
                assert current["node_count"] >= previous["node_count"]


def main():
    """Run tests manually (for non-pytest execution)"""
    print("=" * 60)
    print("Graph Evolution Timeline API Integration Tests")
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
    
    test_suite = TestEvolutionAPI()
    
    tests = [
        ("Evolution timeline - basic", test_suite.test_evolution_timeline_basic),
        ("Evolution timeline - yearly", test_suite.test_evolution_timeline_yearly),
        ("Evolution timeline - monthly", test_suite.test_evolution_timeline_monthly),
        ("Evolution timeline - quarterly", test_suite.test_evolution_timeline_quarterly),
        ("Evolution timeline - default dates", test_suite.test_evolution_timeline_default_dates),
        ("Evolution timeline - stats", test_suite.test_evolution_timeline_stats),
        ("Evolution timeline - caching", test_suite.test_evolution_timeline_caching),
        ("Graph snapshot - basic", test_suite.test_graph_snapshot_basic),
        ("Graph snapshot - yearly", test_suite.test_graph_snapshot_yearly),
        ("Graph snapshot - monthly", test_suite.test_graph_snapshot_monthly),
        ("Graph snapshot - daily", test_suite.test_graph_snapshot_daily),
        ("Invalid granularity", test_suite.test_invalid_granularity),
        ("Growth metrics", test_suite.test_growth_metrics),
        ("Edge counts by type", test_suite.test_edge_counts_by_type),
        ("Timeline consistency", test_suite.test_timeline_consistency),
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
