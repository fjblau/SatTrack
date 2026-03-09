from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from database.connection import get_satellites_collection, COLLECTION_NAME
import database.connection as db_conn
from database.transformations import update_canonical


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
    cursor = db_conn.db.aql.execute(
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


def find_satellite(
    identifier: Optional[str] = None,
    international_designator: Optional[str] = None,
    registration_number: Optional[str] = None,
    name: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Find a satellite document"""
    collection = get_satellites_collection()
    
    if identifier:
        aql = """
        FOR doc IN @@collection
            FILTER doc.identifier == @value
            LIMIT 1
            RETURN doc
        """
        bind_vars = {'@collection': COLLECTION_NAME, 'value': identifier}
    elif international_designator:
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
    
    cursor = db_conn.db.aql.execute(aql, bind_vars=bind_vars)
    results = list(cursor)
    return results[0] if results else None


def search_satellites(
    query: str = "",
    country: Optional[str] = None,
    status: Optional[str] = None,
    orbital_band: Optional[str] = None,
    congestion_risk: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Search satellites with optional filters and sorting"""
    collection = get_satellites_collection()
    
    SORT_FIELD_MAPPING = {
        'Identifier': 'doc.identifier',
        'Object Name': 'doc.canonical.object_name',
        'Country of Origin': 'doc.canonical.country_of_origin',
        'Date of Launch': 'doc.canonical.launch_date',
        'Status': 'doc.canonical.status',
        'Orbital Band': 'doc.canonical.orbital_band',
        'Congestion Risk': 'doc.canonical.congestion_risk',
        'Apogee (km)': 'doc.canonical.orbit.apogee_km',
        'Perigee (km)': 'doc.canonical.orbit.perigee_km',
        'Inclination (degrees)': 'doc.canonical.orbit.inclination_degrees',
        'Period (minutes)': 'doc.canonical.orbit.period_minutes'
    }
    
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
    
    sort_clause = "SORT doc.identifier ASC"
    if sort_by and sort_by in SORT_FIELD_MAPPING:
        sort_field = SORT_FIELD_MAPPING[sort_by]
        sort_direction = "DESC" if sort_order and sort_order.upper() == "DESC" else "ASC"
        sort_clause = f"SORT {sort_field} {sort_direction}"
    
    aql = f"""
    FOR doc IN @@collection
        {filter_clause}
        {sort_clause}
        LIMIT @skip, @limit
        RETURN doc
    """
    
    cursor = db_conn.db.aql.execute(aql, bind_vars=bind_vars)
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
    
    cursor = db_conn.db.aql.execute(aql, bind_vars=bind_vars)
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
    cursor = db_conn.db.aql.execute(aql, bind_vars={'@collection': COLLECTION_NAME})
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
    cursor = db_conn.db.aql.execute(aql, bind_vars={'@collection': COLLECTION_NAME})
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
    cursor = db_conn.db.aql.execute(aql, bind_vars={'@collection': COLLECTION_NAME})
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
    cursor = db_conn.db.aql.execute(aql, bind_vars={'@collection': COLLECTION_NAME})
    result = list(cursor)
    return result[0] if result else []


def clear_collection():
    """Clear all documents from satellites collection"""
    collection = get_satellites_collection()
    collection.truncate()


def update_satellite_tle(
    identifier: str,
    norad_id: str,
    tle_data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Persist parsed TLE data into a satellite document.

    Merges raw + parsed TLE into sources["tleapi"] and overwrites
    canonical.tle with the fresh parsed TLE fields.

    Args:
        identifier: Satellite identifier used to locate the document
        norad_id: NORAD catalog ID
        tle_data: Parsed TLE dictionary from parse_tle_fields()

    Returns:
        Updated document dict, or None if the satellite was not found.
    """
    collection = get_satellites_collection()

    aql = """
    FOR doc IN @@collection
        FILTER doc.identifier == @identifier
        LIMIT 1
        RETURN doc
    """
    cursor = db_conn.db.aql.execute(
        aql,
        bind_vars={'@collection': COLLECTION_NAME, 'identifier': identifier}
    )
    results = list(cursor)
    if not results:
        return None

    doc = results[0]
    now = datetime.now(timezone.utc).isoformat()

    doc.setdefault("sources", {})
    doc["sources"]["tleapi"] = {
        "line1": tle_data.get("line1"),
        "line2": tle_data.get("line2"),
        "name": tle_data.get("name"),
        "norad_id": norad_id,
        "fetched_at": tle_data.get("fetched_at"),
        "updated_at": now,
        "parsed": tle_data,
    }

    doc.setdefault("canonical", {})
    doc["canonical"]["tle"] = tle_data

    doc.setdefault("metadata", {})
    doc["metadata"]["last_updated_at"] = now

    collection.update(doc)
    return doc
