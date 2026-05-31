import unittest
from api.main import app

class TestSwaggerOpenAPI(unittest.TestCase):
    def test_openapi_schema_generation(self):
        schema = app.openapi()
        self.assertIsNotNone(schema)
        self.assertIn("openapi", schema)
        self.assertIn("info", schema)
        self.assertIn("paths", schema)
        self.assertIn("components", schema)

    def test_openapi_metadata(self):
        schema = app.openapi()
        info = schema.get("info", {})
        self.assertEqual(info.get("title"), "Talon API")
        self.assertEqual(info.get("version"), "2.0.0")
        self.assertTrue(len(info.get("description", "")) > 0)

    def test_openapi_security_schemes(self):
        schema = app.openapi()
        components = schema.get("components", {})
        security_schemes = components.get("securitySchemes", {})
        self.assertIn("BearerAuth", security_schemes)
        self.assertEqual(security_schemes["BearerAuth"].get("type"), "http")
        self.assertEqual(security_schemes["BearerAuth"].get("scheme"), "bearer")

    def test_openapi_tags_completeness(self):
        schema = app.openapi()
        tags_list = schema.get("tags", [])
        defined_tags = {tag["name"] for tag in tags_list}
        
        used_tags = set()
        for path, path_info in schema.get("paths", {}).items():
            for method, method_info in path_info.items():
                if "tags" in method_info:
                    used_tags.update(method_info["tags"])
                    
        for tag in used_tags:
            self.assertIn(tag, defined_tags)
