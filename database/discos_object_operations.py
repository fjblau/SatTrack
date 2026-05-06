"""
Shared helper for ensuring a DISCOS object exists in the objects collection.

Used by both ingest_discos_objects (bulk sampling) and ingest_discos_attributions
(lazy fragment ingestion). Encapsulates the match-or-create pattern so both scripts
stay consistent.
"""
import re
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def _build_discos_source_envelope(discos_obj: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "ingested_at": now,
        "discos_id": discos_obj.get("discos_id"),
        "cospar_id": discos_obj.get("cosparId"),
        "satno": discos_obj.get("satno"),
        "object_class": discos_obj.get("objectClass"),
        "mass_kg": discos_obj.get("mass"),
        "shape": discos_obj.get("shape"),
        "height_m": discos_obj.get("height"),
        "width_m": discos_obj.get("width"),
        "depth_m": discos_obj.get("depth"),
        "diameter_m": discos_obj.get("diameter"),
        "span_m": discos_obj.get("span"),
        "xSectMax": discos_obj.get("xSectMax"),
        "xSectMin": discos_obj.get("xSectMin"),
        "xSectAvg": discos_obj.get("xSectAvg"),
    }


def _envelope_changed(existing_envelope: dict, new_envelope: dict) -> bool:
    """Return True if any data field (excluding ingested_at) differs."""
    skip = {"ingested_at"}
    all_keys = set(existing_envelope) | set(new_envelope) - skip
    for k in all_keys:
        if k in skip:
            continue
        if existing_envelope.get(k) != new_envelope.get(k):
            return True
    return False


def _make_surrogate_doc(discos_obj: dict, now: str, operator: str) -> dict:
    discos_id = discos_obj.get("discos_id")
    cospar_id = discos_obj.get("cosparId")
    return {
        "_key": f"DISCOS-{discos_id}",
        "identifier": f"DISCOS-{discos_id}",
        "canonical": {
            "satellite_name": discos_obj.get("name"),
            "international_designator": cospar_id,
            "object_class": discos_obj.get("objectClass"),
            "mass_kg": discos_obj.get("mass"),
        },
        "identifier_aliases": {
            "discos": str(discos_id),
            "cospar": cospar_id,
            "norad": str(discos_obj.get("satno")) if discos_obj.get("satno") else None,
        },
        "sources": {
            "discos": _build_discos_source_envelope(discos_obj),
        },
        "metadata": {
            "attribution_status": "pending",
            "policy_overlay": None,
            "transformations": [
                {
                    "source": "discos",
                    "action": "ingest",
                    "timestamp": now,
                    "operator": operator,
                    "detail": "No matching object found; surrogate created",
                }
            ],
        },
    }


def _lookup_existing(db, discos_obj: dict) -> Optional[dict]:
    """
    Look up an existing object using NORAD → COSPAR (with base-designator fallback) → DISCOS ID.

    Returns the first matching document or None.
    """
    satno = discos_obj.get("satno")
    cospar_id = discos_obj.get("cosparId")
    discos_id = discos_obj.get("discos_id")

    if satno is not None:
        try:
            rows = list(db.aql.execute(
                "FOR obj IN objects FILTER obj.canonical.norad_cat_id == @satno "
                "OR obj.identifier_aliases.norad == TO_STRING(@satno) LIMIT 1 RETURN obj",
                bind_vars={"satno": satno},
            ))
            if rows:
                return rows[0]
        except Exception as exc:
            logger.warning(f"NORAD lookup failed for satno={satno}: {exc}")

    if cospar_id:
        candidates = [cospar_id]
        base = re.sub(r'[A-Z]+$', '', cospar_id)
        if base and base != cospar_id:
            candidates.append(base)
        try:
            rows = list(db.aql.execute(
                "FOR obj IN objects FILTER obj.canonical.international_designator IN @c "
                "OR obj.identifier_aliases.cospar IN @c LIMIT 1 RETURN obj",
                bind_vars={"c": candidates},
            ))
            if rows:
                return rows[0]
        except Exception as exc:
            logger.warning(f"COSPAR lookup failed for cosparId={cospar_id}: {exc}")

    if discos_id is not None:
        try:
            rows = list(db.aql.execute(
                "FOR obj IN objects FILTER obj.identifier_aliases.discos == @did LIMIT 1 RETURN obj",
                bind_vars={"did": str(discos_id)},
            ))
            if rows:
                return rows[0]
        except Exception as exc:
            logger.warning(f"DISCOS ID lookup failed for discos_id={discos_id}: {exc}")

    return None


