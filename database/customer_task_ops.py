from datetime import datetime, timezone, timedelta
import uuid

from database.connection import (
    COLLECTION_CUSTOMER_TASKS,
    COLLECTION_CUSTOMER_TASK_TRANS,
)

ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "drafted":                ["submitted", "cancelled"],
    "submitted":              ["scoping", "cancelled"],
    "scoping":                ["quoted", "cancelled"],
    "quoted":                 ["accepted", "cancelled"],
    "accepted":               ["scheduled"],
    "scheduled":              ["executing"],
    "executing":              ["observations_complete"],
    "observations_complete":  ["under_review"],
    "under_review":           ["delivered"],
    "delivered":              ["accepted_by_customer", "disputed"],
    "disputed":               ["under_review", "cancelled"],
    "accepted_by_customer":   ["closed"],
    "closed":                 [],
    "cancelled":              [],
}

CUSTOMER_STATUS_MAP: dict[str, str] = {
    "drafted":               "Requested",
    "submitted":             "Requested",
    "scoping":               "Under review by TALON",
    "quoted":                "Quoted",
    "accepted":              "In progress",
    "scheduled":             "In progress",
    "executing":             "In progress",
    "observations_complete": "In progress",
    "under_review":          "In progress",
    "delivered":             "Delivered",
    "accepted_by_customer":  "Complete",
    "closed":                "Complete",
    "disputed":              "Dispute open",
    "cancelled":             "Cancelled",
}


def can_transition(from_status: str, to_status: str) -> bool:
    return to_status in ALLOWED_TRANSITIONS.get(from_status, [])


def validate_transition(from_status: str, to_status: str) -> None:
    if not can_transition(from_status, to_status):
        allowed = ALLOWED_TRANSITIONS.get(from_status, [])
        raise ValueError(
            f"Cannot transition from '{from_status}' to '{to_status}'. "
            f"Allowed next states: {allowed}"
        )


def get_allowed_next_states(current_status: str) -> list[str]:
    return ALLOWED_TRANSITIONS.get(current_status, [])


def customer_status(internal_status: str) -> str:
    return CUSTOMER_STATUS_MAP[internal_status]


def transition_task(
    db,
    task_id: str,
    to_status: str,
    actor: str,
    actor_type: str,
    note: str = "",
) -> dict:
    tasks_col = db.collection(COLLECTION_CUSTOMER_TASKS)
    task = tasks_col.get(task_id)
    if task is None:
        raise ValueError(f"Task '{task_id}' not found.")

    from_status = task["status"]
    validate_transition(from_status, to_status)

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    trans_doc = {
        "_key": str(uuid.uuid4()),
        "task_id": f"{COLLECTION_CUSTOMER_TASKS}/{task_id}",
        "from_status": from_status,
        "to_status": to_status,
        "occurred_at": now_iso,
        "actor": actor,
        "actor_type": actor_type,
        "note": note,
    }
    trans_col = db.collection(COLLECTION_CUSTOMER_TASK_TRANS)
    trans_col.insert(trans_doc)

    update_fields: dict = {"status": to_status}

    if to_status == "quoted":
        quoted_at = now_iso
        expires_at = (now + timedelta(days=14)).isoformat()
        timestamps = task.get("timestamps", {})
        timestamps["quoted_at"] = quoted_at
        timestamps["quote_expires_at"] = expires_at
        update_fields["timestamps"] = timestamps

    tasks_col.update({"_key": task_id, **update_fields})
    updated = tasks_col.get(task_id)
    return updated
