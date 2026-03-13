import unittest
from unittest.mock import patch, MagicMock

from api.services.spacetrack_service import (
    _gp_entry_to_tle_dict,
    fetch_tle_from_spacetrack_by_norad_id,
    fetch_tle_from_spacetrack_by_intl_des,
    _invalidate_session,
)

SAMPLE_GP_ENTRY = {
    "OBJECT_NAME": "COSMOS 2251 DEB",
    "OBJECT_ID": "1993-036AHH",
    "NORAD_CAT_ID": "33895",
    "EPOCH": "2024-02-07T12:00:00.000000",
    "TLE_LINE1": "1 33895U 93036AHH 24038.50000000  .00000123  00000+0  12345-4 0  9991",
    "TLE_LINE2": "2 33895  74.0123 123.4567 0012345  98.7654 261.4567 14.48765432123456",
}


class TestGpEntryToTleDict(unittest.TestCase):
    def test_converts_valid_entry(self):
        result = _gp_entry_to_tle_dict(SAMPLE_GP_ENTRY)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "COSMOS 2251 DEB")
        self.assertEqual(result["line1"], SAMPLE_GP_ENTRY["TLE_LINE1"])
        self.assertEqual(result["line2"], SAMPLE_GP_ENTRY["TLE_LINE2"])
        self.assertEqual(result["source"], "spacetrack")
        self.assertEqual(result["norad_cat_id"], "33895")
        self.assertEqual(result["intl_designator"], "1993-036AHH")
        self.assertEqual(result["date"], "2024-02-07T12:00:00.000000")

    def test_returns_none_if_lines_missing(self):
        entry = {**SAMPLE_GP_ENTRY, "TLE_LINE1": None}
        self.assertIsNone(_gp_entry_to_tle_dict(entry))

    def test_returns_none_if_both_lines_absent(self):
        entry = {"OBJECT_NAME": "X"}
        self.assertIsNone(_gp_entry_to_tle_dict(entry))


class TestFetchByNoradIdNoCredentials(unittest.TestCase):
    def setUp(self):
        _invalidate_session()

    @patch("api.services.spacetrack_service.config")
    def test_returns_none_when_no_credentials(self, mock_config):
        mock_config.external.SPACETRACK_USERNAME = ""
        mock_config.external.SPACETRACK_PASSWORD = ""
        result = fetch_tle_from_spacetrack_by_norad_id("33895")
        self.assertIsNone(result)

    @patch("api.services.spacetrack_service._credentials_configured", return_value=True)
    @patch("api.services.spacetrack_service._get_session")
    def test_returns_none_when_session_fails(self, mock_session, _mock_creds):
        mock_session.return_value = None
        result = fetch_tle_from_spacetrack_by_norad_id("33895")
        self.assertIsNone(result)

    @patch("api.services.spacetrack_service._credentials_configured", return_value=True)
    @patch("api.services.spacetrack_service._get_session")
    def test_returns_tle_on_success(self, mock_session, _mock_creds):
        sess = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = [SAMPLE_GP_ENTRY]
        sess.get.return_value = resp
        mock_session.return_value = sess

        result = fetch_tle_from_spacetrack_by_norad_id("33895")
        self.assertIsNotNone(result)
        self.assertEqual(result["source"], "spacetrack")
        self.assertEqual(result["norad_cat_id"], "33895")

    @patch("api.services.spacetrack_service._credentials_configured", return_value=True)
    @patch("api.services.spacetrack_service._get_session")
    def test_returns_none_when_empty_list(self, mock_session, _mock_creds):
        sess = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = []
        sess.get.return_value = resp
        mock_session.return_value = sess

        result = fetch_tle_from_spacetrack_by_norad_id("99999")
        self.assertIsNone(result)


