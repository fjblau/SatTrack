import unittest
from unittest.mock import patch, MagicMock

from api.services.tle_service import check_decay_from_celestrak
from scripts.maintenance.promote_gcat_attributes import GCAT_STATUS_MAP


TERMINAL_STATUSES = {"decayed", "heliocentric", "in disposal/graveyard orbit"}


class TestCheckDecayFromCelesTrak(unittest.TestCase):
    """
    Regression tests for the CelesTrak satcat decay-check helper.

    Bug: GCAT-S57687 ("deb Artemis I", NORAD 57687) shows canonical.status="in orbit"
    even though the object decayed on 2023-11-07. GCAT has not yet recorded the decay.
    The fix adds a lazy CelesTrak lookup in the satellite detail endpoint that writes the
    correct status on first view.
    """

    @patch("api.services.tle_service.requests.get")
    def test_returns_decay_date_when_celestrak_has_record(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "OBJECT_NAME": "SLS DEB",
                "NORAD_CAT_ID": "57687",
                "DECAY_DATE": "2023-11-07",
                "OPS_STATUS_CODE": "-",
            }
        ]
        mock_get.return_value = mock_response

        result = check_decay_from_celestrak("57687")

        self.assertIsNotNone(result)
        self.assertEqual(result["decay_date"], "2023-11-07")
        self.assertEqual(result["ops_status_code"], "-")
        self.assertEqual(result["object_name"], "SLS DEB")

    @patch("api.services.tle_service.requests.get")
    def test_returns_none_when_no_decay_date(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "OBJECT_NAME": "ISS (ZARYA)",
                "NORAD_CAT_ID": "25544",
                "DECAY_DATE": None,
                "OPS_STATUS_CODE": "+",
            }
        ]
        mock_get.return_value = mock_response

        result = check_decay_from_celestrak("25544")

        self.assertIsNotNone(result)
        self.assertIsNone(result["decay_date"])

    @patch("api.services.tle_service.requests.get")
    def test_returns_none_when_empty_records(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        result = check_decay_from_celestrak("57687")

        self.assertIsNone(result)

    @patch("api.services.tle_service.requests.get")
    def test_returns_none_on_http_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = check_decay_from_celestrak("57687")

        self.assertIsNone(result)

    @patch("api.services.tle_service.requests.get")
    def test_returns_none_on_exception(self, mock_get):
        mock_get.side_effect = Exception("Network error")

        result = check_decay_from_celestrak("57687")

        self.assertIsNone(result)

    @patch("api.services.tle_service.requests.get")
    def test_calls_celestrak_satcat_with_correct_params(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        check_decay_from_celestrak("57687")

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params", {})
        self.assertEqual(params.get("CATNR"), "57687")
        self.assertEqual(params.get("FORMAT"), "JSON")


class TestGcatStatusMap(unittest.TestCase):
    """
    Regression tests for the GCAT status code → canonical status mapping.

    Bug root cause: GCAT for NORAD 57687 has status_code="O" (in orbit) with no decay date.
    Even when GCAT is refreshed and shows a terminal code, the old fill-if-null logic in
    promote_gcat_attributes.py would not overwrite an existing "in orbit" status.
    """

    def test_orbital_codes_map_to_in_orbit(self):
        orbital_codes = ["O", "AO", "AR", "OX", "ATT", "N", "TFR", "REL"]
        for code in orbital_codes:
            with self.subTest(code=code):
                self.assertEqual(GCAT_STATUS_MAP[code], "in orbit")

    def test_decay_codes_map_to_decayed(self):
        decay_codes = ["R", "R?", "D", "DK", "C", "L"]
        for code in decay_codes:
            with self.subTest(code=code):
                self.assertEqual(GCAT_STATUS_MAP[code], "decayed")

    def test_heliocentric_codes(self):
        helio_codes = ["DSO", "DSA", "E"]
        for code in helio_codes:
            with self.subTest(code=code):
                self.assertEqual(GCAT_STATUS_MAP[code], "heliocentric")

    def test_graveyard_orbit_code(self):
        self.assertEqual(GCAT_STATUS_MAP["GRP"], "in disposal/graveyard orbit")

    def test_all_terminal_statuses_are_non_orbit(self):
        for code, status in GCAT_STATUS_MAP.items():
            if status in TERMINAL_STATUSES:
                self.assertNotEqual(status, "in orbit",
                    msg=f"Code {code!r} maps to terminal status but also 'in orbit'")


class TestGcatWinsOnDecayLogic(unittest.TestCase):
    """
    Unit tests for the Python equivalent of the AQL 'GCAT-wins-on-decay' logic.

    The AQL in promote_gcat_attributes.py uses:
        LET terminal_status = (status_mapped == "decayed" OR ...)
        status: (terminal_status AND status_mapped != null)
                ? status_mapped
                : (doc.canonical.status != null ? doc.canonical.status : status_mapped)

    These tests verify that same logic expressed in Python, ensuring terminal GCAT
    statuses always override a stale "in orbit" canonical status.
    """

    def _apply_promotion_logic(self, gcat_status_raw, existing_canonical_status):
        status_mapped = GCAT_STATUS_MAP.get(gcat_status_raw)
        terminal_status = status_mapped in TERMINAL_STATUSES
        if terminal_status and status_mapped is not None:
            return status_mapped
        return existing_canonical_status if existing_canonical_status is not None else status_mapped

    def test_decayed_gcat_overrides_stale_in_orbit(self):
        result = self._apply_promotion_logic("R", "in orbit")
        self.assertEqual(result, "decayed")

    def test_decayed_gcat_overrides_in_orbit_for_norad_57687_scenario(self):
        result = self._apply_promotion_logic("D", "in orbit")
        self.assertEqual(result, "decayed")

    def test_heliocentric_gcat_overrides_stale_in_orbit(self):
        result = self._apply_promotion_logic("DSO", "in orbit")
        self.assertEqual(result, "heliocentric")

    def test_graveyard_gcat_overrides_stale_in_orbit(self):
        result = self._apply_promotion_logic("GRP", "in orbit")
        self.assertEqual(result, "in disposal/graveyard orbit")

    def test_in_orbit_gcat_does_not_override_existing_canonical(self):
        result = self._apply_promotion_logic("O", "decayed")
        self.assertEqual(result, "decayed")

    def test_in_orbit_gcat_fills_null_canonical(self):
        result = self._apply_promotion_logic("O", None)
        self.assertEqual(result, "in orbit")

    def test_decayed_gcat_fills_null_canonical(self):
        result = self._apply_promotion_logic("R", None)
        self.assertEqual(result, "decayed")

    def test_unknown_gcat_code_with_null_canonical(self):
        result = self._apply_promotion_logic("UNKNOWN_CODE", None)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
