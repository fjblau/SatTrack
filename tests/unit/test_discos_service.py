import unittest
from unittest.mock import patch, MagicMock, call
import time

import api.services.discos_service as svc


class TestTokenConfigured(unittest.TestCase):
    @patch("api.services.discos_service.config")
    def test_returns_true_when_token_set(self, mock_config):
        mock_config.external.DISCOS_API_TOKEN = "tok-123"
        self.assertTrue(svc._token_configured())

    @patch("api.services.discos_service.config")
    def test_returns_false_when_empty(self, mock_config):
        mock_config.external.DISCOS_API_TOKEN = ""
        self.assertFalse(svc._token_configured())


class TestMakeHeaders(unittest.TestCase):
    @patch("api.services.discos_service.config")
    def test_includes_required_headers(self, mock_config):
        mock_config.external.DISCOS_API_TOKEN = "mytoken"
        headers = svc._make_headers()
        self.assertEqual(headers["Authorization"], "Bearer mytoken")
        self.assertEqual(headers["DiscosWeb-Api-Version"], "2")
        self.assertIn("Accept", headers)


class TestCache(unittest.TestCase):
    def setUp(self):
        svc.clear_cache()

    def test_cache_miss_returns_none(self):
        self.assertIsNone(svc._cache_get("nonexistent"))

    def test_cache_set_and_get(self):
        svc._cache_set("key1", {"data": "value"})
        result = svc._cache_get("key1")
        self.assertEqual(result, {"data": "value"})

    @patch("api.services.discos_service.time")
    def test_expired_entry_returns_none(self, mock_time):
        mock_time.monotonic.return_value = 0.0
        svc._cache_set("key2", "some_value")
        mock_time.monotonic.return_value = 999999.0
        self.assertIsNone(svc._cache_get("key2"))


class TestDoGet(unittest.TestCase):
    def setUp(self):
        svc.clear_cache()

    @patch("api.services.discos_service.config")
    def test_returns_none_when_no_token(self, mock_config):
        mock_config.external.DISCOS_API_TOKEN = ""
        result = svc._do_get("/objects")
        self.assertIsNone(result)

    @patch("api.services.discos_service.requests.get")
    @patch("api.services.discos_service.config")
    def test_returns_parsed_json_on_200(self, mock_config, mock_get):
        mock_config.external.DISCOS_API_TOKEN = "tok"
        mock_config.external.DISCOS_BASE_URL = "https://discosweb.esoc.esa.int/api"
        mock_config.external.DISCOS_REQUEST_TIMEOUT = 30
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [], "links": {}}
        mock_resp.headers.get.return_value = None
        mock_get.return_value = mock_resp
        result = svc._do_get("/objects")
        self.assertEqual(result, {"data": [], "links": {}})

    @patch("api.services.discos_service.requests.get")
    @patch("api.services.discos_service.config")
    def test_returns_none_on_401(self, mock_config, mock_get):
        mock_config.external.DISCOS_API_TOKEN = "bad_token"
        mock_config.external.DISCOS_BASE_URL = "https://discosweb.esoc.esa.int/api"
        mock_config.external.DISCOS_REQUEST_TIMEOUT = 30
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp
        result = svc._do_get("/objects")
        self.assertIsNone(result)

    @patch("api.services.discos_service.requests.get")
    @patch("api.services.discos_service.config")
    def test_returns_none_on_404(self, mock_config, mock_get):
        mock_config.external.DISCOS_API_TOKEN = "tok"
        mock_config.external.DISCOS_BASE_URL = "https://discosweb.esoc.esa.int/api"
        mock_config.external.DISCOS_REQUEST_TIMEOUT = 30
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp
        result = svc._do_get("/objects/9999")
        self.assertIsNone(result)

    @patch("api.services.discos_service.time.sleep")
    @patch("api.services.discos_service.requests.get")
    @patch("api.services.discos_service.config")
    def test_retries_on_429(self, mock_config, mock_get, mock_sleep):
        mock_config.external.DISCOS_API_TOKEN = "tok"
        mock_config.external.DISCOS_BASE_URL = "https://discosweb.esoc.esa.int/api"
        mock_config.external.DISCOS_REQUEST_TIMEOUT = 30
        rate_resp = MagicMock()
        rate_resp.status_code = 429
        rate_resp.headers.get.return_value = None
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"data": []}
        ok_resp.headers.get.return_value = None
        mock_get.side_effect = [rate_resp, ok_resp]
        result = svc._do_get("/objects")
        self.assertEqual(result, {"data": []})
        mock_sleep.assert_called_once()

    @patch("api.services.discos_service.requests.get")
    @patch("api.services.discos_service.config")
    def test_returns_none_on_timeout(self, mock_config, mock_get):
        import requests as req_lib
        mock_config.external.DISCOS_API_TOKEN = "tok"
        mock_config.external.DISCOS_BASE_URL = "https://discosweb.esoc.esa.int/api"
        mock_config.external.DISCOS_REQUEST_TIMEOUT = 30
        mock_get.side_effect = req_lib.exceptions.Timeout()
        result = svc._do_get("/objects")
        self.assertIsNone(result)


