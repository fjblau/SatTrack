#!/usr/bin/env python3
"""
Integration tests for the /v2/analytics/* endpoints.

Requires a running API server (default: http://localhost:8000) with ArangoDB
connected and at least one satellite with stored TLE history.

Tests are skipped automatically when the server is not reachable.
"""
import pytest
import requests
from datetime import datetime, timezone

API_BASE = "http://localhost:8000"

KNOWN_NORAD_ID = "25544"


@pytest.fixture(scope="module")
def api_available():
    try:
        r = requests.get(f"{API_BASE}/v2/health", timeout=3)
        if r.status_code != 200:
            pytest.skip("API server returned non-200 on /v2/health")
    except Exception:
        pytest.skip("API server not reachable")


@pytest.fixture(scope="module")
def norad_with_history(api_available):
    """Return a NORAD ID that has TLE history, or skip."""
    candidates = [KNOWN_NORAD_ID, "43013", "49260"]
    for nid in candidates:
        r = requests.get(f"{API_BASE}/v2/tle-history/{nid}/coverage", timeout=5)
        if r.status_code == 200 and r.json().get("covered"):
            return nid
    pytest.skip("No satellite with stored TLE history found; seed TLE history first.")


class TestAnalyticsHealth:
    def test_health_score_returns_200(self, norad_with_history):
        r = requests.get(f"{API_BASE}/v2/analytics/health/{norad_with_history}", timeout=10)
        assert r.status_code == 200

    def test_health_score_shape(self, norad_with_history):
        r = requests.get(f"{API_BASE}/v2/analytics/health/{norad_with_history}", timeout=10)
        data = r.json()
        assert "health_score" in data
        assert "factors" in data
        assert "computed_at" in data
        assert "norad_id" in data
        assert 0.0 <= data["health_score"] <= 100.0

    def test_health_score_factors_present(self, norad_with_history):
        r = requests.get(f"{API_BASE}/v2/analytics/health/{norad_with_history}", timeout=10)
        factors = r.json()["factors"]
        expected_keys = ["tle_age_days", "eccentricity", "perigee_altitude_km", "bstar_drag"]
        for key in expected_keys:
            assert key in factors

    def test_health_score_unknown_norad_returns_404(self, api_available):
        r = requests.get(f"{API_BASE}/v2/analytics/health/999999999", timeout=10)
        assert r.status_code == 404


class TestAnalyticsAnomalies:
    def test_anomalies_returns_200(self, norad_with_history):
        r = requests.get(f"{API_BASE}/v2/analytics/anomalies/{norad_with_history}", timeout=10)
        assert r.status_code == 200

    def test_anomalies_shape(self, norad_with_history):
        r = requests.get(f"{API_BASE}/v2/analytics/anomalies/{norad_with_history}", timeout=10)
        data = r.json()
        assert "norad_id" in data
        assert "change_points" in data
        assert "severity" in data
        assert data["severity"] in ("none", "low", "medium", "high")

    def test_anomalies_custom_threshold(self, norad_with_history):
        r = requests.get(
            f"{API_BASE}/v2/analytics/anomalies/{norad_with_history}",
            params={"cusum_threshold": 3.0, "cusum_drift": 0.3},
            timeout=10,
        )
        assert r.status_code == 200
        data = r.json()
        assert "threshold_used" in data or "change_points" in data

    def test_anomalies_unknown_norad_returns_404(self, api_available):
        r = requests.get(f"{API_BASE}/v2/analytics/anomalies/999999999", timeout=10)
        assert r.status_code == 404


class TestAnalyticsManeuvers:
    def test_maneuvers_returns_200(self, norad_with_history):
        r = requests.get(f"{API_BASE}/v2/analytics/maneuvers/{norad_with_history}", timeout=10)
        assert r.status_code == 200

    def test_maneuvers_shape(self, norad_with_history):
        r = requests.get(f"{API_BASE}/v2/analytics/maneuvers/{norad_with_history}", timeout=10)
        data = r.json()
        assert "norad_id" in data
        assert "maneuver_events" in data
        assert "maneuver_count" in data
        assert "total_pairs_checked" in data
        assert isinstance(data["maneuver_events"], list)

    def test_maneuvers_count_matches_events(self, norad_with_history):
        r = requests.get(f"{API_BASE}/v2/analytics/maneuvers/{norad_with_history}", timeout=10)
        data = r.json()
        assert data["maneuver_count"] == len(data["maneuver_events"])

    def test_maneuvers_unknown_norad_returns_404(self, api_available):
        r = requests.get(f"{API_BASE}/v2/analytics/maneuvers/999999999", timeout=10)
        assert r.status_code == 404


