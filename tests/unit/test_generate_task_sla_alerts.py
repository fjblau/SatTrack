import pytest
from datetime import datetime, timezone, timedelta

from scripts.maintenance.generate_task_sla_alerts import (
    is_delivery_overdue,
    is_qa_overdue,
    is_quote_expiring_soon,
    is_quote_expired,
)

NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=timezone.utc)


def _ts(dt: datetime) -> str:
    return dt.isoformat()


def _past(days=0, hours=0) -> str:
    return _ts(NOW - timedelta(days=days, hours=hours))


def _future(days=0, hours=0) -> str:
    return _ts(NOW + timedelta(days=days, hours=hours))


def test_delivery_overdue_true():
    task = {
        "status": "executing",
        "sla": {"delivery_due": _past(days=1)},
        "timestamps": {},
    }
    assert is_delivery_overdue(task, NOW) is True


def test_delivery_overdue_false_delivered():
    task = {
        "status": "delivered",
        "sla": {"delivery_due": _past(days=1)},
        "timestamps": {"delivered_at": _past(days=2)},
    }
    assert is_delivery_overdue(task, NOW) is False


def test_delivery_overdue_false_not_yet_due():
    task = {
        "status": "executing",
        "sla": {"delivery_due": _future(days=5)},
        "timestamps": {},
    }
    assert is_delivery_overdue(task, NOW) is False


def test_delivery_overdue_false_exempt_status():
    for status in ("delivered", "accepted_by_customer", "closed", "cancelled"):
        task = {
            "status": status,
            "sla": {"delivery_due": _past(days=3)},
            "timestamps": {},
        }
        assert is_delivery_overdue(task, NOW) is False, f"Expected False for status={status}"


def test_qa_overdue_true():
    task = {
        "status": "under_review",
        "sla": {"qa_window_days": 2},
        "timestamps": {},
    }
    under_review_ts = _past(days=5)
    assert is_qa_overdue(task, under_review_ts, NOW) is True


def test_qa_overdue_false_within_window():
    task = {
        "status": "under_review",
        "sla": {"qa_window_days": 3},
        "timestamps": {},
    }
    under_review_ts = _past(days=1)
    assert is_qa_overdue(task, under_review_ts, NOW) is False


def test_qa_overdue_false_wrong_status():
    task = {
        "status": "executing",
        "sla": {"qa_window_days": 2},
        "timestamps": {},
    }
    assert is_qa_overdue(task, _past(days=5), NOW) is False


def test_qa_overdue_false_no_ts():
    task = {
        "status": "under_review",
        "sla": {"qa_window_days": 2},
        "timestamps": {},
    }
    assert is_qa_overdue(task, None, NOW) is False


def test_quote_expiring_soon_true():
    task = {
        "status": "quoted",
        "timestamps": {"quote_expires_at": _future(hours=10)},
    }
    assert is_quote_expiring_soon(task, NOW) is True


def test_quote_expiring_soon_false_already_expired():
    task = {
        "status": "quoted",
        "timestamps": {"quote_expires_at": _past(hours=1)},
    }
    assert is_quote_expiring_soon(task, NOW) is False


def test_quote_expiring_soon_false_too_far_future():
    task = {
        "status": "quoted",
        "timestamps": {"quote_expires_at": _future(hours=72)},
    }
    assert is_quote_expiring_soon(task, NOW) is False


def test_quote_expiring_soon_false_wrong_status():
    task = {
        "status": "executing",
        "timestamps": {"quote_expires_at": _future(hours=10)},
    }
    assert is_quote_expiring_soon(task, NOW) is False


def test_quote_expired_true():
    task = {
        "status": "quoted",
        "timestamps": {"quote_expires_at": _past(days=2)},
    }
    assert is_quote_expired(task, NOW) is True


def test_quote_expired_false_not_yet():
    task = {
        "status": "quoted",
        "timestamps": {"quote_expires_at": _future(days=1)},
    }
    assert is_quote_expired(task, NOW) is False


def test_quote_expired_false_wrong_status():
    task = {
        "status": "executing",
        "timestamps": {"quote_expires_at": _past(days=2)},
    }
    assert is_quote_expired(task, NOW) is False
