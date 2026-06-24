"""
Re-entry estimation service based on orbital altitude/perigee decay trends.

Fits linear and exponential regression models to historical perigee altitude
(or mean motion) data extracted from TLE history, then extrapolates to the
re-entry threshold to produce a predicted date window.
"""
import math
import statistics
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple


_REENTRY_ALTITUDE_KM = 80.0
_MIN_POINTS_FOR_FIT = 3


def _linear_regression(xs: List[float], ys: List[float]) -> Tuple[float, float, float]:
    """
    Ordinary least-squares linear regression y = slope * x + intercept.

    Returns:
        (slope, intercept, r_squared)
    """
    n = len(xs)
    if n < 2:
        raise ValueError("Need at least 2 points for linear regression")
    x_mean = statistics.mean(xs)
    y_mean = statistics.mean(ys)
    sxx = sum((x - x_mean) ** 2 for x in xs)
    sxy = sum((xs[i] - x_mean) * (ys[i] - y_mean) for i in range(n))
    if sxx == 0:
        raise ValueError("All x values are identical; cannot fit regression")
    slope = sxy / sxx
    intercept = y_mean - slope * x_mean
    y_pred = [slope * x + intercept for x in xs]
    ss_res = sum((ys[i] - y_pred[i]) ** 2 for i in range(n))
    ss_tot = sum((y - y_mean) ** 2 for y in ys)
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return slope, intercept, r_squared


def _exp_regression(xs: List[float], ys: List[float]) -> Tuple[float, float, float]:
    """
    Exponential regression y = A * exp(B * x) via log-linearisation.

    Returns:
        (A, B, r_squared_of_log_fit)
    """
    if any(y <= 0 for y in ys):
        raise ValueError("Exponential regression requires all y values > 0")
    log_ys = [math.log(y) for y in ys]
    b_coeff, log_a, r_sq = _linear_regression(xs, log_ys)
    a_coeff = math.exp(log_a)
    return a_coeff, b_coeff, r_sq


def _days_to_reentry_linear(slope: float, intercept: float,
                              reentry_alt: float, x0: float) -> Optional[float]:
    """Days from x=x0 until altitude reaches reentry_alt under linear model."""
    if slope >= 0:
        return None
    days = (reentry_alt - intercept) / slope - x0
    return days if days > 0 else None


def _days_to_reentry_exp(a: float, b: float,
                          reentry_alt: float, x0: float) -> Optional[float]:
    """Days from x=x0 until A*exp(B*x) reaches reentry_alt."""
    if b >= 0 or a <= 0 or reentry_alt <= 0:
        return None
    try:
        x_reentry = math.log(reentry_alt / a) / b
        days = x_reentry - x0
        return days if days > 0 else None
    except (ValueError, ZeroDivisionError):
        return None


