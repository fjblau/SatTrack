from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional, List
import json

from api.services.tle_service import fetch_tle_by_norad_id, parse_tle_fields
from api.services.propagation_service import PropagationService, PropagationError
from api.services.gmat_service import propagate_hifi, GmatError, is_available as gmat_available
from database.ephemeris_ops import (
    save_ephemeris_envelope,
    list_ephemeris_envelopes,
    count_ephemeris_envelopes,
    get_ephemeris_envelope,
    delete_ephemeris_envelope,
)

router = APIRouter(prefix="/v2/ephemeris", tags=["ephemeris"])

MAX_DURATION_HOURS = 168
MAX_STEP_SECONDS = 3600
MIN_STEP_SECONDS = 10


class GenerateEphemerisRequest(BaseModel):
    norad_id: int
    duration_hours: float = 24.0
    step_seconds: int = 60
    propagator: str = "SGP4"


def _build_czml(envelope: dict) -> list:
    norad_id = envelope.get("norad_id")
    satellite_name = envelope.get("satellite_name", f"NORAD {norad_id}")
    valid_from = envelope.get("valid_from", "")
    valid_until = envelope.get("valid_until", "")
    points = envelope.get("ephemeris_points", [])

    preamble = {
        "id": "document",
        "name": f"Ephemeris for {satellite_name}",
        "version": "1.0",
        "clock": {
            "interval": f"{valid_from}/{valid_until}",
            "currentTime": valid_from,
            "multiplier": 60,
        },
    }

    cart_degrees = []
    for pt in points:
        ts = pt.get("timestamp", "")
        geo = pt.get("geodetic", {})
        lat = geo.get("latitude")
        lon = geo.get("longitude")
        alt_km = geo.get("altitude_km")
        if lat is None or lon is None or alt_km is None:
            continue
        cart_degrees.extend([ts, lon, lat, alt_km * 1000])

    satellite_packet = {
        "id": f"satellite/{norad_id}",
        "name": satellite_name,
        "availability": f"{valid_from}/{valid_until}",
        "position": {
            "epoch": valid_from,
            "cartographicDegrees": cart_degrees,
            "interpolationAlgorithm": "LAGRANGE",
            "interpolationDegree": 5,
        },
        "point": {
            "color": {"rgba": [255, 255, 0, 255]},
            "pixelSize": 8,
            "outlineColor": {"rgba": [0, 0, 0, 255]},
            "outlineWidth": 1,
        },
        "path": {
            "material": {
                "solidColor": {"color": {"rgba": [255, 255, 0, 128]}}
            },
            "width": 1,
            "leadTime": 3600,
            "trailTime": 3600,
            "resolution": 60,
        },
        "label": {
            "text": satellite_name,
            "font": "11pt Lucida Console",
            "style": "FILL",
            "fillColor": {"rgba": [255, 255, 255, 255]},
            "outlineColor": {"rgba": [0, 0, 0, 255]},
            "outlineWidth": 2,
            "horizontalOrigin": "LEFT",
            "pixelOffset": {"cartesian2": [12, 0]},
            "show": True,
        },
    }

    return [preamble, satellite_packet]


