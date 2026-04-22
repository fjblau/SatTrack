import glob
import logging
import math
import re
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_GMAT_HOME = os.environ.get("GMAT_HOME", "/opt/gmat")
_TEMPLATE_DIR = Path(__file__).parent.parent.parent / "gmat_scripts" / "templates"

_EGM96_CANDIDATE = os.path.join(_GMAT_HOME, "data", "gravity", "Earth", "EGM96.cof")


def find_egm96() -> str | None:
    """Return the absolute path to EGM96.cof, searching under GMAT_HOME if the default location fails."""
    if os.path.isfile(_EGM96_CANDIDATE):
        return _EGM96_CANDIDATE
    matches = glob.glob(os.path.join(_GMAT_HOME, "**", "EGM96.cof"), recursive=True)
    if matches:
        found = matches[0]
        logger.info("EGM96.cof found at non-default location: %s", found)
        return found
    return None


_EGM96_PATH: str = find_egm96() or _EGM96_CANDIDATE

_BINARY_CANDIDATES = [
    os.path.join(_GMAT_HOME, "bin", "GmatConsole-R2022a"),
    os.path.join(_GMAT_HOME, "bin", "GmatConsole"),
    shutil.which("GmatConsole-R2022a") or "",
    shutil.which("GmatConsole") or "",
]


class GmatError(Exception):
    pass


def _find_binary() -> str | None:
    return next((p for p in _BINARY_CANDIDATES if p and os.path.isfile(p) and os.access(p, os.X_OK)), None)


def is_available() -> bool:
    return _find_binary() is not None


def check_data_files() -> list[str]:
    """Return a list of missing required GMAT data files; empty = all present."""
    missing = []
    if find_egm96() is None:
        searched = glob.glob(os.path.join(_GMAT_HOME, "**", "EGM96.cof"), recursive=True)
        missing.append(
            f"EGM96 gravity file not found anywhere under {_GMAT_HOME}. "
            f"Searched: {_EGM96_CANDIDATE}. "
            f"glob result: {searched}"
        )
    return missing


def _mean_to_true_anomaly(mean_anomaly_deg: float, eccentricity: float) -> float:
    M = math.radians(mean_anomaly_deg)
    E = M
    for _ in range(100):
        dE = (M - E + eccentricity * math.sin(E)) / (1 - eccentricity * math.cos(E))
        E += dE
        if abs(dE) < 1e-12:
            break
    sin_ta = (math.sqrt(1 - eccentricity ** 2) * math.sin(E)) / (1 - eccentricity * math.cos(E))
    cos_ta = (math.cos(E) - eccentricity) / (1 - eccentricity * math.cos(E))
    ta_rad = math.atan2(sin_ta, cos_ta)
    return math.degrees(ta_rad) % 360


def _tle_to_keplerian(line1: str, line2: str) -> dict[str, float]:
    try:
        inclination = float(line2[8:16])
        raan = float(line2[17:25])
        eccentricity = float("0." + line2[26:33])
        aop = float(line2[34:42])
        mean_anomaly = float(line2[43:51])
        mean_motion_rev_day = float(line2[52:63])
    except (ValueError, IndexError) as exc:
        raise GmatError(f"Invalid TLE format: {exc}") from exc

    GM = 398600.4418
    n_rad_s = mean_motion_rev_day * 2 * math.pi / 86400.0
    sma_km = (GM / (n_rad_s ** 2)) ** (1.0 / 3.0)

    ta_deg = _mean_to_true_anomaly(mean_anomaly, eccentricity)

    return {
        "sma_km": round(sma_km, 4),
        "ecc": round(eccentricity, 7),
        "inc_deg": round(inclination, 4),
        "raan_deg": round(raan, 4),
        "aop_deg": round(aop, 4),
        "ta_deg": round(ta_deg, 4),
    }


def _tle_epoch_to_utc_gregorian(line1: str) -> str:
    epoch_year_2 = int(line1[18:20])
    epoch_day = float(line1[20:32])
    year = 2000 + epoch_year_2 if epoch_year_2 < 57 else 1900 + epoch_year_2
    epoch = datetime(year, 1, 1, tzinfo=timezone.utc)
    from datetime import timedelta
    epoch += timedelta(days=epoch_day - 1)
    return epoch.strftime("%d %b %Y %H:%M:%S.%f")[:-3]