def estimate_reentry(
    epochs: List[datetime],
    perigee_altitudes_km: List[float],
    reentry_altitude_km: float = _REENTRY_ALTITUDE_KM,
    confidence_days: float = 30.0,
) -> Dict[str, Any]:
    """
    Estimate re-entry date from historical perigee altitude measurements.

    Both a linear and an exponential model are fitted; the model with the higher
    R² is selected as the primary estimate.  A symmetric confidence window of
    ±*confidence_days* is applied around the point estimate.

    Args:
        epochs: UTC datetimes for each perigee measurement (same length as altitudes).
        perigee_altitudes_km: Perigee altitude above Earth surface in km.
        reentry_altitude_km: Threshold altitude considered atmospheric re-entry (default 80 km).
        confidence_days: Half-width of the date window in days (default 30).

    Returns:
        Dict with keys:
          - ``predicted_reentry_date``: ISO date string or None
          - ``window_earliest``: ISO date string or None
          - ``window_latest``: ISO date string or None
          - ``model_selected``: ``"linear"`` or ``"exponential"``
          - ``linear_model``: {slope, intercept, r_squared}
          - ``exponential_model``: {A, B, r_squared} or None
          - ``current_decay_rate_km_day``: estimated daily altitude loss (positive value)
          - ``n_points``: number of data points used
          - ``reentry_altitude_km``: threshold used
    """
    if len(epochs) != len(perigee_altitudes_km):
        raise ValueError("epochs and perigee_altitudes_km must have the same length")
    if len(epochs) < _MIN_POINTS_FOR_FIT:
        return {
            "predicted_reentry_date": None,
            "window_earliest": None,
            "window_latest": None,
            "model_selected": None,
            "linear_model": None,
            "exponential_model": None,
            "current_decay_rate_km_day": None,
            "n_points": len(epochs),
            "reentry_altitude_km": reentry_altitude_km,
            "error": f"Insufficient data: need >= {_MIN_POINTS_FOR_FIT} points",
        }

    ref_epoch = min(epochs)
    if ref_epoch.tzinfo is None:
        ref_epoch = ref_epoch.replace(tzinfo=timezone.utc)

    xs: List[float] = []
    for ep in epochs:
        ep_utc = ep.replace(tzinfo=timezone.utc) if ep.tzinfo is None else ep
        xs.append((ep_utc - ref_epoch).total_seconds() / 86400.0)

    ys = list(perigee_altitudes_km)

    lin_slope, lin_intercept, lin_r2 = _linear_regression(xs, ys)

    exp_model: Optional[Dict[str, Any]] = None
    exp_r2 = -1.0
    exp_a = exp_b = None
    try:
        if all(y > 0 for y in ys):
            exp_a, exp_b, exp_r2 = _exp_regression(xs, ys)
            exp_model = {"A": round(exp_a, 4), "B": round(exp_b, 8), "r_squared": round(exp_r2, 4)}
    except ValueError:
        pass

    x_now = xs[-1]
    reference_now = ref_epoch + timedelta(days=x_now)

    use_exp = exp_model is not None and exp_r2 > lin_r2
    if use_exp:
        days_left = _days_to_reentry_exp(exp_a, exp_b, reentry_altitude_km, x_now)
        model_selected = "exponential"
    else:
        days_left = _days_to_reentry_linear(lin_slope, lin_intercept, reentry_altitude_km, x_now)
        model_selected = "linear"

    predicted_date = None
    window_earliest = None
    window_latest = None
    if days_left is not None:
        predicted_dt = reference_now + timedelta(days=days_left)
        early_dt = predicted_dt - timedelta(days=confidence_days)
        late_dt = predicted_dt + timedelta(days=confidence_days)
        predicted_date = predicted_dt.date().isoformat()
        window_earliest = early_dt.date().isoformat()
        window_latest = late_dt.date().isoformat()

    decay_rate = -lin_slope if lin_slope < 0 else None

    return {
        "predicted_reentry_date": predicted_date,
        "window_earliest": window_earliest,
        "window_latest": window_latest,
        "model_selected": model_selected,
        "linear_model": {
            "slope": round(lin_slope, 6),
            "intercept": round(lin_intercept, 4),
            "r_squared": round(lin_r2, 4),
        },
        "exponential_model": exp_model,
        "current_decay_rate_km_day": round(decay_rate, 6) if decay_rate is not None else None,
        "n_points": len(xs),
        "reentry_altitude_km": reentry_altitude_km,
    }


def extract_perigee_series_from_tle_history(
    tle_history: List[Dict[str, Any]],
) -> Tuple[List[datetime], List[float]]:
    """
    Extract (epoch, perigee_km) pairs from a list of TLE history records.

    Each record must have keys ``line1``, ``line2``, and optionally ``perigee_km``.
    If ``perigee_km`` is absent it is computed from TLE line 2 using the standard
    two-body formula.

    Returns:
        (epochs, perigee_altitudes_km) lists of equal length, sorted oldest-first.
    """
    _EARTH_R = 6378.137
    _MU = 398600.4418

    pairs: List[Tuple[datetime, float]] = []
    for record in tle_history:
        line1 = record.get("line1", "")
        line2 = record.get("line2", "")
        epoch = record.get("epoch")
        if epoch is None:
            try:
                year_raw = int(line1[18:20])
                day = float(line1[20:32])
                year = 2000 + year_raw if year_raw < 57 else 1900 + year_raw
                epoch = datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(days=day - 1.0)
            except (ValueError, IndexError):
                continue
        if isinstance(epoch, str):
            epoch = datetime.fromisoformat(epoch)
        if epoch.tzinfo is None:
            epoch = epoch.replace(tzinfo=timezone.utc)

        perigee_km = record.get("perigee_km")
        if perigee_km is None:
            try:
                ecc = float("0." + line2[26:33])
                mm = float(line2[52:63])
                n = mm * 2 * math.pi / 86400.0
                a = (_MU / (n * n)) ** (1.0 / 3.0)
                perigee_km = a * (1 - ecc) - _EARTH_R
            except (ValueError, IndexError):
                continue

        pairs.append((epoch, float(perigee_km)))

    pairs.sort(key=lambda p: p[0])
    epochs = [p[0] for p in pairs]
    perigees = [p[1] for p in pairs]
    return epochs, perigees
