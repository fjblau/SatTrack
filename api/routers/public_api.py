from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone

from database import search_satellites
from api.services.tle_service import fetch_tle_by_norad_id
from api.services.propagation_service import PropagationService, PropagationError
from api.services.orbital_service import OrbitalService

router = APIRouter(prefix="/v2/public", tags=["public"])


@router.get("/objects/search")
def public_search_objects(
    q: str = Query("", description="Search by name, NORAD ID, or international designator"),
    limit: int = Query(10, ge=1, le=50),
):
    """Public minimal object search — returns name + NORAD ID only. No authentication required."""
    results = search_satellites(query=q, limit=limit)
    items = []
    for doc in results:
        canonical = doc.get("canonical", {})
        norad_id = canonical.get("norad_cat_id")
        name = canonical.get("name") or canonical.get("object_name") or ""
        if norad_id:
            items.append({
                "name": name or f"NORAD {norad_id}",
                "norad_id": str(norad_id),
            })
    return {"results": items}


@router.get("/passes/{norad_id}")
def public_get_passes(
    norad_id: str,
    lat: float = Query(..., ge=-90, le=90, description="Observer latitude (degrees)"),
    lon: float = Query(..., ge=-180, le=180, description="Observer longitude (degrees)"),
    elevation_m: float = Query(0.0, ge=0, description="Observer elevation above sea level (meters)"),
    min_elevation_deg: float = Query(10.0, ge=0, le=90, description="Minimum elevation angle for a pass (degrees)"),
    hours_ahead: float = Query(24.0, gt=0, le=336, description="Search window in hours"),
    num_passes: int = Query(30, ge=1, le=50, description="Maximum number of passes to return"),
):
    """Public pass prediction by NORAD ID — no authentication required."""
    tle = fetch_tle_by_norad_id(norad_id)
    if not tle:
        raise HTTPException(status_code=404, detail=f"TLE not found for NORAD {norad_id}")

    line1 = tle.get("line1")
    line2 = tle.get("line2")
    if not line1 or not line2:
        raise HTTPException(status_code=400, detail="Invalid TLE data")

    tle_epoch = OrbitalService.extract_tle_epoch(line1)
    tle_age_hours = None
    if tle_epoch:
        tle_age_hours = round(
            (datetime.now(timezone.utc) - tle_epoch).total_seconds() / 3600, 1
        )

    satellite_name = tle.get("name", f"NORAD {norad_id}")

    try:
        passes = PropagationService.find_passes(
            line1=line1,
            line2=line2,
            satellite_name=satellite_name,
            lat=lat,
            lon=lon,
            elevation_m=elevation_m,
            min_elevation_deg=min_elevation_deg,
            hours_ahead=hours_ahead,
            num_passes=num_passes,
        )
    except PropagationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

    return {
        "norad_id": norad_id,
        "satellite_name": satellite_name,
        "observer": {
            "latitude": lat,
            "longitude": lon,
            "elevation_m": elevation_m,
            "min_elevation_deg": min_elevation_deg,
        },
        "search_window_hours": hours_ahead,
        "tle_age_hours": tle_age_hours,
        "passes": passes,
        "num_passes": len(passes),
    }


class TlePassRequest(BaseModel):
    tle_text: str
    lat: float
    lon: float
    elevation_m: float = 0.0
    min_elevation_deg: float = 10.0
    hours_ahead: float = 24.0
    num_passes: int = 30


@router.post("/passes/tle")
def public_passes_from_tle(body: TlePassRequest):
    """Public pass prediction from raw TLE text — no authentication required.

    Accepts 2-line (TLE line 1 + line 2) or 3-line (name + line 1 + line 2) TLE format.
    """
    lines = [line.strip() for line in body.tle_text.strip().splitlines() if line.strip()]

    if len(lines) == 3:
        satellite_name, line1, line2 = lines[0], lines[1], lines[2]
    elif len(lines) == 2:
        line1, line2 = lines[0], lines[1]
        satellite_name = f"NORAD {line1[2:7].strip()}"
    else:
        raise HTTPException(
            status_code=400,
            detail="TLE must be 2 lines (TLE line 1 + line 2) or 3 lines (name + line 1 + line 2)",
        )

    if not line1.startswith("1 ") or not line2.startswith("2 "):
        raise HTTPException(
            status_code=400,
            detail="Invalid TLE format: line 1 must start with '1 ' and line 2 with '2 '",
        )

    tle_epoch = OrbitalService.extract_tle_epoch(line1)
    tle_age_hours = None
    if tle_epoch:
        tle_age_hours = round(
            (datetime.now(timezone.utc) - tle_epoch).total_seconds() / 3600, 1
        )

    try:
        passes = PropagationService.find_passes(
            line1=line1,
            line2=line2,
            satellite_name=satellite_name,
            lat=body.lat,
            lon=body.lon,
            elevation_m=body.elevation_m,
            min_elevation_deg=body.min_elevation_deg,
            hours_ahead=body.hours_ahead,
            num_passes=body.num_passes,
        )
    except PropagationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

    return {
        "norad_id": None,
        "satellite_name": satellite_name,
        "observer": {
            "latitude": body.lat,
            "longitude": body.lon,
            "elevation_m": body.elevation_m,
            "min_elevation_deg": body.min_elevation_deg,
        },
        "search_window_hours": body.hours_ahead,
        "tle_age_hours": tle_age_hours,
        "passes": passes,
        "num_passes": len(passes),
    }
