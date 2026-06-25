"""
RSO Summary Service — precompute and cache ML outputs for all catalogued satellites.

Runs the full ML pipeline (health score, anomaly detection, maneuver detection,
re-entry estimation, similarity profiling) for every NORAD ID that has TLE history
stored in the database and upserts results into the ``rso_summary`` collection.

The service is designed to be called from a scheduled batch job or an admin trigger.
Each document in ``rso_summary`` is keyed by NORAD ID and contains a snapshot of
all ML signals at the time of computation.
"""
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import database.connection as db_conn
from database.connection import (
    COLLECTION_RSO_SUMMARY,
    COLLECTION_TLE_HISTORY,
    COLLECTION_NAME,
)
from api.services.health_score_service import calculate_health_score
from api.services.anomaly_detection_service import detect_attitude_anomalies, score_anomaly_severity
from api.services.maneuver_detection_service import extract_maneuver_events
from api.services.reentry_estimation_service import (
    estimate_reentry,
    extract_perigee_series_from_tle_history,
)
from api.services.similarity_search_service import build_profile

logger = logging.getLogger(__name__)

_EARTH_R_KM = 6378.137
_MU = 398600.4418


def _db():
    if db_conn.db is None:
        raise RuntimeError("Database not connected")
    return db_conn.db


def _tle_epoch_to_datetime(line1: str) -> Optional[datetime]:
    try:
        year_raw = int(line1[18:20])
        day = float(line1[20:32])
        year = 2000 + year_raw if year_raw < 57 else 1900 + year_raw
        return datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(days=day - 1.0)
    except (ValueError, IndexError):
        return None


def _parse_tle_orbital_params(line1: str, line2: str) -> Dict[str, Any]:
    try:
        ecc = float("0." + line2[26:33].strip())
        inclination = float(line2[8:16].strip())
        mm = float(line2[52:63].strip())
        n = mm * 2 * math.pi / 86400.0
        a = (_MU / (n * n)) ** (1.0 / 3.0)
        perigee_km = a * (1 - ecc) - _EARTH_R_KM
        apogee_km = a * (1 + ecc) - _EARTH_R_KM
        mean_alt = (perigee_km + apogee_km) / 2.0
        period_min = (2 * math.pi / n) / 60.0
        bstar_str = line1[53:61].strip()
        bstar = 0.0
        if bstar_str and bstar_str not in ("00000-0", "00000+0"):
            try:
                if len(bstar_str) >= 6:
                    mantissa = float(bstar_str[:5]) * 1e-5
                    exp = int(bstar_str[5:])
                    bstar = mantissa * (10 ** exp)
            except (ValueError, IndexError):
                bstar = 0.0
        return {
            "eccentricity": ecc,
            "inclination_deg": inclination,
            "perigee_km": perigee_km,
            "apogee_km": apogee_km,
            "mean_altitude_km": mean_alt,
            "orbital_period_min": period_min,
            "bstar": bstar,
        }
    except (ValueError, IndexError) as exc:
        logger.warning(f"Failed to parse TLE orbital params: {exc}")
        return {}


def _fetch_tle_history_for_norad(norad_id: str, limit: int = 90) -> List[Dict[str, Any]]:
    aql = """
    FOR t IN @@col
        FILTER t.norad_id == @norad_id
        SORT t.tle_epoch DESC
        LIMIT @limit
        RETURN t
    """
    try:
        cursor = _db().aql.execute(
            aql,
            bind_vars={
                "@col": COLLECTION_TLE_HISTORY,
                "norad_id": str(norad_id),
                "limit": limit,
            },
        )
        results = list(cursor)
        results.sort(key=lambda r: r.get("tle_epoch", ""))
        return results
    except Exception as exc:
        logger.error(f"_fetch_tle_history_for_norad failed for {norad_id}: {exc}")
        return []


def _fetch_all_norad_ids_with_history() -> List[str]:
    aql = """
    FOR t IN @@col
        COLLECT norad_id = t.norad_id
        RETURN norad_id
    """
    try:
        cursor = _db().aql.execute(
            aql,
            bind_vars={"@col": COLLECTION_TLE_HISTORY},
        )
        return list(cursor)
    except Exception as exc:
        logger.error(f"_fetch_all_norad_ids_with_history failed: {exc}")
        return []


def _fetch_all_norad_ids_from_catalog(limit: int = 5000) -> List[str]:
    aql = """
    FOR s IN @@col
        FILTER s.identifier != null
        LIMIT @limit
        RETURN s.identifier
    """
    try:
        cursor = _db().aql.execute(
            aql,
            bind_vars={"@col": COLLECTION_NAME, "limit": limit},
        )
        return [str(r) for r in cursor if r]
    except Exception as exc:
        logger.error(f"_fetch_all_norad_ids_from_catalog failed: {exc}")
        return []


