"""Tests for aql_agent.schema_cache — TTL caching, Levenshtein, field flattening."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

import aql_agent.schema_cache as sc
from aql_agent.schema_cache import (
    _levenshtein,
    did_you_mean,
    flatten_fields,
    get_all_collection_names,
    get_collections,
    describe_collection,
    invalidate_cache,
)


@pytest.fixture(autouse=True)
def _reset_cache():
    invalidate_cache()
    yield
    invalidate_cache()


def _make_db(collections=None):
    db = MagicMock()
    if collections is None:
        collections = [
            {"name": "objects", "type": 2},
            {"name": "policies", "type": 2},
            {"name": "collision_risk_edges", "type": 3},
            {"name": "_system", "type": 2},
        ]
    db.collections.return_value = collections
    return db


class TestLevenshtein:
    def test_identical_strings_zero(self):
        assert _levenshtein("abc", "abc") == 0

    def test_empty_a_returns_len_b(self):
        assert _levenshtein("", "hello") == 5

    def test_empty_b_returns_len_a(self):
        assert _levenshtein("hello", "") == 5

    def test_both_empty_zero(self):
        assert _levenshtein("", "") == 0

    def test_single_insertion(self):
        assert _levenshtein("abc", "abcd") == 1

    def test_single_deletion(self):
        assert _levenshtein("abcd", "abc") == 1

    def test_single_substitution(self):
        assert _levenshtein("abc", "axc") == 1

    def test_typo_sattelites(self):
        assert _levenshtein("sattelites", "satellites") == 2

    def test_completely_different(self):
        dist = _levenshtein("objects", "policies")
        assert dist > 3

    def test_case_sensitive(self):
        assert _levenshtein("ABC", "abc") == 3


class TestDidYouMean:
    def test_exact_match_returned(self):
        result = did_you_mean("objects", ["objects", "policies", "claims"])
        assert "objects" in result

    def test_close_typo_returned(self):
        result = did_you_mean("satelites", ["satellites", "objects", "policies"])
        assert "satellites" in result

    def test_no_match_returns_empty(self):
        result = did_you_mean("zzzzz", ["objects", "policies", "claims"])
        assert result == []

    def test_threshold_1_excludes_distant(self):
        result = did_you_mean("claims", ["objects", "policies"], threshold=1)
        assert result == []

    def test_case_insensitive_match(self):
        result = did_you_mean("Objects", ["objects", "policies"])
        assert "objects" in result


class TestFlattenFields:
    def test_flat_doc(self):
        doc = {"name": "ISS", "norad": 25544}
        fields = flatten_fields(doc)
        assert "name" in fields
        assert "norad" in fields

    def test_nested_doc(self):
        doc = {"canonical": {"satellite_name": "ISS", "status": "in orbit"}}
        fields = flatten_fields(doc)
        assert "canonical" in fields
        assert "canonical.satellite_name" in fields
        assert "canonical.status" in fields

    def test_deeply_nested_respects_max_depth(self):
        doc = {"a": {"b": {"c": {"d": {"e": "deep"}}}}}
        fields = flatten_fields(doc, max_depth=3)
        assert "a" in fields
        assert "a.b" in fields
        assert "a.b.c" in fields
        assert "a.b.c.d" not in fields

    def test_empty_doc(self):
        assert flatten_fields({}) == []

    def test_prefix_prepended(self):
        doc = {"name": "ISS"}
        fields = flatten_fields(doc, prefix="canonical")
        assert "canonical.name" in fields


class TestGetCollections:
    def test_separates_vertex_and_edge(self):
        db = _make_db()
        result = get_collections(db)
        assert "objects" in result["vertex"]
        assert "policies" in result["vertex"]
        assert "collision_risk_edges" in result["edge"]

    def test_skips_system_collections(self):
        db = _make_db()
        result = get_collections(db)
        assert "_system" not in result["vertex"]
        assert "_system" not in result["edge"]

    def test_returns_sorted_lists(self):
        db = _make_db([
            {"name": "zebra", "type": 2},
            {"name": "alpha", "type": 2},
        ])
        result = get_collections(db)
        assert result["vertex"] == sorted(result["vertex"])

    def test_cache_hit_skips_db_call(self):
        db = _make_db()
        get_collections(db)
        db.collections.reset_mock()
        get_collections(db)
        db.collections.assert_not_called()

    def test_cache_miss_after_invalidate(self):
        db = _make_db()
        get_collections(db)
        invalidate_cache()
        db.collections.reset_mock()
        get_collections(db)
        db.collections.assert_called_once()

    def test_db_error_returns_empty(self):
        db = MagicMock()
        db.collections.side_effect = Exception("DB offline")
        result = get_collections(db)
        assert result == {"vertex": [], "edge": []}


class TestGetAllCollectionNames:
    def test_combines_vertex_and_edge(self):
        db = _make_db()
        names = get_all_collection_names(db)
        assert "objects" in names
        assert "collision_risk_edges" in names

    def test_no_system_collections(self):
        db = _make_db()
        names = get_all_collection_names(db)
        for name in names:
            assert not name.startswith("_")


class TestDescribeCollection:
    def test_not_found_returns_error(self):
        db = _make_db()
        with patch("aql_agent.schema_cache.get_all_collection_names", return_value=["objects"]):
            result = describe_collection(db, "nonexistent")
        assert "error" in result
        assert result["error"] == "collection not found"

    def test_not_found_returns_did_you_mean(self):
        db = _make_db()
        with patch("aql_agent.schema_cache.get_all_collection_names", return_value=["objects"]), \
             patch("aql_agent.schema_cache.did_you_mean", return_value=["objects"]):
            result = describe_collection(db, "objectss")
        assert "did_you_mean" in result

    def test_found_returns_fields_and_sample(self):
        db = _make_db()
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = MagicMock(return_value=iter([
            {"_key": "1", "canonical": {"satellite_name": "ISS", "status": "in orbit"}},
        ]))
        db.aql.execute.return_value = mock_cursor
        with patch("aql_agent.schema_cache.get_all_collection_names", return_value=["objects"]), \
             patch("aql_agent.schema_cache.get_collections", return_value={"vertex": ["objects"], "edge": []}):
            result = describe_collection(db, "objects")
        assert result.get("collection") == "objects"
        assert "fields" in result
        assert "sample" in result
        assert "canonical.satellite_name" in result["fields"]

    def test_cache_hit(self):
        db = _make_db()
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = MagicMock(return_value=iter([{"_key": "1"}]))
        db.aql.execute.return_value = mock_cursor
        with patch("aql_agent.schema_cache.get_all_collection_names", return_value=["objects"]), \
             patch("aql_agent.schema_cache.get_collections", return_value={"vertex": ["objects"], "edge": []}):
            describe_collection(db, "objects")
            db.aql.execute.reset_mock()
            describe_collection(db, "objects")
        db.aql.execute.assert_not_called()

    def test_describe_edge_collection(self):
        db = _make_db()
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = MagicMock(return_value=iter([
            {"_from": "objects/1", "_to": "objects/2", "risk": 0.5}
        ]))
        db.aql.execute.return_value = mock_cursor
        with patch("aql_agent.schema_cache.get_all_collection_names", return_value=["collision_risk_edges"]), \
             patch("aql_agent.schema_cache.get_collections", return_value={"vertex": [], "edge": ["collision_risk_edges"]}):
            result = describe_collection(db, "collision_risk_edges")
        assert result.get("is_edge") is True

    def test_db_error_returns_error_dict(self):
        db = _make_db()
        db.aql.execute.side_effect = Exception("timeout")
        with patch("aql_agent.schema_cache.get_all_collection_names", return_value=["objects"]), \
             patch("aql_agent.schema_cache.get_collections", return_value={"vertex": ["objects"], "edge": []}):
            result = describe_collection(db, "objects")
        assert "error" in result
