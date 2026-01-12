from arango import ArangoClient
from arango.exceptions import DatabaseCreateError, CollectionCreateError, DocumentInsertError, ArangoServerError
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
import os

ARANGO_HOST = os.getenv("ARANGO_HOST", "http://localhost:8529")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "kessler_dev_password")
DB_NAME = "kessler"
COLLECTION_NAME = "satellites"

client = None
db = None
satellites_collection = None


def connect_mongodb():
    """Initialize ArangoDB connection (kept name for backward compatibility)"""
    global client, db, satellites_collection
    try:
        client = ArangoClient(hosts=ARANGO_HOST)
        
        sys_db = client.db('_system', username=ARANGO_USER, password=ARANGO_PASSWORD)
        
        if not sys_db.has_database(DB_NAME):
            sys_db.create_database(DB_NAME)
        
        db = client.db(DB_NAME, username=ARANGO_USER, password=ARANGO_PASSWORD)
        
        if not db.has_collection(COLLECTION_NAME):
            satellites_collection = db.create_collection(COLLECTION_NAME)
        else:
            satellites_collection = db.collection(COLLECTION_NAME)
        
        satellites_collection.add_persistent_index(fields=['canonical.international_designator'], unique=False)
        satellites_collection.add_persistent_index(fields=['canonical.registration_number'], unique=False)
        satellites_collection.add_persistent_index(fields=['identifier'], unique=True)
        
        print(f"Connected to ArangoDB: {DB_NAME}.{COLLECTION_NAME}")
        return True
    except Exception as e:
        print(f"Failed to connect to ArangoDB: {e}")
        return False


def disconnect_mongodb():
    """Close ArangoDB connection (kept name for backward compatibility)"""
    global client
    if client:
        client.close()


def get_satellites_collection():
    """Get satellites collection (lazy initialization)"""
    global satellites_collection
    if satellites_collection is None:
        connect_mongodb()
    return satellites_collection


def get_nested_field(obj: Dict[str, Any], path: str) -> Any:
    """
    Safely access nested dictionary fields using dot notation.
    
    Args:
        obj: Dictionary to access
        path: Dot-separated path (e.g., "kaggle.orbital_band" or "canonical.orbit.apogee_km")
    
    Returns:
        Value at the path, or None if path doesn't exist
    
    Examples:
        get_nested_field({"a": {"b": {"c": 1}}}, "a.b.c") -> 1
        get_nested_field({"a": {"b": 2}}, "a.x.y") -> None
    """
    keys = path.split(".")
    current = obj
    
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    
    return current


def set_nested_field(obj: Dict[str, Any], path: str, value: Any) -> bool:
    """
    Safely set nested dictionary fields using dot notation.
    Creates intermediate dictionaries if they don't exist.
    
    Args:
        obj: Dictionary to modify
        path: Dot-separated path (e.g., "canonical.orbital_band")
        value: Value to set
    
    Returns:
        True if successful, False otherwise
    
    Examples:
        set_nested_field({}, "a.b.c", 1) -> {"a": {"b": {"c": 1}}}
        set_nested_field({"a": {}}, "a.b", 2) -> {"a": {"b": 2}}
    """
    keys = path.split(".")
    current = obj
    
    for i, key in enumerate(keys[:-1]):
        if key not in current:
            current[key] = {}
        elif not isinstance(current[key], dict):
            return False
        current = current[key]
    
    current[keys[-1]] = value
    return True


def record_transformation(
    doc: Dict[str, Any],
    source_field: str,
    target_field: str,
    value: Any,
    reason: Optional[str] = None
) -> None:
    """
    Record a field promotion in the document's transformation history.
    
    Args:
        doc: Document to update
        source_field: Source field path (e.g., "kaggle.orbital_band")
        target_field: Target field path (e.g., "canonical.orbital_band")
        value: The promoted value
        reason: Optional reason for the transformation
    """
    if "metadata" not in doc:
        doc["metadata"] = {}
    
    if "transformations" not in doc["metadata"]:
        doc["metadata"]["transformations"] = []
    
    transformation = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_field": source_field,
        "target_field": target_field,
        "value": value,
        "promoted_by": "manual_script"
    }
    
    if reason:
        transformation["reason"] = reason
    
    doc["metadata"]["transformations"].append(transformation)


