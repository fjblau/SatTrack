#!/usr/bin/env python3
"""
Ingest ESA DISCOS space object records, enriching existing objects via cosparId join.

Join key: cosparId (COSPAR / international designator), with satno (NORAD) fallback.
- Match found: enrich the existing object document with a DISCOS source envelope.
- No match: create a surrogate document with key DISCOS-<discosId>.

The cospar lookup tries the full cosparId (e.g. "2022-151B") and also the base
launch designator without piece letter (e.g. "2022-151"). If neither matches, a
satno (NORAD number) lookup is attempted. This handles cases where GCAT stores
the international_designator without a piece letter while DISCOS includes it.

cosparId conflicts (cospar match but satno differs) are logged in metadata.transformations
and surfaced for operator review via the merge utility.

Run order: 5th in the DISCOS ingestion sequence (after launches).

Usage:
    python scripts/population/ingest_discos_objects.py [--dry-run] [--batch-size N]
"""
import re
import sys
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

import database.connection as db_conn
import database as db_module
from api.services import discos_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _lookup_by_cospar(cospar_id: str):
    """Find an existing object by COSPAR / international designator.

    Tries the full cosparId first (e.g. "2022-151B"), then strips the trailing
    piece letter and retries with the base launch designator (e.g. "2022-151").
    """
    if not cospar_id:
        return None
    candidates = [cospar_id]
    base = re.sub(r'[A-Z]+$', '', cospar_id)
    if base and base != cospar_id:
        candidates.append(base)
    try:
        cursor = db_module.db.aql.execute(
            """
            FOR obj IN objects
                FILTER obj.canonical.international_designator IN @candidates
                   OR obj.identifier_aliases.cospar IN @candidates
                LIMIT 1
                RETURN obj
            """,
            bind_vars={"candidates": candidates},
        )
        rows = list(cursor)
        return rows[0] if rows else None
    except Exception as exc:
        logger.warning(f"cospar lookup failed for {cospar_id}: {exc}")
        return None


def _lookup_by_satno(satno):
    """Find an existing object by satno (NORAD catalogue number)."""
    if satno is None:
        return None
    try:
        cursor = db_module.db.aql.execute(
            """
            FOR obj IN objects
                FILTER obj.canonical.norad_cat_id == @satno
                   OR obj.identifier_aliases.norad == TO_STRING(@satno)
                LIMIT 1
                RETURN obj
            """,
            bind_vars={"satno": satno},
        )
        rows = list(cursor)
        return rows[0] if rows else None
    except Exception as exc:
        logger.warning(f"satno lookup failed for {satno}: {exc}")
        return None


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


def _make_surrogate_doc(discos_obj: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
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
                    "action": "surrogate_created",
                    "timestamp": now,
                    "operator": "ingest_discos_objects",
                    "detail": "No matching object found by cosparId; surrogate created",
                }
            ],
        },
    }


def run(dry_run: bool = False, batch_size: int = 500):
    if not db_conn.connect_arangodb():
        logger.error("Failed to connect to ArangoDB")
        sys.exit(1)

    logger.info("Fetching space objects from DISCOS...")
    discos_objs = discos_service.get_objects()
    logger.info(f"Fetched {len(discos_objs)} objects from DISCOS")

    if not discos_objs:
        logger.warning("No objects returned — check DISCOS_API_TOKEN and connectivity")
        return

    col = db_module.db.collection("objects")
    enriched = 0
    surrogates_created = 0
    surrogates_updated = 0
    conflicts_logged = 0
    errors = 0

    for discos_obj in discos_objs:
        cospar_id = discos_obj.get("cosparId")
        discos_id = discos_obj.get("discos_id")
        satno = discos_obj.get("satno")
        now = datetime.now(timezone.utc).isoformat()

        existing = _lookup_by_cospar(cospar_id) if cospar_id else None
        if existing is None and satno is not None:
            existing = _lookup_by_satno(satno)
            if existing:
                logger.info(
                    f"Matched discos_id={discos_id} cospar={cospar_id} "
                    f"to {existing['_key']} via satno={satno} fallback"
                )

        if existing:
            existing_satno = (
                existing.get("canonical", {}).get("norad_cat_id")
                or existing.get("identifier_aliases", {}).get("norad")
            )
            satno_str = str(satno) if satno is not None else None
            existing_satno_str = str(existing_satno) if existing_satno is not None else None

            transformation = {
                "source": "discos",
                "action": "enrich",
                "timestamp": now,
                "operator": "ingest_discos_objects",
                "discos_id": discos_id,
                "cospar_id": cospar_id,
            }

            if satno_str and existing_satno_str and satno_str != existing_satno_str:
                logger.warning(
                    f"satno conflict for cospar={cospar_id}: "
                    f"DISCOS={satno_str} vs DB={existing_satno_str} — logged for operator review"
                )
                transformation["conflict"] = {
                    "field": "satno",
                    "discos_value": satno_str,
                    "db_value": existing_satno_str,
                    "resolution": "cospar_wins",
                }
                conflicts_logged += 1

            if dry_run:
                logger.info(
                    f"[DRY RUN] Would enrich existing object {existing['_key']} "
                    f"with DISCOS source (cospar={cospar_id})"
                )
                enriched += 1
                continue

            try:
                transformations = existing.get("metadata", {}).get("transformations", [])
                transformations.append(transformation)
                transformations = transformations[-10:]

                col.update({
                    "_key": existing["_key"],
                    "sources": {
                        **existing.get("sources", {}),
                        "discos": _build_discos_source_envelope(discos_obj),
                    },
                    "identifier_aliases": {
                        **existing.get("identifier_aliases", {}),
                        "discos": str(discos_id),
                    },
                    "metadata": {
                        **existing.get("metadata", {}),
                        "attribution_status": existing.get("metadata", {}).get(
                            "attribution_status", "pending"
                        ),
                        "policy_overlay": existing.get("metadata", {}).get("policy_overlay"),
                        "transformations": transformations,
                    },
                })
                enriched += 1
            except Exception as exc:
                logger.error(f"Failed to enrich {existing.get('_key')}: {exc}")
                errors += 1
        else:
            doc = _make_surrogate_doc(discos_obj)
            if dry_run:
                logger.info(f"[DRY RUN] Would create surrogate {doc['_key']}")
                surrogates_created += 1
                continue
            try:
                existing_surrogate = None
                try:
                    existing_surrogate = col.get(doc["_key"])
                except Exception:
                    pass

                if existing_surrogate:
                    transformations = existing_surrogate.get("metadata", {}).get("transformations", [])
                    transformations.append(doc["metadata"]["transformations"][0])
                    transformations = transformations[-10:]
                    doc["metadata"]["transformations"] = transformations
                    col.update(doc)
                    surrogates_updated += 1
                else:
                    col.insert(doc)
                    surrogates_created += 1
            except Exception as exc:
                logger.error(f"Failed to upsert surrogate {doc.get('_key')}: {exc}")
                errors += 1

    logger.info(
        f"Done — enriched={enriched} surrogates_created={surrogates_created} "
        f"surrogates_updated={surrogates_updated} conflicts_logged={conflicts_logged} "
        f"errors={errors} total={len(discos_objs)}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest DISCOS space objects")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()
    run(dry_run=args.dry_run, batch_size=args.batch_size)
