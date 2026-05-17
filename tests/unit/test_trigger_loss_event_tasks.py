import pytest
from datetime import datetime, timezone, timedelta

from scripts.maintenance.trigger_loss_event_tasks import build_draft_task

NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=timezone.utc)


def _make_loss_event(key="LE-2026-014", **kwargs):
    base = {
        "_key": key,
        "status": "active",
        "occurred_at": "2026-05-10T08:00:00+00:00",
        "primary_object_id": "objects/SAT-ABC",
    }
    base.update(kwargs)
    return base


def test_build_draft_task_from_loss_event():
    le = _make_loss_event()
    task = build_draft_task(le, NOW)
    assert task["trigger"]["type"] == "loss_event"
    assert task["status"] == "drafted"
    assert task["priority"] == "urgent"
    time_end = datetime.fromisoformat(task["scope"]["time_window_end"])
    time_start = datetime.fromisoformat(task["scope"]["time_window_start"])
    if time_end.tzinfo is None:
        time_end = time_end.replace(tzinfo=timezone.utc)
    if time_start.tzinfo is None:
        time_start = time_start.replace(tzinfo=timezone.utc)
    assert (time_end - time_start).days == 7


def test_build_draft_task_key_format():
    le = _make_loss_event(key="LE-2026-014")
    task = build_draft_task(le, NOW)
    assert task["_key"] == "TSK-LE-LE-2026-014"


def test_build_draft_task_scope_defaults():
    le = _make_loss_event()
    task = build_draft_task(le, NOW)
    scope = task["scope"]
    assert scope["observation_count_min"] == 6
    assert scope["maneuver_authorised"] is True


def test_build_draft_task_trigger_source():
    le = _make_loss_event(key="LE-2026-014")
    task = build_draft_task(le, NOW)
    assert task["trigger"]["source"] == "loss_events/LE-2026-014"


def test_build_draft_task_sla_14_days():
    le = _make_loss_event()
    task = build_draft_task(le, NOW)
    delivery_due = datetime.fromisoformat(task["sla"]["delivery_due"])
    if delivery_due.tzinfo is None:
        delivery_due = delivery_due.replace(tzinfo=timezone.utc)
    delta = delivery_due - NOW
    assert delta.days == 14


def test_build_draft_task_uses_detected_at_over_occurred_at():
    le = _make_loss_event(
        detected_at="2026-05-01T00:00:00+00:00",
        occurred_at="2026-04-01T00:00:00+00:00",
    )
    task = build_draft_task(le, NOW)
    assert task["scope"]["time_window_start"] == "2026-05-01T00:00:00+00:00"


def test_build_draft_task_satellite_id_from_primary_object_id():
    le = _make_loss_event(primary_object_id="objects/SAT-XYZ")
    task = build_draft_task(le, NOW)
    assert task["target_object_id"] == "objects/SAT-XYZ"


def test_build_draft_task_satellite_id_explicit():
    le = _make_loss_event(satellite_id="objects/SAT-EXPLICIT", primary_object_id="objects/SAT-XYZ")
    task = build_draft_task(le, NOW)
    assert task["target_object_id"] == "objects/SAT-EXPLICIT"


def test_build_draft_task_norad_id_fallback():
    le = {
        "_key": "LE-2026-099",
        "status": "active",
        "occurred_at": "2026-05-10T08:00:00+00:00",
        "norad_id": "25544",
    }
    task = build_draft_task(le, NOW)
    assert task["target_object_id"] == "objects/25544"


def test_build_draft_task_scope_max():
    le = _make_loss_event()
    task = build_draft_task(le, NOW)
    assert task["scope"]["observation_count_max"] == 12


def test_build_draft_task_internal_notes():
    le = _make_loss_event(key="LE-2026-014")
    task = build_draft_task(le, NOW)
    assert "LE-2026-014" in task["internal_notes"]
