"""Tests for aql_agent.formatter — AQL pretty-printer."""
from __future__ import annotations

import pytest

from aql_agent.formatter import format_aql, _split_at_top_level_keywords, _wrap_long_line


def test_empty_string_passthrough():
    assert format_aql("") == ""


def test_whitespace_passthrough():
    assert format_aql("   ") == "   "


def test_simple_query_splits_keywords():
    result = format_aql("FOR s IN objects FILTER s.active == true LIMIT 10 RETURN s")
    lines = result.splitlines()
    assert any(l.startswith("FOR") for l in lines)
    assert any(l.startswith("FILTER") for l in lines)
    assert any(l.startswith("LIMIT") for l in lines)
    assert any(l.startswith("RETURN") for l in lines)


def test_each_keyword_on_own_line():
    result = format_aql("FOR s IN objects SORT s.name LIMIT 5 RETURN s")
    lines = result.splitlines()
    keyword_lines = [l.split()[0].upper() for l in lines if l.strip()]
    assert keyword_lines == ["FOR", "SORT", "LIMIT", "RETURN"]


def test_multiple_for_loops_blank_line_between():
    aql = "FOR a IN objects RETURN a FOR b IN policies RETURN b"
    result = format_aql(aql)
    assert "\n\n" in result


def test_keyword_in_string_not_split():
    aql = "FOR s IN objects FILTER s.name == 'RETURN this' LIMIT 10 RETURN s"
    result = format_aql(aql)
    lines = result.splitlines()
    return_lines = [l for l in lines if l.startswith("RETURN")]
    assert len(return_lines) == 1


def test_keyword_in_double_quoted_string_not_split():
    aql = 'FOR s IN objects FILTER s.name == "INSERT me" LIMIT 10 RETURN s'
    result = format_aql(aql)
    lines = result.splitlines()
    assert sum(1 for l in lines if l.startswith("FOR")) == 1
    assert sum(1 for l in lines if l.startswith("RETURN")) == 1


def test_keyword_in_backtick_not_split():
    aql = "FOR s IN `objects` LIMIT 10 RETURN s"
    result = format_aql(aql)
    lines = result.splitlines()
    assert any(l.startswith("FOR") for l in lines)


def test_format_does_not_crash_on_invalid_aql():
    result = format_aql("NOT VALID AQL {{{{")
    assert isinstance(result, str)


def test_let_keyword_on_own_line():
    aql = "FOR s IN objects LET name = s.canonical.satellite_name LIMIT 10 RETURN name"
    result = format_aql(aql)
    lines = result.splitlines()
    assert any(l.startswith("LET") for l in lines)


def test_collect_keyword_on_own_line():
    aql = "FOR s IN objects COLLECT country = s.canonical.country_of_origin WITH COUNT INTO n RETURN {country, n}"
    result = format_aql(aql)
    lines = result.splitlines()
    assert any(l.startswith("COLLECT") for l in lines)


def test_sort_keyword_on_own_line():
    aql = "FOR s IN objects SORT s.canonical.rcs DESC LIMIT 10 RETURN s"
    result = format_aql(aql)
    lines = result.splitlines()
    assert any(l.startswith("SORT") for l in lines)


def test_whitespace_normalized():
    aql = "FOR   s   IN   objects    LIMIT   10   RETURN   s"
    result = format_aql(aql)
    assert "   " not in result


def test_comma_spacing_fixed():
    aql = "FOR s IN objects LIMIT 10 RETURN {a: s.a,   b: s.b}"
    result = format_aql(aql)
    assert ",   " not in result
    assert ", " in result


def test_wrap_long_line_with_and():
    long_filter = "FILTER " + " AND ".join([f"d.field{i} == {i}" for i in range(10)])
    result = _wrap_long_line(long_filter)
    if len(long_filter) > 100:
        assert "\n" in result
        assert "AND" in result


def test_wrap_long_line_with_or():
    long_filter = "FILTER " + " OR ".join([f"d.field{i} == {i}" for i in range(10)])
    result = _wrap_long_line(long_filter)
    if len(long_filter) > 100:
        assert "\n" in result


def test_wrap_short_line_unchanged():
    short = "LIMIT 10"
    assert _wrap_long_line(short) == short


def test_split_single_clause_no_keywords():
    parts = _split_at_top_level_keywords("GRAPH_RUNTIME")
    assert len(parts) == 1


def test_format_aql_returns_string():
    result = format_aql("FOR s IN objects LIMIT 10 RETURN s")
    assert isinstance(result, str)


def test_format_aql_nested_filter():
    aql = "FOR s IN objects FILTER s.canonical.status == 'in orbit' AND s.canonical.rcs > 0.1 SORT s.canonical.rcs DESC LIMIT 20 RETURN s"
    result = format_aql(aql)
    assert "FOR" in result
    assert "FILTER" in result
    assert "SORT" in result
    assert "LIMIT" in result
    assert "RETURN" in result


def test_format_aql_subquery_preserved():
    aql = "FOR s IN objects LET risk = (FOR e IN collision_risk_edges FILTER e._from == s._id RETURN e) LIMIT 5 RETURN {s, risk}"
    result = format_aql(aql)
    assert isinstance(result, str)
    assert "RETURN" in result
