from fastapi import APIRouter, HTTPException
from typing import Optional

import database as db_module
from database.connection import COLLECTION_OBSERVATIONS

router = APIRouter(tags=["observations"])


def get_observations_collection():
    db = db_module.db
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    if not db.has_collection(COLLECTION_OBSERVATIONS):
        raise HTTPException(status_code=503, detail="Observations collection not found")
    return db.collection(COLLECTION_OBSERVATIONS)


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