@router.post("/generate")
def generate_ephemeris(body: GenerateEphemerisRequest):
    """Generate and store an ephemeris envelope for a satellite.

    Fetches the current TLE for the given NORAD ID and propagates it over the
    requested duration and step size using SGP4 (default) or GMAT high-fidelity
    (`HIFI`) propagation. The resulting ephemeris envelope is persisted and a
    summary (envelope ID, validity window, point count, orbital period) is
    returned.
    """
    if body.duration_hours <= 0 or body.duration_hours > MAX_DURATION_HOURS:
        raise HTTPException(
            status_code=400,
            detail=f"duration_hours must be between 1 and {MAX_DURATION_HOURS}"
        )
    if body.step_seconds < MIN_STEP_SECONDS or body.step_seconds > MAX_STEP_SECONDS:
        raise HTTPException(
            status_code=400,
            detail=f"step_seconds must be between {MIN_STEP_SECONDS} and {MAX_STEP_SECONDS}"
        )

    tle = fetch_tle_by_norad_id(str(body.norad_id))
    if not tle:
        raise HTTPException(
            status_code=404,
            detail=f"TLE data not found for NORAD ID {body.norad_id}"
        )

    line1 = tle.get("line1")
    line2 = tle.get("line2")
    if not line1 or not line2:
        raise HTTPException(status_code=400, detail="Invalid TLE data: missing line1 or line2")

    use_gmat = body.propagator.upper() == "HIFI"
    if use_gmat and not gmat_available():
        raise HTTPException(status_code=503, detail="GMAT engine not available on this server")

    try:
        if use_gmat:
            result = propagate_hifi(
                line1=line1,
                line2=line2,
                duration_hours=body.duration_hours,
                step_seconds=body.step_seconds,
            )
        else:
            result = PropagationService.propagate_window(
                line1=line1,
                line2=line2,
                duration_hours=body.duration_hours,
                step_seconds=body.step_seconds,
            )
    except (PropagationError, GmatError) as e:
        raise HTTPException(status_code=400, detail=f"Propagation failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

    envelope = {
        "norad_id": body.norad_id,
        "satellite_name": tle.get("name", f"NORAD {body.norad_id}"),
        "tle_line1": line1,
        "tle_line2": line2,
        "source_tle_epoch": result["tle_epoch"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "step_seconds": body.step_seconds,
        "duration_hours": body.duration_hours,
        "valid_from": result["valid_from"],
        "valid_until": result["valid_until"],
        "propagator": result.get("propagator", body.propagator),
        "orbital_period_minutes": result["orbital_period_minutes"],
        "num_points": result["num_points"],
        "ephemeris_points": result["ephemeris_points"],
    }

    saved = save_ephemeris_envelope(envelope)
    saved_id = saved.get("_key") or saved.get("_id", "")

    return {
        "envelope_id": saved_id,
        "norad_id": body.norad_id,
        "satellite_name": envelope["satellite_name"],
        "generated_at": envelope["generated_at"],
        "valid_from": envelope["valid_from"],
        "valid_until": envelope["valid_until"],
        "step_seconds": body.step_seconds,
        "num_points": result["num_points"],
        "orbital_period_minutes": result["orbital_period_minutes"],
    }


@router.get("")
def list_envelopes(
    norad_id: Optional[int] = Query(None, description="Filter by NORAD ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List stored ephemeris envelopes.

    Returns a paginated list of ephemeris envelopes, optionally filtered by
    NORAD ID, along with the total count matching the filter.
    """
    envelopes = list_ephemeris_envelopes(norad_id=norad_id, limit=limit, offset=offset)
    total = count_ephemeris_envelopes(norad_id=norad_id)

    return {
        "data": envelopes,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{envelope_id}/czml")
def get_czml(envelope_id: str):
    """Export an ephemeris envelope as CZML for CesiumJS visualization.

    Returns a CZML document array (preamble + satellite packet) derived from
    the stored ephemeris points, suitable for ingestion by a Cesium viewer.
    """
    envelope = get_ephemeris_envelope(envelope_id)
    if not envelope:
        raise HTTPException(status_code=404, detail=f"Ephemeris envelope '{envelope_id}' not found")

    czml = _build_czml(envelope)
    return JSONResponse(content=czml, media_type="application/json")


@router.get("/{envelope_id}")
def get_envelope(envelope_id: str):
    """Retrieve a stored ephemeris envelope by ID.

    Returns the full envelope document, including propagation metadata and the
    ephemeris points within its validity window.
    """
    envelope = get_ephemeris_envelope(envelope_id)
    if not envelope:
        raise HTTPException(status_code=404, detail=f"Ephemeris envelope '{envelope_id}' not found")
    return envelope


@router.delete("/{envelope_id}")
def delete_envelope(envelope_id: str):
    """Delete a stored ephemeris envelope by ID.

    Permanently removes the envelope and its ephemeris points from the
    database.
    """
    ok = delete_ephemeris_envelope(envelope_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Ephemeris envelope '{envelope_id}' not found")
    return {"deleted": True, "envelope_id": envelope_id}
