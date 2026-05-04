"""
Unit tests for Spec 1: Rename satellites → objects, object_class, identifier_aliases.
"""
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


class TestCollectionNameConstant(unittest.TestCase):
    def test_collection_name_is_objects(self):
        from database.connection import COLLECTION_NAME
        self.assertEqual(COLLECTION_NAME, "objects")

    def test_config_collection_objects(self):
        from config import DatabaseConfig
        self.assertEqual(DatabaseConfig.COLLECTION_OBJECTS, "objects")

    def test_config_collection_satellites_deprecated_alias(self):
        from config import DatabaseConfig
        self.assertEqual(DatabaseConfig.COLLECTION_SATELLITES, "objects")


class TestAqlSchemaContextBase(unittest.TestCase):
    def _get_schema(self):
        import sys
        import types

        for mod_name in list(sys.modules.keys()):
            if "aql_agent" in mod_name:
                del sys.modules[mod_name]

        config_mock = MagicMock()
        config_mock.agent.OPENAI_API_KEY = ""
        config_mock.agent.MODEL = "gpt-4o-mini"

        with patch.dict(sys.modules, {"config": MagicMock(config=config_mock)}):
            from api.services.aql_agent_service import _SCHEMA_CONTEXT_BASE
            return _SCHEMA_CONTEXT_BASE

    def test_schema_references_objects_not_satellites(self):
        from api.services.aql_agent_service import _SCHEMA_CONTEXT_BASE
        self.assertIn("objects", _SCHEMA_CONTEXT_BASE)
        self.assertNotIn("FOR s IN satellites", _SCHEMA_CONTEXT_BASE)
        self.assertNotIn('"satellites/"', _SCHEMA_CONTEXT_BASE)

    def test_schema_references_object_class(self):
        from api.services.aql_agent_service import _SCHEMA_CONTEXT_BASE
        self.assertIn("object_class", _SCHEMA_CONTEXT_BASE)

    def test_schema_references_identifier_aliases(self):
        from api.services.aql_agent_service import _SCHEMA_CONTEXT_BASE
        self.assertIn("identifier_aliases", _SCHEMA_CONTEXT_BASE)


class TestClassifyObjects(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, ".")
        from scripts.migration.migrate_classify_objects import classify
        self.classify = classify

    def test_payload_uppercase(self):
        self.assertEqual(self.classify("PAYLOAD"), "Payload")

    def test_payload_mixed(self):
        self.assertEqual(self.classify("Payload"), "Payload")

    def test_pay_abbreviation(self):
        self.assertEqual(self.classify("PAY"), "Payload")

    def test_rocket_body_with_space(self):
        self.assertEqual(self.classify("ROCKET BODY"), "Rocket Body")

    def test_r_slash_b(self):
        self.assertEqual(self.classify("R/B"), "Rocket Body")

    def test_debris_uppercase(self):
        self.assertEqual(self.classify("DEBRIS"), "Unknown")

    def test_deb_abbreviation(self):
        self.assertEqual(self.classify("DEB"), "Unknown")

    def test_unknown_uppercase(self):
        self.assertEqual(self.classify("UNKNOWN"), "Unknown")

    def test_unk_abbreviation(self):
        self.assertEqual(self.classify("UNK"), "Unknown")

    def test_none_returns_unknown(self):
        self.assertEqual(self.classify(None), "Unknown")

    def test_mixed_case_rocket_body(self):
        self.assertEqual(self.classify("Rocket Body"), "Rocket Body")

    def test_mission_related(self):
        self.assertEqual(self.classify("Mission-Related Object"), "Mission-Related Object")


class TestIdentifierOperations(unittest.TestCase):
    def test_backfill_with_norad(self):
        from database.identifier_operations import backfill_identifier_aliases
        doc = {"canonical": {"norad_cat_id": 25544, "international_designator": "1998-067A"}}
        aliases = backfill_identifier_aliases(doc)
        self.assertEqual(aliases["norad"], "25544")
        self.assertEqual(aliases["cospar"], "1998-067A")

    def test_backfill_without_norad(self):
        from database.identifier_operations import backfill_identifier_aliases
        doc = {"canonical": {}}
        aliases = backfill_identifier_aliases(doc)
        self.assertNotIn("norad", aliases)
        self.assertNotIn("cospar", aliases)

    def test_alias_types_constant(self):
        from database.identifier_operations import ALIAS_TYPES
        self.assertIn("norad", ALIAS_TYPES)
        self.assertIn("cospar", ALIAS_TYPES)
        self.assertIn("discos", ALIAS_TYPES)
        self.assertIn("vimpel", ALIAS_TYPES)
        self.assertIn("kestrel", ALIAS_TYPES)

    def test_lookup_by_alias_invalid_type(self):
        from database.identifier_operations import lookup_by_alias
        with self.assertRaises(ValueError):
            lookup_by_alias("invalid_type", "12345")


