#!/usr/bin/env python3
"""
Loss-event auto-draft trigger script for TALON customer tasks.

Finds loss_events rows without a corresponding drafted customer_tasks row
and inserts one.
"""
import sys
import json
import uuid
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def build_draft_task(loss_event: dict, now: datetime) -> dict:
    le_key = loss_event["_key"]

    satellite_id = loss_event.get("satellite_id")
    if not satellite_id:
        primary_object_id = loss_event.get("primary_object_id")
        if primary_object_id:
            satellite_id = primary_object_id
        elif loss_event.get("norad_id"):
            satellite_id = f"objects/{loss_event['norad_id']}"
        else:
            satellite_id = None

    time_start = (
        loss_event.get("created_at")
        or loss_event.get("detected_at")
        or loss_event.get("occurred_at")
        or now.isoformat()
    )

    try:
        start_dt = datetime.fromisoformat(time_start)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        start_dt = now

    time_end = (start_dt + timedelta(days=7)).isoformat()
    delivery_due = (now + timedelta(days=14)).isoformat()

    task = {
        "_key": f"TSK-LE-{le_key}",
        "task_number": f"TALON-TSK-LE-{le_key}",
        "status": "drafted",
        "priority": "urgent",
        "requesting_party_id": None,
        "target_object_id": satellite_id,
        "related_policy_id": loss_event.get("policy_id"),
        "trigger": {
            "type": "loss_event",
            "source": f"loss_events/{le_key}",
        },
        "scope": {
            "observation_count_min": 6,
            "observation_count_max": 12,
            "time_window_start": time_start,
            "time_window_end": time_end,
            "required_sensor_types": ["optical_visible", "optical_ir"],
            "min_independence_score": 0.7,
            "maneuver_authorised": True,
            "max_maneuver_delta_v_mps": 3.0,
        },
        "commercial_terms": None,
        "sla": {
            "delivery_due": delivery_due,
            "qa_window_days": 1,
        },
        "timestamps": {
            "created_at": now.isoformat(),
        },
        "internal_notes": f"Auto-drafted from loss event {le_key}",
    }
    return task


def _resolve_requesting_party(loss_event: dict, db) -> str | None:
    policy_id = loss_event.get("policy_id")
    if policy_id:
        pol_key = policy_id.split("/")[-1]
        try:
            cursor = db.aql.execute(
                """
                FOR ii IN insured_interests
                    FILTER ii.policy_id == @pol_id
                    FILTER ii.role == "carrier" OR ii.interest_type == "carrier"
                    LIMIT 1
                    RETURN ii.party_id
                """,
                bind_vars={"pol_id": policy_id},
            )
            rows = list(cursor)
            if rows and rows[0]:
                return rows[0]
        except Exception:
            pass

    try:
        cursor = db.aql.execute(
            """
            FOR p IN parties
                LIMIT 1
                RETURN CONCAT("parties/", p._key)
            """
        )
        rows = list(cursor)
        if rows:
            return rows[0]
    except Exception:
        pass

    return None


def _task_exists(le_key: str, db) -> bool:
    cursor = db.aql.execute(
        """
        FOR t IN customer_tasks
            FILTER t.trigger.type == "loss_event"
            FILTER t.trigger.source == CONCAT("loss_events/", @le_key)
            LIMIT 1
            RETURN t._key
        """,
        bind_vars={"le_key": le_key},
    )
    return len(list(cursor)) > 0


def _insert_task_and_edges(task: dict, loss_event: dict, db):
    le_key = loss_event["_key"]

    tasks_col = db.collection("customer_tasks")
    tasks_col.insert(task)
    task_key = task["_key"]

    edges_col = db.collection("task_relates_to_loss_event")
    edges_col.insert({
        "_key": f"TRLE-{task_key}",
        "_from": f"customer_tasks/{task_key}",
        "_to": f"loss_events/{le_key}",
    })

    requesting_party_id = task.get("requesting_party_id")
    if requesting_party_id:
        rb_col = db.collection("task_requested_by")
        rb_col.insert({
            "_key": f"TRB-{task_key}",
            "_from": f"customer_tasks/{task_key}",
            "_to": requesting_party_id,
        })

    target_object_id = task.get("target_object_id")
    if target_object_id:
        to_col = db.collection("task_targets_object")
        to_col.insert({
            "_key": f"TTO-{task_key}",
            "_from": f"customer_tasks/{task_key}",
            "_to": target_object_id,
        })

    trans_col = db.collection("customer_task_transitions")
    trans_col.insert({
        "_key": str(uuid.uuid4()),
        "task_id": f"customer_tasks/{task_key}",
        "from_status": None,
        "to_status": "drafted",
        "occurred_at": task["timestamps"]["created_at"],
        "actor": "system:loss_event_trigger",
        "actor_type": "system",
        "note": "",
    })


