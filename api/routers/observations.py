from fastapi import APIRouter, HTTPException
from typing import Optional

import database as db_module
from database.connection import COLLECTION_OBSERVATIONS

router = APIRouter(tags=["observations"])

ALLOWED_SORT_FIELDS = {
    'observation_epoch', 'source', 'object_name', 'object_type',
    'origin_country', 'derived_health_score', 'estimated_mass_kg', 'spin_rate_rpm'
}


def get_observations_collection():
    db = db_module.db
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    if not db.has_collection(COLLECTION_OBSERVATIONS):
        raise HTTPException(status_code=503, detail="Observations collection not found")
    return db.collection(COLLECTION_OBSERVATIONS)


@router.get("/v2/observations/filter-options")
def get_observation_filter_options():
    db = db_module.db
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    cursor = db.aql.execute("""
    RETURN {
        sources: (FOR obs IN observations COLLECT s = obs.source INTO g FILTER s != null SORT s RETURN s),
        object_types: (FOR obs IN observations COLLECT t = obs.object_type INTO g FILTER t != null SORT t RETURN t),
        origin_countries: (FOR obs IN observations COLLECT c = obs.origin_country INTO g FILTER c != null SORT c RETURN c)
    }
    """)
    result = next(iter(list(cursor)), {"sources": [], "object_types": [], "origin_countries": []})
    return result


@router.get("/v2/observations")
def get_all_observations(
    source: Optional[str] = None,
    object_type: Optional[str] = None,
    origin_country: Optional[str] = None,
    search: Optional[str] = None,
    has_anomaly: Optional[bool] = None,
    health_score_min: Optional[float] = None,
    health_score_max: Optional[float] = None,
    epoch_from: Optional[str] = None,
    epoch_to: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    sort_by: str = 'observation_epoch',
    sort_order: str = 'DESC',
):
    db = db_module.db
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    if sort_by not in ALLOWED_SORT_FIELDS:
        sort_by = 'observation_epoch'
    sort_order = 'ASC' if sort_order.upper() == 'ASC' else 'DESC'

    filter_clauses = []
    bind_vars = {'skip': skip, 'limit': limit}

    if search:
        filter_clauses.append('CONTAINS(LOWER(obs.object_name), LOWER(@search))')
        bind_vars['search'] = search
    if source:
        filter_clauses.append('obs.source == @source')
        bind_vars['source'] = source
    if object_type:
        filter_clauses.append('obs.object_type == @object_type')
        bind_vars['object_type'] = object_type
    if origin_country:
        filter_clauses.append('CONTAINS(LOWER(obs.origin_country), LOWER(@origin_country))')
        bind_vars['origin_country'] = origin_country
    if has_anomaly:
        filter_clauses.append('obs.thermal.anomaly_flag == true')
    if health_score_min is not None:
        filter_clauses.append('obs.derived_health_score >= @health_score_min')
        bind_vars['health_score_min'] = health_score_min
    if health_score_max is not None:
        filter_clauses.append('obs.derived_health_score <= @health_score_max')
        bind_vars['health_score_max'] = health_score_max
    if epoch_from:
        filter_clauses.append('obs.observation_epoch >= @epoch_from')
        bind_vars['epoch_from'] = epoch_from
    if epoch_to:
        filter_clauses.append('obs.observation_epoch <= @epoch_to')
        bind_vars['epoch_to'] = epoch_to

    filter_str = '\n'.join(f'    FILTER {clause}' for clause in filter_clauses)

    query = f"""
    FOR obs IN observations
    {filter_str}
    SORT obs.{sort_by} {sort_order}
    LIMIT @skip, @limit
    RETURN obs
    """

    count_query = f"""
    FOR obs IN observations
    {filter_str}
    COLLECT WITH COUNT INTO total
    RETURN total
    """

    cursor = db.aql.execute(query, bind_vars=bind_vars)
    results = list(cursor)

    count_bind_vars = {k: v for k, v in bind_vars.items() if k not in ('skip', 'limit')}
    count_cursor = db.aql.execute(count_query, bind_vars=count_bind_vars)
    total = next(iter(list(count_cursor)), 0)

    return {
        "data": results,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/v2/observations/{norad_id}")
def get_observations(norad_id: int, limit: Optional[int] = 100, offset: Optional[int] = 0):
    db = db_module.db
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    cursor = db.aql.execute(
        """
        FOR obs IN observations
        FILTER obs.norad_id == @norad_id
        SORT obs.observation_epoch DESC
        LIMIT @offset, @limit
        RETURN obs
        """,
        bind_vars={"norad_id": norad_id, "offset": offset, "limit": limit}
    )
    results = list(cursor)

    count_cursor = db.aql.execute(
        "FOR obs IN observations FILTER obs.norad_id == @norad_id COLLECT WITH COUNT INTO total RETURN total",
        bind_vars={"norad_id": norad_id}
    )
    total = next(iter(list(count_cursor)), 0)

    return {
        "data": results,
        "total": total,
        "norad_id": norad_id,
        "limit": limit,
        "offset": offset
    }
