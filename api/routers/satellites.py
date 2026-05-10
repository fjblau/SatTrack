from fastapi import APIRouter, Query
from typing import Optional
import logging
from datetime import datetime, timezone

from database import find_satellite, search_satellites, count_satellites
import database.connection as db_conn
from api.utils.converters import filter_nan_values
from api.services.tle_service import check_decay_from_celestrak

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v2", tags=["satellites"])


@router.get("/search")
def search_satellites_v2(
    q: Optional[str] = Query(None, description="Search query (name, designator, registration number)"),
    country: Optional[str] = Query(None, description="Filter by country"),
    status: Optional[str] = Query(None, description="Filter by status"),
    orbital_band: Optional[str] = Query(None, description="Filter by orbital band"),
    congestion_risk: Optional[str] = Query(None, description="Filter by congestion risk"),
    object_type: Optional[str] = Query(None, description="Filter by object type"),
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0),
    sort_by: Optional[str] = Query(None, description="Sort by column name"),
    sort_order: Optional[str] = Query(None, description="Sort order (ASC or DESC)")
):
    """
    Search satellites in MongoDB.
    Supports filtering by country, status, orbital band, and congestion risk.
    Supports sorting by any column with ascending or descending order.
    """
    results = search_satellites(
        query=q or "",
        country=country,
        status=status,
        orbital_band=orbital_band,
        congestion_risk=congestion_risk,
        object_type=object_type,
        limit=limit,
        skip=skip,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    total_count = count_satellites(
        query=q or "",
        country=country,
        status=status,
        orbital_band=orbital_band,
        congestion_risk=congestion_risk,
        object_type=object_type
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

        if canonical.get("status") == "in orbit":
            norad_id = canonical.get("norad_cat_id")
            if norad_id:
                satcat = check_decay_from_celestrak(str(norad_id))
                if satcat and satcat.get("decay_date"):
                    ts = datetime.now(timezone.utc).isoformat()
                    transformation = {
                        "timestamp": ts,
                        "source_field": "celestrak/satcat",
                        "target_field": "canonical.status + canonical.date_of_decay_or_change",
                        "value": {
                            "status": "decayed",
                            "date_of_decay_or_change": satcat["decay_date"],
                        },
                        "promoted_by": "lazy_celestrak_decay_check",
                        "reason": f"CelesTrak satcat confirms decay on {satcat['decay_date']} (ops_status={satcat.get('ops_status_code')})",
                    }
                    try:
                        db_conn.db.aql.execute("""
                            FOR doc IN objects
                                FILTER doc._key == @key
                                UPDATE doc WITH {
                                    canonical: MERGE(doc.canonical, {
                                        status: "decayed",
                                        date_of_decay_or_change: @decay_date,
                                        updated_at: @ts
                                    }),
                                    metadata: MERGE(doc.metadata, {
                                        transformations: APPEND(doc.metadata.transformations || [], [@transformation]),
                                        last_updated_at: @ts
                                    })
                                } IN objects
                        """, bind_vars={
                            "key": sat["_key"],
                            "decay_date": satcat["decay_date"],
                            "ts": ts,
                            "transformation": transformation,
                        })
                        canonical["status"] = "decayed"
                        canonical["date_of_decay_or_change"] = satcat["decay_date"]
                        canonical["updated_at"] = ts
                        logger.info(f"Lazy decay update applied to {sat.get('identifier')} via CelesTrak satcat")
                    except Exception as e:
                        logger.error(f"Failed to persist lazy decay update for {sat.get('identifier')}: {e}")

        safe_canonical = filter_nan_values(canonical, recursive=True)

        sources = sat.get("sources", {})
        safe_sources = {
            k: filter_nan_values(v, recursive=True)
            for k, v in sources.items()
            if k != "_id" and isinstance(v, dict)
        }

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
