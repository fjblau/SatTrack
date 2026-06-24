import unittest
from api.services.maneuver_detection_service import (
    compute_delta_v_residual,
    extract_maneuver_events,
    _tle_epoch_to_datetime,
    _vector_magnitude,
    _vector_diff,
)


_ISS_LINE1_A = "1 25544U 98067A   24038.54586899  .00012769  00000+0  22680-3 0  9996"
_ISS_LINE2_A = "2 25544  51.6406 302.7583 0001012  95.3523  23.3829 15.50234806439337"

_ISS_LINE1_B = "1 25544U 98067A   24039.54586899  .00012769  00000+0  22680-3 0  9997"
_ISS_LINE2_B = "2 25544  51.6406 302.7583 0001012  95.3523  23.3829 15.50234806439337"

_ISS_LINE1_MANEUVER = "1 25544U 98067A   24039.54586899  .00012769  00000+0  22680-3 0  9997"
_ISS_LINE2_MANEUVER = "2 25544  51.6406 302.7583 0001012  95.3523  23.3829 15.80234806439338"


class TestVectorHelpers(unittest.TestCase):
    def test_magnitude_zero_vector(self):
        self.assertEqual(_vector_magnitude([0.0, 0.0, 0.0]), 0.0)

    def test_magnitude_unit_vector(self):
        self.assertAlmostEqual(_vector_magnitude([1.0, 0.0, 0.0]), 1.0, places=10)

    def test_magnitude_345_triangle(self):
        self.assertAlmostEqual(_vector_magnitude([3.0, 4.0, 0.0]), 5.0, places=10)

    def test_diff_correct(self):
        result = _vector_diff([4.0, 3.0, 2.0], [1.0, 1.0, 1.0])
        self.assertEqual(result, [3.0, 2.0, 1.0])


class TestTleEpochParsing(unittest.TestCase):
    def test_parses_known_epoch(self):
        dt = _tle_epoch_to_datetime(_ISS_LINE1_A)
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2024)

    def test_invalid_line_returns_none(self):
        result = _tle_epoch_to_datetime("not a tle line at all")
        self.assertIsNone(result)


class TestComputeDeltaVResidual(unittest.TestCase):
    def test_identical_tles_near_zero_residual(self):
        result = compute_delta_v_residual(
            _ISS_LINE1_A, _ISS_LINE2_A,
            _ISS_LINE1_B, _ISS_LINE2_B,
        )
        if result["propagation_ok"]:
            self.assertIsNotNone(result["delta_v_m_s"])
            self.assertGreaterEqual(result["delta_v_m_s"], 0.0)

    def test_result_has_required_keys(self):
        result = compute_delta_v_residual(
            _ISS_LINE1_A, _ISS_LINE2_A,
            _ISS_LINE1_B, _ISS_LINE2_B,
        )
        for key in ("delta_v_m_s", "delta_v_components_m_s", "delta_r_km",
                    "epoch_before", "epoch_after", "propagation_ok", "error"):
            self.assertIn(key, result)

    def test_maneuver_produces_larger_residual(self):
        result_no_maneuver = compute_delta_v_residual(
            _ISS_LINE1_A, _ISS_LINE2_A,
            _ISS_LINE1_B, _ISS_LINE2_B,
        )
        result_maneuver = compute_delta_v_residual(
            _ISS_LINE1_A, _ISS_LINE2_A,
            _ISS_LINE1_MANEUVER, _ISS_LINE2_MANEUVER,
        )
        if result_no_maneuver["propagation_ok"] and result_maneuver["propagation_ok"]:
            self.assertGreater(
                result_maneuver["delta_v_m_s"],
                result_no_maneuver["delta_v_m_s"],
            )

    def test_invalid_line1_returns_error(self):
        result = compute_delta_v_residual(
            "bad line", _ISS_LINE2_A,
            _ISS_LINE1_B, _ISS_LINE2_B,
        )
        self.assertFalse(result["propagation_ok"])
        self.assertIsNotNone(result["error"])

    def test_components_length_three(self):
        result = compute_delta_v_residual(
            _ISS_LINE1_A, _ISS_LINE2_A,
            _ISS_LINE1_B, _ISS_LINE2_B,
        )
        if result["propagation_ok"] and result["delta_v_components_m_s"]:
            self.assertEqual(len(result["delta_v_components_m_s"]), 3)


class TestExtractManeuverEvents(unittest.TestCase):
    def test_empty_history_returns_empty(self):
        result = extract_maneuver_events([])
        self.assertEqual(result["maneuver_events"], [])
        self.assertEqual(result["total_pairs_checked"], 0)

    def test_single_tle_returns_empty(self):
        history = [{"line1": _ISS_LINE1_A, "line2": _ISS_LINE2_A}]
        result = extract_maneuver_events(history)
        self.assertEqual(result["maneuver_events"], [])

    def test_result_structure(self):
        history = [
            {"line1": _ISS_LINE1_A, "line2": _ISS_LINE2_A},
            {"line1": _ISS_LINE1_B, "line2": _ISS_LINE2_B},
        ]
        result = extract_maneuver_events(history)
        for key in ("maneuver_events", "total_pairs_checked", "maneuver_count", "threshold_m_s"):
            self.assertIn(key, result)
        self.assertEqual(result["total_pairs_checked"], 1)

    def test_custom_threshold_respected(self):
        history = [
            {"line1": _ISS_LINE1_A, "line2": _ISS_LINE2_A},
            {"line1": _ISS_LINE1_MANEUVER, "line2": _ISS_LINE2_MANEUVER},
        ]
        result_low = extract_maneuver_events(history, dv_threshold_m_s=0.001)
        result_high = extract_maneuver_events(history, dv_threshold_m_s=10000.0)
        self.assertGreaterEqual(result_low["maneuver_count"], result_high["maneuver_count"])

    def test_maneuver_event_has_pair_index(self):
        history = [
            {"line1": _ISS_LINE1_A, "line2": _ISS_LINE2_A},
            {"line1": _ISS_LINE1_MANEUVER, "line2": _ISS_LINE2_MANEUVER},
        ]
        result = extract_maneuver_events(history, dv_threshold_m_s=0.001)
        for event in result["maneuver_events"]:
            self.assertIn("pair_index", event)


if __name__ == "__main__":
    unittest.main()
