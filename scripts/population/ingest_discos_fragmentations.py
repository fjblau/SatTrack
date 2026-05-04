#!/usr/bin/env python3
"""
Ingest ESA DISCOS fragmentation event records into the fragmentation_events vertex collection.

Run order: 6th in the DISCOS ingestion sequence (after objects).

Usage:
    python scripts/population/ingest_discos_fragmentations.py [--dry-run]
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


def _make_event_doc(event: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    discos_id = event.get("discos_id")
    return {
        "_key": f"DISCOS-FRAG-{discos_id}",
        "identifier": f"DISCOS-FRAG-{discos_id}",
        "canonical": {
            "epoch": event.get("epoch"),
            "altitude_km": event.get("altitude"),
            "event_type": event.get("type") or event.get("eventType"),
            "fragment_count": event.get("fragmentCount"),
            "casualty_risk": event.get("casualtyRisk"),
            "comment": event.get("comment"),
        },
        "sources": {
            "discos": {
                "ingested_at": now,
                "discos_id": discos_id,
                "raw": event,
            }
        },
        "metadata": {
            "policy_overlay": None,
            "transformations": [
                {
                    "source": "discos",
                    "action": "ingest",
                    "timestamp": now,
                    "operator": "ingest_discos_fragmentations",
                }
            ],
        },
    }


def run(dry_run: bool = False):
    if not db_conn.connect_arangodb():
        logger.error("Failed to connect to ArangoDB")
        sys.exit(1)

    logger.info("Fetching fragmentation events from DISCOS...")
    events = discos_service.get_fragmentation_events()
    logger.info(f"Fetched {len(events)} fragmentation events from DISCOS")

    if not events:
        logger.warning("No fragmentation events returned — check DISCOS_API_TOKEN and connectivity")
        return

    col = db_module.db.collection("fragmentation_events")
    inserted = 0
    updated = 0

    for event in events:
        doc = _make_event_doc(event)
        if dry_run:
            logger.info(f"[DRY RUN] Would upsert event: {doc['_key']}")
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
            logger.error(f"Failed to upsert event {doc.get('_key')}: {exc}")

    logger.info(f"Done — inserted={inserted} updated={updated} total={len(events)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest DISCOS fragmentation events")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
