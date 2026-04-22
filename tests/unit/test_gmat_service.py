import math
import os
import textwrap
import unittest
from unittest.mock import MagicMock, patch

from api.services.gmat_service import (
    GmatError,
    _EGM96_CANDIDATE,
    _EGM96_PATH,
    _PLACEHOLDER_PATTERN,
    _REQUIRED_SCRIPT_KEYWORDS,
    _TEMPLATE_DIR,
    _build_smoke_script,
    _mean_to_true_anomaly,
    _tle_epoch_to_utc_gregorian,
    _tle_to_keplerian,
    _parse_report,
    check_data_files,
    find_egm96,
    is_available,
    propagate_hifi,
    run_smoke_test,
    validate_script,
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

    def test_raises_when_script_invalid(self):
        with patch("api.services.gmat_service._find_binary", return_value="/fake/GmatConsole"):
            with patch("api.services.gmat_service.validate_script", return_value=["Unresolved placeholders: ['%BAD%']"]):
                with self.assertRaises(GmatError) as ctx:
                    propagate_hifi(ISS_LINE1, ISS_LINE2)
                self.assertIn("invalid", str(ctx.exception))

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
        fake_result.stdout = "GMAT script error: unknown parameter"
        fake_result.stderr = ""
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


class TestValidateScript(unittest.TestCase):
    def _make_script(self, overrides: dict | None = None) -> str:
        base = {k: "PLACEHOLDER" for k in _REQUIRED_SCRIPT_KEYWORDS}
        base.update(overrides or {})
        return "\n".join(base.values())

    def test_valid_template_has_no_errors(self):
        template = (_TEMPLATE_DIR / "propagation.script").read_text()
        kep = _tle_to_keplerian(ISS_LINE1, ISS_LINE2)
        epoch = _tle_epoch_to_utc_gregorian(ISS_LINE1)
        script = (
            template
            .replace("%EPOCH%", epoch)
            .replace("%SMA_KM%", str(kep["sma_km"]))
            .replace("%ECC%", str(kep["ecc"]))
            .replace("%INC_DEG%", str(kep["inc_deg"]))
            .replace("%RAAN_DEG%", str(kep["raan_deg"]))
            .replace("%AOP_DEG%", str(kep["aop_deg"]))
            .replace("%TA_DEG%", str(kep["ta_deg"]))
            .replace("%DURATION_SECS%", "3600")
            .replace("%OUTPUT_FILE%", "/tmp/test_ephemeris.txt")
        )
        errors = validate_script(script)
        self.assertEqual(errors, [], f"Unexpected validation errors: {errors}")

    def test_detects_unresolved_placeholder(self):
        script = "Create Spacecraft Sat;\n%EPOCH% is not substituted"
        errors = validate_script(script)
        self.assertTrue(any("Unresolved placeholders" in e for e in errors))
        self.assertIn("%EPOCH%", str(errors))

    def test_detects_multiple_placeholders(self):
        script = "stuff %SMA_KM% and %ECC% not replaced"
        errors = validate_script(script)
        matches = _PLACEHOLDER_PATTERN.findall(script)
        self.assertGreaterEqual(len(matches), 2)

    def test_detects_missing_keywords(self):
        script = "Create Spacecraft Sat;\nBeginMissionSequence;"
        errors = validate_script(script)
        missing = [e for e in errors if "Required GMAT keyword missing" in e]
        self.assertTrue(len(missing) > 0)

    def test_template_contains_all_required_keywords(self):
        template = (_TEMPLATE_DIR / "propagation.script").read_text()
        for kw in _REQUIRED_SCRIPT_KEYWORDS:
            self.assertIn(kw, template, f"Template missing required keyword: '{kw}'")

    def test_template_has_no_comments_only_placeholders(self):
        template = (_TEMPLATE_DIR / "propagation.script").read_text()
        placeholders = _PLACEHOLDER_PATTERN.findall(template)
        expected = {
            "%EPOCH%", "%SMA_KM%", "%ECC%", "%INC_DEG%",
            "%RAAN_DEG%", "%AOP_DEG%", "%TA_DEG%",
            "%DURATION_SECS%", "%OUTPUT_FILE%",
        }
        self.assertEqual(set(placeholders), expected,
                         f"Unexpected placeholders in template: {set(placeholders) - expected}")

    def test_valid_full_script_passes(self):
        good_script = "\n".join(_REQUIRED_SCRIPT_KEYWORDS)
        errors = validate_script(good_script)
        placeholder_errors = [e for e in errors if "Unresolved" in e]
        self.assertEqual(placeholder_errors, [])

    def test_smoke_script_has_no_placeholders(self):
        smoke = _build_smoke_script()
        placeholders = _PLACEHOLDER_PATTERN.findall(smoke)
        self.assertEqual(placeholders, [], f"Smoke script has unresolved placeholders: {placeholders}")

    def test_smoke_script_has_begin_mission_sequence(self):
        self.assertIn("BeginMissionSequence", _build_smoke_script())

    def test_smoke_script_has_propagate(self):
        self.assertIn("Propagate", _build_smoke_script())

    def test_smoke_script_uses_egm96_cof(self):
        smoke = _build_smoke_script()
        self.assertIn("'EGM96.cof'", smoke, "Smoke script must reference EGM96.cof")

    def test_smoke_script_uses_force_model(self):
        smoke = _build_smoke_script()
        self.assertIn("Create ForceModel", smoke, "Smoke script must exercise EGM96 via a force model")
        self.assertIn("PotentialFile", smoke)


class TestPropagateHifiScriptGeneration(unittest.TestCase):
    """Tests that the script rendered for GMAT is always valid before subprocess call."""

    def _capture_script(self, line1: str, line2: str, **kwargs) -> str:
        """Run propagate_hifi with a mock that captures the generated script content."""
        captured = {}

        def fake_run(cmd, *args, **kwargs_inner):
            script_path = cmd[1] if len(cmd) > 1 else ""
            if script_path and os.path.exists(script_path):
                captured["script"] = open(script_path).read()
            result = MagicMock()
            result.returncode = 1
            result.stdout = "deliberate fail"
            result.stderr = ""
            return result

        with patch("api.services.gmat_service._find_binary", return_value="/fake/GmatConsole"):
            with patch("subprocess.run", side_effect=fake_run):
                try:
                    propagate_hifi(line1, line2, **kwargs)
                except GmatError:
                    pass

        return captured.get("script", "")

    def test_iss_script_has_no_placeholders(self):
        script = self._capture_script(ISS_LINE1, ISS_LINE2, duration_hours=1)
        self.assertNotEqual(script, "", "Script was never written — check tmpdir lifetime")
        errors = validate_script(script)
        placeholder_errors = [e for e in errors if "Unresolved" in e]
        self.assertEqual(placeholder_errors, [], f"Placeholders remain: {placeholder_errors}")

    def test_geo_script_has_no_placeholders(self):
        script = self._capture_script(GEO_LINE1, GEO_LINE2, duration_hours=1)
        errors = validate_script(script)
        placeholder_errors = [e for e in errors if "Unresolved" in e]
        self.assertEqual(placeholder_errors, [], f"Placeholders remain: {placeholder_errors}")

    def test_iss_script_contains_epoch(self):
        script = self._capture_script(ISS_LINE1, ISS_LINE2)
        self.assertIn("2024", script, "Expected year 2024 in epoch line")
        self.assertIn("Feb", script, "Expected 'Feb' in epoch line")

    def test_iss_script_sma_reasonable(self):
        import re
        script = self._capture_script(ISS_LINE1, ISS_LINE2)
        match = re.search(r"Sat\.SMA\s*=\s*([0-9.]+)", script)
        self.assertIsNotNone(match, "SMA not found in script")
        sma = float(match.group(1))
        self.assertAlmostEqual(sma, 6790, delta=100)

    def test_iss_script_inclination_correct(self):
        import re
        script = self._capture_script(ISS_LINE1, ISS_LINE2)
        match = re.search(r"Sat\.INC\s*=\s*([0-9.]+)", script)
        self.assertIsNotNone(match)
        inc = float(match.group(1))
        self.assertAlmostEqual(inc, 51.6406, delta=0.01)

    def test_duration_substituted_correctly(self):
        import re
        script = self._capture_script(ISS_LINE1, ISS_LINE2, duration_hours=2, step_seconds=60)
        match = re.search(r"ElapsedSecs\s*=\s*([0-9]+)", script)
        self.assertIsNotNone(match)
        self.assertEqual(int(match.group(1)), 7200)

    def test_output_file_path_absolute(self):
        import re
        script = self._capture_script(ISS_LINE1, ISS_LINE2)
        match = re.search(r"Filename\s*=\s*'(.+?)'", script)
        self.assertIsNotNone(match)
        self.assertTrue(os.path.isabs(match.group(1)), "Report Filename must be an absolute path")

    def test_script_passes_validate_script(self):
        script = self._capture_script(ISS_LINE1, ISS_LINE2)
        errors = validate_script(script)
        self.assertEqual(errors, [], f"Script validation failed: {errors}")


class TestFindEgm96(unittest.TestCase):
    def test_returns_str_or_none(self):
        result = find_egm96()
        self.assertIsInstance(result, (str, type(None)))

    def test_returns_path_if_candidate_exists(self):
        with patch("os.path.isfile", return_value=True):
            result = find_egm96()
        self.assertIsNotNone(result)
        self.assertTrue(result.endswith("EGM96.cof"))

    def test_falls_back_to_glob(self):
        with patch("os.path.isfile", return_value=False):
            with patch("glob.glob", return_value=["/opt/gmat/some/other/EGM96.cof"]):
                result = find_egm96()
        self.assertEqual(result, "/opt/gmat/some/other/EGM96.cof")

    def test_returns_none_when_missing_everywhere(self):
        with patch("os.path.isfile", return_value=False):
            with patch("glob.glob", return_value=[]):
                result = find_egm96()
        self.assertIsNone(result)

    def test_egm96_candidate_is_absolute(self):
        self.assertTrue(os.path.isabs(_EGM96_CANDIDATE))

    def test_egm96_candidate_ends_with_cof(self):
        self.assertTrue(_EGM96_CANDIDATE.endswith("EGM96.cof"))


class TestCheckDataFiles(unittest.TestCase):
    def test_returns_list(self):
        result = check_data_files()
        self.assertIsInstance(result, list)

    def test_reports_missing_egm96(self):
        with patch("api.services.gmat_service.find_egm96", return_value=None):
            with patch("glob.glob", return_value=[]):
                result = check_data_files()
        self.assertTrue(len(result) > 0)
        self.assertTrue(any("EGM96" in e for e in result))

    def test_empty_when_egm96_found(self):
        with patch("api.services.gmat_service.find_egm96", return_value="/opt/gmat/data/gravity/Earth/EGM96.cof"):
            result = check_data_files()
        self.assertEqual(result, [])



class TestRunSmokeTest(unittest.TestCase):
    def test_returns_dict_with_required_keys(self):
        with patch("api.services.gmat_service._find_binary", return_value=None):
            result = run_smoke_test()
        self.assertIn("ok", result)
        self.assertIn("output", result)
        self.assertIn("error", result)

    def test_returns_not_ok_when_no_binary(self):
        with patch("api.services.gmat_service._find_binary", return_value=None):
            result = run_smoke_test()
        self.assertFalse(result["ok"])
        self.assertIsNotNone(result["error"])

    def test_returns_ok_on_success(self):
        fake_result = MagicMock()
        fake_result.returncode = 0
        fake_result.stdout = "GMAT Build Date: 2022\nScript ran successfully"
        fake_result.stderr = ""
        with patch("api.services.gmat_service._find_binary", return_value="/fake/GmatConsole"):
            with patch("subprocess.run", return_value=fake_result):
                result = run_smoke_test()
        self.assertTrue(result["ok"])
        self.assertIsNone(result["error"])

    def test_returns_not_ok_on_nonzero_exit(self):
        fake_result = MagicMock()
        fake_result.returncode = 1
        fake_result.stdout = "Application Execution Failed: errors in script"
        fake_result.stderr = ""
        with patch("api.services.gmat_service._find_binary", return_value="/fake/GmatConsole"):
            with patch("subprocess.run", return_value=fake_result):
                result = run_smoke_test()
        self.assertFalse(result["ok"])
        self.assertIn("exit 1", result["error"])

    def test_returns_not_ok_on_execution_failed_string(self):
        fake_result = MagicMock()
        fake_result.returncode = 0
        fake_result.stdout = "Application Execution Failed: Errors were found in the script"
        fake_result.stderr = ""
        with patch("api.services.gmat_service._find_binary", return_value="/fake/GmatConsole"):
            with patch("subprocess.run", return_value=fake_result):
                result = run_smoke_test()
        self.assertFalse(result["ok"], "Should fail when 'Application Execution Failed' in output")

    def test_returns_not_ok_on_timeout(self):
        import subprocess
        with patch("api.services.gmat_service._find_binary", return_value="/fake/GmatConsole"):
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="x", timeout=60)):
                result = run_smoke_test()
        self.assertFalse(result["ok"])
        self.assertIn("timed out", result["error"])


if __name__ == "__main__":
    unittest.main()