def _ensure_edge_collections(db):
    for col_name in [
        "task_relates_to_loss_event",
        "task_requested_by",
        "task_targets_object",
    ]:
        if not db.has_collection(col_name):
            db.create_collection(col_name, edge=True)


def main():
    parser = argparse.ArgumentParser(
        description="Auto-draft customer tasks from unprocessed loss events."
    )
    parser.add_argument("--dry-run", action="store_true", help="Print without writing to DB")
    parser.add_argument("--loss-event-key", metavar="KEY", help="Process only this loss event key")
    parser.add_argument("--force", action="store_true", help="Re-draft even if a task already exists")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)

    if args.dry_run:
        if args.loss_event_key:
            le_key = args.loss_event_key
            mock_le = {
                "_key": le_key,
                "status": "active",
                "occurred_at": now.isoformat(),
            }
            task = build_draft_task(mock_le, now)
            print(f"[DRY-RUN] Would draft for loss event {le_key}:")
            print(json.dumps(task, indent=2, default=str))
        else:
            print("[DRY-RUN] Would query all active/investigating loss events and draft tasks.")
        sys.exit(0)

    import database as db_module
    from database.connection import connect_mongodb

    try:
        connected = connect_mongodb()
    except Exception as exc:
        print(f"ERROR: Could not connect to ArangoDB — {exc}")
        sys.exit(1)

    if not connected:
        print("ERROR: Could not connect to ArangoDB. Check ARANGO_HOST, ARANGO_USER, ARANGO_PASSWORD.")
        sys.exit(1)

    db = db_module.db

    try:
        if args.loss_event_key:
            cursor = db.aql.execute(
                "FOR le IN loss_events FILTER le._key == @key RETURN le",
                bind_vars={"key": args.loss_event_key},
            )
        else:
            cursor = db.aql.execute(
                """
                FOR le IN loss_events
                    FILTER le.status IN ["active", "investigating"]
                    RETURN le
                """
            )
        loss_events = list(cursor)
    except Exception as exc:
        print(f"ERROR: Failed to query ArangoDB — {exc}")
        sys.exit(1)

    try:
        _ensure_edge_collections(db)
    except Exception as exc:
        print(f"ERROR: Failed to ensure edge collections — {exc}")
        sys.exit(1)

    inserted = 0
    skipped = 0

    for le in loss_events:
        le_key = le["_key"]

        target_object_id = (
            le.get("satellite_id")
            or le.get("primary_object_id")
        )
        if not target_object_id and not le.get("norad_id"):
            print(f"[WARN] Loss event {le_key} has no resolvable satellite — skipping")
            continue

        if not args.force and _task_exists(le_key, db):
            print(f"[SKIP] Task already exists for {le_key}")
            skipped += 1
            continue

        task = build_draft_task(le, now)

        if args.force and _task_exists(le_key, db):
            suffix = uuid.uuid4().hex[:8]
            task["_key"] = f"TSK-LE-{le_key}-{suffix}"
            task["task_number"] = f"TALON-TSK-LE-{le_key}-{suffix}"

        requesting_party_id = _resolve_requesting_party(le, db)
        task["requesting_party_id"] = requesting_party_id

        try:
            _insert_task_and_edges(task, le, db)
            print(f"[NEW] Drafted {task['_key']} for loss event {le_key}")
            inserted += 1
        except Exception as exc:
            print(f"[ERROR] Failed to insert task for {le_key} — {exc}")

    print(f"\nDone. {inserted} tasks drafted, {skipped} skipped.")


if __name__ == "__main__":
    main()