class TestAnalyticsReentry:
    def test_reentry_returns_200(self, norad_with_history):
        r = requests.get(f"{API_BASE}/v2/analytics/reentry/{norad_with_history}", timeout=10)
        assert r.status_code == 200

    def test_reentry_shape(self, norad_with_history):
        r = requests.get(f"{API_BASE}/v2/analytics/reentry/{norad_with_history}", timeout=10)
        data = r.json()
        assert "norad_id" in data
        assert "predicted_reentry_date" in data
        assert "model_selected" in data or "n_points" in data

    def test_reentry_unknown_norad_returns_404(self, api_available):
        r = requests.get(f"{API_BASE}/v2/analytics/reentry/999999999", timeout=10)
        assert r.status_code == 404


class TestAnalyticsSimilar:
    def test_similar_returns_200(self, norad_with_history):
        r = requests.get(f"{API_BASE}/v2/analytics/similar/{norad_with_history}", timeout=15)
        assert r.status_code == 200

    def test_similar_shape(self, norad_with_history):
        r = requests.get(f"{API_BASE}/v2/analytics/similar/{norad_with_history}", timeout=15)
        data = r.json()
        assert "norad_id" in data
        assert "results" in data
        assert "result_count" in data
        assert isinstance(data["results"], list)

    def test_similar_top_k_respected(self, norad_with_history):
        r = requests.get(
            f"{API_BASE}/v2/analytics/similar/{norad_with_history}",
            params={"top_k": 5},
            timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["results"]) <= 5


class TestAnalyticsSummary:
    def test_summary_returns_200_or_404(self, norad_with_history):
        r = requests.get(f"{API_BASE}/v2/analytics/summary/{norad_with_history}", timeout=30)
        assert r.status_code in (200, 404)

    def test_summary_200_shape(self, norad_with_history):
        r = requests.get(f"{API_BASE}/v2/analytics/summary/{norad_with_history}", timeout=30)
        if r.status_code == 404:
            pytest.skip("No summary available and TLE history insufficient")
        data = r.json()
        assert "norad_id" in data
        assert "health_score" in data
        assert "updated_at" in data

    def test_summary_recompute_flag(self, norad_with_history):
        r = requests.get(
            f"{API_BASE}/v2/analytics/summary/{norad_with_history}",
            params={"recompute": True},
            timeout=60,
        )
        assert r.status_code in (200, 404)

    def test_summary_unknown_norad_returns_404(self, api_available):
        r = requests.get(f"{API_BASE}/v2/analytics/summary/999999999", timeout=10)
        assert r.status_code == 404


