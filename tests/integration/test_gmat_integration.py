"""
Integration tests that invoke real GmatConsole.

Run only when GMAT_HOME is set and the binary exists.
These are skipped automatically in CI unless the integration job runs.
"""
import os
import unittest

import pytest

from api.services.gmat_service import (
    GmatError,
    check_data_files,
    find_egm96,
    is_available,
    propagate_hifi,
    run_smoke_test,
)

GMAT_AVAILABLE = is_available()
EGM96_AVAILABLE = find_egm96() is not None

requires_gmat = pytest.mark.skipif(
    not GMAT_AVAILABLE,
    reason="GmatConsole binary not found — skipping integration tests",
)
requires_egm96 = pytest.mark.skipif(
    not EGM96_AVAILABLE,
    reason="EGM96.cof not found — skipping ephemeris integration tests",
)

ISS_LINE1 = "1 25544U 98067A   24038.54586899  .00012769  00000+0  22680-3 0  9996"
ISS_LINE2 = "2 25544  51.6406 302.7583 0001012  95.3523  23.3829 15.50234806439337"

GEO_LINE1 = "1 43226U 18017A   24038.50000000  .00000000  00000+0  00000-0 0  9991"
GEO_LINE2 = "2 43226   0.0120  95.6200 0001000  10.0000 350.0000  1.00273791 22000"


@requires_gmat
class TestSmoke(unittest.TestCase):
    def test_smoke_passes(self):
        result = run_smoke_test()
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("ok"), f"Smoke test failed: {result}")
        self.assertIn("elapsed_ms", result)

    def test_check_data_files_empty(self):
        missing = check_data_files()
        self.assertEqual(missing, [], f"Missing data files: {missing}")


@requires_gmat
@requires_egm96
class TestPropagateHifi(unittest.TestCase):
    def _assert_envelope(self, result: dict, min_points: int = 10):
        self.assertIn("ephemeris_points", result)
        self.assertIn("num_points", result)
        self.assertIn("tle_epoch", result)
        self.assertIn("valid_from", result)
        self.assertIn("valid_until", result)
        self.assertIn("propagator", result)
        self.assertEqual(result["propagator"], "GMAT_RK89_EGM96")

        points = result["ephemeris_points"]
        self.assertGreaterEqual(len(points), min_points, "Too few ephemeris points")

        p0 = points[0]
        self.assertIn("timestamp", p0)
        self.assertIn("eci", p0)
        self.assertIn("geodetic", p0)

        eci = p0["eci"]
        self.assertIn("x_km", eci)
        self.assertIn("y_km", eci)
        self.assertIn("z_km", eci)

        radius = (eci["x_km"]**2 + eci["y_km"]**2 + eci["z_km"]**2) ** 0.5
        self.assertGreater(radius, 6378.0, "ECI radius below Earth surface")
        self.assertLess(radius, 50000.0, "ECI radius implausibly large")

        geo = p0["geodetic"]
        self.assertGreaterEqual(geo["altitude_km"], 0.0, "Negative altitude")
        self.assertGreaterEqual(geo["latitude"], -90.0)
        self.assertLessEqual(geo["latitude"], 90.0)
        self.assertGreaterEqual(geo["longitude"], -180.0)
        self.assertLessEqual(geo["longitude"], 360.0)

    def test_iss_1hour(self):
        result = propagate_hifi(ISS_LINE1, ISS_LINE2, duration_hours=1.0, step_seconds=60)
        self._assert_envelope(result, min_points=55)

    def test_iss_6hours(self):
        result = propagate_hifi(ISS_LINE1, ISS_LINE2, duration_hours=6.0, step_seconds=300)
        self._assert_envelope(result, min_points=70)

    def test_geo_1hour(self):
        result = propagate_hifi(GEO_LINE1, GEO_LINE2, duration_hours=1.0, step_seconds=60)
        self._assert_envelope(result, min_points=55)

        p0 = result["ephemeris_points"][0]
        alt = p0["geodetic"]["altitude_km"]
        self.assertGreater(alt, 30000.0, f"GEO altitude too low: {alt}")

    def test_points_are_monotonically_increasing_in_time(self):
        result = propagate_hifi(ISS_LINE1, ISS_LINE2, duration_hours=1.0, step_seconds=60)
        timestamps = [p["timestamp"] for p in result["ephemeris_points"]]
        self.assertEqual(timestamps, sorted(timestamps), "Timestamps are not monotonically increasing")

    def test_bad_tle_raises(self):
        with self.assertRaises(GmatError):
            propagate_hifi("garbage line 1", "garbage line 2", duration_hours=1.0)


if __name__ == "__main__":
    unittest.main()
