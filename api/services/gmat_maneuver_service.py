import logging
import math
import os
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from api.services.gmat_service import (
    GmatError,
    _find_binary,
    _tle_to_keplerian,
    _tle_epoch_to_utc_gregorian,
    _GMAT_HOME,
    _TEMPLATE_DIR,
    find_egm96,
    validate_script,
)

logger = logging.getLogger(__name__)

_GM = 398600.4418  # km³/s²
_RE = 6371.0       # km


def _sma_to_alt(sma_km: float) -> float:
    return sma_km - _RE


def _orbital_velocity(sma_km: float) -> float:
    return math.sqrt(_GM / sma_km)


def _hohmann_dvs(r1: float, r2: float) -> tuple[float, float]:
    """Return (dv1, dv2) in km/s for a Hohmann transfer from r1 to r2 (both in km SMA)."""
    a_t = (r1 + r2) / 2.0
    v1 = _orbital_velocity(r1)
    v_t_peri = math.sqrt(_GM * (2.0 / r1 - 1.0 / a_t))
    v2 = _orbital_velocity(r2)
    v_t_apo = math.sqrt(_GM * (2.0 / r2 - 1.0 / a_t))
    dv1 = v_t_peri - v1
    dv2 = v2 - v_t_apo
    return dv1, dv2


def _transfer_time(r1: float, r2: float) -> float:
    """Half-period of Hohmann transfer ellipse in seconds."""
    a_t = (r1 + r2) / 2.0
    return math.pi * math.sqrt(a_t ** 3 / _GM)


def _synodic_period(r1: float, r2: float) -> float:
    """Synodic period (seconds) — time between phase alignment windows."""
    T1 = 2 * math.pi * math.sqrt(r1 ** 3 / _GM)
    T2 = 2 * math.pi * math.sqrt(r2 ** 3 / _GM)
    if abs(T1 - T2) < 1e-6:
        return float("inf")
    return abs(T1 * T2 / (T1 - T2))


def _epoch_plus_seconds(epoch_str: str, secs: float) -> str:
    """Advance a UTCGregorian epoch string by `secs` seconds, return ISO-8601 string."""
    fmt = "%d %b %Y %H:%M:%S.%f"
    try:
        dt = datetime.strptime(epoch_str, fmt).replace(tzinfo=timezone.utc)
    except ValueError:
        dt = datetime.now(timezone.utc)
    dt2 = dt + timedelta(seconds=secs)
    return dt2.isoformat()


def _parse_maneuver_report(report_path: str, burn1_at_secs: float) -> dict[str, Any]:
    """
    Parse two-spacecraft GMAT report and extract:
    - burn1_epoch (ISO)
    - burn2_epoch (ISO)
    - closest_approach_km
    - closest_approach_time (ISO)
    - arrival_range_km  (range at the moment of Burn2)
    """
    try:
        with open(report_path) as f:
            lines = f.readlines()
    except FileNotFoundError:
        raise GmatError(f"GMAT maneuver report not found: {report_path}")

    rows = []
    for ln in lines:
        ln = ln.strip()
        if not ln or ln.startswith("Kestrel."):
            continue
        parts = ln.split()
        if len(parts) < 8:
            continue
        try:
            ts = f"{parts[0]} {parts[1]} {parts[2]} {parts[3]}"
            dt = datetime.strptime(ts, "%d %b %Y %H:%M:%S.%f").replace(tzinfo=timezone.utc)
            kx, ky, kz = float(parts[4]), float(parts[5]), float(parts[6])
            tx, ty, tz = float(parts[7]), float(parts[8]), float(parts[9])
            rng = math.sqrt((kx - tx) ** 2 + (ky - ty) ** 2 + (kz - tz) ** 2)
            rows.append({"dt": dt, "kx": kx, "ky": ky, "kz": kz, "tx": tx, "ty": ty, "tz": tz, "range_km": rng})
        except (ValueError, IndexError):
            continue

    if not rows:
        raise GmatError("No valid rows in GMAT maneuver report")

    closest = min(rows, key=lambda r: r["range_km"])
    burn1_epoch = rows[0]["dt"].isoformat() if rows else None

    return {
        "closest_approach_km": round(closest["range_km"], 3),
        "closest_approach_time": closest["dt"].isoformat(),
        "burn1_epoch": rows[0]["dt"].isoformat() if rows else None,
        "arrival_range_km": rows[-1]["range_km"] if rows else None,
        "report_rows": len(rows),
    }