def compute_summary_for_norad(norad_id: str) -> Dict[str, Any]:
    """
    Run the full ML pipeline for a single NORAD ID and return the summary dict.

    Returns an empty dict with an ``error`` key when no TLE history is available.
    """
    norad_id = str(norad_id)
    now = datetime.now(timezone.utc)

    history = _fetch_tle_history_for_norad(norad_id, limit=90)
    if not history:
        return {
            "norad_id": norad_id,
            "error": "no_tle_history",
            "updated_at": now.isoformat(),
        }

    latest = history[-1]
    line1 = latest.get("line1", "")
    line2 = latest.get("line2", "")

    orbital = _parse_tle_orbital_params(line1, line2)
    if not orbital:
        return {
            "norad_id": norad_id,
            "error": "tle_parse_failed",
            "updated_at": now.isoformat(),
        }

    tle_epoch = _tle_epoch_to_datetime(line1)

    health_result: Dict[str, Any] = {}
    if tle_epoch:
        try:
            health_result = calculate_health_score(
                tle_epoch=tle_epoch,
                eccentricity=orbital["eccentricity"],
                perigee_km=orbital["perigee_km"],
                bstar=orbital["bstar"],
            )
        except Exception as exc:
            logger.warning(f"health score failed for {norad_id}: {exc}")

    maneuver_result: Dict[str, Any] = {}
    try:
        maneuver_result = extract_maneuver_events(
            tle_history=[{"line1": r["line1"], "line2": r["line2"]} for r in history],
        )
    except Exception as exc:
        logger.warning(f"maneuver detection failed for {norad_id}: {exc}")

    maneuver_count = maneuver_result.get("maneuver_count", 0)
    maneuvers_per_year = 0.0
    if history and maneuver_count:
        try:
            first_epoch = _tle_epoch_to_datetime(history[0]["line1"])
            last_epoch = _tle_epoch_to_datetime(history[-1]["line1"])
            if first_epoch and last_epoch:
                span_years = max(
                    (last_epoch - first_epoch).total_seconds() / (365.25 * 86400), 1 / 365.0
                )
                maneuvers_per_year = maneuver_count / span_years
        except Exception:
            pass

    epochs, perigees = extract_perigee_series_from_tle_history(history)

    reentry_result: Dict[str, Any] = {}
    if len(epochs) >= 3:
        try:
            reentry_result = estimate_reentry(epochs=epochs, perigee_altitudes_km=perigees)
        except Exception as exc:
            logger.warning(f"reentry estimation failed for {norad_id}: {exc}")

    decay_rate = reentry_result.get("current_decay_rate_km_day", 0.0) or 0.0

    attitude_values = [float(p) for p in perigees]
    anomaly_result: Dict[str, Any] = {}
    if len(epochs) >= 2:
        try:
            anomaly_result = detect_attitude_anomalies(
                timestamps=epochs,
                attitude_values=attitude_values,
            )
        except Exception as exc:
            logger.warning(f"anomaly detection failed for {norad_id}: {exc}")

    severity = score_anomaly_severity(anomaly_result.get("change_points", []))

    similarity_profile = {}
    try:
        similarity_profile = build_profile(
            inclination_deg=orbital.get("inclination_deg", 0.0),
            eccentricity=orbital.get("eccentricity", 0.0),
            mean_altitude_km=orbital.get("mean_altitude_km", 400.0),
            decay_rate_km_day=decay_rate,
            maneuvers_per_year=maneuvers_per_year,
            orbital_period_min=orbital.get("orbital_period_min", 90.0),
        )
    except Exception as exc:
        logger.warning(f"similarity profile failed for {norad_id}: {exc}")

    return {
        "norad_id": norad_id,
        "updated_at": now.isoformat(),
        "health_score": health_result.get("health_score"),
        "health_factors": health_result.get("factors"),
        "anomaly_severity": severity,
        "anomaly_change_points": anomaly_result.get("change_points", []),
        "anomaly_series_stats": anomaly_result.get("series_stats"),
        "maneuver_count": maneuver_count,
        "maneuver_events": maneuver_result.get("maneuver_events", []),
        "maneuvers_per_year": round(maneuvers_per_year, 4),
        "reentry_predicted_date": reentry_result.get("predicted_reentry_date"),
        "reentry_window_earliest": reentry_result.get("window_earliest"),
        "reentry_window_latest": reentry_result.get("window_latest"),
        "reentry_model_selected": reentry_result.get("model_selected"),
        "decay_rate_km_day": decay_rate,
        "similarity_profile": similarity_profile,
        "orbital": {
            "eccentricity": orbital.get("eccentricity"),
            "inclination_deg": orbital.get("inclination_deg"),
            "perigee_km": orbital.get("perigee_km"),
            "apogee_km": orbital.get("apogee_km"),
            "mean_altitude_km": orbital.get("mean_altitude_km"),
            "orbital_period_min": orbital.get("orbital_period_min"),
            "bstar": orbital.get("bstar"),
        },
        "tle_epoch": tle_epoch.isoformat() if tle_epoch else None,
        "tle_history_count": len(history),
    }


