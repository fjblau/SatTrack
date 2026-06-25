"""
Analytics router — ML-powered RSO signal endpoints.

Exposes per-object and batch analytics derived from Shantanu's ML services:
health scoring, anomaly detection, maneuver detection, re-entry estimation,
similarity search, and precomputed batch summaries.
"""
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from api.services import rso_summary_service
from api.services.health_score_service import calculate_health_score, bulk_calculate_health_scores
from api.services.anomaly_detection_service import detect_attitude_anomalies, score_anomaly_severity
from api.services.maneuver_detection_service import extract_maneuver_events
from api.services.reentry_estimation_service import (
    estimate_reentry,
    extract_perigee_series_from_tle_history,
)
from api.services.similarity_search_service import build_profile, find_similar_objects

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v2/analytics", tags=["analytics"])

_batch_lock = threading.Lock()
_batch_status: Dict[str, Any] = {"running": False, "last_result": None}


def _get_tle_history(norad_id: str, limit: int = 90) -> List[Dict[str, Any]]:
    return rso_summary_service._fetch_tle_history_for_norad(str(norad_id), limit=limit)


def _require_tle_history(norad_id: str) -> List[Dict[str, Any]]:
    history = _get_tle_history(norad_id)
    if not history:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No TLE history found for NORAD {norad_id}. "
                "Fetch historical TLEs via POST /v2/tle-history/{norad_id}/fetch first."
            ),
        )
    return history


@router.get("/health/{norad_id}", summary="RSO health score")
def get_health(norad_id: str):
    """
    Compute and return the calibrated health score (0–100) for the satellite
    identified by *norad_id*, together with per-factor breakdowns.

    The health score is derived from the most recent TLE stored in the local
    TLE-history archive (BSTAR drag, perigee altitude, eccentricity, TLE age).
    """
    history = _require_tle_history(norad_id)
    latest = history[-1]
    line1 = latest.get("line1", "")
    line2 = latest.get("line2", "")

    orbital = rso_summary_service._parse_tle_orbital_params(line1, line2)
    if not orbital:
        raise HTTPException(status_code=422, detail="Unable to parse TLE orbital parameters")

    tle_epoch = rso_summary_service._tle_epoch_to_datetime(line1)
    if tle_epoch is None:
        raise HTTPException(status_code=422, detail="Unable to parse TLE epoch")

    result = calculate_health_score(
        tle_epoch=tle_epoch,
        eccentricity=orbital["eccentricity"],
        perigee_km=orbital["perigee_km"],
        bstar=orbital["bstar"],
    )
    result["norad_id"] = norad_id
    return result


@router.get("/anomalies/{norad_id}", summary="RSO anomaly detection")
def get_anomalies(
    norad_id: str,
    cusum_threshold: float = Query(5.0, description="CUSUM decision threshold"),
    cusum_drift: float = Query(0.5, description="CUSUM allowance parameter"),
):
    """
    Detect anomalous change-points in the historical perigee altitude series
    (derived from TLE history) using the CUSUM algorithm.

    Returns detected change-points, series statistics, and a severity label
    (``none``, ``low``, ``medium``, or ``high``).
    """
    history = _require_tle_history(norad_id)
    epochs, perigees = extract_perigee_series_from_tle_history(history)

    if len(epochs) < 2:
        return {
            "norad_id": norad_id,
            "change_points": [],
            "severity": "none",
            "series_stats": {"n": len(epochs)},
            "message": "Insufficient TLE history for anomaly detection (need >= 2 entries)",
        }

    result = detect_attitude_anomalies(
        timestamps=epochs,
        attitude_values=[float(p) for p in perigees],
        cusum_threshold=cusum_threshold,
        cusum_drift=cusum_drift,
    )
    result["norad_id"] = norad_id
    result["severity"] = score_anomaly_severity(result["change_points"])
    return result