def compute_analytical_maneuver(
    kestrel_line1: str,
    kestrel_line2: str,
    target_line1: str,
    target_line2: str,
) -> dict[str, Any]:
    """
    Pure-Python analytical Hohmann transfer between two TLE-defined circular orbits.
    Always available — no GMAT required.
    """
    kep_k = _tle_to_keplerian(kestrel_line1, kestrel_line2)
    kep_t = _tle_to_keplerian(target_line1, target_line2)

    r1 = kep_k["sma_km"]
    r2 = kep_t["sma_km"]

    dv1, dv2 = _hohmann_dvs(r1, r2)
    t_transfer = _transfer_time(r1, r2)
    t_synodic = _synodic_period(r1, r2)
    wait_time = t_synodic / 2.0

    kestrel_epoch_str = _tle_epoch_to_utc_gregorian(kestrel_line1)
    burn1_iso = _epoch_plus_seconds(kestrel_epoch_str, wait_time)
    burn2_iso = _epoch_plus_seconds(kestrel_epoch_str, wait_time + t_transfer)

    raan_diff = abs((kep_t["raan_deg"] - kep_k["raan_deg"] + 540) % 360 - 180)
    inc_diff = abs(kep_t["inc_deg"] - kep_k["inc_deg"])

    dv_plane_change = 0.0
    if inc_diff > 0.5:
        v_avg = (_orbital_velocity(r1) + _orbital_velocity(r2)) / 2.0
        dv_plane_change = 2.0 * v_avg * math.sin(math.radians(inc_diff) / 2.0)

    return {
        "propagator": "analytical",
        "kestrel_alt_km": round(_sma_to_alt(r1), 2),
        "target_alt_km": round(_sma_to_alt(r2), 2),
        "kestrel_inc_deg": kep_k["inc_deg"],
        "target_inc_deg": kep_t["inc_deg"],
        "raan_diff_deg": round(raan_diff, 3),
        "inc_diff_deg": round(inc_diff, 3),
        "dv1_ms": round(dv1 * 1000, 3),
        "dv2_ms": round(dv2 * 1000, 3),
        "dv_total_ms": round((abs(dv1) + abs(dv2)) * 1000, 3),
        "dv_plane_change_ms": round(dv_plane_change * 1000, 3),
        "transfer_time_s": round(t_transfer, 1),
        "wait_time_s": round(wait_time, 1),
        "total_time_s": round(wait_time + t_transfer, 1),
        "burn1_epoch": burn1_iso,
        "burn2_epoch": burn2_iso,
        "closest_approach_km": None,
        "closest_approach_time": None,
        "gmat_verified": False,
    }


