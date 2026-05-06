#!/usr/bin/env python3
"""
Bulk-ingest a sample of ESA DISCOS space object records, enriching existing objects
via cosparId / satno join and creating surrogate documents for unmatched entries.

Purpose: bulk sampling of DISCOS objects for development and general catalog presence.
This script is NOT the primary mechanism for fragment ingestion — fragments are ingested
lazily as a side effect of running ingest_discos_attributions. For comprehensive operational
payload ingestion a separate script tuned to active-payload filtering should be added in a
future spec; the current sampling is dev-oriented.

Join key: cosparId (COSPAR / international designator), with satno (NORAD) fallback.
- Match found: enrich the existing object document with a DISCOS source envelope.
- No match: create a surrogate document with key DISCOS-<discosId>.

cosparId conflicts (cospar match but satno differs) are logged in metadata.transformations
and surfaced for operator review via the merge utility.

Run order: 5th in the DISCOS ingestion sequence (after launches).

Usage:
    python scripts/population/ingest_discos_objects.py [--dry-run] [--batch-size N]
"""
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
from database.discos_object_operations import ensure_discos_object_exists

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


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
    matched = 0
    created = 0
    unchanged = 0
    conflicts_logged = 0
    surrogates_deleted = 0
    errors = 0

    for discos_obj in discos_objs:
        discos_id = discos_obj.get("discos_id")
        cospar_id = discos_obj.get("cosparId")
        satno = discos_obj.get("satno")

        if dry_run:
            logger.info(f"[DRY RUN] Would ensure discos_id={discos_id} cospar={cospar_id}")
            continue

        try:
            object_key, status = ensure_discos_object_exists(
                discos_obj,
                db_module.db,
                operator="ingest_discos_objects",
            )

            if status == "matched_existing":
                matched += 1
                existing_doc = col.get(object_key)
                existing_satno = (
                    existing_doc.get("canonical", {}).get("norad_cat_id")
                    or existing_doc.get("identifier_aliases", {}).get("norad")
                ) if existing_doc else None
                satno_str = str(satno) if satno is not None else None
                existing_satno_str = str(existing_satno) if existing_satno is not None else None
                if satno_str and existing_satno_str and satno_str != existing_satno_str:
                    logger.warning(
                        f"satno conflict for cospar={cospar_id}: "
                        f"DISCOS={satno_str} vs DB={existing_satno_str} — logged for operator review"
                    )
                    conflicts_logged += 1

                surrogate_key = f"DISCOS-{discos_id}"
                if surrogate_key != object_key:
                    try:
                        surrogate = col.get(surrogate_key)
                        if surrogate:
                            col.delete(surrogate_key)
                            surrogates_deleted += 1
                            logger.info(
                                f"Deleted orphan surrogate {surrogate_key} "
                                f"(data now on {object_key})"
                            )
                    except Exception as exc:
                        logger.warning(f"Could not delete surrogate {surrogate_key}: {exc}")

            elif status == "created_new":
                created += 1
            elif status == "verified_unchanged":
                unchanged += 1

        except Exception as exc:
            logger.error(f"Failed to process discos_id={discos_id}: {exc}")
            errors += 1

    logger.info(
        f"Done — matched={matched} created={created} unchanged={unchanged} "
        f"surrogates_deleted={surrogates_deleted} conflicts_logged={conflicts_logged} "
        f"errors={errors} total={len(discos_objs)}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk-ingest DISCOS space objects (dev/sampling)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()
    run(dry_run=args.dry_run, batch_size=args.batch_size)
