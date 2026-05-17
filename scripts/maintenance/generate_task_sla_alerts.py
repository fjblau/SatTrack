#!/usr/bin/env python3
"""
Hourly SLA alert generator for TALON customer tasks.

Scans customer_tasks and writes task_sla_alerts rows.
"""
import sys
import json
import argparse
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DELIVERY_OVERDUE_EXEMPT = {"delivered", "accepted_by_customer", "closed", "cancelled"}

SEVERITY_MAP = {
    "delivery_overdue": "high",
    "qa_overdue": "medium",
    "quote_expiring_soon": "low",
    "quote_expired": "medium",
}


def _parse_dt(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def is_delivery_overdue(task: dict, now: datetime) -> bool:
    if task.get("status") in DELIVERY_OVERDUE_EXEMPT:
        return False
    sla = task.get("sla") or {}
    delivery_due = sla.get("delivery_due")
    if not delivery_due:
        return False
    timestamps = task.get("timestamps") or {}
    if timestamps.get("delivered_at"):
        return False
    return _parse_dt(delivery_due) < now


def is_qa_overdue(task: dict, under_review_ts: str | None, now: datetime) -> bool:
    if task.get("status") != "under_review":
        return False
    if not under_review_ts:
        return False
    sla = task.get("sla") or {}
    qa_window_days = sla.get("qa_window_days")
    if qa_window_days is None:
        return False
    entered = _parse_dt(under_review_ts)
    return (now - entered).total_seconds() > qa_window_days * 86400


def is_quote_expiring_soon(task: dict, now: datetime) -> bool:
    if task.get("status") != "quoted":
        return False
    timestamps = task.get("timestamps") or {}
    quote_expires_at = timestamps.get("quote_expires_at")
    if not quote_expires_at:
        return False
    expires = _parse_dt(quote_expires_at)
    return now < expires <= now + timedelta(hours=48)


def is_quote_expired(task: dict, now: datetime) -> bool:
    if task.get("status") != "quoted":
        return False
    timestamps = task.get("timestamps") or {}
    quote_expires_at = timestamps.get("quote_expires_at")
    if not quote_expires_at:
        return False
    return _parse_dt(quote_expires_at) < now


def _build_alert(task: dict, alert_type: str, now: datetime, details: dict) -> dict:
    task_key = task["_key"]
    return {
        "_key": f"ALERT-{uuid.uuid4()}",
        "task_id": f"customer_tasks/{task_key}",
        "alert_type": alert_type,
        "triggered_at": now.isoformat(),
        "severity": SEVERITY_MAP[alert_type],
        "status": "active",
        "simulated": True,
        "details": details,
    }


def _get_under_review_ts(task: dict, db) -> str | None:
    timestamps = task.get("timestamps") or {}
    if timestamps.get("under_review_at"):
        return timestamps["under_review_at"]
    task_key = task["_key"]
    task_id = f"customer_tasks/{task_key}"
    cursor = db.aql.execute(
        """
        FOR t IN customer_task_transitions
            FILTER t.task_id == @task_id AND t.to_status == "under_review"
            SORT t.occurred_at ASC
            LIMIT 1
            RETURN t.occurred_at
        """,
        bind_vars={"task_id": task_id},
    )
    rows = list(cursor)
    return rows[0] if rows else None


def _load_active_alerts(db) -> set:
    cursor = db.aql.execute(
        """
        FOR a IN task_sla_alerts
            FILTER a.status == "active"
            RETURN {task_id: a.task_id, alert_type: a.alert_type}
        """
    )
    return {(r["task_id"], r["alert_type"]) for r in cursor}


def _collect_alerts_for_task(task: dict, db, now: datetime, active_set: set) -> list[dict]:
    task_key = task["_key"]
    task_id = f"customer_tasks/{task_key}"
    alerts = []

    candidates = []

    sla = task.get("sla") or {}
    timestamps = task.get("timestamps") or {}

    if is_delivery_overdue(task, now):
        details = {
            "expected": sla.get("delivery_due"),
            "current_task_status": task.get("status"),
        }
        candidates.append(("delivery_overdue", details))

    under_review_ts = None
    if task.get("status") == "under_review":
        under_review_ts = _get_under_review_ts(task, db)
    if is_qa_overdue(task, under_review_ts, now):
        details = {
            "expected": under_review_ts,
            "current_task_status": task.get("status"),
        }
        candidates.append(("qa_overdue", details))

    if is_quote_expiring_soon(task, now):
        details = {
            "expected": timestamps.get("quote_expires_at"),
            "current_task_status": task.get("status"),
        }
        candidates.append(("quote_expiring_soon", details))

    if is_quote_expired(task, now):
        details = {
            "expected": timestamps.get("quote_expires_at"),
            "current_task_status": task.get("status"),
        }
        candidates.append(("quote_expired", details))

    for alert_type, details in candidates:
        key = (task_id, alert_type)
        if key in active_set:
            alerts.append({"_skip": True, "task_id": task_id, "alert_type": alert_type, "task_key": task_key})
        else:
            alerts.append({
                "_skip": False,
                "task_key": task_key,
                "doc": _build_alert(task, alert_type, now, details),
            })

    return alerts


def _resolve_stale_alerts(tasks_by_key: dict, db, now: datetime):
    cursor = db.aql.execute(
        """
        FOR a IN task_sla_alerts
            FILTER a.status == "active"
            RETURN a
        """
    )
    active_alerts = list(cursor)
    resolved_count = 0

    for alert in active_alerts:
        task_id = alert.get("task_id", "")
        alert_type = alert.get("alert_type", "")
        parts = task_id.split("/")
        if len(parts) != 2:
            continue
        task_key = parts[1]
        task = tasks_by_key.get(task_key)
        if task is None:
            continue

        still_active = False
        if alert_type == "delivery_overdue":
            still_active = is_delivery_overdue(task, now)
        elif alert_type == "qa_overdue":
            under_review_ts = _get_under_review_ts(task, db)
            still_active = is_qa_overdue(task, under_review_ts, now)
        elif alert_type == "quote_expiring_soon":
            still_active = is_quote_expiring_soon(task, now)
        elif alert_type == "quote_expired":
            still_active = is_quote_expired(task, now)

        if not still_active:
            col = db.collection("task_sla_alerts")
            col.update({"_key": alert["_key"], "status": "resolved"})
            resolved_count += 1
            print(f"[RESOLVED] {alert_type} for {task_key}")

    return resolved_count


def main():
    parser = argparse.ArgumentParser(description="Generate SLA alerts for customer tasks.")
    parser.add_argument("--dry-run", action="store_true", help="Print alerts without writing to DB")
    parser.add_argument("--resolve-stale", action="store_true", help="Resolve active alerts whose condition is no longer true")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)

    if args.dry_run:
        from scripts.population.seed_customer_tasks import CUSTOMER_TASKS
        inserted = 0
        skipped = 0
        for task in CUSTOMER_TASKS:
            task_key = task["_key"]
            sla = task.get("sla") or {}
            timestamps = task.get("timestamps") or {}
            candidates = []
            if is_delivery_overdue(task, now):
                candidates.append(("delivery_overdue", {
                    "expected": sla.get("delivery_due"),
                    "current_task_status": task.get("status"),
                }))
            under_review_ts = (task.get("timestamps") or {}).get("under_review_at")
            if is_qa_overdue(task, under_review_ts, now):
                candidates.append(("qa_overdue", {
                    "expected": under_review_ts,
                    "current_task_status": task.get("status"),
                }))
            if is_quote_expiring_soon(task, now):
                candidates.append(("quote_expiring_soon", {
                    "expected": timestamps.get("quote_expires_at"),
                    "current_task_status": task.get("status"),
                }))
            if is_quote_expired(task, now):
                candidates.append(("quote_expired", {
                    "expected": timestamps.get("quote_expires_at"),
                    "current_task_status": task.get("status"),
                }))
            for alert_type, details in candidates:
                alert_doc = _build_alert(task, alert_type, now, details)
                print(f"[DRY-RUN] {alert_type} for {task_key} (severity={SEVERITY_MAP[alert_type]})")
                print(json.dumps(alert_doc, indent=2, default=str))
                inserted += 1
        print(f"\nDone. {inserted} alerts would be inserted, {skipped} skipped.")
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
        if not db.has_collection("task_sla_alerts"):
            db.create_collection("task_sla_alerts")

        cursor = db.aql.execute("FOR t IN customer_tasks RETURN t")
        tasks = list(cursor)
    except Exception as exc:
        print(f"ERROR: Failed to query ArangoDB — {exc}")
        sys.exit(1)

    tasks_by_key = {t["_key"]: t for t in tasks}
    active_set = _load_active_alerts(db)
    alerts_col = db.collection("task_sla_alerts")

    inserted = 0
    skipped = 0

    for task in tasks:
        task_key = task["_key"]
        results = _collect_alerts_for_task(task, db, now, active_set)
        for result in results:
            alert_type = result.get("alert_type") or result.get("doc", {}).get("alert_type")
            severity = SEVERITY_MAP.get(alert_type, "unknown")
            if result["_skip"]:
                print(f"[SKIP] {alert_type} for {task_key} — already active")
                skipped += 1
            else:
                doc = result["doc"]
                alerts_col.insert(doc)
                active_set.add((doc["task_id"], doc["alert_type"]))
                print(f"[NEW] {alert_type} for {task_key} (severity={severity})")
                inserted += 1

    if args.resolve_stale:
        _resolve_stale_alerts(tasks_by_key, db, now)

    print(f"\nDone. {inserted} new alerts inserted, {skipped} skipped.")


if __name__ == "__main__":
    main()
