from fastapi import APIRouter, Query
from typing import Optional
import math

from database import find_satellite, search_satellites, count_satellites
import database.connection as db_conn
from api.utils.converters import filter_nan_values

router = APIRouter(prefix="/v2", tags=["satellites"])


@router.get("/search")
def search_satellites_v2(
    q: Optional[str] = Query(None, description="Search query (name, designator, registration number)"),
    country: Optional[str] = Query(None, description="Filter by country"),
    status: Optional[str] = Query(None, description="Filter by status"),
    orbital_band: Optional[str] = Query(None, description="Filter by orbital band"),
    congestion_risk: Optional[str] = Query(None, description="Filter by congestion risk"),
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0)
):
    """
    Search satellites in MongoDB.
    Supports filtering by country, status, orbital band, and congestion risk.
    """
    results = search_satellites(
        query=q or "",
        country=country,
        status=status,
        orbital_band=orbital_band,
        congestion_risk=congestion_risk,
        limit=limit,
        skip=skip
    )
    
    total_count = count_satellites(
        query=q or "",
        country=country,
        status=status,
        orbital_band=orbital_band,
        congestion_risk=congestion_risk
    )
    
    data = []
    for r in results:
        canonical = r.get("canonical", {})
        safe_canonical = filter_nan_values(canonical, recursive=False)
        
        data.append({
            "identifier": r.get("identifier"),
            "canonical": safe_canonical,
            "sources_available": r.get("metadata", {}).get("sources_available", [])
        })
    
    return {
        "count": total_count,
        "skip": skip,
        "limit": limit,
        "data": data
    }


@router.get("/satellite/{identifier}")
def get_satellite_v2(identifier: str):
    """
    Get detailed satellite information from ArangoDB.
    Identifier can be the document identifier, international designator, or registration number.
    """
    sat = (find_satellite(identifier=identifier) or 
           find_satellite(international_designator=identifier) or 
           find_satellite(registration_number=identifier))
    
    if sat:
        canonical = sat.get("canonical", {})
        safe_canonical = {}
        for k, v in canonical.items():
            if k != '_id':
                if isinstance(v, dict):
                    safe_v = {}
                    for kk, vv in v.items():
                        if not (isinstance(vv, float) and (math.isnan(vv) or math.isinf(vv))):
                            safe_v[kk] = vv
                    safe_canonical[k] = safe_v
                elif not (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
                    safe_canonical[k] = v
        
        sources = sat.get("sources", {})
        safe_sources = {}
        for k, v in sources.items():
            if k != '_id' and isinstance(v, dict):
                safe_v = {}
                for kk, vv in v.items():
                    if kk != '_id' and not (isinstance(vv, float) and (math.isnan(vv) or math.isinf(vv))):
                        safe_v[kk] = vv
                safe_sources[k] = safe_v
        
        return {
            "data": {
                "identifier": sat.get("identifier"),
                "canonical": safe_canonical,
                "sources": safe_sources,
                "metadata": sat.get("metadata", {})
            }
        }
    else:
        return {"error": "Satellite not found"}, 404


@router.get("/registration-documents/{doc_id}")
def get_registration_document(doc_id: str):
    """
    Get registration document details from ArangoDB.
    """
    try:
        # Query the registration_documents collection
        query = """
        FOR doc IN registration_documents
            FILTER doc._key == @doc_id
            LIMIT 1
            RETURN doc
        """
        
        cursor = db_conn.db.aql.execute(query, bind_vars={'doc_id': doc_id})
        results = list(cursor)
        
        if results:
            doc = results[0]
            # Remove internal ArangoDB fields
            clean_doc = {k: v for k, v in doc.items() if not k.startswith('_')}
            return {"data": clean_doc}
        else:
            return {"error": "Registration document not found"}, 404
    except Exception as e:
        return {"error": f"Failed to fetch registration document: {str(e)}"}, 500
