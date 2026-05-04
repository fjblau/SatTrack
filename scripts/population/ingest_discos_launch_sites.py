#!/usr/bin/env python3
"""
Ingest ESA DISCOS launch site records into the launch_sites vertex collection.

Run order: 2nd in the DISCOS ingestion sequence (after entities).

Usage:
    python scripts/population/ingest_discos_launch_sites.py [--dry-run]
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


def _make_site_doc(site: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    discos_id = site.get("discos_id")
    return {
        "_key": f"DISCOS-SITE-{discos_id}",
        "identifier": f"DISCOS-SITE-{discos_id}",
        "canonical": {
            "name": site.get("name"),
            "country": site.get("country"),
            "latitude": site.get("latitude"),
            "longitude": site.get("longitude"),
        },
        "sources": {
            "discos": {
                "ingested_at": now,
                "discos_id": discos_id,
                "raw": site,
            }
        },
        "metadata": {
            "transformations": [
                {
                    "source": "discos",
                    "action": "ingest",
                    "timestamp": now,
                    "operator": "ingest_discos_launch_sites",
                }
            ]
        },
    }


def run(dry_run: bool = False):
    if not db_conn.connect_arangodb():
        logger.error("Failed to connect to ArangoDB")
        sys.exit(1)

    logger.info("Fetching launch sites from DISCOS...")
    sites = discos_service.get_launch_sites()
    logger.info(f"Fetched {len(sites)} launch sites from DISCOS")

    if not sites:
        logger.warning("No launch sites returned — check DISCOS_API_TOKEN and connectivity")
        return

    col = db_module.db.collection("launch_sites")
    inserted = 0
    updated = 0

    for site in sites:
        doc = _make_site_doc(site)
        if dry_run:
            logger.info(f"[DRY RUN] Would upsert site: {doc['_key']}")
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
            logger.error(f"Failed to upsert site {doc.get('_key')}: {exc}")

    logger.info(f"Done — inserted={inserted} updated={updated} total={len(sites)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest DISCOS launch sites")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