@router.get("/maneuvers/{norad_id}", summary="RSO maneuver detection")
def get_maneuvers(
    norad_id: str,
    dv_threshold_m_s: float = Query(1.0, description="Delta-V threshold in m/s"),
):
    """
    Detect maneuver events in TLE history for *norad_id* by computing SGP4-based
    delta-V residuals between consecutive TLE pairs.

    Events whose residual velocity exceeds *dv_threshold_m_s* are flagged as maneuvers.
    """
    history = _require_tle_history(norad_id)

    result = extract_maneuver_events(
        tle_history=[{"line1": r["line1"], "line2": r["line2"]} for r in history],
        dv_threshold_m_s=dv_threshold_m_s,
    )
    result["norad_id"] = norad_id
    return result


@router.get("/reentry/{norad_id}", summary="RSO re-entry estimation")
def get_reentry(
    norad_id: str,
    reentry_altitude_km: float = Query(80.0, description="Re-entry threshold altitude in km"),
    confidence_days: float = Query(30.0, description="Half-width of date window in days"),
):
    """
    Estimate re-entry date for *norad_id* by fitting linear/exponential decay
    models to the historical perigee altitude series derived from stored TLE history.

    Returns predicted date, confidence window, and model diagnostics.
    Returns ``null`` dates for non-decaying or stable orbits.
    """
    history = _require_tle_history(norad_id)
    epochs, perigees = extract_perigee_series_from_tle_history(history)

    result = estimate_reentry(
        epochs=epochs,
        perigee_altitudes_km=perigees,
        reentry_altitude_km=reentry_altitude_km,
        confidence_days=confidence_days,
    )
    result["norad_id"] = norad_id
    return result


@router.get("/similar/{norad_id}", summary="Find behaviorally similar RSOs")
def get_similar(
    norad_id: str,
    top_k: int = Query(10, ge=1, le=100, description="Maximum results to return"),
    min_similarity: float = Query(0.0, ge=0.0, le=1.0, description="Minimum similarity score"),
):
    """
    Find the most behaviorally similar resident space objects to *norad_id* using
    precomputed similarity profiles stored in ``rso_summary``.

    Falls back to computing the query object's profile on-the-fly from TLE history
    when no cached summary exists.
    """
    results = rso_summary_service.find_similar_from_catalog(
        norad_id=norad_id,
        top_k=top_k,
        min_similarity=min_similarity,
    )
    return {
        "norad_id": norad_id,
        "top_k": top_k,
        "results": results,
        "result_count": len(results),
    }


@router.get("/summary/{norad_id}", summary="Precomputed RSO summary")
def get_summary(norad_id: str, recompute: bool = Query(False, description="Force recomputation even if cached")):
    """
    Return the precomputed ML summary for *norad_id* from the ``rso_summary``
    collection.

    When no cached entry exists (or *recompute* is True), the pipeline is run
    immediately and the result is stored before returning.
    """
    summary = None if recompute else rso_summary_service.get_summary(norad_id)

    if summary is None:
        summary = rso_summary_service.compute_summary_for_norad(norad_id)
        if "error" not in summary:
            rso_summary_service.upsert_summary(summary)
        else:
            err = summary.get("error", "unknown")
            if err == "no_tle_history":
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"No TLE history for NORAD {norad_id}. "
                        "Fetch TLEs via POST /v2/tle-history/{norad_id}/fetch first."
                    ),
                )
            raise HTTPException(status_code=422, detail=f"Could not compute summary: {err}")

    for k in ("_id", "_rev"):
        summary.pop(k, None)

    return summary


@router.get("/overview/batch", summary="Batch overview of all cached summaries")
def get_overview_batch(
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    min_health_score: Optional[float] = Query(None, ge=0.0, le=100.0),
):
    """
    Return a paginated overview of all precomputed RSO summaries, sorted by
    descending health score.

    Use the admin ``POST /v2/admin/analytics/precompute`` endpoint to populate
    or refresh the cache.
    """
    summaries = rso_summary_service.get_all_summaries(
        limit=limit,
        offset=offset,
        min_health_score=min_health_score,
    )
    for s in summaries:
        for k in ("_id", "_rev"):
            s.pop(k, None)

    return {
        "limit": limit,
        "offset": offset,
        "count": len(summaries),
        "results": summaries,
    }


