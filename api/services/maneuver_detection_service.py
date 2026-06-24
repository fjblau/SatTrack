"""
Maneuver detection service using SGP4-based delta-V residual analysis.

Propagates each TLE forward to the next TLE's epoch, compares the predicted state
with the observed state derived from the next TLE, and flags the difference as a
maneuver event when the velocity residual exceeds a configurable threshold.
"""
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sgp4.api import Satrec, jday


_EARTH_RADIUS_KM = 6378.137
_MU_KM3_S2 = 398600.4418
_DEFAULT_DV_THRESHOLD_M_S = 1.0


def _parse_tle(line1: str, line2: str) -> Satrec:
    """Create an SGP4 Satrec object from TLE lines."""
    sat = Satrec.twoline2rv(line1, line2)
    return sat


def _propagate_to_epoch(sat: Satrec, target_dt: datetime) -> Optional[Tuple[List[float], List[float]]]:
    """
    Propagate *sat* to *target_dt* and return (position_km, velocity_km_s) in ECI.

    Returns None if propagation fails (e.g., decayed object, invalid epoch).
    """
    if target_dt.tzinfo is None:
        target_dt = target_dt.replace(tzinfo=timezone.utc)
    jd, fr = jday(
        target_dt.year, target_dt.month, target_dt.day,
        target_dt.hour, target_dt.minute,
        target_dt.second + target_dt.microsecond / 1e6,
    )
    e, r, v = sat.sgp4(jd, fr)
    if e != 0:
        return None
    return list(r), list(v)


def _tle_epoch_to_datetime(line1: str) -> Optional[datetime]:
    """Extract epoch UTC datetime from TLE line 1."""
    try:
        epoch_year_raw = int(line1[18:20])
        epoch_day = float(line1[20:32])
        year = 2000 + epoch_year_raw if epoch_year_raw < 57 else 1900 + epoch_year_raw
        from datetime import timedelta
        epoch_dt = datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(days=epoch_day - 1.0)
        return epoch_dt
    except (ValueError, IndexError):
        return None


def _vector_magnitude(v: List[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def _vector_diff(a: List[float], b: List[float]) -> List[float]:
    return [a[i] - b[i] for i in range(len(a))]


def compute_delta_v_residual(
    tle_before_line1: str,
    tle_before_line2: str,
    tle_after_line1: str,
    tle_after_line2: str,
) -> Dict[str, Any]:
    """
    Compute the velocity residual (delta-V proxy) between two consecutive TLEs.

    Propagates the *before* TLE to the epoch of the *after* TLE, then subtracts the
    predicted velocity from the velocity implied by the *after* TLE at its own epoch.

    Args:
        tle_before_line1 / tle_before_line2: Earlier TLE.
        tle_after_line1  / tle_after_line2:  Later TLE.

    Returns:
        Dict with keys:
          - ``delta_v_m_s``: magnitude of velocity residual in m/s
          - ``delta_v_components_m_s``: [dx, dy, dz] residual components
          - ``delta_r_km``: position residual magnitude in km
          - ``epoch_before``: ISO epoch of earlier TLE
          - ``epoch_after``: ISO epoch of later TLE
          - ``propagation_ok``: bool
          - ``error``: error message string or None
    """
    epoch_before = _tle_epoch_to_datetime(tle_before_line1)
    epoch_after = _tle_epoch_to_datetime(tle_after_line1)

    if epoch_before is None or epoch_after is None:
        return {
            "delta_v_m_s": None,
            "delta_v_components_m_s": None,
            "delta_r_km": None,
            "epoch_before": epoch_before.isoformat() if epoch_before else None,
            "epoch_after": epoch_after.isoformat() if epoch_after else None,
            "propagation_ok": False,
            "error": "Failed to parse TLE epoch",
        }

    sat_before = _parse_tle(tle_before_line1, tle_before_line2)
    sat_after = _parse_tle(tle_after_line1, tle_after_line2)

    predicted = _propagate_to_epoch(sat_before, epoch_after)
    observed = _propagate_to_epoch(sat_after, epoch_after)

    if predicted is None or observed is None:
        return {
            "delta_v_m_s": None,
            "delta_v_components_m_s": None,
            "delta_r_km": None,
            "epoch_before": epoch_before.isoformat(),
            "epoch_after": epoch_after.isoformat(),
            "propagation_ok": False,
            "error": "SGP4 propagation error",
        }

    pred_r, pred_v = predicted
    obs_r, obs_v = observed

    dv = _vector_diff(obs_v, pred_v)
    dv_m_s = [x * 1000.0 for x in dv]
    dv_mag_m_s = _vector_magnitude(dv_m_s)

    dr = _vector_diff(obs_r, pred_r)
    dr_km = _vector_magnitude(dr)

    return {
        "delta_v_m_s": round(dv_mag_m_s, 4),
        "delta_v_components_m_s": [round(x, 4) for x in dv_m_s],
        "delta_r_km": round(dr_km, 4),
        "epoch_before": epoch_before.isoformat(),
        "epoch_after": epoch_after.isoformat(),
        "propagation_ok": True,
        "error": None,
    }


def extract_maneuver_events(
    tle_history: List[Dict[str, str]],
    dv_threshold_m_s: float = _DEFAULT_DV_THRESHOLD_M_S,
) -> Dict[str, Any]:
    """
    Scan a chronological list of TLEs and extract maneuver events.

    Args:
        tle_history: List of dicts with keys ``line1`` and ``line2``, ordered oldest-first.
        dv_threshold_m_s: Minimum delta-V residual (m/s) to classify as a maneuver.

    Returns:
        Dict with keys:
          - ``maneuver_events``: list of residual dicts that exceeded the threshold,
            each containing all fields from :func:`compute_delta_v_residual`.
          - ``total_pairs_checked``: int
          - ``maneuver_count``: int
          - ``threshold_m_s``: float
    """
    if len(tle_history) < 2:
        return {
            "maneuver_events": [],
            "total_pairs_checked": 0,
            "maneuver_count": 0,
            "threshold_m_s": dv_threshold_m_s,
        }

    maneuver_events: List[Dict[str, Any]] = []
    total_pairs = len(tle_history) - 1

    for i in range(total_pairs):
        before = tle_history[i]
        after = tle_history[i + 1]
        residual = compute_delta_v_residual(
            before["line1"], before["line2"],
            after["line1"], after["line2"],
        )
        if residual["propagation_ok"] and residual["delta_v_m_s"] is not None:
            if residual["delta_v_m_s"] >= dv_threshold_m_s:
                residual["pair_index"] = i
                maneuver_events.append(residual)

    return {
        "maneuver_events": maneuver_events,
        "total_pairs_checked": total_pairs,
        "maneuver_count": len(maneuver_events),
        "threshold_m_s": dv_threshold_m_s,
    }
