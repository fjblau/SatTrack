"""
Integration tests for DISCOS ingestion pipeline.

Follows existing pattern: hits live API at http://localhost:8000.
No DB isolation; real ArangoDB is used.
DISCOS HTTP client is mocked to avoid live DISCOS API calls.

Mark tests requiring real DISCOS API with @pytest.mark.requires_discos.
"""
import pytest
import requests

BASE_URL = "http://localhost:8000"


def _api(path: str, **kwargs) -> requests.Response:
    return requests.get(f"{BASE_URL}{path}", **kwargs)


@pytest.mark.integration
class TestDiscosStatusEndpoint:
    def test_discos_status_returns_json(self):
        resp = _api("/v2/admin/discos-status")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] in ("ready", "not_configured", "error")

    def test_discos_status_has_expected_fields(self):
        resp = _api("/v2/admin/discos-status")
        assert resp.status_code == 200
        data = resp.json()
        assert "token_configured" in data
        assert "base_url" in data
        assert "status" in data


@pytest.mark.integration
class TestProvenanceSummaryEndpoint:
    def test_provenance_summary_returns_counts(self):
        resp = _api("/v2/provenance/summary")
        assert resp.status_code == 200
        data = resp.json()
        expected_keys = [
            "fragmentation_events",
            "launch_events",
            "launch_vehicles",
            "launch_sites",
            "entities",
            "fragmented_from_edges",
            "caused_by_edges",
            "launched_by_edges",
            "launched_via_edges",
            "launched_from_edges",
        ]
        for key in expected_keys:
            assert key in data, f"Missing key: {key}"
            assert isinstance(data[key], int), f"Expected int for {key}"


@pytest.mark.integration
class TestProvenanceObjectChain:
    def test_nonexistent_object_returns_404(self):
        resp = _api("/v2/provenance/objects/NONEXISTENT_KEY_99999/chain")
        assert resp.status_code == 404

    def test_nonexistent_object_siblings_returns_404(self):
        resp = _api("/v2/provenance/objects/NONEXISTENT_KEY_99999/siblings")
        assert resp.status_code == 404


@pytest.mark.integration
class TestProvenanceEventEndpoint:
    def test_nonexistent_event_returns_404(self):
        resp = _api("/v2/provenance/events/NONEXISTENT_KEY_99999")
        assert resp.status_code == 404


@pytest.mark.integration
class TestInferenceStub:
    def test_attribute_fragmentation_returns_501(self):
        resp = requests.post(
            f"{BASE_URL}/v2/inference/attribute-fragmentation",
            json={"object_key": "test-key"},
        )
        assert resp.status_code == 501


@pytest.mark.integration
class TestScriptCatalogueDiscosEntries:
    def test_discos_scripts_in_catalogue(self):
        resp = _api("/v2/admin/scripts")
        assert resp.status_code == 200
        scripts = {s["id"]: s for s in resp.json()["scripts"]}
        expected_ids = [
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
        for script_id in expected_ids:
            assert script_id in scripts, f"Missing script: {script_id}"

    def test_discos_scripts_have_order_hints(self):
        resp = _api("/v2/admin/scripts")
        assert resp.status_code == 200
        scripts = {s["id"]: s for s in resp.json()["scripts"]}
        for script_id in ["ingest_discos_entities", "ingest_discos_objects"]:
            if script_id in scripts:
                assert scripts[script_id].get("order_hint") is not None
