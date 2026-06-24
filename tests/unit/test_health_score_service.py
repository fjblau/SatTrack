import unittest
from datetime import datetime, timezone, timedelta
from api.services.health_score_service import (
    calculate_health_score,
    bulk_calculate_health_scores,
    _score_tle_age,
    _score_eccentricity,
    _score_perigee_altitude,
    _score_bstar_drag,
    _score_anomaly_count,
    _score_maneuver_recency,
    FACTOR_WEIGHTS,
)


_NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


class TestScoreTleAge(unittest.TestCase):
    def test_fresh_tle_scores_one(self):
        epoch = _NOW - timedelta(hours=1)
        self.assertGreater(_score_tle_age(epoch, _NOW), 0.99)

    def test_stale_tle_scores_zero(self):
        epoch = _NOW - timedelta(days=31)
        self.assertEqual(_score_tle_age(epoch, _NOW), 0.0)

    def test_half_age_scores_half(self):
        epoch = _NOW - timedelta(days=15)
        score = _score_tle_age(epoch, _NOW)
        self.assertAlmostEqual(score, 0.5, delta=0.01)

    def test_future_epoch_scores_one(self):
        epoch = _NOW + timedelta(days=1)
        self.assertEqual(_score_tle_age(epoch, _NOW), 1.0)


class TestScoreEccentricity(unittest.TestCase):
    def test_circular_orbit_scores_one(self):
        self.assertEqual(_score_eccentricity(0.0), 1.0)
        self.assertEqual(_score_eccentricity(0.001), 1.0)

    def test_high_eccentricity_scores_zero(self):
        self.assertEqual(_score_eccentricity(0.3), 0.0)
        self.assertEqual(_score_eccentricity(0.99), 0.0)

    def test_intermediate_eccentricity(self):
        score = _score_eccentricity(0.155)
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)

    def test_invalid_eccentricity(self):
        self.assertEqual(_score_eccentricity(-0.1), 0.0)
        self.assertEqual(_score_eccentricity(1.0), 0.0)


class TestScorePerigeAltitude(unittest.TestCase):
    def test_nominal_altitude_scores_one(self):
        self.assertEqual(_score_perigee_altitude(500.0), 1.0)

    def test_critical_altitude_scores_zero(self):
        self.assertEqual(_score_perigee_altitude(200.0), 0.0)
        self.assertEqual(_score_perigee_altitude(100.0), 0.0)

    def test_midpoint(self):
        score = _score_perigee_altitude(300.0)
        self.assertAlmostEqual(score, 0.5, delta=0.01)


class TestScoreBstar(unittest.TestCase):
    def test_zero_drag_scores_one(self):
        self.assertEqual(_score_bstar_drag(0.0), 1.0)

    def test_nominal_drag_scores_one(self):
        self.assertEqual(_score_bstar_drag(1e-5), 1.0)

    def test_very_high_drag_scores_low(self):
        score = _score_bstar_drag(1e-2)
        self.assertLessEqual(score, 0.01)

    def test_negative_bstar(self):
        score = _score_bstar_drag(-1e-3)
        self.assertGreater(score, 0.0)
        self.assertLessEqual(score, 1.0)


class TestScoreAnomalyCount(unittest.TestCase):
    def test_no_anomalies_scores_one(self):
        self.assertEqual(_score_anomaly_count(0), 1.0)

    def test_ten_anomalies_scores_zero(self):
        self.assertEqual(_score_anomaly_count(10), 0.0)

    def test_five_anomalies_scores_half(self):
        self.assertAlmostEqual(_score_anomaly_count(5), 0.5, delta=0.01)


class TestScoreManeuverRecency(unittest.TestCase):
    def test_recent_maneuver_scores_one(self):
        last = _NOW - timedelta(days=3)
        self.assertEqual(_score_maneuver_recency(last, _NOW), 1.0)

    def test_no_maneuver_scores_half(self):
        self.assertEqual(_score_maneuver_recency(None, _NOW), 0.5)

    def test_old_maneuver_scores_zero(self):
        last = _NOW - timedelta(days=91)
        self.assertEqual(_score_maneuver_recency(last, _NOW), 0.0)


class TestCalculateHealthScore(unittest.TestCase):
    def _nominal_params(self):
        return dict(
            tle_epoch=_NOW - timedelta(hours=12),
            eccentricity=0.001,
            perigee_km=450.0,
            bstar=1e-5,
            anomaly_count=0,
            last_maneuver_date=_NOW - timedelta(days=3),
            reference_time=_NOW,
        )

    def test_returns_required_keys(self):
        result = calculate_health_score(**self._nominal_params())
        self.assertIn("health_score", result)
        self.assertIn("factors", result)
        self.assertIn("computed_at", result)

    def test_high_health_for_nominal_satellite(self):
        result = calculate_health_score(**self._nominal_params())
        self.assertGreater(result["health_score"], 80.0)

    def test_low_health_for_degraded_satellite(self):
        result = calculate_health_score(
            tle_epoch=_NOW - timedelta(days=28),
            eccentricity=0.25,
            perigee_km=210.0,
            bstar=5e-3,
            anomaly_count=8,
            last_maneuver_date=_NOW - timedelta(days=89),
            reference_time=_NOW,
        )
        self.assertLess(result["health_score"], 30.0)

    def test_score_is_between_0_and_100(self):
        result = calculate_health_score(**self._nominal_params())
        self.assertGreaterEqual(result["health_score"], 0.0)
        self.assertLessEqual(result["health_score"], 100.0)

    def test_factors_match_weights_keys(self):
        result = calculate_health_score(**self._nominal_params())
        self.assertEqual(set(result["factors"].keys()), set(FACTOR_WEIGHTS.keys()))

    def test_factor_contributions_sum_to_health_score(self):
        result = calculate_health_score(**self._nominal_params())
        total_contribution = sum(f["contribution"] for f in result["factors"].values())
        self.assertAlmostEqual(total_contribution, result["health_score"], delta=0.5)

    def test_naive_datetime_accepted(self):
        epoch_naive = datetime(2024, 5, 31, 0, 0, 0)
        result = calculate_health_score(
            tle_epoch=epoch_naive,
            eccentricity=0.001,
            perigee_km=450.0,
            bstar=1e-5,
            reference_time=_NOW,
        )
        self.assertIn("health_score", result)


class TestBulkCalculateHealthScores(unittest.TestCase):
    def test_bulk_returns_list(self):
        objects = [
            {
                "norad_id": "25544",
                "tle_epoch": _NOW - timedelta(hours=6),
                "eccentricity": 0.001,
                "perigee_km": 410.0,
                "bstar": 2e-4,
            },
            {
                "norad_id": "00005",
                "tle_epoch": _NOW - timedelta(days=5),
                "eccentricity": 0.01,
                "perigee_km": 380.0,
                "bstar": 1e-4,
            },
        ]
        results = bulk_calculate_health_scores(objects, reference_time=_NOW)
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertIn("health_score", r)
            self.assertIn("norad_id", r)


if __name__ == "__main__":
    unittest.main()
