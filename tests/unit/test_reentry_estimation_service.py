import unittest
from datetime import datetime, timezone, timedelta
from api.services.reentry_estimation_service import (
    estimate_reentry,
    extract_perigee_series_from_tle_history,
    _linear_regression,
    _exp_regression,
    _days_to_reentry_linear,
    _days_to_reentry_exp,
)


_BASE_DATE = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _make_decay_epochs(n: int, start: datetime = None) -> list:
    if start is None:
        start = _BASE_DATE
    return [start + timedelta(days=i) for i in range(n)]


class TestLinearRegression(unittest.TestCase):
    def test_perfect_line(self):
        xs = [0.0, 1.0, 2.0, 3.0]
        ys = [10.0, 8.0, 6.0, 4.0]
        slope, intercept, r2 = _linear_regression(xs, ys)
        self.assertAlmostEqual(slope, -2.0, delta=1e-9)
        self.assertAlmostEqual(intercept, 10.0, delta=1e-9)
        self.assertAlmostEqual(r2, 1.0, delta=1e-9)

    def test_single_point_raises(self):
        with self.assertRaises(ValueError):
            _linear_regression([1.0], [1.0])

    def test_flat_line(self):
        xs = [0.0, 1.0, 2.0]
        ys = [5.0, 5.0, 5.0]
        slope, intercept, r2 = _linear_regression(xs, ys)
        self.assertAlmostEqual(slope, 0.0, delta=1e-9)
        self.assertAlmostEqual(intercept, 5.0, delta=1e-9)

    def test_identical_xs_raises(self):
        with self.assertRaises(ValueError):
            _linear_regression([1.0, 1.0, 1.0], [1.0, 2.0, 3.0])


class TestExpRegression(unittest.TestCase):
    def test_perfect_exponential(self):
        import math
        xs = [0.0, 1.0, 2.0, 3.0]
        a_true, b_true = 500.0, -0.05
        ys = [a_true * math.exp(b_true * x) for x in xs]
        a, b, r2 = _exp_regression(xs, ys)
        self.assertAlmostEqual(a, a_true, delta=0.01)
        self.assertAlmostEqual(b, b_true, delta=1e-6)
        self.assertAlmostEqual(r2, 1.0, delta=1e-6)

    def test_negative_values_raise(self):
        with self.assertRaises(ValueError):
            _exp_regression([0.0, 1.0], [-1.0, 2.0])


class TestDaysToReentry(unittest.TestCase):
    def test_linear_positive_slope_returns_none(self):
        self.assertIsNone(_days_to_reentry_linear(1.0, 100.0, 80.0, 0.0))

    def test_linear_correct_days(self):
        days = _days_to_reentry_linear(-2.0, 500.0, 80.0, 0.0)
        self.assertAlmostEqual(days, 210.0, delta=0.01)

    def test_exp_positive_b_returns_none(self):
        self.assertIsNone(_days_to_reentry_exp(500.0, 0.01, 80.0, 0.0))

    def test_exp_correct_days(self):
        import math
        a, b = 500.0, -0.01
        target = 80.0
        expected = math.log(target / a) / b
        days = _days_to_reentry_exp(a, b, target, 0.0)
        self.assertAlmostEqual(days, expected, delta=0.01)


class TestEstimateReentry(unittest.TestCase):
    def _linear_decay_series(self, n: int = 20, start_km: float = 400.0,
                              rate: float = 5.0) -> tuple:
        epochs = _make_decay_epochs(n)
        altitudes = [max(0.1, start_km - i * rate) for i in range(n)]
        return epochs, altitudes

    def test_insufficient_data_returns_error(self):
        epochs = _make_decay_epochs(2)
        alts = [400.0, 395.0]
        result = estimate_reentry(epochs, alts)
        self.assertIsNone(result["predicted_reentry_date"])
        self.assertIn("error", result)

    def test_returns_required_keys(self):
        epochs, alts = self._linear_decay_series()
        result = estimate_reentry(epochs, alts)
        for key in ("predicted_reentry_date", "window_earliest", "window_latest",
                    "model_selected", "linear_model", "n_points", "reentry_altitude_km"):
            self.assertIn(key, result)

    def test_predicts_future_date_for_decaying_orbit(self):
        epochs, alts = self._linear_decay_series(n=30, start_km=400.0, rate=5.0)
        result = estimate_reentry(epochs, alts, reentry_altitude_km=80.0)
        self.assertIsNotNone(result["predicted_reentry_date"])

    def test_window_bounds_consistent(self):
        epochs, alts = self._linear_decay_series(n=30, start_km=400.0, rate=5.0)
        result = estimate_reentry(epochs, alts, confidence_days=14.0)
        if result["predicted_reentry_date"]:
            from datetime import date
            pred = date.fromisoformat(result["predicted_reentry_date"])
            earliest = date.fromisoformat(result["window_earliest"])
            latest = date.fromisoformat(result["window_latest"])
            self.assertLessEqual(earliest, pred)
            self.assertGreaterEqual(latest, pred)

    def test_n_points_matches_input(self):
        epochs, alts = self._linear_decay_series(n=15)
        result = estimate_reentry(epochs, alts)
        self.assertEqual(result["n_points"], 15)

    def test_linear_model_structure(self):
        epochs, alts = self._linear_decay_series()
        result = estimate_reentry(epochs, alts)
        lm = result["linear_model"]
        self.assertIn("slope", lm)
        self.assertIn("intercept", lm)
        self.assertIn("r_squared", lm)

    def test_length_mismatch_raises(self):
        epochs = _make_decay_epochs(5)
        alts = [400.0] * 3
        with self.assertRaises(ValueError):
            estimate_reentry(epochs, alts)

    def test_stable_orbit_no_reentry(self):
        epochs = _make_decay_epochs(20)
        alts = [500.0] * 20
        result = estimate_reentry(epochs, alts)
        self.assertIsNone(result["predicted_reentry_date"])


class TestExtractPerigeeSeries(unittest.TestCase):
    _LINE1 = "1 25544U 98067A   24038.54586899  .00012769  00000+0  22680-3 0  9996"
    _LINE2 = "2 25544  51.6406 302.7583 0001012  95.3523  23.3829 15.50234806439337"

    def test_extracts_series_from_tle_records(self):
        history = [
            {"line1": self._LINE1, "line2": self._LINE2},
            {"line1": self._LINE1.replace("24038", "24039"), "line2": self._LINE2},
        ]
        epochs, perigees = extract_perigee_series_from_tle_history(history)
        self.assertEqual(len(epochs), len(perigees))
        self.assertGreater(len(epochs), 0)
        for p in perigees:
            self.assertGreater(p, 0)

    def test_precomputed_perigee_used(self):
        history = [
            {"line1": self._LINE1, "line2": self._LINE2, "perigee_km": 412.5},
        ]
        _, perigees = extract_perigee_series_from_tle_history(history)
        self.assertAlmostEqual(perigees[0], 412.5, delta=0.01)

    def test_sorted_oldest_first(self):
        history = [
            {"line1": self._LINE1.replace("24038", "24040"), "line2": self._LINE2},
            {"line1": self._LINE1.replace("24038", "24039"), "line2": self._LINE2},
            {"line1": self._LINE1, "line2": self._LINE2},
        ]
        epochs, _ = extract_perigee_series_from_tle_history(history)
        for i in range(len(epochs) - 1):
            self.assertLessEqual(epochs[i], epochs[i + 1])


if __name__ == "__main__":
    unittest.main()