@router.get("/health/batch", summary="Batch health scores for multiple satellites")
def get_health_batch(
    norad_ids: str = Query(..., description="Comma-separated NORAD IDs, e.g. 25544,43013"),
):
    """
    Compute health scores for a list of NORAD IDs in one request.

    Each item in *norad_ids* is looked up in the TLE history archive and scored.
    Missing or unparseable TLEs are reported per-item with an ``error`` field.
    """
    ids = [n.strip() for n in norad_ids.split(",") if n.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="norad_ids must be a non-empty comma-separated list")
    if len(ids) > 200:
        raise HTTPException(status_code=400, detail="norad_ids list must not exceed 200 entries")

    results = []
    for norad_id in ids:
        history = _get_tle_history(norad_id, limit=3)
        if not history:
            results.append({"norad_id": norad_id, "error": "no_tle_history"})
            continue
        latest = history[-1]
        line1 = latest.get("line1", "")
        line2 = latest.get("line2", "")
        orbital = rso_summary_service._parse_tle_orbital_params(line1, line2)
        tle_epoch = rso_summary_service._tle_epoch_to_datetime(line1)
        if not orbital or tle_epoch is None:
            results.append({"norad_id": norad_id, "error": "tle_parse_failed"})
            continue
        try:
            score = calculate_health_score(
                tle_epoch=tle_epoch,
                eccentricity=orbital["eccentricity"],
                perigee_km=orbital["perigee_km"],
                bstar=orbital["bstar"],
            )
            score["norad_id"] = norad_id
            results.append(score)
        except Exception as exc:
            results.append({"norad_id": norad_id, "error": str(exc)})

    return {"count": len(results), "results": results}


class HealthProxyBatchRequest(BaseModel):
    objects: List[Dict[str, Any]]


@router.post("/health/proxy-batch", summary="Proxy batch health score computation")
def proxy_health_batch(body: HealthProxyBatchRequest):
    """
    Compute health scores for a list of RSO parameter dicts supplied in the
    request body (proxy mode — no TLE history lookup required).

    Each object in ``objects`` must have:
    - ``tle_epoch`` (ISO 8601 string or datetime)
    - ``eccentricity`` (float 0–1)
    - ``perigee_km`` (float km)
    - ``bstar`` (float)
    - ``norad_id`` (optional, passed through to results)
    - ``anomaly_count`` (optional int, default 0)
    - ``last_maneuver_date`` (optional ISO 8601 string)
    """
    if not body.objects:
        raise HTTPException(status_code=400, detail="objects list must not be empty")
    if len(body.objects) > 500:
        raise HTTPException(status_code=400, detail="objects list must not exceed 500 entries")

    parsed: List[Dict[str, Any]] = []
    for i, obj in enumerate(body.objects):
        try:
            epoch_raw = obj.get("tle_epoch")
            if isinstance(epoch_raw, str):
                epoch_raw = epoch_raw.replace("Z", "+00:00")
                epoch_dt = datetime.fromisoformat(epoch_raw)
            elif isinstance(epoch_raw, datetime):
                epoch_dt = epoch_raw
            else:
                raise ValueError("tle_epoch is required")

            last_maneuver = None
            lm_raw = obj.get("last_maneuver_date")
            if isinstance(lm_raw, str):
                last_maneuver = datetime.fromisoformat(lm_raw.replace("Z", "+00:00"))

            parsed.append({
                "norad_id": obj.get("norad_id"),
                "tle_epoch": epoch_dt,
                "eccentricity": float(obj["eccentricity"]),
                "perigee_km": float(obj["perigee_km"]),
                "bstar": float(obj.get("bstar", 0.0)),
                "anomaly_count": int(obj.get("anomaly_count", 0)),
                "last_maneuver_date": last_maneuver,
            })
        except (KeyError, ValueError, TypeError) as exc:
            raise HTTPException(
                status_code=422,
                detail=f"objects[{i}] is invalid: {exc}",
            )

    results = bulk_calculate_health_scores(parsed)
    return {"count": len(results), "results": results}
