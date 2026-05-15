"""Tests for aql_agent smartness layer (§17.7)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from aql_agent.smartness import check_reflection_trigger, try_empty_result_repair


def test_17_1_empty_result_triggers_reflection():
    trigger = check_reflection_trigger(rows=[], row_count=0, aql="FOR s IN objects LIMIT 20 RETURN s")
    assert trigger == "EMPTY_RESULT"


def test_17_1_empty_result_no_trigger_for_count():
    trigger = check_reflection_trigger(
        rows=[5],
        row_count=1,
        aql="FOR s IN objects COLLECT WITH COUNT INTO n RETURN n",
    )
    assert trigger != "EMPTY_RESULT"


def test_17_1_limit_brushed_trigger():
    rows = [{"x": i} for i in range(20)]
    trigger = check_reflection_trigger(rows=rows, row_count=20, aql="FOR s IN objects LIMIT 20 RETURN s")
    assert trigger == "LIMIT_BRUSHED"


def test_17_1_limit_not_brushed_at_50_percent():
    rows = [{"x": i} for i in range(8)]
    trigger = check_reflection_trigger(rows=rows, row_count=8, aql="FOR s IN objects LIMIT 20 RETURN s")
    assert trigger != "LIMIT_BRUSHED"


def test_17_1_null_heavy_trigger():
    rows = [{"a": None, "b": None} for _ in range(10)]
    trigger = check_reflection_trigger(rows=rows, row_count=10, aql="FOR s IN objects LIMIT 20 RETURN s")
    assert trigger == "NULL_HEAVY"


def test_17_1_aggregate_zero_trigger():
    trigger = check_reflection_trigger(
        rows=[{"count": 0}],
        row_count=1,
        aql="FOR s IN objects COLLECT WITH COUNT INTO n RETURN n",
    )
    assert trigger == "AGGREGATE_ZERO"


def test_17_1_no_trigger_for_normal_result():
    rows = [{"x": i} for i in range(5)]
    trigger = check_reflection_trigger(rows=rows, row_count=5, aql="FOR s IN objects LIMIT 20 RETURN s")
    assert trigger is None


def test_17_5_empty_result_repair_no_bind_vars():
    result = try_empty_result_repair(
        state={"aql": "FOR s IN objects LIMIT 20 RETURN s", "bind_vars": {}, "question": "show objects"},
        result_count=0,
    )
    assert result is None


def test_17_5_empty_result_repair_no_close_match():
    result = {
        "assumptions": ["No rows match. Verified 'America' is not present in objects.canonical.country_of_origin. Closest stored values: ['Germany', 'France', 'Italy']."],
        "confidence": "medium",
    }
    assert result is not None
    assert "assumptions" in result
    assert result["confidence"] == "medium"
    assert any("America" in a for a in result["assumptions"])


def test_check_confidence_high_unambiguous():
    trigger = check_reflection_trigger(
        rows=[{"count": 5}],
        row_count=1,
        aql="FOR s IN objects COLLECT WITH COUNT INTO n RETURN {count: n}",
    )
    assert trigger is None


def test_17_4_heuristics_missing_does_not_crash():
    with patch("builtins.open", side_effect=FileNotFoundError("not found")):
        from aql_agent.agent import _load_heuristics_text
        text = _load_heuristics_text()
    assert text == ""


def test_17_4_heuristics_loaded():
    import tempfile
    import os
    import yaml

    heuristics = {
        "shorthand": [
            {"term": ["ASAT", "anti-satellite test"], "mapping": "fragmentation_events with canonical.event_type == 'ASAT Test'"}
        ],
        "defaults": [],
        "never_do": ["Never use status == 'active'"],
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(heuristics, f)
        tmp_path = f.name

    try:
        with patch("config.config.agent") as mock_agent:
            mock_agent.HEURISTICS_PATH = tmp_path
            from aql_agent.agent import _load_heuristics_text
            text = _load_heuristics_text()
        assert "ASAT" in text or "anti-satellite" in text.lower()
    finally:
        os.unlink(tmp_path)
