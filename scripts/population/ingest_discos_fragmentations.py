#!/usr/bin/env python3
"""
Ingest ESA DISCOS fragmentation event records into the fragmentation_events vertex collection.

Captures all DISCOS attributes verbatim under sources.discos.raw.
Canonical fragment count fields (fragment_count_kessler, fragment_count_discos,
fragment_count_estimated) are initialised to null here; they are populated by
ingest_discos_attributions and promote_discos_fragmentations respectively.

Transformation log:
  - New records: action="ingest"
  - Re-run with no change: action="verify"
  - Re-run with changes: action="ingest" with changed_fields list

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


def _raw_changed_fields(old_raw: dict, new_raw: dict) -> list:
    all_keys = set(old_raw.keys()) | set(new_raw.keys())
    return [k for k in sorted(all_keys) if old_raw.get(k) != new_raw.get(k)]


def _make_event_doc(event: dict, now: str) -> dict:
    discos_id = event.get("discos_id")
    return {
        "_key": f"DISCOS-FRAG-{discos_id}",
        "identifier": f"DISCOS-FRAG-{discos_id}",
        "canonical": {
            "epoch": event.get("epoch"),
            "altitude_km": event.get("altitude"),
            "latitude": event.get("latitude"),
            "longitude": event.get("longitude"),
            "event_type": event.get("type") or event.get("eventType"),
            "comment": event.get("comment"),
            "fragment_count_kessler": None,
            "fragment_count_discos": None,
            "fragment_count_estimated": None,
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
    verified = 0

    now = datetime.now(timezone.utc).isoformat()

    for event in events:
        doc = _make_event_doc(event, now)
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
                existing_raw = existing.get("sources", {}).get("discos", {}).get("raw", {})
                new_raw = event
                changed = _raw_changed_fields(existing_raw, new_raw)

                transformations = existing.get("metadata", {}).get("transformations", [])
                if changed:
                    transformations.append({
                        "source": "discos",
                        "action": "ingest",
                        "timestamp": now,
                        "operator": "ingest_discos_fragmentations",
                        "changed_fields": changed,
                    })
                    transformations = transformations[-10:]
                    doc["metadata"]["transformations"] = transformations
                    existing_canonical = existing.get("canonical", {})
                    for fk in ("fragment_count_kessler", "fragment_count_discos", "fragment_count_estimated"):
                        if existing_canonical.get(fk) is not None:
                            doc["canonical"][fk] = existing_canonical[fk]
                    col.update(doc)
                    updated += 1
                else:
                    transformations.append({
                        "source": "discos",
                        "action": "verify",
                        "timestamp": now,
                        "operator": "ingest_discos_fragmentations",
                    })
                    transformations = transformations[-10:]
                    col.update({
                        "_key": doc["_key"],
                        "metadata": {
                            **existing.get("metadata", {}),
                            "transformations": transformations,
                        },
                    })
                    verified += 1
            else:
                col.insert(doc)
                inserted += 1
        except Exception as exc:
            logger.error(f"Failed to upsert event {doc.get('_key')}: {exc}")

    logger.info(f"Done — inserted={inserted} updated={updated} verified={verified} total={len(events)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest DISCOS fragmentation events")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
