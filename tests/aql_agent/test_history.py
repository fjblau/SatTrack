"""Tests for aql_agent query history (§18.4)."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, call, patch

import pytest

from aql_agent import history


def _make_state(**kwargs):
    base = {
        "question": "show me satellites",
        "clarification": "",
        "clarifying_question": "",
        "aql": "FOR s IN objects LIMIT 10 RETURN s",
        "bind_vars": {},
        "row_count": 10,
        "error": "",
        "validator_errors": [],
        "confidence": "high",
        "log_id": "test-log-id",
        "started_at": datetime.utcnow(),
    }
    base.update(kwargs)
    return base


def test_record_history_writes_when_user_id_provided():
    mock_db = MagicMock()
    mock_db.has_collection.return_value = True
    mock_coll = MagicMock()
    mock_db.collection.return_value = mock_coll

    with patch("aql_agent.history._get_db", return_value=mock_db):
        key = history.record_history(_make_state(), user_id="alice")

    assert key is not None
    mock_coll.insert.assert_called_once()
    inserted = mock_coll.insert.call_args[0][0]
    assert inserted["user_id"] == "alice"
    assert inserted["starred"] is False


def test_record_history_no_write_without_user_id():
    mock_db = MagicMock()
    with patch("aql_agent.history._get_db", return_value=mock_db):
        key = history.record_history(_make_state(), user_id=None)
    assert key is None
    mock_db.collection.assert_not_called()


def test_record_history_failure_is_non_fatal():
    mock_db = MagicMock()
    mock_db.has_collection.return_value = True
    mock_coll = MagicMock()
    mock_coll.insert.side_effect = Exception("arango down")
    mock_db.collection.return_value = mock_coll

    with patch("aql_agent.history._get_db", return_value=mock_db):
        key = history.record_history(_make_state(), user_id="alice")

    assert key is None


def test_get_history_returns_items():
    mock_db = MagicMock()
    mock_db.has_collection.return_value = True
    mock_cursor = MagicMock()
    items = [
        {"key": "k1", "ts": "2026-05-14T10:30:00Z", "question": "Q1", "aql": "aql1", "row_count": 5, "outcome": "success", "confidence": "high", "starred": False},
    ]
    mock_cursor.__iter__ = MagicMock(return_value=iter(items))
    mock_db.aql.execute.return_value = mock_cursor

    with patch("aql_agent.history._get_db", return_value=mock_db):
        result = history.get_history(user_id="alice", limit=5)

    assert len(result) == 1
    assert result[0]["question"] == "Q1"


def test_get_history_ts_desc_order():
    mock_db = MagicMock()
    mock_db.has_collection.return_value = True
    mock_cursor = MagicMock()
    items = [
        {"key": "k2", "ts": "2026-05-14T12:00:00Z", "question": "newer", "aql": "", "row_count": 0, "outcome": "success", "confidence": "high", "starred": False},
        {"key": "k1", "ts": "2026-05-14T10:00:00Z", "question": "older", "aql": "", "row_count": 0, "outcome": "success", "confidence": "high", "starred": False},
    ]
    mock_cursor.__iter__ = MagicMock(return_value=iter(items))
    mock_db.aql.execute.return_value = mock_cursor

    with patch("aql_agent.history._get_db", return_value=mock_db):
        result = history.get_history(user_id="alice", limit=5)

    assert result[0]["question"] == "newer"
    assert result[1]["question"] == "older"


def test_toggle_star_sets_starred():
    mock_db = MagicMock()
    mock_db.has_collection.return_value = True
    mock_coll = MagicMock()
    mock_coll.get.return_value = {
        "_key": "k1", "user_id": "alice", "starred": False,
        "ts": "2026-05-14T10:00:00Z", "question": "Q", "aql": "", "row_count": 0, "outcome": "success", "confidence": "high",
    }
    mock_db.collection.return_value = mock_coll

    with patch("aql_agent.history._get_db", return_value=mock_db):
        result = history.toggle_star("k1", user_id="alice", starred=True)

    assert result is not None
    assert result["starred"] is True
    mock_coll.update.assert_called_once()


def test_toggle_star_cross_user_denied():
    mock_db = MagicMock()
    mock_db.has_collection.return_value = True
    mock_coll = MagicMock()
    mock_coll.get.return_value = {
        "_key": "k1", "user_id": "alice", "starred": False,
        "ts": "2026-05-14T10:00:00Z", "question": "Q", "aql": "", "row_count": 0, "outcome": "success", "confidence": "high",
    }
    mock_db.collection.return_value = mock_coll

    with patch("aql_agent.history._get_db", return_value=mock_db):
        result = history.toggle_star("k1", user_id="bob", starred=True)

    assert result is None
    mock_coll.update.assert_not_called()


def test_toggle_star_not_found():
    mock_db = MagicMock()
    mock_db.has_collection.return_value = True
    mock_coll = MagicMock()
    mock_coll.get.return_value = None
    mock_db.collection.return_value = mock_coll

    with patch("aql_agent.history._get_db", return_value=mock_db):
        result = history.toggle_star("missing-key", user_id="alice", starred=True)

    assert result is None


def test_toggle_star_no_db_returns_none():
    with patch("aql_agent.history._get_db", return_value=None):
        result = history.toggle_star("k1", user_id="alice", starred=True)
    assert result is None


def test_get_history_starred_only():
    mock_db = MagicMock()
    mock_db.has_collection.return_value = True
    mock_cursor = MagicMock()
    items = [
        {"key": "k1", "ts": "2026-05-14T10:00:00Z", "question": "starred Q", "aql": "", "row_count": 1, "outcome": "success", "confidence": "high", "starred": True},
    ]
    mock_cursor.__iter__ = MagicMock(return_value=iter(items))
    mock_db.aql.execute.return_value = mock_cursor

    with patch("aql_agent.history._get_db", return_value=mock_db):
        result = history.get_history(user_id="alice", limit=5, starred_only=True)

    assert len(result) == 1
    assert result[0]["starred"] is True

    called_aql = mock_db.aql.execute.call_args[0][0]
    assert "starred" in called_aql


def test_get_history_no_db_returns_empty():
    with patch("aql_agent.history._get_db", return_value=None):
        result = history.get_history(user_id="alice")
    assert result == []


def test_record_history_outcome_clarification_requested():
    mock_db = MagicMock()
    mock_db.has_collection.return_value = True
    mock_coll = MagicMock()
    mock_db.collection.return_value = mock_coll

    state = _make_state(clarifying_question="Which satellite?", clarification="")
    with patch("aql_agent.history._get_db", return_value=mock_db):
        history.record_history(state, user_id="alice")

    inserted = mock_coll.insert.call_args[0][0]
    assert inserted["outcome"] == "clarification_requested"


def test_record_history_outcome_execution_failed():
    mock_db = MagicMock()
    mock_db.has_collection.return_value = True
    mock_coll = MagicMock()
    mock_db.collection.return_value = mock_coll

    state = _make_state(error="ArangoDB connection refused", clarifying_question="")
    with patch("aql_agent.history._get_db", return_value=mock_db):
        history.record_history(state, user_id="alice")

    inserted = mock_coll.insert.call_args[0][0]
    assert inserted["outcome"] == "execution_failed"


def test_record_history_outcome_validator_failed():
    mock_db = MagicMock()
    mock_db.has_collection.return_value = True
    mock_coll = MagicMock()
    mock_db.collection.return_value = mock_coll

    state = _make_state(error="", clarifying_question="", validator_errors=[{"code": "WRITE_OPERATION", "message": "not allowed"}])
    with patch("aql_agent.history._get_db", return_value=mock_db):
        history.record_history(state, user_id="alice")

    inserted = mock_coll.insert.call_args[0][0]
    assert inserted["outcome"] == "validator_failed"


def test_record_history_duration_ms_is_non_negative():
    mock_db = MagicMock()
    mock_db.has_collection.return_value = True
    mock_coll = MagicMock()
    mock_db.collection.return_value = mock_coll

    state = _make_state(started_at=datetime.utcnow())
    with patch("aql_agent.history._get_db", return_value=mock_db):
        history.record_history(state, user_id="alice")

    inserted = mock_coll.insert.call_args[0][0]
    assert inserted["duration_ms"] >= 0


def test_record_history_key_is_uuid():
    import re
    mock_db = MagicMock()
    mock_db.has_collection.return_value = True
    mock_coll = MagicMock()
    mock_db.collection.return_value = mock_coll

    with patch("aql_agent.history._get_db", return_value=mock_db):
        key = history.record_history(_make_state(), user_id="alice")

    assert re.match(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", key)


def test_ensure_collection_creates_if_missing():
    mock_db = MagicMock()
    mock_db.has_collection.return_value = False
    mock_coll = MagicMock()
    mock_db.collection.return_value = mock_coll

    state = _make_state()
    with patch("aql_agent.history._get_db", return_value=mock_db):
        history.record_history(state, user_id="alice")

    mock_db.create_collection.assert_called_once_with(history.COLLECTION_NAME)
