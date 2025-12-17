from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
import os

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27018")
DB_NAME = "kessler"
COLLECTION_NAME = "satellites"

client = None
db = None
satellites_collection = None


def connect_mongodb():
    """Initialize MongoDB connection"""
    global client, db, satellites_collection
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        client.admin.command('ping')
        db = client[DB_NAME]
        satellites_collection = db[COLLECTION_NAME]
        
        satellites_collection.create_index("canonical.international_designator", unique=False)
        satellites_collection.create_index("canonical.registration_number", unique=False)
        satellites_collection.create_index("identifier", unique=True)
        
        print(f"Connected to MongoDB: {DB_NAME}.{COLLECTION_NAME}")
        return True
    except ConnectionFailure as e:
        print(f"Failed to connect to MongoDB: {e}")
        return False


def disconnect_mongodb():
    """Close MongoDB connection"""
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
    
    existing = collection.find_one({"identifier": identifier})
    
    if existing:
        existing["sources"][source] = {
            **data,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        existing["metadata"]["sources_available"] = list(existing["sources"].keys())
        existing["metadata"]["last_updated_at"] = datetime.now(timezone.utc).isoformat()
        
        update_canonical(existing)
        
        collection.replace_one(
            {"identifier": identifier},
            existing
        )
        return existing
    else:
        doc = {
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
                "source_priority": ["unoosa", "celestrak", "spacetrack", "kaggle"]
            }
        }
        
        update_canonical(doc)
        result = collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc


def update_canonical(doc: Dict[str, Any]):
    """
    Update canonical section from source nodes based on priority.
    Source priority: UNOOSA > CelesTrak > Space-Track > Kaggle
    """
    source_priority = doc["metadata"].get("source_priority", ["unoosa", "celestrak", "spacetrack", "kaggle"])
    sources = doc["sources"]
    
    source_priority = [s for s in source_priority if s in sources] + [s for s in sources if s not in source_priority]
    
    canonical = {}
    
    canonical_fields = [
        "name", "object_name", "country_of_origin", "international_designator",
        "registration_number", "norad_cat_id", "date_of_launch", "function", "status",
        "registration_document", "un_registered", "gso_location",
        "date_of_decay_or_change", "secretariat_remarks", "external_website",
        "launch_vehicle", "place_of_launch", "object_type", "rcs"
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
        return collection.find_one({"canonical.international_designator": international_designator})
    elif registration_number:
        return collection.find_one({"canonical.registration_number": registration_number})
    elif name:
        return collection.find_one({"canonical.name": {"$regex": name, "$options": "i"}})
    
    return None


def search_satellites(
    query: str = "",
    country: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    skip: int = 0
) -> List[Dict[str, Any]]:
    """Search satellites with optional filters"""
    collection = get_satellites_collection()
    
    filters = {}
    
    if query:
        filters["$or"] = [
            {"canonical.name": {"$regex": query, "$options": "i"}},
            {"canonical.object_name": {"$regex": query, "$options": "i"}},
            {"canonical.international_designator": {"$regex": query, "$options": "i"}},
            {"canonical.registration_number": {"$regex": query, "$options": "i"}}
        ]
    
    if country:
        filters["canonical.country_of_origin"] = {"$regex": country, "$options": "i"}
    
    if status:
        filters["canonical.status"] = {"$regex": status, "$options": "i"}
    
    return list(
        collection.find(filters)
        .skip(skip)
        .limit(limit)
    )


def count_satellites(
    query: Optional[str] = None,
    country: Optional[str] = None,
    status: Optional[str] = None
) -> int:
    """Count satellites with optional filters"""
    collection = get_satellites_collection()
    
    filters = {}
    
    if query:
        filters["$or"] = [
            {"canonical.name": {"$regex": query, "$options": "i"}},
            {"canonical.object_name": {"$regex": query, "$options": "i"}},
            {"canonical.international_designator": {"$regex": query, "$options": "i"}},
            {"canonical.registration_number": {"$regex": query, "$options": "i"}}
        ]
    
    if country:
        filters["canonical.country_of_origin"] = {"$regex": country, "$options": "i"}
    
    if status:
        filters["canonical.status"] = {"$regex": status, "$options": "i"}
    
    return collection.count_documents(filters)


def get_all_countries() -> List[str]:
    """Get list of unique countries"""
    collection = get_satellites_collection()
    return collection.distinct("canonical.country_of_origin")


def get_all_statuses() -> List[str]:
    """Get list of unique statuses"""
    collection = get_satellites_collection()
    return collection.distinct("canonical.status")


def clear_collection():
    """Clear all documents from satellites collection"""
    collection = get_satellites_collection()
    collection.delete_many({})
