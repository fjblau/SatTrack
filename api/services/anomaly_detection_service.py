"""
Anomaly detection service for satellite attitude and spin-rate time series.

Implements CUSUM (Cumulative Sum) change-point detection to identify abrupt shifts
in attitude stability or spin rate that may indicate tumbling, thruster anomalies,
or attitude control system failures.
"""
import math
import statistics
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def _cusum_changepoints(
    values: List[float],
    threshold: float,
    drift: float = 0.0,
) -> List[int]:
    """
    Run two-sided CUSUM on *values* and return indices of detected change-points.

    Args:
        values: Ordered scalar observations.
        threshold: Decision threshold h; change-point declared when |S| >= h.
        drift: Allowance parameter k; reduces sensitivity to gradual drift.

    Returns:
        List of 0-based indices where change-points were declared.
    """
    if len(values) < 2:
        return []

    mean = statistics.mean(values)
    std = statistics.pstdev(values) or 1.0

    s_pos = 0.0
    s_neg = 0.0
    changepoints: List[int] = []

    for i, v in enumerate(values):
        z = (v - mean) / std
        s_pos = max(0.0, s_pos + z - drift)
        s_neg = min(0.0, s_neg + z + drift)
        if s_pos >= threshold or s_neg <= -threshold:
            changepoints.append(i)
            s_pos = 0.0
            s_neg = 0.0

    return changepoints


def detect_attitude_anomalies(
    timestamps: List[datetime],
    attitude_values: List[float],
    cusum_threshold: float = 5.0,
    cusum_drift: float = 0.5,
) -> Dict[str, Any]:
    """
    Detect change-points in attitude time series using CUSUM.

    Args:
        timestamps: UTC datetimes for each observation (same length as *attitude_values*).
        attitude_values: Scalar attitude metric per epoch (e.g., quaternion residual norm,
            pointing error in degrees, or roll/pitch/yaw angle).
        cusum_threshold: CUSUM decision threshold *h* (default 5.0 – ≈ 5-σ shift detection).
        cusum_drift: CUSUM allowance *k* (default 0.5).

    Returns:
        Dict with keys:
          - ``change_points``: list of {index, timestamp, value, magnitude} dicts
          - ``series_stats``: {mean, std, min, max, n}
          - ``threshold_used``: float
          - ``drift_used``: float
    """
    if len(timestamps) != len(attitude_values):
        raise ValueError("timestamps and attitude_values must have the same length")
    if len(attitude_values) == 0:
        return {
            "change_points": [],
            "series_stats": {"mean": None, "std": None, "min": None, "max": None, "n": 0},
            "threshold_used": cusum_threshold,
            "drift_used": cusum_drift,
        }

    cp_indices = _cusum_changepoints(attitude_values, cusum_threshold, cusum_drift)

    mean_val = statistics.mean(attitude_values)
    std_val = statistics.pstdev(attitude_values) or 1.0

    change_points = []
    for idx in cp_indices:
        ts = timestamps[idx]
        val = attitude_values[idx]
        magnitude = abs(val - mean_val) / std_val
        change_points.append({
            "index": idx,
            "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
            "value": val,
            "magnitude_sigma": round(magnitude, 3),
        })

    return {
        "change_points": change_points,
        "series_stats": {
            "mean": round(mean_val, 6),
            "std": round(std_val, 6),
            "min": min(attitude_values),
            "max": max(attitude_values),
            "n": len(attitude_values),
        },
        "threshold_used": cusum_threshold,
        "drift_used": cusum_drift,
    }


def detect_spin_rate_anomalies(
    timestamps: List[datetime],
    spin_rates_rpm: List[float],
    cusum_threshold: float = 4.0,
    cusum_drift: float = 0.5,
    expected_spin_rate_rpm: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Detect anomalous spin-rate excursions using CUSUM change-point detection.

    Args:
        timestamps: UTC datetimes for each spin-rate sample.
        spin_rates_rpm: Spin-rate observations in revolutions per minute.
        cusum_threshold: Decision threshold h (default 4.0).
        cusum_drift: Allowance k (default 0.5).
        expected_spin_rate_rpm: Nominal spin rate; used to compute residuals when provided.
            If None, residuals are computed relative to the series mean.

    Returns:
        Dict matching the schema returned by :func:`detect_attitude_anomalies` plus an
        ``expected_spin_rate_rpm`` field.
    """
    if len(timestamps) != len(spin_rates_rpm):
        raise ValueError("timestamps and spin_rates_rpm must have the same length")

    baseline = expected_spin_rate_rpm if expected_spin_rate_rpm is not None else (
        statistics.mean(spin_rates_rpm) if spin_rates_rpm else 0.0
    )
    residuals = [r - baseline for r in spin_rates_rpm]

    result = detect_attitude_anomalies(
        timestamps=timestamps,
        attitude_values=residuals,
        cusum_threshold=cusum_threshold,
        cusum_drift=cusum_drift,
    )
    result["expected_spin_rate_rpm"] = baseline
    result["series_stats"]["mean_raw"] = round(statistics.mean(spin_rates_rpm), 6) if spin_rates_rpm else None
    return result


def score_anomaly_severity(change_points: List[Dict[str, Any]]) -> str:
    """
    Map detected change-points to a human-readable severity label.

    Args:
        change_points: List as returned in the ``change_points`` key by detect_* functions.

    Returns:
        ``"none"``, ``"low"``, ``"medium"``, or ``"high"``.
    """
    if not change_points:
        return "none"
    max_sigma = max(cp.get("magnitude_sigma", 0.0) for cp in change_points)
    count = len(change_points)
    if max_sigma >= 8.0 or count >= 5:
        return "high"
    if max_sigma >= 5.0 or count >= 3:
        return "medium"
    return "low"