class TestParseAttributes(unittest.TestCase):
    def test_extracts_id_and_attributes(self):
        item = {
            "id": "42",
            "type": "object",
            "attributes": {"name": "COSMOS 1408", "cosparId": "1982-092A"},
        }
        result = svc._parse_attributes(item)
        self.assertEqual(result["discos_id"], "42")
        self.assertEqual(result["name"], "COSMOS 1408")
        self.assertEqual(result["cosparId"], "1982-092A")

    def test_handles_missing_attributes(self):
        item = {"id": "99"}
        result = svc._parse_attributes(item)
        self.assertEqual(result["discos_id"], "99")


class TestGetObjects(unittest.TestCase):
    def setUp(self):
        svc.clear_cache()

    @patch("api.services.discos_service._get_paginated")
    def test_returns_parsed_list(self, mock_pag):
        mock_pag.return_value = [
            {"id": "1", "attributes": {"name": "OBJ-A"}},
            {"id": "2", "attributes": {"name": "OBJ-B"}},
        ]
        result = svc.get_objects()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["discos_id"], "1")
        self.assertEqual(result[1]["name"], "OBJ-B")

    @patch("api.services.discos_service._get_paginated")
    def test_caches_results(self, mock_pag):
        mock_pag.return_value = [{"id": "1", "attributes": {}}]
        svc.get_objects()
        svc.get_objects()
        mock_pag.assert_called_once()


class TestGetObjectByCospar(unittest.TestCase):
    def setUp(self):
        svc.clear_cache()

    @patch("api.services.discos_service._get_paginated")
    def test_returns_first_match(self, mock_pag):
        mock_pag.return_value = [{"id": "10", "attributes": {"cosparId": "1999-025A"}}]
        result = svc.get_object_by_cospar("1999-025A")
        self.assertIsNotNone(result)
        self.assertEqual(result["discos_id"], "10")

    @patch("api.services.discos_service._get_paginated")
    def test_returns_none_when_not_found(self, mock_pag):
        mock_pag.return_value = []
        result = svc.get_object_by_cospar("9999-999Z")
        self.assertIsNone(result)


class TestHealthCheck(unittest.TestCase):
    def setUp(self):
        svc.clear_cache()

    @patch("api.services.discos_service.config")
    def test_returns_not_configured_when_no_token(self, mock_config):
        mock_config.external.DISCOS_API_TOKEN = ""
        result = svc.health_check()
        self.assertEqual(result["status"], "error")
        self.assertIn("not configured", result["detail"])

    @patch("api.services.discos_service._do_get")
    @patch("api.services.discos_service.config")
    def test_returns_ready_when_api_reachable(self, mock_config, mock_do_get):
        mock_config.external.DISCOS_API_TOKEN = "tok"
        mock_do_get.return_value = {"data": []}
        result = svc.health_check()
        self.assertEqual(result["status"], "ready")

    @patch("api.services.discos_service._do_get")
    @patch("api.services.discos_service.config")
    def test_returns_error_when_api_unreachable(self, mock_config, mock_do_get):
        mock_config.external.DISCOS_API_TOKEN = "tok"
        mock_do_get.return_value = None
        result = svc.health_check()
        self.assertEqual(result["status"], "error")


class TestGetFragmentationEvents(unittest.TestCase):
    def setUp(self):
        svc.clear_cache()

    @patch("api.services.discos_service._get_paginated")
    def test_returns_events(self, mock_pag):
        mock_pag.return_value = [
            {"id": "100", "attributes": {"epoch": "2009-02-10", "type": "collision"}},
        ]
        result = svc.get_fragmentation_events()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["discos_id"], "100")
        self.assertEqual(result[0]["epoch"], "2009-02-10")


class TestGetObjectAttributions(unittest.TestCase):
    def setUp(self):
        svc.clear_cache()

    @patch("api.services.discos_service._do_get")
    def test_returns_attribution_list(self, mock_do_get):
        mock_do_get.return_value = {
            "data": [
                {"id": "200", "type": "object"},
                {"id": "201", "type": "object"},
            ]
        }
        result = svc.get_object_attributions("100")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["discos_id"], "200")

    @patch("api.services.discos_service._do_get")
    def test_returns_empty_when_none(self, mock_do_get):
        mock_do_get.return_value = None
        result = svc.get_object_attributions("999")
        self.assertEqual(result, [])

    @patch("api.services.discos_service._do_get")
    def test_wraps_single_dict_data(self, mock_do_get):
        mock_do_get.return_value = {"data": {"id": "300", "type": "object"}}
        result = svc.get_object_attributions("100")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["discos_id"], "300")


if __name__ == "__main__":
    unittest.main()
