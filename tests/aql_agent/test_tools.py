"""Tests for aql_agent tools (mocked DB)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from aql_agent import tools as _tools


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.collections.return_value = [
        {"name": "objects", "type": 2},
        {"name": "policies", "type": 2},
        {"name": "claims", "type": 2},
        {"name": "collision_risk_edges", "type": 3},
        {"name": "_system", "type": 2},
    ]
    return db


def test_list_collections(mock_db):
    with patch("aql_agent.tools._get_db", return_value=mock_db), \
         patch("aql_agent.schema_cache._collections_cache", None), \
         patch("aql_agent.schema_cache._collections_cache_ts", 0.0):
        result = _tools.list_collections.invoke({})
    assert "vertex" in result
    assert "edge" in result
    assert "objects" in result["vertex"]
    assert "policies" in result["vertex"]
    assert "collision_risk_edges" in result["edge"]
    assert "_system" not in result["vertex"]
    assert "_system" not in result["edge"]


def test_describe_collection_not_found(mock_db):
    with patch("aql_agent.tools._get_db", return_value=mock_db), \
         patch("aql_agent.schema_cache.get_all_collection_names", return_value=["objects", "policies"]):
        result = _tools.describe_collection.invoke({"name": "nonexistent"})
    assert "error" in result
    assert result["error"] == "collection not found"


def test_describe_collection_found(mock_db):
    mock_cursor = MagicMock()
    mock_cursor.__iter__ = MagicMock(return_value=iter([
        {"_key": "1", "canonical": {"satellite_name": "ISS", "status": "in orbit"}},
        {"_key": "2", "canonical": {"satellite_name": "STARLINK-1", "status": "in orbit"}},
    ]))
    mock_db.aql.execute.return_value = mock_cursor

    with patch("aql_agent.tools._get_db", return_value=mock_db), \
         patch("aql_agent.schema_cache.get_all_collection_names", return_value=["objects", "policies"]), \
         patch("aql_agent.schema_cache.get_collections", return_value={"vertex": ["objects", "policies"], "edge": []}):
        result = _tools.describe_collection.invoke({"name": "objects"})

    assert result.get("collection") == "objects"
    assert "fields" in result
    assert "sample" in result


def test_distinct_values(mock_db):
    mock_cursor = MagicMock()
    mock_cursor.__iter__ = MagicMock(return_value=iter(["Austria", "Australia", "Belgium"]))
    mock_db.aql.execute.return_value = mock_cursor

    with patch("aql_agent.tools._get_db", return_value=mock_db):
        result = _tools.distinct_values.invoke({
            "collection": "objects",
            "field": "canonical.country_of_origin",
            "limit": 50,
            "contains": "",
        })

    assert "values" in result
    assert isinstance(result["values"], list)
    assert "Austria" in result["values"]


def test_distinct_values_with_contains(mock_db):
    mock_cursor = MagicMock()
    mock_cursor.__iter__ = MagicMock(return_value=iter(["Austria"]))
    mock_db.aql.execute.return_value = mock_cursor

    with patch("aql_agent.tools._get_db", return_value=mock_db):
        result = _tools.distinct_values.invoke({
            "collection": "objects",
            "field": "canonical.country_of_origin",
            "limit": 50,
            "contains": "aust",
        })

    assert "values" in result


def test_validate_aql_write_rejected():
    with patch("aql_agent.tools._get_db", return_value=None):
        result = _tools.validate_aql.invoke({
            "aql": "INSERT {x: 1} INTO objects",
            "bind_vars": {},
        })
    assert not result["ok"]
    assert any(e["code"] == "WRITE_OPERATION" for e in result["errors"])


def test_validate_aql_clean():
    mock_db = MagicMock()
    mock_db.aql.validate.return_value = None
    with patch("aql_agent.tools._get_db", return_value=mock_db), \
         patch("aql_agent.validator.get_all_collection_names", return_value=["objects"]):
        result = _tools.validate_aql.invoke({
            "aql": "FOR s IN objects LIMIT 10 RETURN s",
            "bind_vars": {},
        })
    assert result["ok"]


def test_submit_answer_returns_submitted():
    result = _tools.submit_answer.invoke({
        "aql": "FOR s IN objects LIMIT 10 RETURN s",
        "bind_vars": {},
        "explanation": "Returns objects",
        "confidence": "high",
        "assumptions": [],
        "alternative": None,
    })
    assert result == "submitted"


def test_tools_list_length():
    assert len(_tools.TOOLS) == 6