class TestAnalyticsBatch:
    def test_overview_batch_returns_200(self, api_available):
        r = requests.get(f"{API_BASE}/v2/analytics/overview/batch", timeout=15)
        assert r.status_code == 200

    def test_overview_batch_shape(self, api_available):
        r = requests.get(f"{API_BASE}/v2/analytics/overview/batch", timeout=15)
        data = r.json()
        assert "results" in data
        assert "count" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["results"], list)

    def test_overview_batch_pagination(self, api_available):
        r = requests.get(
            f"{API_BASE}/v2/analytics/overview/batch",
            params={"limit": 10, "offset": 0},
            timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["limit"] == 10
        assert data["offset"] == 0

    def test_health_batch_requires_norad_ids(self, api_available):
        r = requests.get(f"{API_BASE}/v2/analytics/health/batch", timeout=10)
        assert r.status_code == 422

    def test_health_batch_with_valid_ids(self, norad_with_history):
        r = requests.get(
            f"{API_BASE}/v2/analytics/health/batch",
            params={"norad_ids": norad_with_history},
            timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert "results" in data
        assert "count" in data
        assert isinstance(data["results"], list)
        assert len(data["results"]) >= 1

    def test_health_batch_result_shape(self, norad_with_history):
        r = requests.get(
            f"{API_BASE}/v2/analytics/health/batch",
            params={"norad_ids": norad_with_history},
            timeout=15,
        )
        assert r.status_code == 200
        results = r.json()["results"]
        if results and "health_score" in results[0]:
            assert 0.0 <= results[0]["health_score"] <= 100.0

    def test_health_batch_unknown_ids_return_error_field(self, api_available):
        r = requests.get(
            f"{API_BASE}/v2/analytics/health/batch",
            params={"norad_ids": "999999998,999999999"},
            timeout=10,
        )
        assert r.status_code == 200
        results = r.json()["results"]
        for item in results:
            assert "error" in item


class TestAnalyticsProxyBatch:
    def _valid_payload(self):
        return {
            "objects": [
                {
                    "norad_id": "25544",
                    "tle_epoch": "2026-01-15T00:00:00Z",
                    "eccentricity": 0.0006703,
                    "perigee_km": 408.5,
                    "bstar": 0.000021,
                    "anomaly_count": 0,
                }
            ]
        }

    def test_proxy_batch_returns_200(self, api_available):
        r = requests.post(
            f"{API_BASE}/v2/analytics/health/proxy-batch",
            json=self._valid_payload(),
            timeout=10,
        )
        assert r.status_code == 200

    def test_proxy_batch_shape(self, api_available):
        r = requests.post(
            f"{API_BASE}/v2/analytics/health/proxy-batch",
            json=self._valid_payload(),
            timeout=10,
        )
        data = r.json()
        assert "results" in data
        assert "count" in data
        assert data["count"] == 1
        result = data["results"][0]
        assert "health_score" in result
        assert 0.0 <= result["health_score"] <= 100.0

    def test_proxy_batch_multiple_objects(self, api_available):
        payload = {
            "objects": [
                {
                    "norad_id": str(i),
                    "tle_epoch": "2026-01-01T00:00:00Z",
                    "eccentricity": 0.001,
                    "perigee_km": 400.0 + i,
                    "bstar": 0.00002,
                }
                for i in range(5)
            ]
        }
        r = requests.post(
            f"{API_BASE}/v2/analytics/health/proxy-batch",
            json=payload,
            timeout=10,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 5

    def test_proxy_batch_empty_objects_returns_400(self, api_available):
        r = requests.post(
            f"{API_BASE}/v2/analytics/health/proxy-batch",
            json={"objects": []},
            timeout=10,
        )
        assert r.status_code == 400

    def test_proxy_batch_missing_required_field_returns_422(self, api_available):
        r = requests.post(
            f"{API_BASE}/v2/analytics/health/proxy-batch",
            json={"objects": [{"norad_id": "25544"}]},
            timeout=10,
        )
        assert r.status_code == 422

    def test_proxy_batch_invalid_body_returns_422(self, api_available):
        r = requests.post(
            f"{API_BASE}/v2/analytics/health/proxy-batch",
            json={"not_objects": []},
            timeout=10,
        )
        assert r.status_code == 422


class TestAdminAnalyticsPrecompute:
    def test_precompute_status_returns_200(self, api_available):
        r = requests.get(f"{API_BASE}/v2/admin/analytics/precompute/status", timeout=10)
        assert r.status_code == 200

    def test_precompute_status_shape(self, api_available):
        r = requests.get(f"{API_BASE}/v2/admin/analytics/precompute/status", timeout=10)
        data = r.json()
        assert "running" in data
        assert isinstance(data["running"], bool)

    def test_precompute_trigger_sync_small_batch(self, api_available):
        payload = {
            "norad_ids": [],
            "max_objects": 2,
            "background": False,
        }
        r = requests.post(
            f"{API_BASE}/v2/admin/analytics/precompute",
            json=payload,
            timeout=60,
        )
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert data["status"] in ("completed", "already_running")

    def test_precompute_trigger_background(self, api_available):
        payload = {
            "norad_ids": [],
            "max_objects": 1,
            "background": True,
        }
        r = requests.post(
            f"{API_BASE}/v2/admin/analytics/precompute",
            json=payload,
            timeout=10,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] in ("accepted", "already_running")
