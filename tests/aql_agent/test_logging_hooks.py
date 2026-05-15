"""Tests for aql_agent.logging_hooks — structured JSON logging."""
from __future__ import annotations

import io
import json
import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from aql_agent.logging_hooks import write_log_line, _serialize


def _base_kwargs(**overrides):
    base = dict(
        log_id="test-log-id-1234",
        question="How many satellites are in orbit?",
        clarification="",
        clarifying_question="",
        tools_called=[{"name": "list_collections"}],
        iterations=2,
        final_aql="FOR s IN objects LIMIT 10 RETURN s",
        raw_aql="FOR s IN objects LIMIT 10 RETURN s",
        final_bind_vars={},
        validator_result={"ok": True, "errors": [], "warnings": []},
        db_error=None,
        row_count=5,
        started_at=datetime.utcnow(),
        outcome="success",
        model="gpt-4o-mini",
        confidence="high",
        assumptions=[],
        alternative=None,
    )
    base.update(overrides)
    return base


class TestSerialize:
    def test_datetime_serialized_to_iso(self):
        dt = datetime(2026, 5, 15, 9, 30, 0, tzinfo=timezone.utc)
        result = _serialize(dt)
        assert "2026-05-15" in result
        assert "T" in result

    def test_unknown_type_raises(self):
        with pytest.raises(TypeError):
            _serialize(object())


