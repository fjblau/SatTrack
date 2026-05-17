import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from database.customer_task_ops import (
    ALLOWED_TRANSITIONS,
    CUSTOMER_STATUS_MAP,
    can_transition,
    validate_transition,
    get_allowed_next_states,
    customer_status,
    transition_task,
)


ALL_STATUSES = list(ALLOWED_TRANSITIONS.keys())


def test_allowed_transitions_complete():
    for status in CUSTOMER_STATUS_MAP:
        assert status in ALLOWED_TRANSITIONS, f"'{status}' missing from ALLOWED_TRANSITIONS"


def test_can_transition_valid():
    valid_pairs = [
        ("drafted", "submitted"),
        ("submitted", "scoping"),
        ("scoping", "quoted"),
        ("quoted", "accepted"),
        ("delivered", "disputed"),
    ]
    for from_s, to_s in valid_pairs:
        assert can_transition(from_s, to_s) is True, f"Expected {from_s}->{to_s} to be valid"


def test_can_transition_invalid():
    invalid_pairs = [
        ("closed", "executing"),
        ("cancelled", "submitted"),
        ("drafted", "executing"),
        ("accepted_by_customer", "disputed"),
        ("executing", "quoted"),
    ]
    for from_s, to_s in invalid_pairs:
        assert can_transition(from_s, to_s) is False, f"Expected {from_s}->{to_s} to be invalid"


def test_validate_transition_raises():
    with pytest.raises(ValueError, match="closed"):
        validate_transition("closed", "executing")


def test_get_allowed_next_states_closed():
    assert get_allowed_next_states("closed") == []


def test_customer_status_all_statuses():
    for status in ALLOWED_TRANSITIONS:
        label = customer_status(status)
        assert isinstance(label, str) and len(label) > 0, f"Empty label for status '{status}'"


def _make_db(task_doc):
    db = MagicMock()
    tasks_col = MagicMock()
    trans_col = MagicMock()

    tasks_col.get.return_value = task_doc
    if task_doc is not None:
        updated = dict(task_doc)
        if task_doc.get("status"):
            tasks_col.get.side_effect = None
        tasks_col.get.return_value = task_doc

    db.collection.side_effect = lambda name: (
        tasks_col if name == "customer_tasks" else trans_col
    )
    return db, tasks_col, trans_col


def test_transition_task_happy_path():
    task = {"_key": "TSK-001", "status": "submitted", "timestamps": {}}
    db = MagicMock()
    tasks_col = MagicMock()
    trans_col = MagicMock()

    tasks_col.get.return_value = task
    updated_task = {"_key": "TSK-001", "status": "scoping", "timestamps": {}}
    tasks_col.get.side_effect = [task, updated_task]

    db.collection.side_effect = lambda name: (
        tasks_col if name == "customer_tasks" else trans_col
    )

    result = transition_task(db, "TSK-001", "scoping", "admin@talon.com", "staff")

    trans_col.insert.assert_called_once()
    inserted = trans_col.insert.call_args[0][0]
    assert inserted["from_status"] == "submitted"
    assert inserted["to_status"] == "scoping"
    assert inserted["actor"] == "admin@talon.com"
    assert inserted["actor_type"] == "staff"

    tasks_col.update.assert_called_once()
    update_arg = tasks_col.update.call_args[0][0]
    assert update_arg["status"] == "scoping"

    assert result == updated_task


def test_transition_task_quote_expiry():
    task = {"_key": "TSK-002", "status": "scoping", "timestamps": {}}
    db = MagicMock()
    tasks_col = MagicMock()
    trans_col = MagicMock()

    tasks_col.get.return_value = task
    tasks_col.get.side_effect = [
        task,
        {"_key": "TSK-002", "status": "quoted", "timestamps": {"quote_expires_at": "2026-05-31T00:00:00+00:00"}},
    ]

    db.collection.side_effect = lambda name: (
        tasks_col if name == "customer_tasks" else trans_col
    )

    transition_task(db, "TSK-002", "quoted", "admin@talon.com", "staff")

    tasks_col.update.assert_called_once()
    update_arg = tasks_col.update.call_args[0][0]
    assert update_arg["status"] == "quoted"
    assert "timestamps" in update_arg
    assert "quote_expires_at" in update_arg["timestamps"]
    assert "quoted_at" in update_arg["timestamps"]

    expires_at = update_arg["timestamps"]["quote_expires_at"]
    quoted_at = update_arg["timestamps"]["quoted_at"]
    dt_expires = datetime.fromisoformat(expires_at)
    dt_quoted = datetime.fromisoformat(quoted_at)
    delta = dt_expires - dt_quoted
    assert delta.days == 14


def test_transition_task_not_found():
    db = MagicMock()
    tasks_col = MagicMock()
    tasks_col.get.return_value = None
    db.collection.return_value = tasks_col

    with pytest.raises(ValueError, match="not found"):
        transition_task(db, "MISSING", "scoping", "actor", "staff")


def test_transition_task_invalid_transition():
    task = {"_key": "TSK-003", "status": "closed", "timestamps": {}}
    db = MagicMock()
    tasks_col = MagicMock()
    tasks_col.get.return_value = task
    db.collection.return_value = tasks_col

    with pytest.raises(ValueError):
        transition_task(db, "TSK-003", "executing", "actor", "staff")
