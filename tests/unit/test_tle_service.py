import unittest
from unittest.mock import patch, MagicMock
from api.services.tle_service import (
    parse_tle_fields,
    _parse_tle_text,
    _fetch_tle_by_norad_id_uncached,
    _fetch_tle_by_intl_des_uncached,
)


ISS_NAME = "ISS (ZARYA)"
ISS_LINE1 = "1 25544U 98067A   24038.54586899  .00012769  00000+0  22680-3 0  9996"
ISS_LINE2 = "2 25544  51.6406 302.7583 0001012  95.3523  23.3829 15.50234806439337"


class TestParseTleFields(unittest.TestCase):

    def setUp(self):
        self.result = parse_tle_fields(ISS_NAME, ISS_LINE1, ISS_LINE2)

    def test_raw_lines_preserved(self):
        self.assertEqual(self.result["line1"], ISS_LINE1)
        self.assertEqual(self.result["line2"], ISS_LINE2)
        self.assertEqual(self.result["name"], ISS_NAME)

    def test_inclination(self):
        self.assertAlmostEqual(self.result["inclination_deg"], 51.6406, delta=0.01)

    def test_eccentricity(self):
        self.assertAlmostEqual(self.result["eccentricity"], 0.0001012, delta=1e-5)

    def test_mean_motion_range(self):
        mm = self.result["mean_motion_rev_per_day"]
        self.assertGreater(mm, 15.0)
        self.assertLess(mm, 16.0)

    def test_raan(self):
        self.assertAlmostEqual(self.result["raan_deg"], 302.7583, delta=0.01)

    def test_arg_of_perigee(self):
        self.assertAlmostEqual(self.result["arg_of_perigee_deg"], 95.3523, delta=0.01)

    def test_mean_anomaly(self):
        self.assertAlmostEqual(self.result["mean_anomaly_deg"], 23.3829, delta=0.01)

    def test_required_keys_present(self):
        required = [
            "line1", "line2", "name", "epoch_year", "epoch_day", "bstar",
            "inclination_deg", "raan_deg", "eccentricity", "arg_of_perigee_deg",
            "mean_anomaly_deg", "mean_motion_rev_per_day", "rev_number",
            "ndot", "nddot", "fetched_at",
        ]
        for key in required:
            self.assertIn(key, self.result, msg=f"Missing key: {key}")

    def test_fetched_at_is_iso_string(self):
        from datetime import datetime
        fetched_at = self.result["fetched_at"]
        self.assertIsInstance(fetched_at, str)
        datetime.fromisoformat(fetched_at)

    def test_epoch_year(self):
        self.assertEqual(self.result["epoch_year"], 24)


SLS_DEB_TLE_TEXT = (
    "SLS DEB\n"
    "1 55904U 22156D   25069.36876843  .00005432  00000+0  34073-3 0  9994\n"
    "2 55904  29.9658 213.5432 4601234  91.2345 287.3456  7.234567890123450\n"
    "SLS DEB\n"
    "1 55905U 22156E   25069.12345678  .00004567  00000+0  28234-3 0  9991\n"
    "2 55905  29.8765 214.1234 4598765  92.3456 286.4567  7.231234567890120\n"
    "SLS DEB\n"
    "1 55907U 22156G   25069.98765432  .00003456  00000+0  21345-3 0  9993\n"
    "2 55907  30.0123 212.9876 4603456  90.1234 288.5678  7.236789012345670\n"
)

ISS_TLE_TEXT = (
    "ISS (ZARYA)\n"
    "1 25544U 98067A   24038.54586899  .00012769  00000+0  22680-3 0  9996\n"
    "2 25544  51.6406 302.7583 0001012  95.3523  23.3829 15.50234806439337\n"
)


