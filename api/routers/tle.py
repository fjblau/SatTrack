from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional

from api.services.tle_service import fetch_tle_by_norad_id, fetch_tle_by_intl_des, parse_tle_fields
from api.services.propagation_service import PropagationService, propagation_service, PropagationError
from api.services.orbital_service import OrbitalService
from database.operations import update_satellite_tle

router = APIRouter(prefix="/v2", tags=["tle"])


class TlePersistRequest(BaseModel):
    identifier: str


@router.post("/tle/{norad_id}/persist")
def persist_tle(norad_id: str, body: TlePersistRequest):
    """Fetch, parse, and persist TLE data into the satellite document."""
    tle = fetch_tle_by_norad_id(norad_id)

    if not tle:
        raise HTTPException(
            status_code=404,
            detail=f"TLE data not found for NORAD ID {norad_id}"
        )

    line1 = tle.get("line1")
    line2 = tle.get("line2")
    name = tle.get("name", f"NORAD {norad_id}")

    if not line1 or not line2:
        raise HTTPException(
            status_code=400,
            detail="Invalid TLE data: missing line1 or line2"
        )

    returned_norad = str(tle.get("norad_cat_id", "")).strip().lstrip("0")
    requested_norad = str(norad_id).strip().lstrip("0")
    if returned_norad and returned_norad != requested_norad:
        raise HTTPException(
            status_code=422,
            detail=(
                f"TLE NORAD mismatch: requested {norad_id} but source returned {tle.get('norad_cat_id')}. "
                f"Refusing to persist to prevent wrong TLE being stored on object."
            )
        )

    parsed = parse_tle_fields(name, line1, line2)

    updated = update_satellite_tle(
        identifier=body.identifier,
        norad_id=norad_id,
        tle_data=parsed,
    )

    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Satellite with identifier '{body.identifier}' not found in database"
        )

    return {
        "tle": parsed,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/tle/{norad_id}")
def get_current_tle(norad_id: str):
    """Get current TLE data from TLE API for a satellite by NORAD ID"""
    tle = fetch_tle_by_norad_id(norad_id)
    
    if tle:
        return {
            "data": tle,
            "source": tle.get("source", "tle-api"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": None,
            "message": f"TLE data not found for NORAD ID {norad_id}.",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, 200


@router.get("/tle/intldes/{intl_des:path}")
def get_tle_by_intl_des(intl_des: str):
    """Get current TLE data from CelesTrak by International Designator.

    Useful for debris objects that may not have a NORAD ID stored locally.
    Returns TLE data including the resolved NORAD catalog ID when available.
    """
    tle = fetch_tle_by_intl_des(intl_des)

    if tle:
        return {
            "data": tle,
            "source": "celestrak",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        return {
            "data": None,
            "message": f"TLE data not found for international designator '{intl_des}' on CelesTrak.",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@router.get("/tle/{norad_id}/orbit")
def calculate_orbit(
    norad_id: str,
    start_time: Optional[str] = Query(None, description="Start time in ISO 8601 format (defaults to current UTC)"),
    interval_minutes: int = Query(1, ge=1, le=10, description="Interval between positions in minutes (1-10)")
):
    """
    Calculate orbital positions for one complete orbit using SGP4 propagation.
    
    Coordinate Accuracy:
    - Uses WGS84 ellipsoid model for accurate geodetic coordinates
    - Accounts for Earth rotation via GMST (Greenwich Mean Sidereal Time)
    - Typical accuracy: <0.1° lat/lon, <1 km altitude vs external references (N2YO)
    
    Returns:
    - TLE epoch position (position at TLE creation time)
    - Current position (position at start_time or now)
    - Future positions (one complete orbit from start_time)
    - Orbital parameters
    
    Position Format:
    - timestamp: ISO 8601 UTC timestamp
    - eci: Earth-Centered Inertial coordinates (x, y, z in km)
    - geodetic: Geographic coordinates (latitude, longitude in degrees, altitude in km)
    """
    tle = fetch_tle_by_norad_id(norad_id)
    
    if not tle:
        raise HTTPException(
            status_code=404,
            detail=f"TLE data not found for NORAD ID {norad_id}"
        )
    
    line1 = tle.get("line1")
    line2 = tle.get("line2")
    
    if not line1 or not line2:
        raise HTTPException(
            status_code=400,
            detail="Invalid TLE data: missing line1 or line2"
        )
    
    parsed_start_time = None
    if start_time:
        try:
            parsed_start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            if parsed_start_time.tzinfo is None:
                parsed_start_time = parsed_start_time.replace(tzinfo=timezone.utc)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid start_time format. Use ISO 8601 format: {str(e)}"
            )
    
    try:
        orbit_data = propagation_service.propagate_orbit(
            line1=line1,
            line2=line2,
            start_time=parsed_start_time,
            interval_minutes=interval_minutes
        )
        
        return {
            "satellite": {
                "norad_id": norad_id,
                "name": tle.get("name", f"NORAD {norad_id}")
            },
            "tle": {
                "source": tle.get("source", "tle-api"),
                "date": tle.get("date"),
                "epoch": orbit_data["tle_epoch"]
            },
            "orbital_parameters": {
                "period_minutes": orbit_data["orbital_period_minutes"],
                "interval_minutes": orbit_data["interval_minutes"],
                "num_positions": orbit_data["num_positions"]
            },
            "tle_epoch_position": orbit_data["tle_epoch_position"],
            "current_position": orbit_data["current_position"],
            "future_positions": orbit_data["future_positions"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except PropagationError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Orbit propagation failed: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error during orbit calculation: {str(e)}"
        )


@router.get("/tle/{norad_id}/passes")
def get_passes(
    norad_id: str,
    lat: float = Query(..., ge=-90, le=90, description="Observer latitude (degrees)"),
    lon: float = Query(..., ge=-180, le=180, description="Observer longitude (degrees)"),
    elevation_m: float = Query(0.0, ge=0, description="Observer elevation above sea level (meters)"),
    min_elevation_deg: float = Query(10.0, ge=0, le=90, description="Minimum elevation angle for a pass (degrees)"),
    hours_ahead: float = Query(24.0, gt=0, le=168, description="Search window in hours (max 168)"),
    num_passes: int = Query(5, ge=1, le=20, description="Maximum number of passes to return"),
):
    """
    Find upcoming passes of a satellite over a ground observer location.

    Returns each pass with rise/culmination/set times and azimuths, duration,
    max elevation, a 1–3 star visibility quality score, and an optical visibility
    flag (true when the satellite is sunlit and the observer is in darkness).
    """
    tle = fetch_tle_by_norad_id(norad_id)

    if not tle:
        raise HTTPException(status_code=404, detail=f"TLE data not found for NORAD ID {norad_id}")

    line1 = tle.get("line1")
    line2 = tle.get("line2")

    if not line1 or not line2:
        raise HTTPException(status_code=400, detail="Invalid TLE data: missing line1 or line2")

    tle_epoch = OrbitalService.extract_tle_epoch(line1)
    tle_age_hours = None
    if tle_epoch:
        tle_age_hours = round((datetime.now(timezone.utc) - tle_epoch).total_seconds() / 3600, 1)

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
        raise HTTPException(status_code=400, detail=f"Pass calculation failed: {str(e)}")
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
