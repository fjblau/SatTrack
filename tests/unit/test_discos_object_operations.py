"""
Unit tests for database.discos_object_operations.ensure_discos_object_exists.

Covers:
- matched_existing via NORAD lookup
- matched_existing via COSPAR lookup
- matched_existing via DISCOS ID (surrogate) lookup
- created_new when no aliases match
- verified_unchanged when source envelope has not changed
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

for _mod_name in [
    "arango", "requests",
    "database", "database.connection", "database.utils",
    "database.utils.normalization", "database.utils.field_utils",
]:
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = MagicMock()


def _import_ops():
    import importlib
    mod_name = "database.discos_object_operations"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    saved = {}
    for key in ["database"]:
        if key in sys.modules:
            saved[key] = sys.modules.pop(key)
    try:
        mod = importlib.import_module(mod_name)
    finally:
        sys.modules.update(saved)
    return mod


def _make_payload(discos_id="42", cospar_id="2020-001A", satno=12345, object_class="Debris"):
    return {
        "discos_id": discos_id,
        "cosparId": cospar_id,
        "satno": satno,
        "objectClass": object_class,
        "name": "TestFrag",
        "mass": 10.5,
        "shape": "Sphere",
        "height": None,
        "width": None,
        "depth": None,
        "diameter": 0.3,
        "span": None,
        "xSectMax": None,
        "xSectMin": None,
        "xSectAvg": None,
    }


def _make_existing_doc(key, discos_id="42", cospar_id="2020-001A", satno=12345):
    return {
        "_key": key,
        "_id": f"objects/{key}",
        "canonical": {
            "norad_cat_id": satno,
            "international_designator": cospar_id,
        },
        "identifier_aliases": {
            "norad": str(satno),
            "cospar": cospar_id,
            "discos": str(discos_id),
        },
        "sources": {"discos": {}},
        "metadata": {"transformations": []},
    }


class TestEnsureDiscosObjectExistsMatchedViaNorad(unittest.TestCase):
    def test_matched_existing_via_norad(self):
        ops = _import_ops()
        payload = _make_payload()
        existing = _make_existing_doc("ISS", discos_id="42", cospar_id="2020-001A", satno=12345)

        mock_db = MagicMock()
        mock_db.aql.execute.return_value = iter([existing])

        mock_col = MagicMock()
        mock_db.collection.return_value = mock_col

        key, status = ops.ensure_discos_object_exists(payload, mock_db, operator="test_op")

        self.assertEqual(status, "matched_existing")
        self.assertEqual(key, "ISS")
        mock_col.update.assert_called_once()
        update_arg = mock_col.update.call_args[0][0]
        self.assertIn("discos", update_arg["sources"])
        tx = update_arg["metadata"]["transformations"][-1]
        self.assertEqual(tx["action"], "ingest")
        self.assertEqual(tx["operator"], "test_op")


class TestEnsureDiscosObjectExistsMatchedViaCospar(unittest.TestCase):
    def test_matched_existing_via_cospar_when_norad_misses(self):
        ops = _import_ops()
        payload = _make_payload(satno=None)
        existing = _make_existing_doc("OBJ-COSPAR", cospar_id="2020-001A")
        existing["identifier_aliases"].pop("norad", None)
        existing["canonical"].pop("norad_cat_id", None)

        call_count = [0]
        def fake_execute(aql, bind_vars=None, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return iter([existing])
            return iter([])

        mock_db = MagicMock()
        mock_db.aql.execute.side_effect = fake_execute
        mock_col = MagicMock()
        mock_db.collection.return_value = mock_col

        key, status = ops.ensure_discos_object_exists(payload, mock_db, operator="test_op")

        self.assertEqual(status, "matched_existing")
        self.assertEqual(key, "OBJ-COSPAR")


class TestEnsureDiscosObjectExistsMatchedViaDiscosId(unittest.TestCase):
    def test_matched_existing_via_discos_id_surrogate(self):
        ops = _import_ops()
        payload = _make_payload(satno=None, cospar_id=None)
        payload["cosparId"] = None
        payload["satno"] = None
        surrogate = _make_existing_doc("DISCOS-42", discos_id="42")
        surrogate["identifier_aliases"] = {"discos": "42"}
        surrogate["canonical"] = {}

        call_count = [0]
        def fake_execute(aql, bind_vars=None, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return iter([surrogate])
            return iter([])

        mock_db = MagicMock()
        mock_db.aql.execute.side_effect = fake_execute
        mock_col = MagicMock()
        mock_db.collection.return_value = mock_col

        key, status = ops.ensure_discos_object_exists(payload, mock_db, operator="test_op")

        self.assertEqual(status, "matched_existing")
        self.assertEqual(key, "DISCOS-42")


class TestEnsureDiscosObjectExistsCreatedNew(unittest.TestCase):
    def test_created_new_when_no_aliases_match(self):
        ops = _import_ops()
        payload = _make_payload()

        mock_db = MagicMock()
        mock_db.aql.execute.return_value = iter([])

        mock_col = MagicMock()
        mock_col.get.return_value = None
        mock_db.collection.return_value = mock_col

        key, status = ops.ensure_discos_object_exists(payload, mock_db, operator="test_op")

        self.assertEqual(status, "created_new")
        self.assertEqual(key, "DISCOS-42")
        mock_col.insert.assert_called_once()
        insert_arg = mock_col.insert.call_args[0][0]
        self.assertEqual(insert_arg["_key"], "DISCOS-42")
        self.assertEqual(insert_arg["identifier_aliases"]["discos"], "42")
        tx = insert_arg["metadata"]["transformations"][0]
        self.assertEqual(tx["action"], "ingest")
        self.assertEqual(tx["operator"], "test_op")


class TestEnsureDiscosObjectExistsVerifiedUnchanged(unittest.TestCase):
    def test_verified_unchanged_writes_verify_transformation(self):
        ops = _import_ops()
        payload = _make_payload()

        existing = _make_existing_doc("ISS", discos_id="42", satno=12345)
        new_envelope = ops._build_discos_source_envelope(payload)
        existing["sources"]["discos"] = {k: v for k, v in new_envelope.items() if k != "ingested_at"}

        mock_db = MagicMock()
        mock_db.aql.execute.return_value = iter([existing])
        mock_col = MagicMock()
        mock_db.collection.return_value = mock_col

        key, status = ops.ensure_discos_object_exists(payload, mock_db, operator="test_op")

        self.assertEqual(status, "verified_unchanged")
        self.assertEqual(key, "ISS")
        mock_col.update.assert_called_once()
        update_arg = mock_col.update.call_args[0][0]
        tx = update_arg["metadata"]["transformations"][-1]
        self.assertEqual(tx["action"], "verify")
        self.assertNotIn("changed_fields", tx)

    def test_verified_unchanged_for_existing_surrogate(self):
        ops = _import_ops()
        payload = _make_payload()

        mock_db = MagicMock()
        mock_db.aql.execute.return_value = iter([])

        surrogate = _make_existing_doc("DISCOS-42", discos_id="42")
        new_envelope = ops._build_discos_source_envelope(payload)
        surrogate["sources"]["discos"] = {k: v for k, v in new_envelope.items() if k != "ingested_at"}

        mock_col = MagicMock()
        mock_col.get.return_value = surrogate
        mock_db.collection.return_value = mock_col

        key, status = ops.ensure_discos_object_exists(payload, mock_db, operator="test_op")

        self.assertEqual(status, "verified_unchanged")
        self.assertEqual(key, "DISCOS-42")
        mock_col.update.assert_called_once()
        update_arg = mock_col.update.call_args[0][0]
        tx = update_arg["metadata"]["transformations"][-1]
        self.assertEqual(tx["action"], "verify")


class TestEnvelopeChanged(unittest.TestCase):
    def setUp(self):
        self.ops = _import_ops()

    def test_identical_envelopes_not_changed(self):
        e = {"discos_id": "1", "mass_kg": 10.0, "shape": "sphere", "ingested_at": "old"}
        self.assertFalse(self.ops._envelope_changed(e, {**e, "ingested_at": "new"}))

    def test_changed_field_detected(self):
        old = {"discos_id": "1", "mass_kg": 10.0}
        new = {"discos_id": "1", "mass_kg": 20.0}
        self.assertTrue(self.ops._envelope_changed(old, new))

    def test_new_field_detected(self):
        old = {"discos_id": "1"}
        new = {"discos_id": "1", "shape": "cube"}
        self.assertTrue(self.ops._envelope_changed(old, new))


if __name__ == "__main__":
    unittest.main()