def ensure_discos_object_exists(
    discos_object_payload: dict,
    db_connection,
    discos_service=None,
    *,
    operator: str,
) -> Tuple[str, str]:
    """
    Ensure a DISCOS object exists in the objects collection.

    Lookup order: NORAD → COSPAR (with base-designator fallback) → DISCOS ID.

    Returns (_key, status) where status is one of:
      "matched_existing"   — object already existed and was updated with DISCOS source envelope
      "created_new"        — new surrogate object record created
      "verified_unchanged" — object existed and DISCOS source envelope was unchanged
    """
    now = datetime.now(timezone.utc).isoformat()
    discos_id = discos_object_payload.get("discos_id")
    col = db_connection.collection("objects")

    existing = _lookup_existing(db_connection, discos_object_payload)

    if existing:
        existing_key = existing["_key"]
        new_envelope = _build_discos_source_envelope(discos_object_payload)
        existing_envelope = existing.get("sources", {}).get("discos", {})

        if not _envelope_changed(existing_envelope, new_envelope):
            transformations = existing.get("metadata", {}).get("transformations", [])
            transformations = transformations[-9:] + [{
                "source": "discos",
                "action": "verify",
                "timestamp": now,
                "operator": operator,
                "discos_id": discos_id,
            }]
            try:
                col.update({
                    "_key": existing_key,
                    "metadata": {
                        **existing.get("metadata", {}),
                        "transformations": transformations,
                    },
                })
            except Exception as exc:
                logger.warning(f"Failed to write verify transformation on {existing_key}: {exc}")
            return existing_key, "verified_unchanged"

        transformations = existing.get("metadata", {}).get("transformations", [])
        transformations = transformations[-9:] + [{
            "source": "discos",
            "action": "ingest",
            "timestamp": now,
            "operator": operator,
            "discos_id": discos_id,
        }]
        try:
            col.update({
                "_key": existing_key,
                "sources": {
                    **existing.get("sources", {}),
                    "discos": new_envelope,
                },
                "identifier_aliases": {
                    **existing.get("identifier_aliases", {}),
                    "discos": str(discos_id),
                },
                "metadata": {
                    **existing.get("metadata", {}),
                    "transformations": transformations,
                },
            })
        except Exception as exc:
            logger.error(f"Failed to update existing object {existing_key}: {exc}")
            raise
        return existing_key, "matched_existing"

    doc = _make_surrogate_doc(discos_object_payload, now, operator)
    surrogate_key = doc["_key"]
    try:
        existing_surrogate = None
        try:
            existing_surrogate = col.get(surrogate_key)
        except Exception:
            pass

        if existing_surrogate:
            transformations = existing_surrogate.get("metadata", {}).get("transformations", [])
            new_envelope = _build_discos_source_envelope(discos_object_payload)
            existing_envelope = existing_surrogate.get("sources", {}).get("discos", {})

            if not _envelope_changed(existing_envelope, new_envelope):
                transformations = transformations[-9:] + [{
                    "source": "discos",
                    "action": "verify",
                    "timestamp": now,
                    "operator": operator,
                    "discos_id": discos_id,
                }]
                col.update({
                    "_key": surrogate_key,
                    "metadata": {
                        **existing_surrogate.get("metadata", {}),
                        "transformations": transformations,
                    },
                })
                return surrogate_key, "verified_unchanged"

            transformations = transformations[-9:] + [{
                "source": "discos",
                "action": "ingest",
                "timestamp": now,
                "operator": operator,
                "discos_id": discos_id,
            }]
            doc["metadata"]["transformations"] = transformations
            col.update(doc)
        else:
            col.insert(doc)
    except Exception as exc:
        logger.error(f"Failed to upsert surrogate {surrogate_key}: {exc}")
        raise
    return surrogate_key, "created_new"