def upsert_summary(summary: Dict[str, Any]) -> None:
    """Upsert a summary document into rso_summary, keyed by norad_id."""
    norad_id = summary.get("norad_id")
    if not norad_id:
        return
    col = _db().collection(COLLECTION_RSO_SUMMARY)
    key = str(norad_id)
    doc = dict(summary)
    doc["_key"] = key
    try:
        if col.has(key):
            col.update(doc)
        else:
            col.insert(doc)
    except Exception as exc:
        logger.error(f"upsert_summary failed for {norad_id}: {exc}")


def get_summary(norad_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve the cached summary for a NORAD ID, or None if not yet computed."""
    try:
        col = _db().collection(COLLECTION_RSO_SUMMARY)
        key = str(norad_id)
        if col.has(key):
            return col.get(key)
        return None
    except Exception as exc:
        logger.error(f"get_summary failed for {norad_id}: {exc}")
        return None


def get_all_summaries(
    limit: int = 500,
    offset: int = 0,
    min_health_score: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Return all cached summaries with optional health score filter."""
    filters = ""
    bind: Dict[str, Any] = {"@col": COLLECTION_RSO_SUMMARY, "limit": limit, "offset": offset}
    if min_health_score is not None:
        filters = "FILTER doc.health_score >= @min_health"
        bind["min_health"] = min_health_score

    aql = f"""
    FOR doc IN @@col
        {filters}
        SORT doc.health_score DESC
        LIMIT @offset, @limit
        RETURN doc
    """
    try:
        cursor = _db().aql.execute(aql, bind_vars=bind)
        return list(cursor)
    except Exception as exc:
        logger.error(f"get_all_summaries failed: {exc}")
        return []


def run_batch_precomputation(
    norad_ids: Optional[List[str]] = None,
    max_objects: int = 1000,
) -> Dict[str, Any]:
    """
    Run the precomputation pipeline for a list of NORAD IDs (or all with TLE history).

    Args:
        norad_ids: Explicit list to process. When None, all NORAD IDs with stored
                   TLE history are processed up to *max_objects*.
        max_objects: Upper bound on the number of objects to process in one run.

    Returns:
        Summary dict with counts of processed, succeeded, and failed objects.
    """
    if norad_ids is None:
        norad_ids = _fetch_all_norad_ids_with_history()

    norad_ids = norad_ids[:max_objects]

    succeeded = 0
    failed = 0
    errors: List[Dict[str, str]] = []

    started_at = datetime.now(timezone.utc).isoformat()

    for norad_id in norad_ids:
        try:
            summary = compute_summary_for_norad(norad_id)
            if "error" not in summary:
                upsert_summary(summary)
                succeeded += 1
            else:
                failed += 1
                errors.append({"norad_id": norad_id, "error": summary.get("error", "unknown")})
        except Exception as exc:
            failed += 1
            errors.append({"norad_id": norad_id, "error": str(exc)})
            logger.error(f"Batch precomputation failed for {norad_id}: {exc}")

    finished_at = datetime.now(timezone.utc).isoformat()

    return {
        "started_at": started_at,
        "finished_at": finished_at,
        "total_requested": len(norad_ids),
        "succeeded": succeeded,
        "failed": failed,
        "errors": errors[:50],
    }


def find_similar_from_catalog(
    norad_id: str,
    top_k: int = 10,
    min_similarity: float = 0.0,
) -> List[Dict[str, Any]]:
    """
    Find the most similar RSOs to *norad_id* from the precomputed summary catalog.

    Uses the similarity profiles stored in ``rso_summary`` to rank neighbors by
    behavioral similarity.
    """
    from api.services.similarity_search_service import find_similar_objects

    query_summary = get_summary(norad_id)
    if not query_summary or not query_summary.get("similarity_profile"):
        query_summary = compute_summary_for_norad(norad_id)

    query_profile = query_summary.get("similarity_profile", {})
    if not query_profile or not query_profile.get("features"):
        return []

    aql = """
    FOR doc IN @@col
        FILTER doc.norad_id != @norad_id
        FILTER doc.similarity_profile != null
        FILTER doc.similarity_profile.features != null
        LIMIT 2000
        RETURN { norad_id: doc.norad_id, profile: doc.similarity_profile, health_score: doc.health_score }
    """
    try:
        cursor = _db().aql.execute(
            aql,
            bind_vars={"@col": COLLECTION_RSO_SUMMARY, "norad_id": str(norad_id)},
        )
        catalog = list(cursor)
    except Exception as exc:
        logger.error(f"find_similar_from_catalog AQL failed: {exc}")
        return []

    return find_similar_objects(
        query_profile=query_profile,
        catalog=catalog,
        top_k=top_k,
        min_similarity=min_similarity,
    )