def create_satellite_document(
    identifier: str,
    source: str,
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create or update a satellite document with envelope structure.
    
    Args:
        identifier: Unique identifier (e.g., international_designator or registration_number)
        source: Source name (e.g., 'unoosa', 'celestrak', 'spacetrack')
        data: Source-specific satellite data
    
    Returns:
        Created/updated document
    """
    collection = get_satellites_collection()
    
    aql = """
    FOR doc IN @@collection
        FILTER doc.identifier == @identifier
        LIMIT 1
        RETURN doc
    """
    cursor = db.aql.execute(
        aql,
        bind_vars={'@collection': COLLECTION_NAME, 'identifier': identifier}
    )
    existing = list(cursor)
    existing = existing[0] if existing else None
    
    if existing:
        existing["sources"][source] = {
            **data,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        existing["metadata"]["sources_available"] = list(existing["sources"].keys())
        existing["metadata"]["last_updated_at"] = datetime.now(timezone.utc).isoformat()
        
        update_canonical(existing)
        
        collection.update(existing)
        return existing
    else:
        doc = {
            "_key": (identifier
                     .replace('/', '_')
                     .replace(':', '_')
                     .replace('.', '_')
                     .replace('*', '_STAR_')
                     .replace(' ', '_')
                     .replace('(', '_')
                     .replace(')', '_')),
            "identifier": identifier,
            "canonical": {},
            "sources": {
                source: {
                    **data,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            },
            "metadata": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_updated_at": datetime.now(timezone.utc).isoformat(),
                "sources_available": [source],
                "source_priority": ["unoosa", "celestrak", "tleapi", "kaggle"]
            }
        }
        
        update_canonical(doc)
        result = collection.insert(doc)
        doc["_key"] = result["_key"]
        return doc


def update_canonical(doc: Dict[str, Any]):
    """
    Update canonical section from source nodes based on priority.
    Source priority: UNOOSA > CelesTrak > TLE API > Kaggle
    """
    source_priority = doc["metadata"].get("source_priority", ["unoosa", "celestrak", "tleapi", "kaggle"])
    sources = doc["sources"]
    
    source_priority = [s for s in source_priority if s in sources] + [s for s in sources if s not in source_priority]
    
    canonical = {}
    
    canonical_fields = [
        "name", "object_name", "country_of_origin", "international_designator",
        "registration_number", "norad_cat_id", "date_of_launch", "function", "status",
        "registration_document", "un_registered", "gso_location",
        "date_of_decay_or_change", "secretariat_remarks", "external_website",
        "launch_vehicle", "place_of_launch", "object_type", "rcs", "orbital_band",
        "congestion_risk"
    ]
    
    for field in canonical_fields:
        for source_name in source_priority:
            if source_name in sources:
                value = sources[source_name].get(field)
                if value is not None and value != "":
                    canonical[field] = value
                    break
    
    orbital_fields = ["apogee_km", "perigee_km", "inclination_degrees", "period_minutes"]
    canonical["orbit"] = {}
    for field in orbital_fields:
        for source_name in source_priority:
            if source_name in sources:
                value = sources[source_name].get(field)
                if value is not None:
                    canonical["orbit"][field] = value
                    break
    
    tle_fields = ["tle_line1", "tle_line2"]
    canonical["tle"] = {}
    for field in tle_fields:
        for source_name in source_priority:
            if source_name in sources:
                value = sources[source_name].get(field)
                if value is not None:
                    canonical_field = "line1" if field == "tle_line1" else "line2"
                    canonical["tle"][canonical_field] = value
                    break
    
    canonical["updated_at"] = datetime.now(timezone.utc).isoformat()
    canonical["source_priority"] = source_priority
    
    doc["canonical"] = canonical


def find_satellite(
    international_designator: Optional[str] = None,
    registration_number: Optional[str] = None,
    name: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Find a satellite document"""
    collection = get_satellites_collection()
    
    if international_designator:
        aql = """
        FOR doc IN @@collection
            FILTER doc.canonical.international_designator == @value
            LIMIT 1
            RETURN doc
        """
        bind_vars = {'@collection': COLLECTION_NAME, 'value': international_designator}
    elif registration_number:
        aql = """
        FOR doc IN @@collection
            FILTER doc.canonical.registration_number == @value
            LIMIT 1
            RETURN doc
        """
        bind_vars = {'@collection': COLLECTION_NAME, 'value': registration_number}
    elif name:
        aql = """
        FOR doc IN @@collection
            FILTER LIKE(doc.canonical.name, @pattern, true)
            LIMIT 1
            RETURN doc
        """
        bind_vars = {'@collection': COLLECTION_NAME, 'pattern': f'%{name}%'}
    else:
        return None
    
    cursor = db.aql.execute(aql, bind_vars=bind_vars)
    results = list(cursor)
    return results[0] if results else None


def search_satellites(
    query: str = "",
    country: Optional[str] = None,
    status: Optional[str] = None,
    orbital_band: Optional[str] = None,
    congestion_risk: Optional[str] = None,
    limit: int = 100,
    skip: int = 0
) -> List[Dict[str, Any]]:
    """Search satellites with optional filters"""
    collection = get_satellites_collection()
    
    filters = []
    bind_vars = {'@collection': COLLECTION_NAME, 'limit': limit, 'skip': skip}
    
    if query:
        filters.append("""
            (LIKE(doc.canonical.name, @query_pattern, true) OR
             LIKE(doc.canonical.object_name, @query_pattern, true) OR
             LIKE(doc.canonical.international_designator, @query_pattern, true) OR
             LIKE(doc.canonical.registration_number, @query_pattern, true))
        """)
        bind_vars['query_pattern'] = f'%{query}%'
    
    if country:
        filters.append("LIKE(doc.canonical.country_of_origin, @country_pattern, true)")
        bind_vars['country_pattern'] = f'%{country}%'
    
    if status:
        filters.append("LIKE(doc.canonical.status, @status_pattern, true)")
        bind_vars['status_pattern'] = f'%{status}%'
    
    if orbital_band:
        filters.append("LIKE(doc.canonical.orbital_band, @orbital_band_pattern, true)")
        bind_vars['orbital_band_pattern'] = f'%{orbital_band}%'
    
    if congestion_risk:
        filters.append("LIKE(doc.canonical.congestion_risk, @congestion_risk_pattern, true)")
        bind_vars['congestion_risk_pattern'] = f'%{congestion_risk}%'
    
    filter_clause = ""
    if filters:
        filter_clause = "FILTER " + " AND ".join(filters)
    
    aql = f"""
    FOR doc IN @@collection
        {filter_clause}
        LIMIT @skip, @limit
        RETURN doc
    """
    
    cursor = db.aql.execute(aql, bind_vars=bind_vars)
    return list(cursor)


def count_satellites(
    query: Optional[str] = None,
    country: Optional[str] = None,
    status: Optional[str] = None,
    orbital_band: Optional[str] = None,
    congestion_risk: Optional[str] = None
) -> int:
    """Count satellites with optional filters"""
    collection = get_satellites_collection()
    
    filters = []
    bind_vars = {'@collection': COLLECTION_NAME}
    
    if query:
        filters.append("""
            (LIKE(doc.canonical.name, @query_pattern, true) OR
             LIKE(doc.canonical.object_name, @query_pattern, true) OR
             LIKE(doc.canonical.international_designator, @query_pattern, true) OR
             LIKE(doc.canonical.registration_number, @query_pattern, true))
        """)
        bind_vars['query_pattern'] = f'%{query}%'
    
    if country:
        filters.append("LIKE(doc.canonical.country_of_origin, @country_pattern, true)")
        bind_vars['country_pattern'] = f'%{country}%'
    
    if status:
        filters.append("LIKE(doc.canonical.status, @status_pattern, true)")
        bind_vars['status_pattern'] = f'%{status}%'
    
    if orbital_band:
        filters.append("LIKE(doc.canonical.orbital_band, @orbital_band_pattern, true)")
        bind_vars['orbital_band_pattern'] = f'%{orbital_band}%'
    
    if congestion_risk:
        filters.append("LIKE(doc.canonical.congestion_risk, @congestion_risk_pattern, true)")
        bind_vars['congestion_risk_pattern'] = f'%{congestion_risk}%'
    
    filter_clause = ""
    if filters:
        filter_clause = "FILTER " + " AND ".join(filters)
    
    aql = f"""
    RETURN COUNT(
        FOR doc IN @@collection
            {filter_clause}
            RETURN 1
    )
    """
    
    cursor = db.aql.execute(aql, bind_vars=bind_vars)
    result = list(cursor)
    return result[0] if result else 0


def get_all_countries() -> List[str]:
    """Get list of unique countries"""
    collection = get_satellites_collection()
    aql = """
    RETURN UNIQUE(
        FOR doc IN @@collection
            FILTER doc.canonical.country_of_origin != null
            RETURN doc.canonical.country_of_origin
    )
    """
    cursor = db.aql.execute(aql, bind_vars={'@collection': COLLECTION_NAME})
    result = list(cursor)
    return result[0] if result else []


def get_all_statuses() -> List[str]:
    """Get list of unique statuses"""
    collection = get_satellites_collection()
    aql = """
    RETURN UNIQUE(
        FOR doc IN @@collection
            FILTER doc.canonical.status != null
            RETURN doc.canonical.status
    )
    """
    cursor = db.aql.execute(aql, bind_vars={'@collection': COLLECTION_NAME})
    result = list(cursor)
    return result[0] if result else []


def get_all_orbital_bands() -> List[str]:
    """Get list of unique orbital bands"""
    collection = get_satellites_collection()
    aql = """
    RETURN UNIQUE(
        FOR doc IN @@collection
            FILTER doc.canonical.orbital_band != null
            RETURN doc.canonical.orbital_band
    )
    """
    cursor = db.aql.execute(aql, bind_vars={'@collection': COLLECTION_NAME})
    result = list(cursor)
    return result[0] if result else []


def get_all_congestion_risks() -> List[str]:
    """Get list of unique congestion risks"""
    collection = get_satellites_collection()
    aql = """
    RETURN UNIQUE(
        FOR doc IN @@collection
            FILTER doc.canonical.congestion_risk != null
            RETURN doc.canonical.congestion_risk
    )
    """
    cursor = db.aql.execute(aql, bind_vars={'@collection': COLLECTION_NAME})
    result = list(cursor)
    return result[0] if result else []


def clear_collection():
    """Clear all documents from satellites collection"""
    collection = get_satellites_collection()
    collection.truncate()