class TestFetchByIntlDes(unittest.TestCase):
    def setUp(self):
        _invalidate_session()

    @patch("api.services.spacetrack_service._credentials_configured", return_value=True)
    @patch("api.services.spacetrack_service._get_session")
    def test_prefers_exact_match(self, mock_session, _mock_creds):
        other_entry = {**SAMPLE_GP_ENTRY, "OBJECT_ID": "1993-036ZZZ", "OBJECT_NAME": "OTHER"}
        exact_entry = {**SAMPLE_GP_ENTRY, "OBJECT_ID": "1993-036AHH", "OBJECT_NAME": "COSMOS 2251 DEB"}

        sess = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = [other_entry, exact_entry]
        sess.get.return_value = resp
        mock_session.return_value = sess

        result = fetch_tle_from_spacetrack_by_intl_des("1993-036AHH")
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "COSMOS 2251 DEB")

    @patch("api.services.spacetrack_service._credentials_configured", return_value=True)
    @patch("api.services.spacetrack_service._get_session")
    def test_falls_back_to_first_when_no_exact_match(self, mock_session, _mock_creds):
        entry_a = {**SAMPLE_GP_ENTRY, "OBJECT_ID": "1993-036AAA", "OBJECT_NAME": "FIRST"}
        entry_b = {**SAMPLE_GP_ENTRY, "OBJECT_ID": "1993-036BBB", "OBJECT_NAME": "SECOND"}

        sess = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = [entry_a, entry_b]
        sess.get.return_value = resp
        mock_session.return_value = sess

        result = fetch_tle_from_spacetrack_by_intl_des("1993-036XXX")
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "FIRST")


class TestTleServiceFallback(unittest.TestCase):
    """Test that tle_service falls back to SpaceTrack when CelesTrak returns nothing."""

    @patch("api.services.tle_service.fetch_tle_from_spacetrack_by_norad_id")
    @patch("api.services.tle_service._tle_cache_instance")
    def test_norad_fallback_called_when_celestrak_fails(self, mock_cache, mock_st_fetch):
        from api.services.tle_service import _fetch_tle_by_norad_id_uncached

        mock_st_fetch.return_value = {
            "name": "COSMOS DEB",
            "line1": SAMPLE_GP_ENTRY["TLE_LINE1"],
            "line2": SAMPLE_GP_ENTRY["TLE_LINE2"],
            "source": "spacetrack",
        }

        with patch("api.services.tle_service.requests.get") as mock_get:
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = []
            mock_get.return_value = resp

            result = _fetch_tle_by_norad_id_uncached("33895")

        mock_st_fetch.assert_called_once_with("33895")
        self.assertIsNotNone(result)
        self.assertEqual(result["source"], "spacetrack")

    @patch("api.services.tle_service.fetch_tle_from_spacetrack_by_intl_des")
    @patch("api.services.tle_service._tle_cache_instance")
    def test_intldes_fallback_called_when_celestrak_fails(self, mock_cache, mock_st_fetch):
        from api.services.tle_service import _fetch_tle_by_intl_des_uncached

        mock_st_fetch.return_value = {
            "name": "COSMOS DEB",
            "line1": SAMPLE_GP_ENTRY["TLE_LINE1"],
            "line2": SAMPLE_GP_ENTRY["TLE_LINE2"],
            "source": "spacetrack",
        }

        with patch("api.services.tle_service.requests.get") as mock_get:
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = []
            mock_get.return_value = resp

            result = _fetch_tle_by_intl_des_uncached("1993-036AHH")

        mock_st_fetch.assert_called_once_with("1993-036AHH")
        self.assertIsNotNone(result)
        self.assertEqual(result["source"], "spacetrack")

    @patch("api.services.tle_service.fetch_tle_from_spacetrack_by_norad_id")
    @patch("api.services.tle_service._tle_cache_instance")
    def test_spacetrack_not_called_when_celestrak_succeeds(self, mock_cache, mock_st_fetch):
        from api.services.tle_service import _fetch_tle_by_norad_id_uncached

        celestrak_entry = {
            "TLE_LINE1": SAMPLE_GP_ENTRY["TLE_LINE1"],
            "TLE_LINE2": SAMPLE_GP_ENTRY["TLE_LINE2"],
            "OBJECT_NAME": "ISS",
            "EPOCH": "2024-02-07T12:00:00.000000",
            "NORAD_CAT_ID": "25544",
            "OBJECT_ID": "1998-067A",
        }

        with patch("api.services.tle_service.requests.get") as mock_get:
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = [celestrak_entry]
            mock_get.return_value = resp

            result = _fetch_tle_by_norad_id_uncached("25544")

        mock_st_fetch.assert_not_called()
        self.assertIsNotNone(result)
        self.assertEqual(result["source"], "celestrak")


if __name__ == "__main__":
    unittest.main()
