import math
import os
import textwrap
import unittest
from unittest.mock import MagicMock, patch

from api.services.gmat_service import (
    GmatError,
    _mean_to_true_anomaly,
    _tle_epoch_to_utc_gregorian,
    _tle_to_keplerian,
    _parse_report,
    is_available,
    propagate_hifi,
)


ISS_LINE1 = "1 25544U 98067A   24038.54586899  .00012769  00000+0  22680-3 0  9996"
ISS_LINE2 = "2 25544  51.6406 302.7583 0001012  95.3523  23.3829 15.50234806439337"

GEO_LINE1 = "1 43226U 18017A   24038.50000000  .00000000  00000+0  00000-0 0  9991"
GEO_LINE2 = "2 43226   0.0500 100.0000 0001000  10.0000 350.0000  1.00269670 21234"


class TestMeanToTrueAnomaly(unittest.TestCase):
    def test_zero_eccentricity(self):
        self.assertAlmostEqual(_mean_to_true_anomaly(0.0, 0.0), 0.0, places=5)
        self.assertAlmostEqual(_mean_to_true_anomaly(90.0, 0.0), 90.0, places=5)
        self.assertAlmostEqual(_mean_to_true_anomaly(180.0, 0.0), 180.0, places=5)

    def test_circular_orbit_identity(self):
        for M in range(0, 360, 45):
            ta = _mean_to_true_anomaly(float(M), 0.0)
            self.assertAlmostEqual(ta % 360, M % 360, places=4)

    def test_eccentric_orbit_periapsis(self):
        ta = _mean_to_true_anomaly(0.0, 0.5)
        self.assertAlmostEqual(ta, 0.0, places=5)

    def test_eccentric_orbit_apoapsis(self):
        ta = _mean_to_true_anomaly(180.0, 0.5)
        self.assertAlmostEqual(ta, 180.0, places=5)

    def test_output_range(self):
        for M in range(0, 360, 10):
            ta = _mean_to_true_anomaly(float(M), 0.3)
            self.assertGreaterEqual(ta, 0.0)
            self.assertLess(ta, 360.0)


class TestTleEpochToUtcGregorian(unittest.TestCase):
    def test_iss_epoch_format(self):
        result = _tle_epoch_to_utc_gregorian(ISS_LINE1)
        self.assertIsInstance(result, str)
        self.assertIn("2024", result)
        self.assertIn("Feb", result)

    def test_contains_time_component(self):
        result = _tle_epoch_to_utc_gregorian(ISS_LINE1)
        parts = result.split()
        self.assertEqual(len(parts), 4)

    def test_two_digit_year_2000s(self):
        result = _tle_epoch_to_utc_gregorian(ISS_LINE1)
        self.assertIn("2024", result)

    def test_two_digit_year_1900s(self):
        line1_1999 = "1 25544U 98067A   99038.54586899  .00012769  00000+0  22680-3 0  9996"
        result = _tle_epoch_to_utc_gregorian(line1_1999)
        self.assertIn("1999", result)


class TestTleToKeplerian(unittest.TestCase):
    def test_iss_sma_range(self):
        kep = _tle_to_keplerian(ISS_LINE1, ISS_LINE2)
        self.assertAlmostEqual(kep["sma_km"], 6790, delta=50)

    def test_iss_inclination(self):
        kep = _tle_to_keplerian(ISS_LINE1, ISS_LINE2)
        self.assertAlmostEqual(kep["inc_deg"], 51.64, delta=0.1)

    def test_iss_eccentricity(self):
        kep = _tle_to_keplerian(ISS_LINE1, ISS_LINE2)
        self.assertAlmostEqual(kep["ecc"], 0.0001012, delta=1e-6)

    def test_iss_raan(self):
        kep = _tle_to_keplerian(ISS_LINE1, ISS_LINE2)
        self.assertAlmostEqual(kep["raan_deg"], 302.7583, delta=0.01)

    def test_iss_aop(self):
        kep = _tle_to_keplerian(ISS_LINE1, ISS_LINE2)
        self.assertAlmostEqual(kep["aop_deg"], 95.3523, delta=0.01)

    def test_ta_in_valid_range(self):
        kep = _tle_to_keplerian(ISS_LINE1, ISS_LINE2)
        self.assertGreaterEqual(kep["ta_deg"], 0.0)
        self.assertLess(kep["ta_deg"], 360.0)

    def test_geo_sma_range(self):
        kep = _tle_to_keplerian(GEO_LINE1, GEO_LINE2)
        self.assertAlmostEqual(kep["sma_km"], 42164, delta=200)

    def test_all_keys_present(self):
        kep = _tle_to_keplerian(ISS_LINE1, ISS_LINE2)
        for key in ("sma_km", "ecc", "inc_deg", "raan_deg", "aop_deg", "ta_deg"):
            self.assertIn(key, kep)


