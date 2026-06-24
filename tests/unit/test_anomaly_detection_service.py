import unittest
from datetime import datetime, timezone, timedelta
from api.services.anomaly_detection_service import (
    detect_attitude_anomalies,
    detect_spin_rate_anomalies,
    score_anomaly_severity,
    _cusum_changepoints,
)


def _make_timestamps(n: int, start: datetime = None) -> list:
    if start is None:
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [start + timedelta(minutes=i) for i in range(n)]


class TestCusumChangepoints(unittest.TestCase):
    def test_flat_series_no_changepoints(self):
        values = [1.0] * 50
        cps = _cusum_changepoints(values, threshold=5.0)
        self.assertEqual(cps, [])

    def test_step_change_detected(self):
        values = [0.0] * 25 + [10.0] * 25
        cps = _cusum_changepoints(values, threshold=3.0, drift=0.0)
        self.assertTrue(len(cps) > 0)

    def test_single_point_series(self):
        cps = _cusum_changepoints([5.0], threshold=3.0)
        self.assertEqual(cps, [])

    def test_empty_series(self):
        cps = _cusum_changepoints([], threshold=3.0)
        self.assertEqual(cps, [])


class TestDetectAttitudeAnomalies(unittest.TestCase):
    def test_stable_series_returns_no_changepoints(self):
        ts = _make_timestamps(50)
        values = [0.5] * 50
        result = detect_attitude_anomalies(ts, values, cusum_threshold=5.0)
        self.assertEqual(result["change_points"], [])
        self.assertEqual(result["series_stats"]["n"], 50)

    def test_step_change_detected(self):
        ts = _make_timestamps(50)
        values = [0.0] * 25 + [20.0] * 25
        result = detect_attitude_anomalies(ts, values, cusum_threshold=3.0, cusum_drift=0.0)
        self.assertTrue(len(result["change_points"]) > 0)

    def test_changepoint_has_required_keys(self):
        ts = _make_timestamps(50)
        values = [0.0] * 25 + [20.0] * 25
        result = detect_attitude_anomalies(ts, values, cusum_threshold=3.0, cusum_drift=0.0)
        if result["change_points"]:
            cp = result["change_points"][0]
            for key in ("index", "timestamp", "value", "magnitude_sigma"):
                self.assertIn(key, cp)

    def test_length_mismatch_raises(self):
        ts = _make_timestamps(10)
        values = [1.0] * 5
        with self.assertRaises(ValueError):
            detect_attitude_anomalies(ts, values)

    def test_empty_series_returns_empty_result(self):
        result = detect_attitude_anomalies([], [])
        self.assertEqual(result["change_points"], [])
        self.assertEqual(result["series_stats"]["n"], 0)

    def test_stats_are_correct(self):
        ts = _make_timestamps(4)
        values = [1.0, 2.0, 3.0, 4.0]
        result = detect_attitude_anomalies(ts, values, cusum_threshold=100.0)
        self.assertAlmostEqual(result["series_stats"]["mean"], 2.5, delta=0.01)
        self.assertEqual(result["series_stats"]["min"], 1.0)
        self.assertEqual(result["series_stats"]["max"], 4.0)

    def test_threshold_and_drift_stored(self):
        ts = _make_timestamps(10)
        values = [1.0] * 10
        result = detect_attitude_anomalies(ts, values, cusum_threshold=7.0, cusum_drift=1.5)
        self.assertEqual(result["threshold_used"], 7.0)
        self.assertEqual(result["drift_used"], 1.5)


class TestDetectSpinRateAnomalies(unittest.TestCase):
    def test_nominal_spin_no_anomaly(self):
        ts = _make_timestamps(40)
        spins = [3.0] * 40
        result = detect_spin_rate_anomalies(ts, spins, cusum_threshold=5.0)
        self.assertEqual(result["change_points"], [])

    def test_spin_excursion_detected(self):
        ts = _make_timestamps(50)
        spins = [3.0] * 25 + [30.0] * 25
        result = detect_spin_rate_anomalies(ts, spins, cusum_threshold=3.0, cusum_drift=0.0)
        self.assertTrue(len(result["change_points"]) > 0)

    def test_expected_spin_rate_stored(self):
        ts = _make_timestamps(10)
        spins = [5.0] * 10
        result = detect_spin_rate_anomalies(ts, spins, expected_spin_rate_rpm=5.0)
        self.assertEqual(result["expected_spin_rate_rpm"], 5.0)

    def test_length_mismatch_raises(self):
        ts = _make_timestamps(5)
        spins = [1.0] * 10
        with self.assertRaises(ValueError):
            detect_spin_rate_anomalies(ts, spins)


class TestScoreAnomalySeverity(unittest.TestCase):
    def test_empty_changepoints_none(self):
        self.assertEqual(score_anomaly_severity([]), "none")

    def test_single_low_magnitude(self):
        cps = [{"magnitude_sigma": 3.0}]
        self.assertEqual(score_anomaly_severity(cps), "low")

    def test_single_medium_magnitude(self):
        cps = [{"magnitude_sigma": 6.0}]
        self.assertEqual(score_anomaly_severity(cps), "medium")

    def test_single_high_magnitude(self):
        cps = [{"magnitude_sigma": 9.0}]
        self.assertEqual(score_anomaly_severity(cps), "high")

    def test_many_changepoints_high(self):
        cps = [{"magnitude_sigma": 2.0}] * 6
        self.assertEqual(score_anomaly_severity(cps), "high")

    def test_three_medium_severity(self):
        cps = [{"magnitude_sigma": 3.0}] * 3
        self.assertEqual(score_anomaly_severity(cps), "medium")


if __name__ == "__main__":
    unittest.main()
