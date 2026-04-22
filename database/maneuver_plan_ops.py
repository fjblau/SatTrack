from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import database.connection as db_conn
from database.connection import COLLECTION_MANEUVER_PLANS


def _get_collection():
    db = db_conn.db
    if db is None:
        raise RuntimeError("Database not available")
    if not db.has_collection(COLLECTION_MANEUVER_PLANS):
        db.create_collection(COLLECTION_MANEUVER_PLANS)
    return db.collection(COLLECTION_MANEUVER_PLANS)


def save_maneuver_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    col = _get_collection()
    plan.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    result = col.insert(plan, return_new=True)
    return result["new"]


def list_maneuver_plans(
    kestrel_norad_id: Optional[int] = None,
    target_norad_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    db = db_conn.db
    if db is None:
        return []

    filters = []
    bind_vars: Dict[str, Any] = {
        "@collection": COLLECTION_MANEUVER_PLANS,
        "limit": limit,
        "offset": offset,
    }

    if kestrel_norad_id is not None:
        filters.append("FILTER doc.kestrel_norad_id == @kestrel_norad_id")
        bind_vars["kestrel_norad_id"] = kestrel_norad_id

    if target_norad_id is not None:
        filters.append("FILTER doc.target_norad_id == @target_norad_id")
        bind_vars["target_norad_id"] = target_norad_id

    filter_clause = "\n        ".join(filters)
    aql = f"""
    FOR doc IN @@collection
        {filter_clause}
        SORT doc.created_at DESC
        LIMIT @offset, @limit
        RETURN doc
    """
    cursor = db.aql.execute(aql, bind_vars=bind_vars)
    return list(cursor)


def count_maneuver_plans(
    kestrel_norad_id: Optional[int] = None,
    target_norad_id: Optional[int] = None,
) -> int:
    db = db_conn.db
    if db is None:
        return 0

    filters = []
    bind_vars: Dict[str, Any] = {"@collection": COLLECTION_MANEUVER_PLANS}

    if kestrel_norad_id is not None:
        filters.append("FILTER doc.kestrel_norad_id == @kestrel_norad_id")
        bind_vars["kestrel_norad_id"] = kestrel_norad_id

    if target_norad_id is not None:
        filters.append("FILTER doc.target_norad_id == @target_norad_id")
        bind_vars["target_norad_id"] = target_norad_id

    filter_clause = "\n        ".join(filters)
    aql = f"""
    FOR doc IN @@collection
        {filter_clause}
        COLLECT WITH COUNT INTO total
        RETURN total
    """
    cursor = db.aql.execute(aql, bind_vars=bind_vars)
    result = list(cursor)
    return result[0] if result else 0


def get_maneuver_plan(plan_id: str) -> Optional[Dict[str, Any]]:
    col = _get_collection()
    try:
        return col.get(plan_id)
    except Exception:
        return None


def delete_maneuver_plan(plan_id: str) -> bool:
    col = _get_collection()
    try:
        col.delete(plan_id)
        return True
    except Exception:
        return False
