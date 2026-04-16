from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

import database.connection as db_conn
from database.connection import COLLECTION_EPHEMERIS


def get_ephemeris_collection():
    db = db_conn.db
    if db is None:
        raise RuntimeError("Database not available")
    if not db.has_collection(COLLECTION_EPHEMERIS):
        db.create_collection(COLLECTION_EPHEMERIS)
    return db.collection(COLLECTION_EPHEMERIS)


def save_ephemeris_envelope(envelope: Dict[str, Any]) -> Dict[str, Any]:
    col = get_ephemeris_collection()
    envelope.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
    result = col.insert(envelope, return_new=True)
    return result["new"]


def list_ephemeris_envelopes(
    norad_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    db = db_conn.db
    if db is None:
        return []

    filters = ""
    bind_vars: Dict[str, Any] = {"@collection": COLLECTION_EPHEMERIS, "limit": limit, "offset": offset}

    if norad_id is not None:
        filters = "FILTER doc.norad_id == @norad_id"
        bind_vars["norad_id"] = norad_id

    aql = f"""
    FOR doc IN @@collection
        {filters}
        SORT doc.generated_at DESC
        LIMIT @offset, @limit
        RETURN UNSET(doc, "ephemeris_points")
    """
    cursor = db.aql.execute(aql, bind_vars=bind_vars)
    return list(cursor)


def count_ephemeris_envelopes(norad_id: Optional[int] = None) -> int:
    db = db_conn.db
    if db is None:
        return 0

    filters = ""
    bind_vars: Dict[str, Any] = {"@collection": COLLECTION_EPHEMERIS}

    if norad_id is not None:
        filters = "FILTER doc.norad_id == @norad_id"
        bind_vars["norad_id"] = norad_id

    aql = f"""
    FOR doc IN @@collection
        {filters}
        COLLECT WITH COUNT INTO total
        RETURN total
    """
    cursor = db.aql.execute(aql, bind_vars=bind_vars)
    result = list(cursor)
    return result[0] if result else 0


def get_ephemeris_envelope(envelope_id: str) -> Optional[Dict[str, Any]]:
    col = get_ephemeris_collection()
    try:
        return col.get(envelope_id)
    except Exception:
        return None


def delete_ephemeris_envelope(envelope_id: str) -> bool:
    col = get_ephemeris_collection()
    try:
        col.delete(envelope_id)
        return True
    except Exception:
        return False
