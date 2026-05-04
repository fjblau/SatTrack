#!/usr/bin/env python3
"""
Promote DISCOS launches: create launched_by, launched_via, and launched_from edges.

For each object with a DISCOS source envelope that includes a launch event reference,
create edges:
- launched_by: object → entity (operator)
- launched_via: object → launch_vehicle
- launched_from: object → launch_site

Usage:
    python scripts/maintenance/promote_discos_launches.py [--dry-run]
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _upsert_edge(col_name: str, from_id: str, to_id: str, extra: dict, dry_run: bool) -> bool:
    if dry_run:
        logger.info(f"[DRY RUN] Would create {col_name} edge: {from_id} → {to_id}")
        return True

    now = datetime.now(timezone.utc).isoformat()
    col = db_module.db.collection(col_name)
    try:
        cursor = db_module.db.aql.execute(
            """
            FOR e IN @@col
                FILTER e._from == @from AND e._to == @to
                LIMIT 1
                RETURN e
            """,
            bind_vars={"@col": col_name, "from": from_id, "to": to_id},
        )
        rows = list(cursor)
        existing = rows[0] if rows else None

        edge_doc = {"_from": from_id, "_to": to_id, **extra}
        if existing:
            transformations = existing.get("metadata", {}).get("transformations", [])
            transformations.append({
                "source": "discos",
                "action": "update",
                "timestamp": now,
                "operator": "promote_discos_launches",
            })
            transformations = transformations[-10:]
            col.update({
                "_key": existing["_key"],
                "metadata": {
                    **existing.get("metadata", {}),
                    "transformations": transformations,
                },
            })
        else:
            edge_doc["metadata"] = {
                "transformations": [
                    {
                        "source": "discos",
                        "action": "create",
                        "timestamp": now,
                        "operator": "promote_discos_launches",
                    }
                ]
            }
            col.insert(edge_doc)
        return True
    except Exception as exc:
        logger.error(f"Failed to upsert {col_name} edge {from_id} → {to_id}: {exc}")
        return False


def run(dry_run: bool = False):
    if not db_conn.connect_arangodb():
        logger.error("Failed to connect to ArangoDB")
        sys.exit(1)

    cursor = db_module.db.aql.execute(
        "FOR obj IN objects FILTER obj.sources.discos != null RETURN obj"
    )
    objects = list(cursor)
    logger.info(f"Processing {len(objects)} objects with DISCOS source envelope")

    launched_by_count = 0
    launched_via_count = 0
    launched_from_count = 0
    skipped = 0

    for obj in objects:
        discos_src = obj.get("sources", {}).get("discos", {})
        raw = discos_src.get("raw", {})
        obj_id = obj.get("_id")
        if not obj_id:
            skipped += 1
            continue

        cospar_launch_id = (
            raw.get("cosparLaunchId")
            or raw.get("cospar_launch_id")
            or obj.get("canonical", {}).get("international_designator", "").rsplit("-", 1)[0]
            if obj.get("canonical", {}).get("international_designator") else None
        )

        if cospar_launch_id:
            launch_key = cospar_launch_id.replace("/", "-")
            try:
                launch_doc = db_module.db.collection("launch_events").get(launch_key)
                if launch_doc:
                    launch_id = launch_doc["_id"]
                    launch_raw = launch_doc.get("sources", {}).get("discos", {}).get("raw", {})

                    site_id_ref = launch_raw.get("launchSiteId") or launch_raw.get("launch_site_id")
                    vehicle_id_ref = launch_raw.get("launchVehicleId") or launch_raw.get("launch_vehicle_id")
                    entity_id_ref = launch_raw.get("entityId") or launch_raw.get("entity_id")

                    if entity_id_ref:
                        ent_key = f"DISCOS-ENT-{entity_id_ref}"
                        try:
                            ent_doc = db_module.db.collection("entities").get(ent_key)
                            if ent_doc and _upsert_edge("launched_by", obj_id, ent_doc["_id"], {}, dry_run):
                                launched_by_count += 1
                        except Exception:
                            pass

                    if vehicle_id_ref:
                        veh_key = f"DISCOS-VEH-{vehicle_id_ref}"
                        try:
                            veh_doc = db_module.db.collection("launch_vehicles").get(veh_key)
                            if veh_doc and _upsert_edge("launched_via", obj_id, veh_doc["_id"], {}, dry_run):
                                launched_via_count += 1
                        except Exception:
                            pass

                    if site_id_ref:
                        site_key = f"DISCOS-SITE-{site_id_ref}"
                        try:
                            site_doc = db_module.db.collection("launch_sites").get(site_key)
                            if site_doc and _upsert_edge("launched_from", obj_id, site_doc["_id"], {}, dry_run):
                                launched_from_count += 1
                        except Exception:
                            pass
            except Exception as exc:
                logger.debug(f"Launch lookup failed for {launch_key}: {exc}")
        else:
            skipped += 1

    logger.info(
        f"Done — launched_by={launched_by_count} launched_via={launched_via_count} "
        f"launched_from={launched_from_count} skipped={skipped} total={len(objects)}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Promote DISCOS launch edges")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
