from typing import Optional, Dict, Any

import database.connection as db_conn
from database.connection import COLLECTION_NAME

ALIAS_TYPES = ("norad", "cospar", "discos", "vimpel", "kestrel")


def lookup_by_alias(alias_type: str, value: str) -> Optional[Dict[str, Any]]:
    """
    Look up an object document by an identifier alias.

    Args:
        alias_type: One of 'norad', 'cospar', 'discos', 'vimpel', 'kestrel'
        value: The alias value to search for

    Returns:
        The matched document or None
    """
    if alias_type not in ALIAS_TYPES:
        raise ValueError(f"Unknown alias type '{alias_type}'. Must be one of: {ALIAS_TYPES}")

    aql = """
    FOR doc IN @@collection
        FILTER doc.identifier_aliases.@alias_type == @value
        LIMIT 1
        RETURN doc
    """
    cursor = db_conn.db.aql.execute(
        aql,
        bind_vars={
            "@collection": COLLECTION_NAME,
            "alias_type": alias_type,
            "value": value,
        },
    )
    results = list(cursor)
    return results[0] if results else None


def lookup_by_norad(norad_id: str) -> Optional[Dict[str, Any]]:
    """Look up an object by NORAD catalog ID alias."""
    doc = lookup_by_alias("norad", norad_id)
    if doc:
        return doc
    aql = """
    FOR doc IN @@collection
        FILTER TO_STRING(doc.canonical.norad_cat_id) == @norad_id
        LIMIT 1
        RETURN doc
    """
    cursor = db_conn.db.aql.execute(
        aql,
        bind_vars={"@collection": COLLECTION_NAME, "norad_id": str(norad_id)},
    )
    results = list(cursor)
    return results[0] if results else None


def lookup_by_cospar(cospar_id: str) -> Optional[Dict[str, Any]]:
    """Look up an object by COSPAR / international designator."""
    doc = lookup_by_alias("cospar", cospar_id)
    if doc:
        return doc
    aql = """
    FOR doc IN @@collection
        FILTER doc.canonical.international_designator == @cospar_id
        LIMIT 1
        RETURN doc
    """
    cursor = db_conn.db.aql.execute(
        aql,
        bind_vars={"@collection": COLLECTION_NAME, "cospar_id": cospar_id},
    )
    results = list(cursor)
    return results[0] if results else None


def backfill_identifier_aliases(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build an identifier_aliases dict from the canonical fields of a document.

    Returns the aliases dict (does not persist; caller is responsible for update).
    """
    canonical = doc.get("canonical", {})
    aliases: Dict[str, Any] = {}

    norad = canonical.get("norad_cat_id")
    if norad is not None:
        aliases["norad"] = str(norad)

    cospar = canonical.get("international_designator")
    if cospar:
        aliases["cospar"] = cospar

    return aliases
