from fastapi import APIRouter, Query, HTTPException
from typing import Optional
import math

from database import find_satellite, search_satellites, count_satellites, get_all_object_classes
import database.connection as db_conn
from database.identifier_operations import lookup_by_alias, lookup_by_norad, lookup_by_cospar, ALIAS_TYPES
from database.connection import COLLECTION_NAME
from api.utils.converters import filter_nan_values

router = APIRouter(prefix="/v2/objects", tags=["objects"])

_OBJECT_CLASSES = [
    "Payload",
    "Rocket Body",
    "Mission-Related Object",
    "Rocket Fragmentation Debris",
    "Payload Fragmentation Debris",
    "Unknown",
]


def _clean_doc(doc):
    canonical = doc.get("canonical", {})
    safe_canonical = {}
    for k, v in canonical.items():
        if k == "_id":
            continue
        if isinstance(v, dict):
            safe_v = {kk: vv for kk, vv in v.items() if not (isinstance(vv, float) and (math.isnan(vv) or math.isinf(vv)))}
            safe_canonical[k] = safe_v
        elif not (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
            safe_canonical[k] = v

    sources = doc.get("sources", {})
    safe_sources = {}
    for k, v in sources.items():
        if k == "_id" or not isinstance(v, dict):
            continue
        safe_v = {kk: vv for kk, vv in v.items() if kk != "_id" and not (isinstance(vv, float) and (math.isnan(vv) or math.isinf(vv)))}
        safe_sources[k] = safe_v

    return {
        "identifier": doc.get("identifier"),
        "canonical": safe_canonical,
        "sources": safe_sources,
        "metadata": doc.get("metadata", {}),
        "identifier_aliases": doc.get("identifier_aliases", {}),
    }


@router.get("/{identifier}")
def get_object(identifier: str):
    """Get a space object by identifier (COSPAR, NORAD, document key)."""
    doc = (
        find_satellite(identifier=identifier)
        or find_satellite(international_designator=identifier)
        or find_satellite(registration_number=identifier)
    )
    if not doc:
        doc = lookup_by_norad(identifier)
    if not doc:
        doc = lookup_by_cospar(identifier)
    if not doc:
        raise HTTPException(status_code=404, detail="Object not found")

    object_class = doc.get("canonical", {}).get("object_class", "")
    if object_class and object_class != "Payload":
        raise HTTPException(status_code=404, detail="Object not found")

    return {"data": _clean_doc(doc)}


@router.get("")
@router.get("/search")
def search_objects(
    q: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    orbital_band: Optional[str] = Query(None),
    object_class: Optional[str] = Query(None),
    object_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query(None),
):
    """Search space objects."""
    results = search_satellites(
        query=q or "",
        country=country,
        status=status,
        orbital_band=orbital_band,
        object_type=object_type,
        limit=limit,
        skip=skip,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    if object_class:
        results = [r for r in results if r.get("canonical", {}).get("object_class") == object_class]

    total_count = count_satellites(
        query=q or "",
        country=country,
        status=status,
        orbital_band=orbital_band,
        object_type=object_type,
    )

    data = []
    for r in results:
        canonical = r.get("canonical", {})
        safe_canonical = filter_nan_values(canonical, recursive=False)
        data.append({
            "identifier": r.get("identifier"),
            "canonical": safe_canonical,
            "identifier_aliases": r.get("identifier_aliases", {}),
            "sources_available": r.get("metadata", {}).get("sources_available", []),
        })

    return {"count": total_count, "skip": skip, "limit": limit, "data": data}


@router.get("/by-class/{object_class}")
def get_objects_by_class(
    object_class: str,
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0),
):
    """Get space objects filtered by object class."""
    aql = """
    FOR doc IN @@collection
        FILTER doc.canonical.object_class == @object_class
        LIMIT @skip, @limit
        RETURN doc
    """
    cursor = db_conn.db.aql.execute(
        aql,
        bind_vars={
            "@collection": COLLECTION_NAME,
            "object_class": object_class,
            "skip": skip,
            "limit": limit,
        },
    )
    docs = list(cursor)

    count_aql = """
    RETURN COUNT(
        FOR doc IN @@collection
            FILTER doc.canonical.object_class == @object_class
            RETURN 1
    )
    """
    count_cursor = db_conn.db.aql.execute(
        count_aql,
        bind_vars={"@collection": COLLECTION_NAME, "object_class": object_class},
    )
    total = list(count_cursor)[0] or 0

    return {
        "count": total,
        "skip": skip,
        "limit": limit,
        "object_class": object_class,
        "data": [_clean_doc(d) for d in docs],
    }


@router.get("/by-alias/{alias_type}/{value}")
def get_object_by_alias(alias_type: str, value: str):
    """Get a space object by identifier alias (norad, cospar, discos, vimpel, kestrel)."""
    if alias_type not in ALIAS_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown alias type '{alias_type}'. Must be one of: {list(ALIAS_TYPES)}",
        )
    doc = lookup_by_alias(alias_type, value)
    if not doc:
        raise HTTPException(status_code=404, detail="Object not found")
    return {"data": _clean_doc(doc)}


@router.get("/stats")
def get_object_stats():
    """Get statistics about all space objects."""
    aql = """
    LET total = LENGTH(@@collection)
    LET by_class = (
        FOR doc IN @@collection
            COLLECT cls = doc.canonical.object_class WITH COUNT INTO cnt
            RETURN {class: cls, count: cnt}
    )
    LET by_status = (
        FOR doc IN @@collection
            COLLECT st = doc.canonical.status WITH COUNT INTO cnt
            RETURN {status: st, count: cnt}
    )
    RETURN {total: total, by_class: by_class, by_status: by_status}
    """
    cursor = db_conn.db.aql.execute(aql, bind_vars={"@collection": COLLECTION_NAME})
    result = list(cursor)
    return result[0] if result else {"total": 0, "by_class": [], "by_status": []}