class TestMergeOperations(unittest.TestCase):
    def test_merge_same_document_raises(self):
        from database.merge_operations import merge_objects

        fake_doc = {"_id": "objects/abc", "_key": "abc", "identifier": "abc",
                    "canonical": {}, "sources": {}, "identifier_aliases": {}, "metadata": {}}

        with patch("database.merge_operations._get_doc", return_value=fake_doc):
            with self.assertRaises(ValueError) as ctx:
                merge_objects("abc", "abc")
            self.assertIn("same", str(ctx.exception))

    def test_merge_primary_not_found_raises(self):
        from database.merge_operations import merge_objects

        with patch("database.merge_operations._get_doc", return_value=None):
            with self.assertRaises(ValueError) as ctx:
                merge_objects("missing_primary", "some_secondary")
            self.assertIn("Primary", str(ctx.exception))

    def test_dry_run_returns_plan(self):
        from database.merge_operations import merge_objects

        primary = {"_id": "objects/primary", "_key": "primary", "identifier": "primary",
                   "canonical": {}, "sources": {}, "identifier_aliases": {"norad": "111"}, "metadata": {}}
        secondary = {"_id": "objects/secondary", "_key": "secondary", "identifier": "secondary",
                     "canonical": {}, "sources": {}, "identifier_aliases": {"norad": "222"}, "metadata": {}}

        def get_doc_side_effect(key):
            if key == "primary":
                return primary
            if key == "secondary":
                return secondary
            return None

        with patch("database.merge_operations._get_doc", side_effect=get_doc_side_effect):
            audit = merge_objects("primary", "secondary", dry_run=True)
            self.assertTrue(audit["dry_run"])
            self.assertEqual(audit["status"], "dry_run")
            self.assertEqual(audit["primary_id"], "objects/primary")
            self.assertEqual(audit["secondary_id"], "objects/secondary")

    def test_alias_conflict_detected(self):
        from database.merge_operations import merge_objects

        primary = {"_id": "objects/p", "_key": "p", "identifier": "p",
                   "canonical": {}, "sources": {}, "identifier_aliases": {"norad": "111"}, "metadata": {}}
        secondary = {"_id": "objects/s", "_key": "s", "identifier": "s",
                     "canonical": {}, "sources": {}, "identifier_aliases": {"norad": "222"}, "metadata": {}}

        def get_doc(key):
            return primary if key == "p" else secondary

        with patch("database.merge_operations._get_doc", side_effect=get_doc):
            audit = merge_objects("p", "s", dry_run=True)
            conflicts = audit["alias_conflicts"]
            self.assertEqual(len(conflicts), 1)
            self.assertEqual(conflicts[0]["key"], "norad")
            self.assertEqual(conflicts[0]["resolution"], "primary_wins")


def _load_script_catalogue():
    """Load SCRIPT_CATALOGUE from admin.py without triggering FastAPI route registration."""
    import importlib.util
    import os

    admin_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "api", "routers", "admin.py"
    )
    source = open(os.path.abspath(admin_path)).read()
    match_start = source.index("SCRIPT_CATALOGUE = [")
    match_end = source.index("\n]", match_start) + 2
    catalogue_src = "SCRIPT_CATALOGUE " + source[match_start + len("SCRIPT_CATALOGUE "):]
    catalogue_src = catalogue_src[: catalogue_src.index("\n]") + 2]
    ns = {}
    exec(compile(catalogue_src, "<admin_catalogue>", "exec"), ns)
    return ns["SCRIPT_CATALOGUE"]


class TestAdminScriptCatalogue(unittest.TestCase):
    def setUp(self):
        self.catalogue = _load_script_catalogue()

    def test_migration_scripts_registered(self):
        ids = [s["id"] for s in self.catalogue]
        expected = [
            "migrate_collection_rename",
            "migrate_create_new_indexes",
            "migrate_classify_objects",
            "migrate_backfill_aliases",
            "migrate_rebuild_aql_rag",
            "migrate_verify_object_model",
        ]
        for script_id in expected:
            self.assertIn(script_id, ids, f"Migration script '{script_id}' not in SCRIPT_CATALOGUE")

    def test_migration_scripts_have_order_hint(self):
        migration_scripts = [s for s in self.catalogue if s["category"] == "migration"]
        for s in migration_scripts:
            self.assertIn("order_hint", s, f"Script '{s['id']}' missing order_hint")

    def test_migration_scripts_have_reversibility(self):
        migration_scripts = [s for s in self.catalogue if s["category"] == "migration"]
        for s in migration_scripts:
            self.assertIn("reversibility", s, f"Script '{s['id']}' missing reversibility")


class TestObjectsRouter(unittest.TestCase):
    def test_router_has_correct_prefix(self):
        from api.routers.objects import router
        self.assertEqual(router.prefix, "/v2/objects")

    def test_object_classes_enum(self):
        from api.routers.objects import _OBJECT_CLASSES
        self.assertIn("Payload", _OBJECT_CLASSES)
        self.assertIn("Rocket Body", _OBJECT_CLASSES)
        self.assertIn("Unknown", _OBJECT_CLASSES)
        self.assertIn("Mission-Related Object", _OBJECT_CLASSES)
        self.assertIn("Rocket Fragmentation Debris", _OBJECT_CLASSES)
        self.assertIn("Payload Fragmentation Debris", _OBJECT_CLASSES)


if __name__ == "__main__":
    unittest.main()
