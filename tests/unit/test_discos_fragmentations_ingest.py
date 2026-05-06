"""
Unit tests for the DISCOS fragmentation ingestion pipeline changes:
  - ingest_discos_fragmentations: verify/ingest log distinction, changed_fields capture
  - ingest_discos_attributions: fragment_count_kessler idempotency, pagination totalCount assertion
  - promote_discos_fragmentations: fragment_count_discos promotion, idempotency
  - migrate_split_fragment_counts: rename canonical.fragment_count → canonical.fragment_count_kessler
  - discos_service.get_fragmentation_attributed_objects_with_count: totalCount extraction
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

_MOCK_DB_CONN = MagicMock()
_MOCK_DB_MODULE = MagicMock()

for _mod_name in [
    "arango", "requests",
    "database", "database.connection", "database.utils",
    "database.utils.normalization", "database.utils.field_utils",
]:
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = MagicMock()

sys.modules["database.connection"] = _MOCK_DB_CONN
sys.modules["database"] = _MOCK_DB_MODULE


def _import_fresh(module_name: str):
    if module_name in sys.modules:
        del sys.modules[module_name]
    import importlib
    return importlib.import_module(module_name)


# ---------------------------------------------------------------------------
# _raw_changed_fields helper
# ---------------------------------------------------------------------------

class TestRawChangedFields(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib
        mod_name = "scripts.population.ingest_discos_fragmentations"
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        cls.mod = importlib.import_module(mod_name)

    def test_no_changes_returns_empty(self):
        old = {"epoch": "2009-02-10", "altitude": None}
        new = {"epoch": "2009-02-10", "altitude": None}
        result = self.mod._raw_changed_fields(old, new)
        self.assertEqual(result, [])

    def test_changed_field_detected(self):
        old = {"epoch": "2009-02-10", "altitude": None}
        new = {"epoch": "2009-02-10", "altitude": 500.0}
        result = self.mod._raw_changed_fields(old, new)
        self.assertEqual(result, ["altitude"])

    def test_new_field_detected(self):
        old = {"epoch": "2009-02-10"}
        new = {"epoch": "2009-02-10", "objectsCount": 24}
        result = self.mod._raw_changed_fields(old, new)
        self.assertEqual(result, ["objectsCount"])

    def test_removed_field_detected(self):
        old = {"epoch": "2009-02-10", "comment": "old"}
        new = {"epoch": "2009-02-10"}
        result = self.mod._raw_changed_fields(old, new)
        self.assertEqual(result, ["comment"])

    def test_multiple_changes_sorted(self):
        old = {"a": 1, "b": 2, "c": 3}
        new = {"a": 1, "b": 99, "c": 3, "d": 4}
        result = self.mod._raw_changed_fields(old, new)
        self.assertEqual(result, ["b", "d"])


# ---------------------------------------------------------------------------
# _make_event_doc
# ---------------------------------------------------------------------------

class TestMakeEventDoc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib
        mod_name = "scripts.population.ingest_discos_fragmentations"
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        cls.mod = importlib.import_module(mod_name)

    def test_basic_structure(self):
        event = {
            "discos_id": "53",
            "epoch": "1979-12-15",
            "eventType": "Unknown",
            "altitude": None,
            "latitude": None,
            "longitude": None,
            "comment": "some comment",
            "objectsCount": 24,
        }
        doc = self.mod._make_event_doc(event, "2026-01-01T00:00:00+00:00")
        self.assertEqual(doc["_key"], "DISCOS-FRAG-53")
        self.assertIsNone(doc["canonical"]["fragment_count_kessler"])
        self.assertIsNone(doc["canonical"]["fragment_count_discos"])
        self.assertIsNone(doc["canonical"]["fragment_count_estimated"])
        self.assertEqual(doc["sources"]["discos"]["raw"], event)
        self.assertEqual(doc["metadata"]["transformations"][0]["action"], "ingest")

    def test_all_api_attributes_stored_verbatim(self):
        event = {
            "discos_id": "100",
            "epoch": "2009-02-10",
            "objectsCount": 2841,
            "someNewField": "future_value",
        }
        doc = self.mod._make_event_doc(event, "2026-01-01T00:00:00+00:00")
        self.assertEqual(doc["sources"]["discos"]["raw"]["objectsCount"], 2841)
        self.assertEqual(doc["sources"]["discos"]["raw"]["someNewField"], "future_value")


# ---------------------------------------------------------------------------
# ingest_discos_fragmentations run() — verify vs ingest log
# ---------------------------------------------------------------------------

class TestIngestDiscosFragmentationsRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib
        mod_name = "scripts.population.ingest_discos_fragmentations"
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        cls.mod = importlib.import_module(mod_name)

    def _make_existing_doc(self, raw: dict, transformations=None):
        return {
            "_key": f"DISCOS-FRAG-{raw.get('discos_id', '1')}",
            "canonical": {
                "fragment_count_kessler": None,
                "fragment_count_discos": None,
                "fragment_count_estimated": None,
            },
            "sources": {"discos": {"raw": raw}},
            "metadata": {"transformations": transformations or []},
        }

    def test_verify_action_when_no_change(self):
        raw = {"discos_id": "1", "epoch": "2009-02-10", "altitude": None}
        existing = self._make_existing_doc(raw)

        mock_col = MagicMock()
        mock_col.get.return_value = existing

        with patch.object(self.mod, "db_conn") as mock_conn, \
             patch.object(self.mod, "db_module") as mock_db, \
             patch.object(self.mod, "discos_service") as mock_svc:
            mock_conn.connect_arangodb.return_value = True
            mock_svc.get_fragmentation_events.return_value = [raw]
            mock_db.db.collection.return_value = mock_col
            self.mod.run(dry_run=False)

        mock_col.update.assert_called_once()
        update_arg = mock_col.update.call_args[0][0]
        transformations = update_arg["metadata"]["transformations"]
        last = transformations[-1]
        self.assertEqual(last["action"], "verify")
        self.assertNotIn("changed_fields", last)

    def test_ingest_action_with_changed_fields_when_data_changes(self):
        old_raw = {"discos_id": "1", "epoch": "2009-02-10", "altitude": None}
        new_raw = {"discos_id": "1", "epoch": "2009-02-10", "altitude": 500.0}
        existing = self._make_existing_doc(old_raw)

        mock_col = MagicMock()
        mock_col.get.return_value = existing

        with patch.object(self.mod, "db_conn") as mock_conn, \
             patch.object(self.mod, "db_module") as mock_db, \
             patch.object(self.mod, "discos_service") as mock_svc:
            mock_conn.connect_arangodb.return_value = True
            mock_svc.get_fragmentation_events.return_value = [new_raw]
            mock_db.db.collection.return_value = mock_col
            self.mod.run(dry_run=False)

        mock_col.update.assert_called_once()
        update_arg = mock_col.update.call_args[0][0]
        transformations = update_arg["metadata"]["transformations"]
        last = transformations[-1]
        self.assertEqual(last["action"], "ingest")
        self.assertIn("altitude", last["changed_fields"])

    def test_new_record_inserted_with_ingest_action(self):
        raw = {"discos_id": "99", "epoch": "2021-01-01"}
        mock_col = MagicMock()
        mock_col.get.return_value = None

        with patch.object(self.mod, "db_conn") as mock_conn, \
             patch.object(self.mod, "db_module") as mock_db, \
             patch.object(self.mod, "discos_service") as mock_svc:
            mock_conn.connect_arangodb.return_value = True
            mock_svc.get_fragmentation_events.return_value = [raw]
            mock_db.db.collection.return_value = mock_col
            self.mod.run(dry_run=False)

        mock_col.insert.assert_called_once()
        insert_arg = mock_col.insert.call_args[0][0]
        self.assertEqual(insert_arg["metadata"]["transformations"][0]["action"], "ingest")

    def test_existing_fragment_counts_preserved_on_data_change(self):
        old_raw = {"discos_id": "1", "altitude": None}
        new_raw = {"discos_id": "1", "altitude": 200.0}
        existing = self._make_existing_doc(old_raw)
        existing["canonical"]["fragment_count_kessler"] = 42
        existing["canonical"]["fragment_count_discos"] = 100

        mock_col = MagicMock()
        mock_col.get.return_value = existing

        with patch.object(self.mod, "db_conn") as mock_conn, \
             patch.object(self.mod, "db_module") as mock_db, \
             patch.object(self.mod, "discos_service") as mock_svc:
            mock_conn.connect_arangodb.return_value = True
            mock_svc.get_fragmentation_events.return_value = [new_raw]
            mock_db.db.collection.return_value = mock_col
            self.mod.run(dry_run=False)

        update_arg = mock_col.update.call_args[0][0]
        self.assertEqual(update_arg["canonical"]["fragment_count_kessler"], 42)
        self.assertEqual(update_arg["canonical"]["fragment_count_discos"], 100)


# ---------------------------------------------------------------------------
# ingest_discos_attributions — fragment_count_kessler idempotency
# ---------------------------------------------------------------------------

class TestIngestDiscosAttributionsIdempotency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib
        mod_name = "scripts.population.ingest_discos_attributions"
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        cls.mod = importlib.import_module(mod_name)

    def _make_event_doc(self, kessler_count=None, discos_id="100"):
        return {
            "_key": f"DISCOS-FRAG-{discos_id}",
            "_id": f"fragmentation_events/DISCOS-FRAG-{discos_id}",
            "sources": {"discos": {"discos_id": discos_id}},
            "canonical": {"fragment_count_kessler": kessler_count},
            "metadata": {"transformations": []},
        }

    def test_no_transformation_logged_when_count_unchanged(self):
        event_doc = self._make_event_doc(kessler_count=5)
        attributions = [{"discos_id": str(i)} for i in range(5)]

        mock_frag_col = MagicMock()
        with patch.object(self.mod, "db_module") as mock_db, \
             patch.object(self.mod, "get_fragmentation_attributed_objects_with_count") as mock_get:
            mock_get.return_value = (attributions, 5)
            mock_db.db.collection.return_value = mock_frag_col
            self.mod._process_event(event_doc, lookup={}, dry_run=False, now="2026-01-01T00:00:00+00:00")

        mock_frag_col.update.assert_not_called()

    def test_transformation_logged_when_count_changes(self):
        event_doc = self._make_event_doc(kessler_count=3)
        attributions = [{"discos_id": str(i)} for i in range(5)]

        mock_frag_col = MagicMock()
        with patch.object(self.mod, "db_module") as mock_db, \
             patch.object(self.mod, "get_fragmentation_attributed_objects_with_count") as mock_get:
            mock_get.return_value = (attributions, 5)
            mock_db.db.collection.return_value = mock_frag_col
            self.mod._process_event(event_doc, lookup={}, dry_run=False, now="2026-01-01T00:00:00+00:00")

        mock_frag_col.update.assert_called_once()
        update_arg = mock_frag_col.update.call_args[0][0]
        self.assertEqual(update_arg["canonical"]["fragment_count_kessler"], 5)
        last_tx = update_arg["metadata"]["transformations"][-1]
        self.assertEqual(last_tx["action"], "update_fragment_count")
        self.assertEqual(last_tx["fragment_count_kessler"], 5)


# ---------------------------------------------------------------------------
# ingest_discos_attributions — pagination totalCount warning
# ---------------------------------------------------------------------------

class TestIngestDiscosAttributionsPaginationWarning(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib
        mod_name = "scripts.population.ingest_discos_attributions"
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        cls.mod = importlib.import_module(mod_name)

    def _make_event_doc(self, discos_id="53"):
        return {
            "_key": f"DISCOS-FRAG-{discos_id}",
            "_id": f"fragmentation_events/DISCOS-FRAG-{discos_id}",
            "sources": {"discos": {"discos_id": discos_id}},
            "canonical": {"fragment_count_kessler": None},
            "metadata": {"transformations": []},
        }

    def test_warning_logged_when_total_count_mismatches(self):
        event_doc = self._make_event_doc()
        attributions = [{"discos_id": str(i)} for i in range(3)]

        with patch.object(self.mod, "db_module") as mock_db, \
             patch.object(self.mod, "get_fragmentation_attributed_objects_with_count") as mock_get:
            mock_get.return_value = (attributions, 250)
            mock_db.db.collection.return_value = MagicMock()
            logger_name = self.mod.__name__
            with self.assertLogs(logger_name, level="WARNING") as cm:
                self.mod._process_event(event_doc, lookup={}, dry_run=False, now="2026-01-01T00:00:00+00:00")
        self.assertTrue(any("mismatch" in msg.lower() or "Pagination mismatch" in msg for msg in cm.output))

    def test_no_warning_when_total_count_none(self):
        event_doc = self._make_event_doc()
        attributions = [{"discos_id": "1"}]

        with patch.object(self.mod, "db_module") as mock_db, \
             patch.object(self.mod, "get_fragmentation_attributed_objects_with_count") as mock_get:
            mock_get.return_value = (attributions, None)
            mock_db.db.collection.return_value = MagicMock()
            import logging
            with self.assertLogs(self.mod.__name__, level="DEBUG") as cm:
                logging.getLogger(self.mod.__name__).debug("ping")
                self.mod._process_event(event_doc, lookup={}, dry_run=False, now="2026-01-01T00:00:00+00:00")
        self.assertFalse(any("mismatch" in msg.lower() for msg in cm.output))


# ---------------------------------------------------------------------------
# promote_discos_fragmentations — _extract_discos_count
# ---------------------------------------------------------------------------

class TestExtractDiscosCount(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib
        mod_name = "scripts.maintenance.promote_discos_fragmentations"
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        cls.mod = importlib.import_module(mod_name)

    def test_objectsCount_primary(self):
        raw = {"objectsCount": 24, "cataloguedFragments": 20}
        count, field = self.mod._extract_discos_count(raw)
        self.assertEqual(count, 24)
        self.assertEqual(field, "objectsCount")

    def test_cataloguedFragments_fallback(self):
        raw = {"cataloguedFragments": 15}
        count, field = self.mod._extract_discos_count(raw)
        self.assertEqual(count, 15)
        self.assertEqual(field, "cataloguedFragments")

    def test_nFragments_fallback(self):
        raw = {"nFragments": 7}
        count, field = self.mod._extract_discos_count(raw)
        self.assertEqual(count, 7)
        self.assertEqual(field, "nFragments")

    def test_no_count_field_returns_none(self):
        raw = {"epoch": "2009-02-10", "altitude": None}
        count, field = self.mod._extract_discos_count(raw)
        self.assertIsNone(count)
        self.assertIsNone(field)

    def test_non_numeric_value_skipped(self):
        raw = {"objectsCount": "unknown", "nFragments": 5}
        count, field = self.mod._extract_discos_count(raw)
        self.assertEqual(count, 5)
        self.assertEqual(field, "nFragments")


# ---------------------------------------------------------------------------
# promote_discos_fragmentations — idempotency
# ---------------------------------------------------------------------------

class TestPromoteDiscosFragmentationsIdempotency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib
        mod_name = "scripts.maintenance.promote_discos_fragmentations"
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        cls.mod = importlib.import_module(mod_name)

    def test_fragment_count_discos_not_promoted_if_already_matches(self):
        event = {
            "_key": "DISCOS-FRAG-1",
            "canonical": {
                "epoch": "2009-02-10",
                "fragment_count_discos": 24,
            },
            "sources": {"discos": {"raw": {"epoch": "2009-02-10", "objectsCount": 24}}},
            "metadata": {"transformations": []},
        }
        mock_col = MagicMock()
        with patch.object(self.mod, "db_conn") as mock_conn, \
             patch.object(self.mod, "db_module") as mock_db:
            mock_conn.connect_arangodb.return_value = True
            mock_db.db.aql.execute.return_value = iter([event])
            mock_db.db.collection.return_value = mock_col
            self.mod.run(dry_run=False)

        mock_col.update.assert_not_called()

    def test_fragment_count_discos_promoted_when_different(self):
        event = {
            "_key": "DISCOS-FRAG-1",
            "canonical": {
                "epoch": "2009-02-10",
                "fragment_count_discos": None,
            },
            "sources": {"discos": {"raw": {"epoch": "2009-02-10", "objectsCount": 24}}},
            "metadata": {"transformations": []},
        }
        mock_col = MagicMock()
        with patch.object(self.mod, "db_conn") as mock_conn, \
             patch.object(self.mod, "db_module") as mock_db:
            mock_conn.connect_arangodb.return_value = True
            mock_db.db.aql.execute.return_value = iter([event])
            mock_db.db.collection.return_value = mock_col
            self.mod.run(dry_run=False)

        mock_col.update.assert_called_once()
        update_arg = mock_col.update.call_args[0][0]
        self.assertEqual(update_arg["canonical"]["fragment_count_discos"], 24)
        last_tx = update_arg["metadata"]["transformations"][-1]
        self.assertEqual(last_tx["action"], "promote")
        self.assertEqual(last_tx["target_field"], "canonical.fragment_count_discos")
        self.assertEqual(last_tx["value"], 24)


# ---------------------------------------------------------------------------
# migrate_split_fragment_counts
# ---------------------------------------------------------------------------

class TestMigrateSplitFragmentCounts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib
        mod_name = "scripts.migration.migrate_split_fragment_counts"
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        cls.mod = importlib.import_module(mod_name)

    def test_no_op_when_no_old_field(self):
        with patch.object(self.mod, "db_conn") as mock_conn, \
             patch.object(self.mod, "db_module") as mock_db:
            mock_conn.connect_arangodb.return_value = True
            mock_db.db.aql.execute.return_value = iter([0])
            result = self.mod.run(dry_run=False, yes=True)

        self.assertTrue(result)
        mock_db.db.aql.execute.assert_called_once()

    def test_dry_run_makes_no_changes(self):
        with patch.object(self.mod, "db_conn") as mock_conn, \
             patch.object(self.mod, "db_module") as mock_db:
            mock_conn.connect_arangodb.return_value = True
            mock_db.db.aql.execute.return_value = iter([5])
            result = self.mod.run(dry_run=True, yes=True)

        self.assertTrue(result)
        mock_db.db.aql.execute.assert_called_once()

    def test_migration_runs_aql_and_returns_true(self):
        call_results = [iter([3]), iter([3]), iter([0])]
        call_count = [0]

        def fake_execute(aql, **kwargs):
            r = call_results[call_count[0]]
            call_count[0] += 1
            return r

        with patch.object(self.mod, "db_conn") as mock_conn, \
             patch.object(self.mod, "db_module") as mock_db:
            mock_conn.connect_arangodb.return_value = True
            mock_db.db.aql.execute.side_effect = fake_execute
            result = self.mod.run(dry_run=False, yes=True)

        self.assertTrue(result)
        self.assertEqual(call_count[0], 3)

    def test_returns_false_when_remaining_docs_after_migration(self):
        call_results = [iter([2]), iter([2]), iter([1])]
        call_count = [0]

        def fake_execute(aql, **kwargs):
            r = call_results[call_count[0]]
            call_count[0] += 1
            return r

        with patch.object(self.mod, "db_conn") as mock_conn, \
             patch.object(self.mod, "db_module") as mock_db:
            mock_conn.connect_arangodb.return_value = True
            mock_db.db.aql.execute.side_effect = fake_execute
            result = self.mod.run(dry_run=False, yes=True)

        self.assertFalse(result)


# ---------------------------------------------------------------------------
# discos_service.get_fragmentation_attributed_objects_with_count
# ---------------------------------------------------------------------------

class TestGetFragmentationAttributedObjectsWithCount(unittest.TestCase):
    def setUp(self):
        import api.services.discos_service as svc
        svc.clear_cache()
        self.svc = svc

    @patch("api.services.discos_service._do_get")
    @patch("api.services.discos_service.config")
    def test_returns_items_and_total_count(self, mock_config, mock_do_get):
        mock_config.external.DISCOS_BASE_URL = "https://discosweb.esoc.esa.int/api"
        mock_config.external.DISCOS_API_TOKEN = "tok"
        mock_config.external.DISCOS_REQUEST_TIMEOUT = 30
        mock_do_get.return_value = {
            "data": [
                {"id": "10", "type": "object"},
                {"id": "11", "type": "object"},
            ],
            "meta": {"pagination": {"totalCount": 2}},
            "links": {},
        }
        items, total = self.svc.get_fragmentation_attributed_objects_with_count("53")
        self.assertEqual(len(items), 2)
        self.assertEqual(total, 2)
        self.assertEqual(items[0]["discos_id"], "10")

    @patch("api.services.discos_service._do_get")
    @patch("api.services.discos_service.config")
    def test_totalcount_none_when_meta_missing(self, mock_config, mock_do_get):
        mock_config.external.DISCOS_BASE_URL = "https://discosweb.esoc.esa.int/api"
        mock_config.external.DISCOS_API_TOKEN = "tok"
        mock_config.external.DISCOS_REQUEST_TIMEOUT = 30
        mock_do_get.return_value = {
            "data": [{"id": "5", "type": "object"}],
            "links": {},
        }
        items, total = self.svc.get_fragmentation_attributed_objects_with_count("100")
        self.assertEqual(len(items), 1)
        self.assertIsNone(total)

    @patch("api.services.discos_service._do_get")
    @patch("api.services.discos_service.config")
    def test_follows_pagination_links(self, mock_config, mock_do_get):
        mock_config.external.DISCOS_BASE_URL = "https://discosweb.esoc.esa.int/api"
        mock_config.external.DISCOS_API_TOKEN = "tok"
        mock_config.external.DISCOS_REQUEST_TIMEOUT = 30

        page1 = {
            "data": [{"id": str(i), "type": "object"} for i in range(100)],
            "meta": {"pagination": {"totalCount": 250}},
            "links": {"next": "https://discosweb.esoc.esa.int/api/fragmentations/53/relationships/objects?page=2"},
        }
        page2 = {
            "data": [{"id": str(i), "type": "object"} for i in range(100, 200)],
            "links": {"next": "https://discosweb.esoc.esa.int/api/fragmentations/53/relationships/objects?page=3"},
        }
        page3 = {
            "data": [{"id": str(i), "type": "object"} for i in range(200, 250)],
            "links": {},
        }
        mock_do_get.side_effect = [page1, page2, page3]

        items, total = self.svc.get_fragmentation_attributed_objects_with_count("53")
        self.assertEqual(len(items), 250)
        self.assertEqual(total, 250)

    @patch("api.services.discos_service._do_get")
    @patch("api.services.discos_service.config")
    def test_returns_empty_when_api_fails(self, mock_config, mock_do_get):
        mock_config.external.DISCOS_BASE_URL = "https://discosweb.esoc.esa.int/api"
        mock_config.external.DISCOS_API_TOKEN = "tok"
        mock_config.external.DISCOS_REQUEST_TIMEOUT = 30
        mock_do_get.return_value = None
        items, total = self.svc.get_fragmentation_attributed_objects_with_count("53")
        self.assertEqual(items, [])
        self.assertIsNone(total)


if __name__ == "__main__":
    unittest.main()
