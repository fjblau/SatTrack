from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from api.services.gmat_maneuver_service import run_maneuver_plan
from api.services.gmat_service import is_available as gmat_available
from api.services.tle_service import fetch_tle_by_norad_id
from database.maneuver_plan_ops import (
    count_maneuver_plans,
    delete_maneuver_plan,
    get_maneuver_plan,
    list_maneuver_plans,
    save_maneuver_plan,
)

router = APIRouter(prefix="/v2/kestrel", tags=["kestrel"])


class ManeuverPlanRequest(BaseModel):
    kestrel_norad_id: int
    target_norad_id: int
    mission_type: str = "inspection"
    max_dv_km_s: float = 0.5
    max_time_days: float = 14.0
    epoch: Optional[str] = None


class ManeuverPlanResponse(BaseModel):
    plan_id: str
    kestrel_norad_id: int
    target_norad_id: int
    mission_type: str
    propagator: str
    gmat_verified: bool
    kestrel_alt_km: float
    target_alt_km: float
    kestrel_inc_deg: float
    target_inc_deg: float
    raan_diff_deg: float
    inc_diff_deg: float
    dv1_ms: float
    dv2_ms: float
    dv_total_ms: float
    dv_plane_change_ms: float
    transfer_time_s: float
    wait_time_s: float
    total_time_s: float
    burn1_epoch: Optional[str]
    burn2_epoch: Optional[str]
    closest_approach_km: Optional[float]
    closest_approach_time: Optional[str]
    created_at: str


def _fetch_tle_lines(norad_id: int) -> tuple[str, str]:
    tle = fetch_tle_by_norad_id(str(norad_id))
    if not tle:
        raise HTTPException(status_code=404, detail=f"TLE not found for NORAD ID {norad_id}")
    line1 = tle.get("line1") or tle.get("tle_line1")
    line2 = tle.get("line2") or tle.get("tle_line2")
    if not line1 or not line2:
        raise HTTPException(status_code=400, detail=f"Incomplete TLE for NORAD ID {norad_id}")
    return line1, line2


@router.post("/maneuver-plan", response_model=ManeuverPlanResponse)
def create_maneuver_plan(body: ManeuverPlanRequest):
    """
    Compute a Kestrel rendezvous maneuver plan between two NORAD-catalogued objects.

    Always computes an analytical Hohmann baseline; if GMAT is installed the plan
    is additionally verified with a high-fidelity RK89/EGM96 propagation that returns
    GMAT-computed ΔV values, burn epochs, and closest-approach distance.

    The result is persisted in the database and returned.
    """
    k_line1, k_line2 = _fetch_tle_lines(body.kestrel_norad_id)
    t_line1, t_line2 = _fetch_tle_lines(body.target_norad_id)

    try:
        result = run_maneuver_plan(
            kestrel_line1=k_line1,
            kestrel_line2=k_line2,
            target_line1=t_line1,
            target_line2=t_line2,
            use_gmat=gmat_available(),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Maneuver computation failed: {exc}")

    plan = {
        "kestrel_norad_id": body.kestrel_norad_id,
        "target_norad_id": body.target_norad_id,
        "mission_type": body.mission_type,
        "max_dv_km_s": body.max_dv_km_s,
        "max_time_days": body.max_time_days,
        "requested_epoch": body.epoch,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **result,
    }

    try:
        saved = save_maneuver_plan(plan)
        plan_id = saved.get("_key") or saved.get("_id", "")
    except Exception:
        plan_id = ""

    return ManeuverPlanResponse(
        plan_id=plan_id,
        kestrel_norad_id=body.kestrel_norad_id,
        target_norad_id=body.target_norad_id,
        mission_type=body.mission_type,
        propagator=result.get("propagator", "analytical"),
        gmat_verified=result.get("gmat_verified", False),
        kestrel_alt_km=result["kestrel_alt_km"],
        target_alt_km=result["target_alt_km"],
        kestrel_inc_deg=result["kestrel_inc_deg"],
        target_inc_deg=result["target_inc_deg"],
        raan_diff_deg=result["raan_diff_deg"],
        inc_diff_deg=result["inc_diff_deg"],
        dv1_ms=result["dv1_ms"],
        dv2_ms=result["dv2_ms"],
        dv_total_ms=result["dv_total_ms"],
        dv_plane_change_ms=result["dv_plane_change_ms"],
        transfer_time_s=result["transfer_time_s"],
        wait_time_s=result["wait_time_s"],
        total_time_s=result["total_time_s"],
        burn1_epoch=result.get("burn1_epoch"),
        burn2_epoch=result.get("burn2_epoch"),
        closest_approach_km=result.get("closest_approach_km"),
        closest_approach_time=result.get("closest_approach_time"),
        created_at=plan["created_at"],
    )


@router.get("/maneuver-plans")
def list_plans(
    kestrel_norad_id: Optional[int] = Query(None),
    target_norad_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List saved Kestrel maneuver plans with optional NORAD ID filters."""
    plans = list_maneuver_plans(
        kestrel_norad_id=kestrel_norad_id,
        target_norad_id=target_norad_id,
        limit=limit,
        offset=offset,
    )
    total = count_maneuver_plans(
        kestrel_norad_id=kestrel_norad_id,
        target_norad_id=target_norad_id,
    )
    return {"data": plans, "total": total, "limit": limit, "offset": offset}


@router.get("/maneuver-plans/{plan_id}")
def get_plan(plan_id: str) -> dict[str, Any]:
    """Retrieve a single saved maneuver plan by ID."""
    plan = get_maneuver_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Maneuver plan '{plan_id}' not found")
    return plan


@router.delete("/maneuver-plans/{plan_id}")
def remove_plan(plan_id: str) -> dict[str, Any]:
    """Delete a saved maneuver plan."""
    ok = delete_maneuver_plan(plan_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Maneuver plan '{plan_id}' not found")
    return {"deleted": True, "plan_id": plan_id}
