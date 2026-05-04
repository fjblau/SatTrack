from fastapi import APIRouter, Query
from typing import Optional

from database import (
    get_all_countries,
    get_all_statuses,
    get_all_orbital_bands,
    get_all_congestion_risks,
    get_all_object_types,
    get_all_object_classes,
    count_satellites
)

router = APIRouter(prefix="/v2", tags=["metadata"])


@router.get("/health")
def health_check():
    """Check API and database health"""
    return {
        "status": "ok",
        "api_version": "v2"
    }


@router.get("/countries")
def get_countries_v2():
    """Get list of all countries with satellite registrations"""
    countries = get_all_countries()
    return {
        "count": len(countries),
        "countries": sorted([c for c in countries if c and c.strip()])
    }


@router.get("/statuses")
def get_statuses_v2():
    """Get list of all satellite statuses"""
    statuses = get_all_statuses()
    return {
        "count": len(statuses),
        "statuses": sorted([s for s in statuses if s and s.strip()])
    }


@router.get("/orbital-bands")
def get_orbital_bands_v2():
    """Get list of all orbital bands"""
    orbital_bands = get_all_orbital_bands()
    return {
        "count": len(orbital_bands),
        "orbital_bands": sorted([b for b in orbital_bands if b and b.strip()])
    }


@router.get("/congestion-risks")
def get_congestion_risks_v2():
    """Get list of all congestion risks"""
    congestion_risks = get_all_congestion_risks()
    return {
        "count": len(congestion_risks),
        "congestion_risks": sorted([r for r in congestion_risks if r and r.strip()])
    }


@router.get("/object-types")
def get_object_types_v2():
    """Get list of all object types"""
    object_types = get_all_object_types()
    return {
        "count": len(object_types),
        "object_types": sorted([t for t in object_types if t and t.strip()])
    }


@router.get("/object-classes")
def get_object_classes_v2():
    """Get list of all object classes (DISCOSweb-aligned enum)"""
    object_classes = get_all_object_classes()
    if not object_classes:
        object_classes = [
            "Payload",
            "Rocket Body",
            "Mission-Related Object",
            "Rocket Fragmentation Debris",
            "Payload Fragmentation Debris",
            "Unknown",
        ]
    return {
        "count": len(object_classes),
        "object_classes": sorted([c for c in object_classes if c and c.strip()])
    }


@router.get("/stats")
def get_stats_v2(country: Optional[str] = Query(None), status: Optional[str] = Query(None)):
    """Get statistics about satellites"""
    total = count_satellites()
    filtered = count_satellites(country=country, status=status) if (country or status) else total
    
    return {
        "total_satellites": total,
        "filtered_count": filtered,
        "filters_applied": {
            "country": country,
            "status": status
        }
    }
