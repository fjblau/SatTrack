from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timezone
from typing import Optional, List
import logging

from api.services.tle_history_service import ensure_tle_history, get_position_at
from database.tle_history_ops import get_coverage, find_nearest_tle

router = APIRouter(prefix="/v2/tle-history", tags=["tle"])

logger = logging.getLogger(__name__)


@router.post("/{norad_id}/fetch")
def fetch_tle_history(
    norad_id: str,
    from_date: str = Query(..., description="Start date YYYY-MM-DD"),
    to_date: str = Query(..., description="End date YYYY-MM-DD"),
):
    """
    Ensure historical TLEs for a satellite are stored in the local DB for the given
    date range.  If they are already present no SpaceTrack API call is made.
    Otherwise a single bulk request is issued and all returned TLEs are persisted.

    This is safe to call repeatedly — idempotent when already covered.
    """
    try:
        datetime.strptime(from_date, "%Y-%m-%d")
        datetime.strptime(to_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="from_date and to_date must be YYYY-MM-DD")

    if from_date > to_date:
        raise HTTPException(status_code=400, detail="from_date must be <= to_date")

    result = ensure_tle_history(norad_id, from_date, to_date)
    return result


@router.get("/{norad_id}/coverage")
def get_tle_coverage(norad_id: str):
    """
    Return the stored TLE history coverage for a satellite — what date range is
    already in the local DB, how many TLEs, and when they were last fetched.
    """
    cov = get_coverage(norad_id)
    if not cov:
        return {
            "norad_id": norad_id,
            "covered": False,
            "message": "No TLE history stored for this satellite. Call POST /fetch first.",
        }
    return {
        "norad_id": norad_id,
        "covered": True,
        "covered_from": cov["covered_from"],
        "covered_to": cov["covered_to"],
        "tle_count": cov.get("tle_count", 0),
        "last_fetched_at": cov.get("last_fetched_at"),
    }


@router.get("/{norad_id}/position-at")
def position_at(
    norad_id: str,
    time: str = Query(..., description="ISO 8601 UTC datetime, e.g. 2026-01-15T08:32:11Z"),
):
    """
    Return the satellite's geodetic position (latitude, longitude, altitude_km) at an
    arbitrary historical timestamp, computed via SGP4 propagation from the nearest
    stored TLE.

    TLE history for the target date is fetched from SpaceTrack automatically if not
    already in the DB (one bulk API call per new date range).
    """
    try:
        target_dt = datetime.fromisoformat(time.replace("Z", "+00:00"))
        if target_dt.tzinfo is None:
            target_dt = target_dt.replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="time must be a valid ISO 8601 datetime string, e.g. 2026-01-15T08:32:11Z",
        )

    result = get_position_at(norad_id, target_dt)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No TLE history available for NORAD {norad_id} near {time}. "
                "Ensure SpaceTrack credentials are configured and the satellite is catalogued."
            ),
        )
    return result


@router.post("/observations/positions")
def positions_for_observations(
    body: dict,
):
    """
    Batch-compute historical positions for a list of observations.

    Request body:
        {
          "observations": [
            { "norad_id": "58023", "observation_epoch": "2026-01-15T08:32:11Z", "observation_id": "..." },
            ...
          ]
        }

    For each unique norad_id, TLE history is fetched (one SpaceTrack call per satellite
    per new date range) and all positions are propagated from the nearest stored TLE.

    Returns:
        { "results": [ { "observation_id", "norad_id", "observation_epoch", "position", "tle_used" }, ... ] }
    """
    observations = body.get("observations", [])
    if not observations:
        raise HTTPException(status_code=400, detail="observations list is required and must not be empty")

    from collections import defaultdict
    by_norad = defaultdict(list)
    for obs in observations:
        norad_id = str(obs.get("norad_id", ""))
        epoch_str = obs.get("observation_epoch", "")
        if not norad_id or not epoch_str:
            continue
        by_norad[norad_id].append(obs)

    for norad_id, obs_list in by_norad.items():
        epochs = []
        for obs in obs_list:
            try:
                dt = datetime.fromisoformat(obs["observation_epoch"].replace("Z", "+00:00"))
                epochs.append(dt)
            except ValueError:
                pass
        if not epochs:
            continue
        from_date = min(epochs).strftime("%Y-%m-%d")
        to_date = max(epochs).strftime("%Y-%m-%d")
        ensure_tle_history(norad_id, from_date, to_date)

    results = []
    for obs in observations:
        norad_id = str(obs.get("norad_id", ""))
        epoch_str = obs.get("observation_epoch", "")
        obs_id = obs.get("observation_id") or obs.get("_key") or obs.get("_id")

        if not norad_id or not epoch_str:
            results.append({
                "observation_id": obs_id,
                "norad_id": norad_id,
                "observation_epoch": epoch_str,
                "error": "missing norad_id or observation_epoch",
            })
            continue

        try:
            target_dt = datetime.fromisoformat(epoch_str.replace("Z", "+00:00"))
            if target_dt.tzinfo is None:
                target_dt = target_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            results.append({
                "observation_id": obs_id,
                "norad_id": norad_id,
                "observation_epoch": epoch_str,
                "error": "invalid observation_epoch format",
            })
            continue

        pos = get_position_at(norad_id, target_dt)
        if pos:
            results.append({
                "observation_id": obs_id,
                "norad_id": norad_id,
                "observation_epoch": epoch_str,
                "position": pos["position"],
                "tle_used": pos["tle_used"],
            })
        else:
            results.append({
                "observation_id": obs_id,
                "norad_id": norad_id,
                "observation_epoch": epoch_str,
                "position": None,
                "error": "no TLE available",
            })

    return {"results": results}
