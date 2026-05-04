#!/usr/bin/env python3
"""
Ingest ESA DISCOS entity records into the entities vertex collection.

Run order: 1st in the DISCOS ingestion sequence.
All entities (operators, countries, organisations) are fetched and upserted.

Usage:
    python scripts/population/ingest_discos_entities.py [--dry-run]
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _make_entity_doc(entity: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    discos_id = entity.get("discos_id")
    return {
        "_key": f"DISCOS-ENT-{discos_id}",
        "identifier": f"DISCOS-ENT-{discos_id}",
        "canonical": {
            "name": entity.get("name"),
            "country": entity.get("country"),
            "entity_type": entity.get("entityType"),
        },
        "sources": {
            "discos": {
                "ingested_at": now,
                "discos_id": discos_id,
                "raw": entity,
            }
        },
        "metadata": {
            "transformations": [
                {
                    "source": "discos",
                    "action": "ingest",
                    "timestamp": now,
                    "operator": "ingest_discos_entities",
                }
            ]
        },
    }


def run(dry_run: bool = False):
    if not db_conn.connect_arangodb():
        logger.error("Failed to connect to ArangoDB")
        sys.exit(1)

    logger.info("Fetching entities from DISCOS...")
    entities = discos_service.get_entities()
    logger.info(f"Fetched {len(entities)} entities from DISCOS")

    if not entities:
        logger.warning("No entities returned — check DISCOS_API_TOKEN and connectivity")
        return

    col = db_module.db.collection("entities")
    inserted = 0
    updated = 0
    skipped = 0

    for entity in entities:
        doc = _make_entity_doc(entity)
        if dry_run:
            logger.info(f"[DRY RUN] Would upsert entity: {doc['_key']}")
            skipped += 1
            continue
        try:
            existing = None
            try:
                existing = col.get(doc["_key"])
            except Exception:
                pass

            if existing:
                transformations = existing.get("metadata", {}).get("transformations", [])
                transformations.append(doc["metadata"]["transformations"][0])
                transformations = transformations[-10:]
                doc["metadata"]["transformations"] = transformations
                col.update(doc)
                updated += 1
            else:
                col.insert(doc)
                inserted += 1
        except Exception as exc:
            logger.error(f"Failed to upsert entity {doc.get('_key')}: {exc}")

    logger.info(f"Done — inserted={inserted} updated={updated} skipped={skipped} total={len(entities)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest DISCOS entities")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without writing")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
