"""Tests for aql_agent.executor — AQL pipeline execution."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from aql_agent.executor import execute, _max_runtime
from config import config


class TestMaxRuntime:
    def test_traversal_query_uses_graph_runtime(self):
        aql = "FOR v IN OUTBOUND 'objects/1' collision_risk_edges RETURN v"
        assert _max_runtime(aql) == config.agent.GRAPH_MAX_RUNTIME_S

    def test_inbound_traversal_uses_graph_runtime(self):
        aql = "FOR v, e IN INBOUND 'objects/1' edges RETURN v"
        assert _max_runtime(aql) == config.agent.GRAPH_MAX_RUNTIME_S

    def test_any_traversal_uses_graph_runtime(self):
        aql = "FOR v IN ANY 'objects/1' edges RETURN v"
        assert _max_runtime(aql) == config.agent.GRAPH_MAX_RUNTIME_S

    def test_normal_query_uses_default_runtime(self):
        aql = "FOR s IN objects LIMIT 10 RETURN s"
        assert _max_runtime(aql) == config.agent.DEFAULT_MAX_RUNTIME_S

    def test_aggregate_query_uses_default_runtime(self):
        aql = "FOR s IN objects COLLECT WITH COUNT INTO n RETURN n"
        assert _max_runtime(aql) == config.agent.DEFAULT_MAX_RUNTIME_S

    def test_traversal_keyword_case_insensitive(self):
        aql = "for v in outbound 'objects/1' edges return v"
        assert _max_runtime(aql) == config.agent.GRAPH_MAX_RUNTIME_S


class TestExecute:
    def _make_mock_db(self, rows=None, error=None):
        db = MagicMock()
        if error:
            db.aql.execute.side_effect = Exception(error)
        else:
            mock_cursor = MagicMock()
            mock_cursor.__iter__ = MagicMock(return_value=iter(rows or []))
            db.aql.execute.return_value = mock_cursor
        return db

    def test_successful_execution_returns_rows(self):
        rows = [{"_key": "1", "name": "ISS"}, {"_key": "2", "name": "STARLINK-1"}]
        mock_db = self._make_mock_db(rows=rows)
        with patch("database.connection") as mock_conn:
            mock_conn.db = mock_db
            with patch.dict("sys.modules", {"database.connection": mock_conn}):
                result = execute("FOR s IN objects LIMIT 10 RETURN s", {})

        assert result["result"] == rows
        assert result["row_count"] == 2
        assert result["error"] == ""

    def test_execution_error_returns_error_string(self):
        mock_db = self._make_mock_db(error="collection not found")
        with patch("database.connection") as mock_conn:
            mock_conn.db = mock_db
            with patch.dict("sys.modules", {"database.connection": mock_conn}):
                result = execute("FOR s IN nonexistent LIMIT 10 RETURN s", {})

        assert result["result"] == []
        assert result["row_count"] == 0
        assert "collection not found" in result["error"]

    def test_empty_result_returns_zero_rows(self):
        mock_db = self._make_mock_db(rows=[])
        with patch("database.connection") as mock_conn:
            mock_conn.db = mock_db
            with patch.dict("sys.modules", {"database.connection": mock_conn}):
                result = execute("FOR s IN objects FILTER s.name == @name LIMIT 10 RETURN s", {"name": "ghost"})

        assert result["result"] == []
        assert result["row_count"] == 0
        assert result["error"] == ""

    def test_bind_vars_passed_to_execute(self):
        rows = [{"_key": "1"}]
        mock_db = self._make_mock_db(rows=rows)
        bind_vars = {"name": "ISS", "@coll": "objects"}
        with patch("database.connection") as mock_conn:
            mock_conn.db = mock_db
            with patch.dict("sys.modules", {"database.connection": mock_conn}):
                execute("FOR s IN @@coll FILTER s.name == @name LIMIT 10 RETURN s", bind_vars)

        call_kwargs = mock_db.aql.execute.call_args
        assert call_kwargs is not None
        _, kwargs = call_kwargs
        assert kwargs.get("bind_vars") == bind_vars

    def test_traversal_query_uses_larger_runtime(self):
        rows = [{"_key": "1"}]
        mock_db = self._make_mock_db(rows=rows)
        traversal_aql = "FOR v IN OUTBOUND 'objects/1' collision_risk_edges RETURN v"
        with patch("database.connection") as mock_conn:
            mock_conn.db = mock_db
            with patch.dict("sys.modules", {"database.connection": mock_conn}):
                execute(traversal_aql, {})

        call_kwargs = mock_db.aql.execute.call_args
        _, kwargs = call_kwargs
        assert kwargs.get("max_runtime") == config.agent.GRAPH_MAX_RUNTIME_S

    def test_normal_query_uses_smaller_runtime(self):
        rows = []
        mock_db = self._make_mock_db(rows=rows)
        normal_aql = "FOR s IN objects LIMIT 5 RETURN s"
        with patch("database.connection") as mock_conn:
            mock_conn.db = mock_db
            with patch.dict("sys.modules", {"database.connection": mock_conn}):
                execute(normal_aql, {})

        call_kwargs = mock_db.aql.execute.call_args
        _, kwargs = call_kwargs
        assert kwargs.get("max_runtime") == config.agent.DEFAULT_MAX_RUNTIME_S

    def test_db_import_failure_returns_error(self):
        import sys
        original = sys.modules.get("database.connection")
        sys.modules["database.connection"] = None
        try:
            result = execute("FOR s IN objects LIMIT 10 RETURN s", {})
        finally:
            if original is None:
                sys.modules.pop("database.connection", None)
            else:
                sys.modules["database.connection"] = original

        assert result["error"] != "" or result["row_count"] == 0

    def test_result_is_list_of_rows(self):
        rows = [{"count": 42}]
        mock_db = self._make_mock_db(rows=rows)
        with patch("database.connection") as mock_conn:
            mock_conn.db = mock_db
            with patch.dict("sys.modules", {"database.connection": mock_conn}):
                result = execute("FOR s IN objects COLLECT WITH COUNT INTO n RETURN {count: n}", {})

        assert isinstance(result["result"], list)