class TestParseReport(unittest.TestCase):
    def _write_report(self, tmpdir, content):
        path = os.path.join(tmpdir, "report.txt")
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_parses_valid_report(self):
        import tempfile
        sample = textwrap.dedent("""\
            Sat.UTCGregorian                   Sat.Latitude   Sat.Longitude   Sat.Altitude   Sat.X          Sat.Y          Sat.Z
            07 Feb 2024 13:06:00.000           51.234567      102.345678      408.12         -3456.789      5678.901       3456.789
            07 Feb 2024 13:07:00.000           50.111222      104.222333      408.55         -3400.000      5700.000       3400.000
        """)
        with tempfile.TemporaryDirectory() as d:
            path = self._write_report(d, sample)
            points = _parse_report(path, step_seconds=60)
        self.assertEqual(len(points), 2)
        self.assertAlmostEqual(points[0]["geodetic"]["latitude"], 51.234567, places=4)
        self.assertAlmostEqual(points[0]["geodetic"]["longitude"], 102.345678, places=4)
        self.assertAlmostEqual(points[0]["geodetic"]["altitude_km"], 408.12, places=1)
        self.assertAlmostEqual(points[0]["eci"]["x_km"], -3456.789, places=2)

    def test_missing_file_raises(self):
        with self.assertRaises(GmatError):
            _parse_report("/nonexistent/path/report.txt", step_seconds=60)

    def test_empty_file_raises(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = self._write_report(d, "Sat.UTCGregorian  Sat.Latitude\n")
            with self.assertRaises(GmatError):
                _parse_report(path, step_seconds=60)

    def test_timestamp_is_iso_format(self):
        import tempfile
        sample = textwrap.dedent("""\
            Sat.UTCGregorian                   Sat.Latitude   Sat.Longitude   Sat.Altitude   Sat.X   Sat.Y   Sat.Z
            07 Feb 2024 13:06:00.000           10.0           20.0            400.0          100.0   200.0   300.0
        """)
        with tempfile.TemporaryDirectory() as d:
            path = self._write_report(d, sample)
            points = _parse_report(path, step_seconds=60)
        self.assertIn("T", points[0]["timestamp"])
        self.assertIn("+00:00", points[0]["timestamp"])


class TestIsAvailable(unittest.TestCase):
    def test_returns_bool(self):
        result = is_available()
        self.assertIsInstance(result, bool)

    @patch("api.services.gmat_service._find_binary", return_value="/opt/gmat/bin/GmatConsole-R2022a")
    @patch("os.path.isfile", return_value=True)
    @patch("os.access", return_value=True)
    def test_available_when_binary_found(self, _access, _isfile, _find):
        self.assertTrue(is_available())

    @patch("api.services.gmat_service._find_binary", return_value=None)
    def test_unavailable_when_no_binary(self, _find):
        self.assertFalse(is_available())


class TestPropagateHifi(unittest.TestCase):
    def test_raises_when_gmat_unavailable(self):
        with patch("api.services.gmat_service._find_binary", return_value=None):
            with self.assertRaises(GmatError) as ctx:
                propagate_hifi(ISS_LINE1, ISS_LINE2)
            self.assertIn("not found", str(ctx.exception))

    def test_raises_on_gmat_timeout(self):
        import subprocess
        with patch("api.services.gmat_service._find_binary", return_value="/fake/GmatConsole"):
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="GMAT", timeout=180)):
                with self.assertRaises(GmatError) as ctx:
                    propagate_hifi(ISS_LINE1, ISS_LINE2)
                self.assertIn("timed out", str(ctx.exception))

    def test_raises_on_nonzero_exit(self):
        fake_result = MagicMock()
        fake_result.returncode = 1
        fake_result.stderr = "GMAT script error: unknown parameter"
        with patch("api.services.gmat_service._find_binary", return_value="/fake/GmatConsole"):
            with patch("subprocess.run", return_value=fake_result):
                with self.assertRaises(GmatError) as ctx:
                    propagate_hifi(ISS_LINE1, ISS_LINE2)
                self.assertIn("exited with code 1", str(ctx.exception))

    def _make_fake_run(self, sample_report: str):
        from pathlib import Path as P

        fake_result = MagicMock()
        fake_result.returncode = 0
        fake_result.stderr = ""

        def fake_run(cmd, *args, **kwargs):
            script_path = cmd[1] if len(cmd) > 1 else ""
            if script_path and os.path.exists(script_path):
                script_text = P(script_path).read_text()
                for line in script_text.splitlines():
                    if "Filename" in line and "=" in line:
                        report_path = line.split("=", 1)[-1].strip().rstrip(";").strip().strip("'\"")
                        parent = os.path.dirname(report_path)
                        if parent and os.path.isdir(parent):
                            with open(report_path, "w") as f:
                                f.write(sample_report)
                        break
            return fake_result

        return fake_run

    def test_returns_correct_schema_on_success(self):
        sample_report = textwrap.dedent("""\
            Sat.UTCGregorian                   Sat.Latitude   Sat.Longitude   Sat.Altitude   Sat.X      Sat.Y      Sat.Z
            07 Feb 2024 13:06:00.000           51.0           100.0           408.0          -3400.0    5600.0     3400.0
            07 Feb 2024 13:07:00.000           50.5           102.0           408.5          -3350.0    5620.0     3350.0
        """)
        with patch("api.services.gmat_service._find_binary", return_value="/fake/GmatConsole"):
            with patch("subprocess.run", side_effect=self._make_fake_run(sample_report)):
                result = propagate_hifi(ISS_LINE1, ISS_LINE2, duration_hours=1, step_seconds=60)

        self.assertIn("ephemeris_points", result)
        self.assertIn("num_points", result)
        self.assertIn("valid_from", result)
        self.assertIn("valid_until", result)
        self.assertIn("keplerian_elements", result)
        self.assertEqual(result["propagator"], "GMAT_RK89_EGM96")
        self.assertGreater(result["num_points"], 0)

    def test_keplerian_elements_in_result(self):
        sample_report = textwrap.dedent("""\
            Sat.UTCGregorian                   Sat.Latitude   Sat.Longitude   Sat.Altitude   Sat.X   Sat.Y   Sat.Z
            07 Feb 2024 13:06:00.000           51.0           100.0           408.0          100.0   200.0   300.0
        """)
        with patch("api.services.gmat_service._find_binary", return_value="/fake/GmatConsole"):
            with patch("subprocess.run", side_effect=self._make_fake_run(sample_report)):
                result = propagate_hifi(ISS_LINE1, ISS_LINE2, duration_hours=0.5)

        kep = result["keplerian_elements"]
        self.assertAlmostEqual(kep["sma_km"], 6790, delta=50)
        self.assertAlmostEqual(kep["inc_deg"], 51.64, delta=0.1)
        self.assertIn("ta_deg", kep)


if __name__ == "__main__":
    unittest.main()
