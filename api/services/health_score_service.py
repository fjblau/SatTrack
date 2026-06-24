"""
Health score service for RSO (Resident Space Object) satellite health assessment.

Calculates a calibrated 0-100 health score with explainable per-factor breakdowns
based on TLE-derived orbital parameters and operational history.
"""
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


FACTOR_WEIGHTS: Dict[str, float] = {
    "tle_age_days": 0.25,
    "eccentricity": 0.15,
    "perigee_altitude_km": 0.20,
    "bstar_drag": 0.20,
    "anomaly_count": 0.10,
    "maneuver_recency_days": 0.10,
}

_TLE_AGE_MAX_DAYS = 30.0
_PERIGEE_CRITICAL_KM = 200.0
_PERIGEE_NOMINAL_KM = 400.0
_ECCENTRICITY_LEO_NOMINAL = 0.01
_ECCENTRICITY_HIGH = 0.3
_BSTAR_NOMINAL = 1e-4
_BSTAR_HIGH = 1e-2
_ANOMALY_NOMINAL = 0
_ANOMALY_HIGH = 10
_MANEUVER_RECENCY_NOMINAL_DAYS = 7.0
_MANEUVER_RECENCY_OLD_DAYS = 90.0


def _score_tle_age(tle_epoch: datetime, reference_time: Optional[datetime] = None) -> float:
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)
    if tle_epoch.tzinfo is None:
        tle_epoch = tle_epoch.replace(tzinfo=timezone.utc)
    age_days = (reference_time - tle_epoch).total_seconds() / 86400.0
    if age_days <= 0:
        return 1.0
    score = max(0.0, 1.0 - (age_days / _TLE_AGE_MAX_DAYS))
    return round(score, 4)


def _score_eccentricity(eccentricity: float) -> float:
    if eccentricity < 0 or eccentricity >= 1:
        return 0.0
    if eccentricity <= _ECCENTRICITY_LEO_NOMINAL:
        return 1.0
    score = max(0.0, 1.0 - ((eccentricity - _ECCENTRICITY_LEO_NOMINAL) /
                              (_ECCENTRICITY_HIGH - _ECCENTRICITY_LEO_NOMINAL)))
    return round(score, 4)


def _score_perigee_altitude(perigee_km: float) -> float:
    if perigee_km >= _PERIGEE_NOMINAL_KM:
        return 1.0
    if perigee_km <= _PERIGEE_CRITICAL_KM:
        return 0.0
    score = (perigee_km - _PERIGEE_CRITICAL_KM) / (_PERIGEE_NOMINAL_KM - _PERIGEE_CRITICAL_KM)
    return round(score, 4)


def _score_bstar_drag(bstar: float) -> float:
    abs_bstar = abs(bstar)
    if abs_bstar <= 0:
        return 1.0
    if abs_bstar <= _BSTAR_NOMINAL:
        return 1.0
    log_ratio = math.log10(abs_bstar / _BSTAR_NOMINAL) / math.log10(_BSTAR_HIGH / _BSTAR_NOMINAL)
    score = max(0.0, 1.0 - log_ratio)
    return round(score, 4)


def _score_anomaly_count(anomaly_count: int) -> float:
    if anomaly_count <= _ANOMALY_NOMINAL:
        return 1.0
    score = max(0.0, 1.0 - (anomaly_count / _ANOMALY_HIGH))
    return round(score, 4)


def _score_maneuver_recency(last_maneuver_date: Optional[datetime],
                             reference_time: Optional[datetime] = None) -> float:
    if last_maneuver_date is None:
        return 0.5
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)
    if last_maneuver_date.tzinfo is None:
        last_maneuver_date = last_maneuver_date.replace(tzinfo=timezone.utc)
    days_ago = (reference_time - last_maneuver_date).total_seconds() / 86400.0
    if days_ago <= _MANEUVER_RECENCY_NOMINAL_DAYS:
        return 1.0
    score = max(0.0, 1.0 - ((days_ago - _MANEUVER_RECENCY_NOMINAL_DAYS) /
                              (_MANEUVER_RECENCY_OLD_DAYS - _MANEUVER_RECENCY_NOMINAL_DAYS)))
    return round(score, 4)


