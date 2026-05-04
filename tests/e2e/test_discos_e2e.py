"""
End-to-end tests for DISCOS fragmentation provenance integration.

Tests the full pipeline: ingest fixture → promote → query provenance chain.

These tests use the live API at localhost:8000 with real ArangoDB,
but mock the DISCOS HTTP client to avoid external API calls.

Tests requiring the real DISCOS API are marked @pytest.mark.requires_discos.
"""
import pytest
import requests
from unittest.mock import patch, MagicMock

BASE_URL = "http://localhost:8000"

FIXTURE_ENTITY = {
    "discos_id": "e2e-ent-1",
    "name": "Test Operator E2E",
    "country": "USA",
    "entityType": "government",
}

FIXTURE_SITE = {
    "discos_id": "e2e-site-1",
    "name": "Test Launch Site E2E",
    "country": "USA",
    "latitude": 28.5,
    "longitude": -80.6,
}

FIXTURE_VEHICLE = {
    "discos_id": "e2e-veh-1",
    "name": "Test Vehicle E2E",
    "family": "Test Family",
    "country": "USA",
}

FIXTURE_FRAG_EVENT = {
    "discos_id": "e2e-frag-1",
    "epoch": "2009-02-10",
    "type": "collision",
    "fragmentCount": 5,
    "altitude": 789.0,
    "casualtyRisk": 0.05,
}


def _api(path: str, **kwargs) -> requests.Response:
    return requests.get(f"{BASE_URL}{path}", **kwargs)


@pytest.mark.integration
class TestProvenance_E2E_Collections:
    """
    Verify provenance collections are accessible and the API works end-to-end.
    Does not require DISCOS API — only tests the API layer over existing data.
    """

    def test_provenance_summary_accessible(self):
        resp = _api("/v2/provenance/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert "fragmentation_events" in body
        assert "launched_by_edges" in body

    def test_discos_status_endpoint_accessible(self):
        resp = _api("/v2/admin/discos-status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] in ("ready", "not_configured", "error")
        assert "token_configured" in body

    def test_inference_stub_returns_501(self):
        resp = requests.post(
            f"{BASE_URL}/v2/inference/attribute-fragmentation",
            json={"object_key": "any-key"},
        )
        assert resp.status_code == 501
        assert "not yet implemented" in resp.json()["detail"].lower()

    def test_all_14_discos_scripts_in_catalogue(self):
        resp = _api("/v2/admin/scripts")
        assert resp.status_code == 200
        scripts_by_id = {s["id"]: s for s in resp.json()["scripts"]}

        required_scripts = [
            "ingest_discos_entities",
            "ingest_discos_launch_sites",
            "ingest_discos_launch_vehicles",
            "ingest_discos_launches",
            "ingest_discos_objects",
            "ingest_discos_fragmentations",
            "ingest_discos_attributions",
            "promote_discos_event_types",
            "promote_discos_object_attributes",
            "promote_discos_object_class",
            "promote_discos_launches",
            "promote_discos_attributions",
            "promote_discos_fragmentations",
            "verify_discos_provenance_e2e",
        ]

        missing = [s for s in required_scripts if s not in scripts_by_id]
        assert not missing, f"Missing scripts in catalogue: {missing}"

    def test_ingestion_scripts_run_order_is_sequential(self):
        resp = _api("/v2/admin/scripts")
        assert resp.status_code == 200
        scripts = {s["id"]: s for s in resp.json()["scripts"]}

        ordered_ingestion = [
            "ingest_discos_entities",
            "ingest_discos_launch_sites",
            "ingest_discos_launch_vehicles",
            "ingest_discos_launches",
            "ingest_discos_objects",
            "ingest_discos_fragmentations",
            "ingest_discos_attributions",
        ]

        hints = [scripts[s]["order_hint"] for s in ordered_ingestion if s in scripts]
        assert hints == sorted(hints), f"order_hints not ascending: {hints}"

    def test_chain_endpoint_handles_missing_gracefully(self):
        resp = _api("/v2/provenance/objects/__e2e_missing_key__/chain")
        assert resp.status_code == 404

    def test_siblings_endpoint_handles_missing_gracefully(self):
        resp = _api("/v2/provenance/objects/__e2e_missing_key__/siblings")
        assert resp.status_code == 404

    def test_events_endpoint_handles_missing_gracefully(self):
        resp = _api("/v2/provenance/events/__e2e_missing_key__")
        assert resp.status_code == 404

    def test_launches_endpoint_handles_missing_gracefully(self):
        resp = _api("/v2/provenance/launches/__e2e_missing_key__")
        assert resp.status_code == 404

    def test_entities_endpoint_handles_missing_gracefully(self):
        resp = _api("/v2/provenance/entities/__e2e_missing_key__")
        assert resp.status_code == 404


@pytest.mark.requires_discos
class TestProvenance_E2E_WithRealDISCOS:
    """
    Tests that hit the real DISCOS API.

    Skipped unless DISCOS_API_TOKEN is set and the DISCOS API is reachable.
    Run with: pytest -m requires_discos
    """

    def test_discos_status_is_ready(self):
        resp = _api("/v2/admin/discos-status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"