class TestParseTleText(unittest.TestCase):

    def test_parses_single_entry(self):
        entries = _parse_tle_text(ISS_TLE_TEXT)
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e["name"], "ISS (ZARYA)")
        self.assertEqual(e["norad_cat_id"], "25544")
        self.assertEqual(e["intl_designator"], "1998-067A")
        self.assertEqual(e["line1"], ISS_LINE1)
        self.assertEqual(e["line2"], ISS_LINE2)

    def test_parses_multiple_entries(self):
        entries = _parse_tle_text(SLS_DEB_TLE_TEXT)
        self.assertEqual(len(entries), 3)

    def test_sls_deb_norad_ids(self):
        entries = _parse_tle_text(SLS_DEB_TLE_TEXT)
        norad_ids = [e["norad_cat_id"] for e in entries]
        self.assertIn("55904", norad_ids)
        self.assertIn("55905", norad_ids)
        self.assertIn("55907", norad_ids)

    def test_sls_deb_intl_designators(self):
        entries = _parse_tle_text(SLS_DEB_TLE_TEXT)
        intl_des = [e["intl_designator"] for e in entries]
        self.assertIn("2022-156D", intl_des)
        self.assertIn("2022-156E", intl_des)
        self.assertIn("2022-156G", intl_des)

    def test_empty_text_returns_empty_list(self):
        self.assertEqual(_parse_tle_text(""), [])
        self.assertEqual(_parse_tle_text("   \n  \n"), [])

    def test_non_tle_text_returns_empty_list(self):
        self.assertEqual(_parse_tle_text("No GP data found"), [])

    def test_year_rollover_pre_2000(self):
        old_tle = (
            "SPUTNIK 1\n"
            "1 00001U 57001B   57275.00000000  .00000000  00000+0  00000+0 0  9999\n"
            "2 00001  65.0000   0.0000 0600000  90.0000   0.0000 15.00000000000001\n"
        )
        entries = _parse_tle_text(old_tle)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["intl_designator"], "1957-001B")


class TestFetchTleByIntlDesUncached(unittest.TestCase):

    @patch("api.services.tle_service.requests.get")
    def test_non_tle_celestrak_response_returns_none(self, mock_get):
        """Regression: if CelesTrak returns non-TLE text (e.g. old JSON format), result is None."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '[{"OBJECT_NAME":"SLS DEB","OBJECT_ID":"2022-156D","MEAN_MOTION":7.23}]'
        mock_get.return_value = mock_response

        result = _fetch_tle_by_intl_des_uncached("2022-156D")
        self.assertIsNone(result)

    @patch("api.services.tle_service.requests.get")
    def test_returns_tle_dict_for_tle_text_response(self, mock_get):
        """Core regression: TLE text response must be parsed and returned successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SLS_DEB_TLE_TEXT
        mock_get.return_value = mock_response

        result = _fetch_tle_by_intl_des_uncached("2022-156D")
        self.assertIsNotNone(result)
        self.assertEqual(result["source"], "celestrak")
        self.assertEqual(result["intl_designator"], "2022-156D")
        self.assertEqual(result["norad_cat_id"], "55904")
        self.assertIn("line1", result)
        self.assertIn("line2", result)

    @patch("api.services.tle_service.requests.get")
    def test_returns_first_entry_when_no_exact_match(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SLS_DEB_TLE_TEXT
        mock_get.return_value = mock_response

        result = _fetch_tle_by_intl_des_uncached("2022-156")
        self.assertIsNotNone(result)
        self.assertEqual(result["norad_cat_id"], "55904")

    @patch("api.services.tle_service.requests.get")
    def test_returns_none_on_empty_celestrak_response(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = ""
        mock_get.return_value = mock_response

        result = _fetch_tle_by_intl_des_uncached("2022-156D")
        self.assertIsNone(result)


class TestFetchTleByNoradIdUncached(unittest.TestCase):

    @patch("api.services.tle_service.requests.get")
    def test_returns_tle_dict_for_tle_text_response(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = (
            "SLS DEB\n"
            "1 55904U 22156D   25069.36876843  .00005432  00000+0  34073-3 0  9994\n"
            "2 55904  29.9658 213.5432 4601234  91.2345 287.3456  7.234567890123450\n"
        )
        mock_get.return_value = mock_response

        result = _fetch_tle_by_norad_id_uncached("55904")
        self.assertIsNotNone(result)
        self.assertEqual(result["norad_cat_id"], "55904")
        self.assertEqual(result["intl_designator"], "2022-156D")
        self.assertEqual(result["source"], "celestrak")

    @patch("api.services.tle_service.requests.get")
    def test_returns_none_when_all_sources_fail(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = ""
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        result = _fetch_tle_by_norad_id_uncached("55904")
        self.assertIsNone(result)

    @patch("api.services.tle_service.requests.get")
    def test_uses_tle_format_param(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = ""
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        _fetch_tle_by_norad_id_uncached("55904")
        first_call = mock_get.call_args_list[0]
        params = first_call.kwargs.get("params") or (first_call[0][1] if len(first_call[0]) > 1 else {})
        if not params:
            params = first_call[1].get("params", {})
        self.assertEqual(params.get("FORMAT"), "TLE")


if __name__ == "__main__":
    unittest.main()