def _parse_report(report_path: str, step_seconds: int) -> list[dict[str, Any]]:
    points = []
    try:
        with open(report_path) as f:
            lines = f.readlines()
    except FileNotFoundError:
        raise GmatError(f"GMAT report file not found: {report_path}")

    data_lines = [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("Sat.")]
    if not data_lines:
        raise GmatError("GMAT report file is empty or header-only")

    for line in data_lines:
        parts = line.split()
        if len(parts) < 10:
            continue
        try:
            timestamp_str = f"{parts[0]} {parts[1]} {parts[2]} {parts[3]}"
            dt = datetime.strptime(timestamp_str, "%d %b %Y %H:%M:%S.%f")
            dt = dt.replace(tzinfo=timezone.utc)
            lat = float(parts[4])
            lon = float(parts[5])
            alt_km = float(parts[6])
            x_km = float(parts[7])
            y_km = float(parts[8])
            z_km = float(parts[9])
            points.append({
                "timestamp": dt.isoformat(),
                "eci": {"x_km": x_km, "y_km": y_km, "z_km": z_km},
                "geodetic": {
                    "latitude": round(lat, 6),
                    "longitude": round(lon, 6),
                    "altitude_km": round(alt_km, 2),
                },
                "propagation_age_minutes": None,
            })
        except (ValueError, IndexError) as exc:
            logger.debug("Skipping malformed report line: %s (%s)", line[:80], exc)
            continue

    if not points:
        raise GmatError("No valid ephemeris points parsed from GMAT report")
    return points


def propagate_hifi(
    line1: str,
    line2: str,
    duration_hours: float = 24.0,
    step_seconds: int = 60,
) -> dict[str, Any]:
    binary = _find_binary()
    if not binary:
        raise GmatError(
            f"GMAT console binary not found. Set GMAT_HOME (currently '{_GMAT_HOME}') "
            "and ensure GmatConsole-R2022a is installed."
        )

    kep = _tle_to_keplerian(line1, line2)
    epoch_str = _tle_epoch_to_utc_gregorian(line1)
    duration_secs = int(duration_hours * 3600)

    template_path = _TEMPLATE_DIR / "propagation.script"
    if not template_path.exists():
        raise GmatError(f"GMAT script template not found: {template_path}")
    template = template_path.read_text()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = os.path.join(tmpdir, "ephemeris.txt")

        script = (
            template
            .replace("%EPOCH%", epoch_str)
            .replace("%SMA_KM%", str(kep["sma_km"]))
            .replace("%ECC%", str(kep["ecc"]))
            .replace("%INC_DEG%", str(kep["inc_deg"]))
            .replace("%RAAN_DEG%", str(kep["raan_deg"]))
            .replace("%AOP_DEG%", str(kep["aop_deg"]))
            .replace("%TA_DEG%", str(kep["ta_deg"]))
            .replace("%STEP_SECS%", str(step_seconds))
            .replace("%DURATION_SECS%", str(duration_secs))
            .replace("%OUTPUT_FILE%", output_file)
        )

        script_errors = validate_script(script)
        if script_errors:
            raise GmatError(f"Generated GMAT script is invalid: {script_errors}")

        script_path = os.path.join(tmpdir, "mission.script")
        Path(script_path).write_text(script)

        gmat_bin_dir = os.path.join(_GMAT_HOME, "bin")
        env = {**os.environ, "GMAT_HOME": _GMAT_HOME}
        try:
            result = subprocess.run(
                [binary, script_path],
                capture_output=True,
                text=True,
                timeout=180,
                env=env,
                cwd=gmat_bin_dir,
            )
        except subprocess.TimeoutExpired:
            raise GmatError("GMAT propagation timed out after 180 s")
        except Exception as exc:
            raise GmatError(f"Failed to launch GMAT: {exc}")

        if result.returncode != 0:
            combined = ((result.stdout or "") + (result.stderr or ""))[-800:]
            try:
                script_snippet = Path(script_path).read_text()[:600]
            except Exception:
                script_snippet = "<unreadable>"
            logger.error(
                "GMAT script failed (exit %d). Script:\n%s\nGMAT output:\n%s",
                result.returncode, script_snippet, combined,
            )
            raise GmatError(f"GMAT exited with code {result.returncode}: {combined}")

        points = _parse_report(output_file, step_seconds)

    if not points:
        raise GmatError("GMAT returned zero ephemeris points")

    valid_from = points[0]["timestamp"]
    valid_until = points[-1]["timestamp"]

    from api.services.orbital_service import OrbitalService
    try:
        params = OrbitalService.calculate_orbital_parameters(line2)
        period_minutes = params["period_minutes"]
    except Exception:
        period_minutes = None

    return {
        "propagator": "GMAT_RK89_EGM96",
        "tle_epoch": epoch_str,
        "valid_from": valid_from,
        "valid_until": valid_until,
        "step_seconds": step_seconds,
        "orbital_period_minutes": period_minutes,
        "num_points": len(points),
        "ephemeris_points": points,
        "keplerian_elements": kep,
    }