class TestWriteLogLine:
    def test_returns_log_id(self):
        with patch("aql_agent.logging_hooks.config") as mock_config:
            mock_config.agent.LOG_TO_STDOUT = False
            mock_config.agent.LOG_TO_FILE = False
            result = write_log_line(**_base_kwargs())
        assert result == "test-log-id-1234"

    def test_stdout_output_when_enabled(self):
        buf = io.StringIO()
        with patch("aql_agent.logging_hooks.config") as mock_config, \
             patch("sys.stdout", buf):
            mock_config.agent.LOG_TO_STDOUT = True
            mock_config.agent.LOG_TO_FILE = False
            write_log_line(**_base_kwargs())

        output = buf.getvalue()
        assert output.strip() != ""
        parsed = json.loads(output.strip())
        assert parsed["log_id"] == "test-log-id-1234"

    def test_no_stdout_when_disabled(self):
        buf = io.StringIO()
        with patch("aql_agent.logging_hooks.config") as mock_config, \
             patch("sys.stdout", buf):
            mock_config.agent.LOG_TO_STDOUT = False
            mock_config.agent.LOG_TO_FILE = False
            write_log_line(**_base_kwargs())

        assert buf.getvalue() == ""

    def test_file_output_when_enabled(self):
        with tempfile.NamedTemporaryFile(mode="r", suffix=".jsonl", delete=False) as f:
            tmp_path = f.name

        try:
            with patch("aql_agent.logging_hooks.config") as mock_config:
                mock_config.agent.LOG_TO_STDOUT = False
                mock_config.agent.LOG_TO_FILE = True
                mock_config.agent.LOG_PATH = tmp_path
                write_log_line(**_base_kwargs())

            with open(tmp_path) as f:
                line = f.read().strip()

            parsed = json.loads(line)
            assert parsed["log_id"] == "test-log-id-1234"
            assert parsed["question"] == "How many satellites are in orbit?"
            assert parsed["outcome"] == "success"
            assert parsed["version"] == "v2"
        finally:
            os.unlink(tmp_path)

    def test_both_disabled_does_not_crash(self):
        with patch("aql_agent.logging_hooks.config") as mock_config:
            mock_config.agent.LOG_TO_STDOUT = False
            mock_config.agent.LOG_TO_FILE = False
            write_log_line(**_base_kwargs())

    def test_record_contains_required_fields(self):
        buf = io.StringIO()
        with patch("aql_agent.logging_hooks.config") as mock_config, \
             patch("sys.stdout", buf):
            mock_config.agent.LOG_TO_STDOUT = True
            mock_config.agent.LOG_TO_FILE = False
            write_log_line(**_base_kwargs(
                tools_called=[{"name": "list_collections"}, {"name": "validate_aql"}],
                assumptions=["Interpreted 'active' as canonical.status == 'in orbit'"],
                confidence="medium",
            ))

        parsed = json.loads(buf.getvalue().strip())
        required_keys = [
            "ts", "log_id", "version", "model", "question", "clarification",
            "clarifying_question", "tools_called", "iterations", "raw_aql",
            "final_aql", "final_bind_vars", "validator", "db_error",
            "row_count", "total_latency_ms", "outcome", "confidence",
            "assumptions", "alternative",
        ]
        for key in required_keys:
            assert key in parsed, f"Missing required field: {key}"

    def test_datetime_in_record_is_serialized(self):
        buf = io.StringIO()
        with patch("aql_agent.logging_hooks.config") as mock_config, \
             patch("sys.stdout", buf):
            mock_config.agent.LOG_TO_STDOUT = True
            mock_config.agent.LOG_TO_FILE = False
            write_log_line(**_base_kwargs())

        parsed = json.loads(buf.getvalue().strip())
        assert isinstance(parsed["ts"], str)
        assert "T" in parsed["ts"]

    def test_total_latency_ms_is_positive_int(self):
        buf = io.StringIO()
        with patch("aql_agent.logging_hooks.config") as mock_config, \
             patch("sys.stdout", buf):
            mock_config.agent.LOG_TO_STDOUT = True
            mock_config.agent.LOG_TO_FILE = False
            write_log_line(**_base_kwargs())

        parsed = json.loads(buf.getvalue().strip())
        assert isinstance(parsed["total_latency_ms"], int)
        assert parsed["total_latency_ms"] >= 0

    def test_stdout_failure_does_not_raise(self):
        failing_stdout = MagicMock()
        failing_stdout.write.side_effect = IOError("pipe broken")
        with patch("aql_agent.logging_hooks.config") as mock_config, \
             patch("sys.stdout", failing_stdout):
            mock_config.agent.LOG_TO_STDOUT = True
            mock_config.agent.LOG_TO_FILE = False
            write_log_line(**_base_kwargs())

    def test_file_failure_does_not_raise(self):
        with patch("aql_agent.logging_hooks.config") as mock_config, \
             patch("builtins.open", side_effect=PermissionError("read-only")):
            mock_config.agent.LOG_TO_STDOUT = False
            mock_config.agent.LOG_TO_FILE = True
            mock_config.agent.LOG_PATH = "/nonexistent/path/log.jsonl"
            write_log_line(**_base_kwargs())

    def test_multiple_lines_appended_to_file(self):
        with tempfile.NamedTemporaryFile(mode="r", suffix=".jsonl", delete=False) as f:
            tmp_path = f.name

        try:
            with patch("aql_agent.logging_hooks.config") as mock_config:
                mock_config.agent.LOG_TO_STDOUT = False
                mock_config.agent.LOG_TO_FILE = True
                mock_config.agent.LOG_PATH = tmp_path
                write_log_line(**_base_kwargs(log_id="id-1"))
                write_log_line(**_base_kwargs(log_id="id-2"))

            with open(tmp_path) as f:
                lines = [l.strip() for l in f if l.strip()]

            assert len(lines) == 2
            assert json.loads(lines[0])["log_id"] == "id-1"
            assert json.loads(lines[1])["log_id"] == "id-2"
        finally:
            os.unlink(tmp_path)

    def test_assumptions_empty_list_when_none(self):
        buf = io.StringIO()
        with patch("aql_agent.logging_hooks.config") as mock_config, \
             patch("sys.stdout", buf):
            mock_config.agent.LOG_TO_STDOUT = True
            mock_config.agent.LOG_TO_FILE = False
            write_log_line(**_base_kwargs(assumptions=None))

        parsed = json.loads(buf.getvalue().strip())
        assert parsed["assumptions"] == []
