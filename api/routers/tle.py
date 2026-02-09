from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timezone
from typing import Optional

from api.services.tle_service import fetch_tle_by_norad_id
from api.services.propagation_service import propagation_service, PropagationError

router = APIRouter(prefix="/v2", tags=["tle"])


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