_REQUIRED_SCRIPT_KEYWORDS = [
    "Create Spacecraft",
    "Create ForceModel",
    "Create Propagator",
    "Create ReportFile",
    "BeginMissionSequence",
    "Propagate",
]

_PLACEHOLDER_PATTERN = re.compile(r"%[A-Z0-9_]+%")


def validate_script(script_text: str) -> list[str]:
    """Return a list of validation error strings; empty list means OK."""
    errors: list[str] = []
    try:
        script_text.encode("ascii")
    except UnicodeEncodeError as exc:
        errors.append(f"Script contains non-ASCII characters (GMAT requires pure ASCII): {exc}")
    remaining = _PLACEHOLDER_PATTERN.findall(script_text)
    if remaining:
        errors.append(f"Unresolved placeholders in script: {remaining}")
    for kw in _REQUIRED_SCRIPT_KEYWORDS:
        if kw not in script_text:
            errors.append(f"Required GMAT keyword missing: '{kw}'")
    return errors


def _build_smoke_script() -> str:
    """Build a smoke-test GMAT script that exercises EGM96 gravity so we catch missing data files."""
    return f"""\
% GMAT smoke test - EGM96 gravity + 60-second propagation
Create Spacecraft Probe;
Probe.DateFormat          = UTCGregorian;
Probe.Epoch               = '01 Jan 2024 00:00:00.000';
Probe.CoordinateSystem    = EarthMJ2000Eq;
Probe.DisplayStateType    = Keplerian;
Probe.SMA  = 6778.0;
Probe.ECC  = 0.001;
Probe.INC  = 51.6;
Probe.RAAN = 0.0;
Probe.AOP  = 0.0;
Probe.TA   = 0.0;
Probe.DryMass = 100;
Probe.Cd  = 2.2;
Probe.Cr  = 1.8;
Probe.DragArea = 15;
Probe.SRPArea  = 15;

Create ForceModel SmokeHiFiFM;
SmokeHiFiFM.CentralBody                  = Earth;
SmokeHiFiFM.PrimaryBodies                = {{Earth}};
SmokeHiFiFM.GravityField.Earth.Degree    = 4;
SmokeHiFiFM.GravityField.Earth.Order     = 4;
SmokeHiFiFM.GravityField.Earth.PotentialFile = 'EGM96.cof';

Create Propagator SmokeProp;
SmokeProp.FM   = SmokeHiFiFM;
SmokeProp.Type = RungeKutta89;

BeginMissionSequence;

Propagate SmokeProp(Probe) {{Probe.ElapsedSecs = 60}};
"""


def run_smoke_test() -> dict[str, Any]:
    """Run a minimal GMAT script to verify the installation is functional.

    Returns a dict with keys: ``ok`` (bool), ``output`` (str), ``error`` (str | None).
    """
    binary = _find_binary()
    if not binary:
        return {"ok": False, "output": "", "error": "GMAT binary not found"}

    gmat_bin_dir = os.path.join(_GMAT_HOME, "bin")
    with tempfile.TemporaryDirectory() as tmpdir:
        script_path = os.path.join(tmpdir, "smoke_test.script")
        Path(script_path).write_text(_build_smoke_script())
        env = {**os.environ, "GMAT_HOME": _GMAT_HOME}
        try:
            result = subprocess.run(
                [binary, script_path],
                capture_output=True,
                text=True,
                timeout=60,
                env=env,
                cwd=gmat_bin_dir,
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "output": "", "error": "Smoke test timed out after 60 s"}
        except Exception as exc:
            return {"ok": False, "output": "", "error": f"Failed to launch GMAT: {exc}"}

    combined = ((result.stdout or "") + (result.stderr or ""))
    ok = result.returncode == 0 and "Application Execution Failed" not in combined
    error = None if ok else f"exit {result.returncode}: {combined[-2000:]}"
    return {"ok": ok, "output": combined[-2000:], "error": error}
