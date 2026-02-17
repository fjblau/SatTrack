from datetime import datetime, timezone
from typing import Optional, Dict, Any
from database.utils.normalization import CountryNormalizer


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
    
    # Ensure name is always populated (fallback to identifier)
    if not canonical.get("name"):
        canonical["name"] = doc.get("identifier", "Unknown")
    
    # Ensure launch_date is populated (alias for date_of_launch)
    if not canonical.get("launch_date") and canonical.get("date_of_launch"):
        canonical["launch_date"] = canonical["date_of_launch"]
    elif canonical.get("launch_date") and not canonical.get("date_of_launch"):
        canonical["date_of_launch"] = canonical["launch_date"]
    
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
    
    # Normalize country field using CountryNormalizer
    raw_country = canonical.get("country_of_origin")
    if raw_country:
        normalizer = CountryNormalizer()
        canonical["country"] = normalizer.normalize(raw_country)
    else:
        canonical["country"] = None
    
    doc["canonical"] = canonical
