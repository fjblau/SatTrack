"""
Provenance graph API endpoints.

All endpoints require authentication (handled by AuthMiddleware).
Raw DISCOS records are not exposed directly per redistribution policy decision.
Confidence thresholds: >=0.9 high, 0.7-0.9 medium (caveat added), <0.7 requires explicit min_confidence filter.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import logging

import database as db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v2/provenance", tags=["provenance"])


def _get_db():
    if db.db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    return db.db


def _confidence_caveat(confidence: Optional[float]) -> Optional[str]:
    if confidence is None:
        return None
    if confidence >= 0.9:
        return None
    if confidence >= 0.7:
        return "medium-confidence attribution; verify before operational use"
    return None


@router.get("/objects/{object_key}/chain")
def get_provenance_chain(
    object_key: str,
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
):
    """
    Return the full provenance chain for an object:
    fragmentation event → parent object → launch event → launch vehicle → operator.

    Confidence < 0.7 is excluded unless min_confidence is explicitly set below 0.7.
    """
    database = _get_db()
    effective_min = min_confidence if min_confidence is not None else 0.7

    aql = """
    LET obj = DOCUMENT(CONCAT("objects/", @key))
    FILTER obj != null

    LET frag_edges = (
        FOR e IN fragmented_from
            FILTER e._from == obj._id
            FILTER (e.confidence == null OR e.confidence >= @min_conf)
            LIMIT 1
            RETURN e
    )
    LET frag_edge = LENGTH(frag_edges) > 0 ? frag_edges[0] : null

    LET parent_obj = frag_edge != null ? DOCUMENT(frag_edge._to) : null

    LET event_edges = (
        FOR e IN caused_by
            FILTER e._from == obj._id
            LIMIT 1
            RETURN e
    )
    LET event_edge = LENGTH(event_edges) > 0 ? event_edges[0] : null
    LET frag_event = event_edge != null ? DOCUMENT(event_edge._to) : null

    LET launch_edges = (
        FOR e IN launched_by
            FILTER e._from == obj._id
            LIMIT 1
            RETURN e
    )
    LET launch_edge = LENGTH(launch_edges) > 0 ? launch_edges[0] : null
    LET operator = launch_edge != null ? DOCUMENT(launch_edge._to) : null

    LET vehicle_edges = (
        FOR e IN launched_via
            FILTER e._from == obj._id
            LIMIT 1
            RETURN e
    )
    LET vehicle_edge = LENGTH(vehicle_edges) > 0 ? vehicle_edges[0] : null
    LET launch_vehicle = vehicle_edge != null ? DOCUMENT(vehicle_edge._to) : null

    LET site_edges = (
        FOR e IN launched_from
            FILTER e._from == obj._id
            LIMIT 1
            RETURN e
    )
    LET site_edge = LENGTH(site_edges) > 0 ? site_edges[0] : null
    LET launch_site = site_edge != null ? DOCUMENT(site_edge._to) : null

    RETURN {
        object: obj,
        fragmented_from: parent_obj,
        fragmentation_confidence: frag_edge != null ? frag_edge.confidence : null,
        fragmentation_event: frag_event,
        operator: operator,
        launch_vehicle: launch_vehicle,
        launch_site: launch_site
    }
    """
    cursor = database.aql.execute(aql, bind_vars={"key": object_key, "min_conf": effective_min})
    rows = list(cursor)
    if not rows or rows[0].get("object") is None:
        raise HTTPException(status_code=404, detail=f"Object '{object_key}' not found")

    row = rows[0]
    caveat = _confidence_caveat(row.get("fragmentation_confidence"))
    response = {
        "object_key": object_key,
        "chain": row,
    }
    if caveat:
        response["caveat"] = caveat
    return response


@router.get("/objects/{object_key}/siblings")
def get_siblings(
    object_key: str,
    limit: int = Query(50, ge=1, le=500),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
):
    """
    Return sibling objects (other fragments from the same parent) via two-hop traversal.

    Siblings are NOT materialized as direct edges — computed on-demand.
    """
    database = _get_db()
    effective_min = min_confidence if min_confidence is not None else 0.7

    aql = """
    LET obj = DOCUMENT(CONCAT("objects/", @key))
    FILTER obj != null

    LET frag_edges = (
        FOR e IN fragmented_from
            FILTER e._from == obj._id
            FILTER (e.confidence == null OR e.confidence >= @min_conf)
            LIMIT 1
            RETURN e
    )

    LET parent = LENGTH(frag_edges) > 0 ? DOCUMENT(frag_edges[0]._to) : null

    LET siblings = parent != null ? (
        FOR e2 IN fragmented_from
            FILTER e2._to == parent._id
            FILTER e2._from != obj._id
            FILTER (e2.confidence == null OR e2.confidence >= @min_conf)
            LET sibling = DOCUMENT(e2._from)
            FILTER sibling != null
            LIMIT @limit
            RETURN MERGE(sibling, {_fragmented_from_edge: e2})
    ) : []

    RETURN {
        parent: parent,
        siblings: siblings,
        sibling_count: LENGTH(siblings)
    }
    """
    cursor = database.aql.execute(
        aql,
        bind_vars={"key": object_key, "min_conf": effective_min, "limit": limit},
    )
    rows = list(cursor)
    if not rows:
        raise HTTPException(status_code=404, detail=f"Object '{object_key}' not found")
    return rows[0]


@router.get("/events/{event_key}")
def get_fragmentation_event(event_key: str):
    """
    Return a fragmentation event document and its attributed fragments.
    """
    database = _get_db()
    aql = """
    LET ev = DOCUMENT(CONCAT("fragmentation_events/", @key))
    FILTER ev != null

    LET fragments = (
        FOR e IN caused_by
            FILTER e._to == ev._id
            LET frag = DOCUMENT(e._from)
            FILTER frag != null
            RETURN {
                object: frag,
                confidence: e.confidence
            }
    )

    RETURN {
        event: ev,
        fragment_count: LENGTH(fragments),
        fragments: fragments
    }
    """
    cursor = database.aql.execute(aql, bind_vars={"key": event_key})
    rows = list(cursor)
    if not rows or rows[0].get("event") is None:
        raise HTTPException(status_code=404, detail=f"Fragmentation event '{event_key}' not found")
    return rows[0]


@router.get("/launches/{launch_key}")
def get_launch_event(launch_key: str):
    """
    Return a launch event document and its launched objects.
    """
    database = _get_db()
    aql = """
    LET ev = DOCUMENT(CONCAT("launch_events/", @key))
    FILTER ev != null

    LET objects_launched = (
        FOR e IN launched_by
            FILTER e._to == ev._id
            LET obj = DOCUMENT(e._from)
            FILTER obj != null
            RETURN obj
    )

    LET vehicle_edges = (
        FOR e IN launched_via
            FILTER e._to == ev._id OR e._from == ev._id
            LIMIT 1
            RETURN DOCUMENT(e._to != ev._id ? e._to : e._from)
    )

    LET site_edges = (
        FOR e IN launched_from
            FILTER e._to == ev._id OR e._from == ev._id
            LIMIT 1
            RETURN DOCUMENT(e._to != ev._id ? e._to : e._from)
    )

    RETURN {
        launch_event: ev,
        object_count: LENGTH(objects_launched),
        objects: objects_launched,
        launch_vehicle: LENGTH(vehicle_edges) > 0 ? vehicle_edges[0] : null,
        launch_site: LENGTH(site_edges) > 0 ? site_edges[0] : null
    }
    """
    cursor = database.aql.execute(aql, bind_vars={"key": launch_key})
    rows = list(cursor)
    if not rows or rows[0].get("launch_event") is None:
        raise HTTPException(status_code=404, detail=f"Launch event '{launch_key}' not found")
    return rows[0]


@router.get("/entities/{entity_key}")
def get_entity(entity_key: str):
    """
    Return an entity (operator/country) document and objects it launched.
    """
    database = _get_db()
    aql = """
    LET ent = DOCUMENT(CONCAT("entities/", @key))
    FILTER ent != null

    LET launched = (
        FOR e IN launched_by
            FILTER e._to == ent._id
            LET obj = DOCUMENT(e._from)
            FILTER obj != null
            LIMIT 100
            RETURN obj
    )

    RETURN {
        entity: ent,
        launched_object_count: LENGTH(launched),
        launched_objects: launched
    }
    """
    cursor = database.aql.execute(aql, bind_vars={"key": entity_key})
    rows = list(cursor)
    if not rows or rows[0].get("entity") is None:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_key}' not found")
    return rows[0]


@router.get("/summary")
def get_provenance_summary():
    """
    Return summary statistics for the provenance graph.
    """
    database = _get_db()
    aql = """
    RETURN {
        fragmentation_events: LENGTH(fragmentation_events),
        launch_events: LENGTH(launch_events),
        launch_vehicles: LENGTH(launch_vehicles),
        launch_sites: LENGTH(launch_sites),
        entities: LENGTH(entities),
        fragmented_from_edges: LENGTH(fragmented_from),
        caused_by_edges: LENGTH(caused_by),
        launched_by_edges: LENGTH(launched_by),
        launched_via_edges: LENGTH(launched_via),
        launched_from_edges: LENGTH(launched_from)
    }
    """
    cursor = database.aql.execute(aql)
    rows = list(cursor)
    return rows[0] if rows else {}
