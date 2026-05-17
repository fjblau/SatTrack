#!/usr/bin/env python3
"""
Integration tests for the customer tasks API endpoints.

Requires a live API server with seed data from seed_customer_tasks.py.
Tests are skipped gracefully if the server is not available.
"""
import requests
import pytest

API_BASE = "http://localhost:8000"


@pytest.fixture(scope="module")
def api_available():
    """Check if API is available before running tests."""
    try:
        response = requests.get(f"{API_BASE}/v2/health", timeout=2)
        if response.status_code != 200:
            pytest.skip("API server not available")
    except Exception:
        pytest.skip("API server not available")


class TestCustomerTasksAPI:

    def test_list_tasks_returns_200(self, api_available):
        response = requests.get(f"{API_BASE}/v2/customer-tasks", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_task_detail_includes_overlay_fields(self, api_available):
        response = requests.get(
            f"{API_BASE}/v2/customer-tasks/TSK-2026-0001", timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert "customer_status" in data
        assert "allowed_next_states" in data
        assert "observation_count" in data
        assert "passes" in data
