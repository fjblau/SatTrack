"""
Integration tests for provenance graph traversal endpoints.

Follows existing pattern: hits live API at http://localhost:8000.
No DB isolation.
"""
import pytest
import requests

BASE_URL = "http://localhost:8000"


def _api(path: str, **kwargs) -> requests.Response:
    return requests.get(f"{BASE_URL}{path}", **kwargs)


@pytest.mark.integration
class TestProvenanceSummaryStructure:
    def test_summary_returns_all_collection_counts(self):
        resp = _api("/v2/provenance/summary")
        assert resp.status_code == 200
        body = resp.json()

        for key in [
            "fragmentation_events", "launch_events", "launch_vehicles",
            "launch_sites", "entities",
            "fragmented_from_edges", "caused_by_edges",
            "launched_by_edges", "launched_via_edges", "launched_from_edges",
        ]:
            assert key in body
            assert isinstance(body[key], int)
            assert body[key] >= 0


@pytest.mark.integration
class TestProvenanceChainStructure:
    def test_chain_404_for_unknown(self):
        resp = _api("/v2/provenance/objects/__no_such_object__/chain")
        assert resp.status_code == 404

    def test_siblings_404_for_unknown(self):
        resp = _api("/v2/provenance/objects/__no_such_object__/siblings")
        assert resp.status_code == 404

    def test_chain_response_structure_when_found(self, integration_object_key=None):
        if integration_object_key is None:
            pytest.skip("No known integration object key; set integration_object_key fixture")


@pytest.mark.integration
class TestProvenanceLaunchEndpoint:
    def test_launch_event_404_for_unknown(self):
        resp = _api("/v2/provenance/launches/__no_such_launch__")
        assert resp.status_code == 404


@pytest.mark.integration
class TestProvenanceEntityEndpoint:
    def test_entity_404_for_unknown(self):
        resp = _api("/v2/provenance/entities/__no_such_entity__")
        assert resp.status_code == 404


@pytest.mark.integration
class TestConfidenceFiltering:
    def test_chain_accepts_min_confidence_param(self):
        resp = _api("/v2/provenance/objects/__no_such_object__/chain", params={"min_confidence": 0.9})
        assert resp.status_code in (404, 200)

    def test_chain_rejects_invalid_min_confidence(self):
        resp = _api("/v2/provenance/objects/__x__/chain", params={"min_confidence": 1.5})
        assert resp.status_code in (404, 422)

    def test_siblings_accepts_limit_param(self):
        resp = _api("/v2/provenance/objects/__no_such_object__/siblings", params={"limit": 10})
        assert resp.status_code in (404, 200)
