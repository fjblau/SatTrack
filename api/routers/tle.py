from fastapi import APIRouter
from datetime import datetime, timezone

from api.services.tle_service import fetch_tle_by_norad_id

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
