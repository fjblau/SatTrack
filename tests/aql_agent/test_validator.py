"""Tests for the AQL validator rules R1–R10."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from aql_agent.validator import validate


def _mock_db(collection_names: list[str] | None = None):
    db = MagicMock()
    if collection_names is None:
        collection_names = ["objects", "policies", "claims", "risk_scores", "entities", "ephemeris_envelopes"]
    db.aql.validate.return_value = None
    return db, collection_names


def _patch_collections(db, names):
    with patch("aql_agent.schema_cache.get_all_collection_names", return_value=names):
        yield


@pytest.fixture
def db():
    mock, names = _mock_db()
    return mock, names


def test_r1_write_insert():
    db_mock, names = _mock_db()
    with patch("aql_agent.schema_cache.get_all_collection_names", return_value=names):
        result = validate("INSERT {x: 1} INTO objects", {}, db=db_mock)
    assert not result.ok
    assert any(e["code"] == "WRITE_OPERATION" for e in result.errors)


def test_r1_write_remove():
    db_mock, names = _mock_db()
    with patch("aql_agent.schema_cache.get_all_collection_names", return_value=names):
        result = validate("FOR d IN objects REMOVE d IN objects", {}, db=db_mock)
    assert not result.ok
    assert any(e["code"] == "WRITE_OPERATION" for e in result.errors)


def test_r1_write_upsert():
    db_mock, names = _mock_db()
    with patch("aql_agent.schema_cache.get_all_collection_names", return_value=names):
        result = validate('UPSERT {x: 1} INSERT {x: 1} UPDATE {x: 1} IN objects', {}, db=db_mock)
    assert not result.ok
    assert any(e["code"] == "WRITE_OPERATION" for e in result.errors)


def test_r1_clean_select():
    db_mock, names = _mock_db()
    with patch("aql_agent.validator.get_all_collection_names", return_value=names):
        result = validate("FOR s IN objects LIMIT 10 RETURN s", {}, db=db_mock)
    assert result.ok
    assert not any(e["code"] == "WRITE_OPERATION" for e in result.errors)


def test_r3_unknown_collection():
    db_mock, names = _mock_db()
    with patch("aql_agent.validator.get_all_collection_names", return_value=names), \
         patch("aql_agent.validator.did_you_mean", return_value=["objects"]):
        result = validate("FOR s IN satellites LIMIT 10 RETURN s", {}, db=db_mock)
    assert not result.ok
    assert any(e["code"] == "UNKNOWN_COLLECTION" for e in result.errors)


def test_r3_known_collection_passes():
    db_mock, names = _mock_db()
    with patch("aql_agent.validator.get_all_collection_names", return_value=names):
        result = validate("FOR s IN objects LIMIT 10 RETURN s", {}, db=db_mock)
    assert result.ok


def test_r5_missing_limit_warning():
    db_mock, names = _mock_db()
    with patch("aql_agent.validator.get_all_collection_names", return_value=names):
        result = validate("FOR s IN objects RETURN s", {}, db=db_mock)
    assert any(w["code"] == "MISSING_LIMIT" for w in result.warnings)


def test_r5_no_missing_limit_warning_with_collect():
    db_mock, names = _mock_db()
    with patch("aql_agent.validator.get_all_collection_names", return_value=names):
        result = validate("FOR s IN objects COLLECT WITH COUNT INTO n RETURN n", {}, db=db_mock)
    assert not any(w["code"] == "MISSING_LIMIT" for w in result.warnings)


def test_r6_limit_after_return():
    db_mock, names = _mock_db()
    db_mock.aql.validate.side_effect = None
    with patch("aql_agent.validator.get_all_collection_names", return_value=names):
        result = validate("FOR s IN objects RETURN s LIMIT 10", {}, db=db_mock)
    assert any(e["code"] == "LIMIT_AFTER_RETURN" for e in result.errors)


def test_r7_missing_bind_var():
    db_mock, names = _mock_db()
    with patch("aql_agent.validator.get_all_collection_names", return_value=names):
        result = validate(
            "FOR s IN objects FILTER s.name == @name LIMIT 10 RETURN s",
            {},
            db=db_mock,
        )
    assert any(e["code"] == "MISSING_BIND_VAR" for e in result.errors)


def test_r7_bind_var_present():
    db_mock, names = _mock_db()
    with patch("aql_agent.validator.get_all_collection_names", return_value=names):
        result = validate(
            "FOR s IN objects FILTER s.name == @name LIMIT 10 RETURN s",
            {"name": "test"},
            db=db_mock,
        )
    assert not any(e["code"] == "MISSING_BIND_VAR" for e in result.errors)


def test_r7_unused_bind_var_warning():
    db_mock, names = _mock_db()
    with patch("aql_agent.validator.get_all_collection_names", return_value=names):
        result = validate(
            "FOR s IN objects LIMIT 10 RETURN s",
            {"unused_var": "value"},
            db=db_mock,
        )
    assert any(w["code"] == "UNUSED_BIND_VAR" for w in result.warnings)


def test_r8_inlined_string_literal_warning():
    db_mock, names = _mock_db()
    with patch("aql_agent.validator.get_all_collection_names", return_value=names):
        result = validate(
            'FOR s IN objects FILTER s.name == "starlink" LIMIT 10 RETURN s',
            {},
            db=db_mock,
            original_question="show starlink satellites",
        )
    assert any(w["code"] == "INLINED_STRING_LITERAL" for w in result.warnings)


def test_r9_ephemeris_without_unset_warning():
    db_mock, names = _mock_db()
    with patch("aql_agent.validator.get_all_collection_names", return_value=names):
        result = validate(
            "FOR e IN ephemeris_envelopes LIMIT 5 RETURN e",
            {},
            db=db_mock,
        )
    assert any(w["code"] == "UNBOUNDED_EPHEMERIS_PAYLOAD" for w in result.warnings)


def test_r9_ephemeris_with_unset_no_warning():
    db_mock, names = _mock_db()
    with patch("aql_agent.validator.get_all_collection_names", return_value=names):
        result = validate(
            "FOR e IN ephemeris_envelopes LIMIT 5 RETURN UNSET(e, 'ephemeris_points')",
            {},
            db=db_mock,
        )
    assert not any(w["code"] == "UNBOUNDED_EPHEMERIS_PAYLOAD" for w in result.warnings)


def test_adversarial_a1_delete():
    db_mock, names = _mock_db()
    with patch("aql_agent.validator.get_all_collection_names", return_value=names):
        result = validate(
            "FOR s IN objects REMOVE s IN objects",
            {},
            db=db_mock,
        )
    assert not result.ok
    assert any(e["code"] == "WRITE_OPERATION" for e in result.errors)


def test_adversarial_injection():
    db_mock, names = _mock_db()
    with patch("aql_agent.validator.get_all_collection_names", return_value=names):
        result = validate(
            "FOR s IN objects FILTER s.name == 'x'; INSERT {y:1} INTO objects RETURN s",
            {},
            db=db_mock,
        )
    assert any(e["code"] == "WRITE_OPERATION" for e in result.errors)


def test_r1_write_update():
    db_mock, names = _mock_db()
    with patch("aql_agent.validator.get_all_collection_names", return_value=names):
        result = validate("FOR s IN objects UPDATE s WITH {x: 1} IN objects", {}, db=db_mock)
    assert not result.ok
    assert any(e["code"] == "WRITE_OPERATION" for e in result.errors)


def test_r1_write_replace():
    db_mock, names = _mock_db()
    with patch("aql_agent.validator.get_all_collection_names", return_value=names):
        result = validate("FOR s IN objects REPLACE s WITH {x: 1} IN objects", {}, db=db_mock)
    assert not result.ok
    assert any(e["code"] == "WRITE_OPERATION" for e in result.errors)


def test_r2_syntax_error_from_db():
    db_mock, names = _mock_db()
    db_mock.aql.validate.side_effect = Exception("parse error near token X")
    with patch("aql_agent.validator.get_all_collection_names", return_value=names):
        result = validate("FOR s IN objects LIMIT 10 RETURN s", {}, db=db_mock)
    assert not result.ok
    assert any(e["code"] == "SYNTAX_ERROR" for e in result.errors)


def test_r4_unknown_id_prefix():
    db_mock, names = _mock_db()
    with patch("aql_agent.validator.get_all_collection_names", return_value=names):
        result = validate(
            "RETURN DOCUMENT('phantom_collection/12345')",
            {},
            db=db_mock,
        )
    assert any(e["code"] == "UNKNOWN_ID_PREFIX" for e in result.errors)


def test_r4_known_id_prefix_passes():
    db_mock, names = _mock_db()
    with patch("aql_agent.validator.get_all_collection_names", return_value=names):
        result = validate(
            "RETURN DOCUMENT('objects/12345')",
            {},
            db=db_mock,
        )
    assert not any(e["code"] == "UNKNOWN_ID_PREFIX" for e in result.errors)


def test_r7_collection_bind_var_with_at_prefix():
    db_mock, names = _mock_db()
    with patch("aql_agent.validator.get_all_collection_names", return_value=names):
        result = validate(
            "FOR s IN @@coll LIMIT 10 RETURN s",
            {"@coll": "objects"},
            db=db_mock,
        )
    assert not any(e["code"] == "MISSING_BIND_VAR" for e in result.errors)


def test_r7_collection_bind_var_missing():
    db_mock, names = _mock_db()
    with patch("aql_agent.validator.get_all_collection_names", return_value=names):
        result = validate(
            "FOR s IN @@coll LIMIT 10 RETURN s",
            {},
            db=db_mock,
        )
    assert any(e["code"] == "MISSING_BIND_VAR" for e in result.errors)


def test_r5_no_missing_limit_warning_with_aggregate():
    db_mock, names = _mock_db()
    with patch("aql_agent.validator.get_all_collection_names", return_value=names):
        result = validate(
            "FOR s IN objects RETURN COUNT(s.field)",
            {},
            db=db_mock,
        )
    assert not any(w["code"] == "MISSING_LIMIT" for w in result.warnings)


def test_no_db_skips_collection_validation():
    result = validate("FOR s IN ghost_collection LIMIT 10 RETURN s", {}, db=None)
    assert not any(e["code"] == "UNKNOWN_COLLECTION" for e in result.errors)


def test_no_db_skips_syntax_validation():
    result = validate("totally invalid @@@@", {}, db=None)
    assert not any(e["code"] == "SYNTAX_ERROR" for e in result.errors)


def test_validation_result_ok_true_for_clean_query():
    db_mock, names = _mock_db()
    with patch("aql_agent.validator.get_all_collection_names", return_value=names):
        result = validate(
            "FOR s IN objects FILTER s.name == @name LIMIT 10 RETURN s",
            {"name": "ISS"},
            db=db_mock,
        )
    assert result.ok
    assert result.errors == []


def test_multiple_errors_accumulated():
    db_mock, names = _mock_db()
    with patch("aql_agent.validator.get_all_collection_names", return_value=names):
        result = validate(
            "INSERT {x: 1} INTO objects RETURN objects LIMIT 10",
            {},
            db=db_mock,
        )
    error_codes = [e["code"] for e in result.errors]
    assert "WRITE_OPERATION" in error_codes
    assert len(result.errors) >= 1


def test_traversal_collection_extracted_and_validated():
    db_mock, names = _mock_db()
    with patch("aql_agent.validator.get_all_collection_names", return_value=names), \
         patch("aql_agent.validator.did_you_mean", return_value=[]):
        result = validate(
            "FOR v IN OUTBOUND 'objects/1' ghost_edges LIMIT 10 RETURN v",
            {},
            db=db_mock,
        )
    assert any(e["code"] == "UNKNOWN_COLLECTION" for e in result.errors)