def calculate_health_score(
    tle_epoch: datetime,
    eccentricity: float,
    perigee_km: float,
    bstar: float,
    anomaly_count: int = 0,
    last_maneuver_date: Optional[datetime] = None,
    reference_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Calculate calibrated health score with explainable per-factor breakdown.

    Args:
        tle_epoch: UTC datetime of the most recent TLE epoch.
        eccentricity: Orbital eccentricity (0 – 1).
        perigee_km: Perigee altitude above Earth surface in km.
        bstar: BSTAR drag term from TLE line 1 (1/Earth radii).
        anomaly_count: Number of detected anomalies in recent window.
        last_maneuver_date: UTC datetime of most recent confirmed maneuver.
        reference_time: Evaluation timestamp (defaults to utcnow).

    Returns:
        Dict with keys:
          - ``health_score``: calibrated float 0-100
          - ``factors``: per-factor dict {name: {raw_value, sub_score, weight, contribution}}
          - ``computed_at``: ISO timestamp
    """
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)

    sub_scores = {
        "tle_age_days": _score_tle_age(tle_epoch, reference_time),
        "eccentricity": _score_eccentricity(eccentricity),
        "perigee_altitude_km": _score_perigee_altitude(perigee_km),
        "bstar_drag": _score_bstar_drag(bstar),
        "anomaly_count": _score_anomaly_count(anomaly_count),
        "maneuver_recency_days": _score_maneuver_recency(last_maneuver_date, reference_time),
    }

    total_weight = sum(FACTOR_WEIGHTS.values())
    weighted_sum = sum(sub_scores[k] * FACTOR_WEIGHTS[k] for k in FACTOR_WEIGHTS)
    normalised = weighted_sum / total_weight if total_weight > 0 else 0.0
    health_score = round(normalised * 100.0, 2)

    tle_age_days_raw = (reference_time - (
        tle_epoch.replace(tzinfo=timezone.utc) if tle_epoch.tzinfo is None else tle_epoch
    )).total_seconds() / 86400.0

    maneuver_days_raw: Optional[float] = None
    if last_maneuver_date is not None:
        ld = last_maneuver_date.replace(tzinfo=timezone.utc) if last_maneuver_date.tzinfo is None else last_maneuver_date
        maneuver_days_raw = (reference_time - ld).total_seconds() / 86400.0

    raw_values: Dict[str, Any] = {
        "tle_age_days": round(tle_age_days_raw, 2),
        "eccentricity": eccentricity,
        "perigee_altitude_km": perigee_km,
        "bstar_drag": bstar,
        "anomaly_count": anomaly_count,
        "maneuver_recency_days": maneuver_days_raw,
    }

    factors: Dict[str, Any] = {}
    for name, weight in FACTOR_WEIGHTS.items():
        ss = sub_scores[name]
        factors[name] = {
            "raw_value": raw_values[name],
            "sub_score": ss,
            "weight": weight,
            "contribution": round(ss * weight * 100.0 / total_weight, 2),
        }

    return {
        "health_score": health_score,
        "factors": factors,
        "computed_at": reference_time.isoformat(),
    }


def bulk_calculate_health_scores(objects: List[Dict[str, Any]],
                                  reference_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """
    Compute health scores for a list of RSO parameter dicts.

    Each dict in *objects* must contain the same keyword arguments accepted by
    :func:`calculate_health_score` plus an optional ``norad_id`` key.

    Returns:
        List of result dicts, each augmented with ``norad_id`` when present.
    """
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)
    results = []
    for obj in objects:
        norad_id = obj.get("norad_id")
        result = calculate_health_score(
            tle_epoch=obj["tle_epoch"],
            eccentricity=obj["eccentricity"],
            perigee_km=obj["perigee_km"],
            bstar=obj["bstar"],
            anomaly_count=obj.get("anomaly_count", 0),
            last_maneuver_date=obj.get("last_maneuver_date"),
            reference_time=reference_time,
        )
        if norad_id is not None:
            result["norad_id"] = norad_id
        results.append(result)
    return results