def compute_gmat_maneuver(
    kestrel_line1: str,
    kestrel_line2: str,
    target_line1: str,
    target_line2: str,
    analytical: dict[str, Any],
) -> dict[str, Any]:
    """
    Use GMAT to verify the analytically-computed Hohmann maneuver.
    Applies Burn1/Burn2 with computed ΔV values and propagates both spacecraft,
    returning closest-approach data from the hi-fi trajectory.
    Raises GmatError if GMAT is unavailable or the script fails.
    """
    binary = _find_binary()
    if not binary:
        raise GmatError(
            f"GMAT console binary not found. Set GMAT_HOME (currently '{_GMAT_HOME}')."
        )
    if find_egm96() is None:
        raise GmatError("EGM96.cof gravity file not found — GMAT maneuver cannot run.")

    kep_k = _tle_to_keplerian(kestrel_line1, kestrel_line2)
    kep_t = _tle_to_keplerian(target_line1, target_line2)
    kestrel_epoch = _tle_epoch_to_utc_gregorian(kestrel_line1)
    target_epoch = _tle_epoch_to_utc_gregorian(target_line1)

    dv1_km_s = analytical["dv1_ms"] / 1000.0
    dv2_km_s = analytical["dv2_ms"] / 1000.0
    wait_secs = int(analytical["wait_time_s"])
    transfer_secs = int(analytical["transfer_time_s"])

    template_path = _TEMPLATE_DIR / "maneuver_plan.script"
    if not template_path.exists():
        raise GmatError(f"Maneuver plan GMAT template not found: {template_path}")
    template = template_path.read_text()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = os.path.join(tmpdir, "maneuver_report.txt")

        script = (
            template
            .replace("%KESTREL_EPOCH%", kestrel_epoch)
            .replace("%KESTREL_SMA%", str(kep_k["sma_km"]))
            .replace("%KESTREL_ECC%", str(kep_k["ecc"]))
            .replace("%KESTREL_INC%", str(kep_k["inc_deg"]))
            .replace("%KESTREL_RAAN%", str(kep_k["raan_deg"]))
            .replace("%KESTREL_AOP%", str(kep_k["aop_deg"]))
            .replace("%KESTREL_TA%", str(kep_k["ta_deg"]))
            .replace("%TARGET_EPOCH%", target_epoch)
            .replace("%TARGET_SMA%", str(kep_t["sma_km"]))
            .replace("%TARGET_ECC%", str(kep_t["ecc"]))
            .replace("%TARGET_INC%", str(kep_t["inc_deg"]))
            .replace("%TARGET_RAAN%", str(kep_t["raan_deg"]))
            .replace("%TARGET_AOP%", str(kep_t["aop_deg"]))
            .replace("%TARGET_TA%", str(kep_t["ta_deg"]))
            .replace("%DV1_KM_S%", f"{dv1_km_s:.6f}")
            .replace("%DV2_KM_S%", f"{dv2_km_s:.6f}")
            .replace("%WAIT_SECS%", str(wait_secs))
            .replace("%TRANSFER_SECS%", str(transfer_secs))
            .replace("%OUTPUT_FILE%", output_file)
        )

        errors = validate_script(script)
        if errors:
            raise GmatError(f"Generated GMAT maneuver script is invalid: {errors}")

        script_path = os.path.join(tmpdir, "maneuver_plan.script")
        Path(script_path).write_text(script)

        gmat_bin_dir = os.path.join(_GMAT_HOME, "bin")
        env = {**os.environ, "GMAT_HOME": _GMAT_HOME}
        try:
            result = subprocess.run(
                [binary, script_path],
                capture_output=True,
                text=True,
                timeout=300,
                env=env,
                cwd=gmat_bin_dir,
            )
        except subprocess.TimeoutExpired:
            raise GmatError("GMAT maneuver plan timed out after 300 s")
        except Exception as exc:
            raise GmatError(f"Failed to launch GMAT: {exc}")

        if result.returncode != 0:
            combined = ((result.stdout or "") + (result.stderr or ""))[-1000:]
            raise GmatError(f"GMAT exited with code {result.returncode}: {combined}")

        report_data = _parse_maneuver_report(output_file, wait_secs)

    return {
        **analytical,
        "propagator": "GMAT_RK89_EGM96",
        "closest_approach_km": report_data["closest_approach_km"],
        "closest_approach_time": report_data["closest_approach_time"],
        "burn1_epoch": report_data["burn1_epoch"] or analytical["burn1_epoch"],
        "gmat_verified": True,
        "gmat_report_rows": report_data["report_rows"],
    }


def run_maneuver_plan(
    kestrel_line1: str,
    kestrel_line2: str,
    target_line1: str,
    target_line2: str,
    use_gmat: bool = True,
) -> dict[str, Any]:
    """
    Compute a Kestrel maneuver plan.
    Always computes analytically first; then optionally verifies with GMAT.
    Falls back gracefully if GMAT is unavailable.
    """
    analytical = compute_analytical_maneuver(
        kestrel_line1, kestrel_line2, target_line1, target_line2
    )

    if not use_gmat:
        return analytical

    try:
        return compute_gmat_maneuver(
            kestrel_line1, kestrel_line2, target_line1, target_line2, analytical
        )
    except GmatError as exc:
        logger.warning("GMAT maneuver plan failed, returning analytical result. Reason: %s", exc)
        analytical["gmat_error"] = str(exc)
        return analytical
