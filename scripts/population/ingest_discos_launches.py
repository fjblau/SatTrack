#!/usr/bin/env python3
"""
Ingest ESA DISCOS launch event records into the launch_events vertex collection.

Run order: 4th in the DISCOS ingestion sequence (after sites and vehicles).

Usage:
    python scripts/population/ingest_discos_launches.py [--dry-run]
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


def _make_launch_doc(launch: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    discos_id = launch.get("discos_id")
    cospar_launch_id = launch.get("cosparLaunchId") or launch.get("cospar_launch_id")
    key = cospar_launch_id.replace("/", "-") if cospar_launch_id else f"DISCOS-LAUNCH-{discos_id}"
    return {
        "_key": key,
        "identifier": key,
        "canonical": {
            "cospar_launch_id": cospar_launch_id,
            "launch_date": launch.get("epoch") or launch.get("launchDate"),
            "launch_site_id": launch.get("launchSiteId"),
            "launch_vehicle_id": launch.get("launchVehicleId"),
        },
        "sources": {
            "discos": {
                "ingested_at": now,
                "discos_id": discos_id,
                "raw": launch,
            }
        },
        "metadata": {
            "transformations": [
                {
                    "source": "discos",
                    "action": "ingest",
                    "timestamp": now,
                    "operator": "ingest_discos_launches",
                }
            ]
        },
    }


def run(dry_run: bool = False):
    if not db_conn.connect_arangodb():
        logger.error("Failed to connect to ArangoDB")
        sys.exit(1)

    logger.info("Fetching launch events from DISCOS...")
    launches = discos_service.get_launch_events()
    logger.info(f"Fetched {len(launches)} launch events from DISCOS")

    if not launches:
        logger.warning("No launch events returned — check DISCOS_API_TOKEN and connectivity")
        return

    col = db_module.db.collection("launch_events")
    inserted = 0
    updated = 0

    for launch in launches:
        doc = _make_launch_doc(launch)
        if dry_run:
            logger.info(f"[DRY RUN] Would upsert launch: {doc['_key']}")
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
            logger.error(f"Failed to upsert launch {doc.get('_key')}: {exc}")

    logger.info(f"Done — inserted={inserted} updated={updated} total={len(launches)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest DISCOS launch events")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
