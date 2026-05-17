#!/usr/bin/env python3
"""
Seed demo data for the TALON Customer Tasks overlay.

Idempotent — safe to run multiple times (upsert by _key).

Collections created/populated:
  customer_tasks, customer_task_transitions, task_deliverables, task_sla_alerts

Edge collections created/populated:
  task_requested_by, task_targets_object, task_relates_to_policy,
  task_relates_to_loss_event, task_produced_deliverable
"""
import sys
import json
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

NOW = datetime.now(timezone.utc)


def ts(dt: datetime) -> str:
    return dt.isoformat()


def ts_future(days=0, hours=0) -> str:
    return ts(NOW + timedelta(days=days, hours=hours))


def ts_past(days=0, hours=0) -> str:
    return ts(NOW - timedelta(days=days, hours=hours))


# ---------------------------------------------------------------------------
# Fixture definitions
# ---------------------------------------------------------------------------

PLACEHOLDER_PARTIES = [
    {
        "_key": "party-cust-alpha",
        "name": "Alpha Orbital Ventures",
        "type": "customer",
        "country": "US",
        "roles": ["customer"],
    },
    {
        "_key": "party-cust-bravo",
        "name": "Bravo Space Systems",
        "type": "customer",
        "country": "DE",
        "roles": ["customer"],
    },
    {
        "_key": "party-cust-charlie",
        "name": "Charlie Satellite Ltd",
        "type": "customer",
        "country": "GB",
        "roles": ["customer"],
    },
]

NORAD_TARGETS = [25544, 49260, 55557, 55119]

POLICY_KEYS = ["POL-2026-001", "POL-2026-002", "POL-2026-003"]
LOSS_EVENT_KEYS = ["LE-2026-001", "LE-2026-002"]

CUSTOMER_TASKS = [
    # §6.1 canonical: TSK-2026-0001 — closed
    {
        "_key": "TSK-2026-0001",
        "task_ref": "TSK-2026-0001",
        "title": "Annual risk characterisation — ISS",
        "description": "Full observational risk assessment for the International Space Station ahead of policy renewal.",
        "status": "closed",
        "requesting_party_id": "parties/party-cust-alpha",
        "target_object_id": "observations/25544",
        "target_norad_id": 25544,
        "trigger": {"type": "renewal_cycle", "policy_id": "POL-2026-001", "renewal_date": "2026-04-01"},
        "sla": {
            "response_due": ts_past(days=90),
            "delivery_due": ts_past(days=60),
            "qa_window_days": 5,
        },
        "timestamps": {
            "created_at": ts_past(days=120),
            "submitted_at": ts_past(days=119),
            "scoping_started_at": ts_past(days=115),
            "quoted_at": ts_past(days=110),
            "accepted_at": ts_past(days=108),
            "scheduled_at": ts_past(days=100),
            "executing_started_at": ts_past(days=90),
            "observations_complete_at": ts_past(days=75),
            "under_review_at": ts_past(days=72),
            "delivered_at": ts_past(days=65),
            "accepted_by_customer_at": ts_past(days=62),
            "closed_at": ts_past(days=60),
            "quote_expires_at": ts_past(days=100),
        },
        "quote": {
            "amount_usd": 48000,
            "line_items": [
                {"description": "Optical observation campaign (30 passes)", "unit_price_usd": 1200, "quantity": 30, "subtotal_usd": 36000},
                {"description": "Risk report & QA", "unit_price_usd": 12000, "quantity": 1, "subtotal_usd": 12000},
            ],
            "valid_until": ts_past(days=100),
            "issued_by": "talon-ops@talon.example",
        },
        "assigned_analyst": "analyst-01@talon.example",
        "created_at": ts_past(days=120),
        "updated_at": ts_past(days=60),
        "_task_seed": True,
    },

    # §6.2 canonical: TSK-2026-0028 — executing
    {
        "_key": "TSK-2026-0028",
        "task_ref": "TSK-2026-0028",
        "title": "Post-conjunction characterisation — Starlink cluster",
        "description": "Observation campaign following reported close approach between Starlink units and debris field.",
        "status": "executing",
        "requesting_party_id": "parties/party-cust-bravo",
        "target_object_id": "observations/49260",
        "target_norad_id": 49260,
        "trigger": {"type": "loss_event", "loss_event_id": "LE-2026-001"},
        "sla": {
            "response_due": ts_future(days=2),
            "delivery_due": ts_future(days=14),
            "qa_window_days": 5,
        },
        "timestamps": {
            "created_at": ts_past(days=10),
            "submitted_at": ts_past(days=9),
            "scoping_started_at": ts_past(days=8),
            "quoted_at": ts_past(days=7),
            "accepted_at": ts_past(days=6),
            "scheduled_at": ts_past(days=4),
            "executing_started_at": ts_past(days=2),
            "quote_expires_at": ts_future(days=3),
        },
        "quote": {
            "amount_usd": 22500,
            "line_items": [
                {"description": "Emergency optical survey (15 passes)", "unit_price_usd": 1200, "quantity": 15, "subtotal_usd": 18000},
                {"description": "Conjunction risk report", "unit_price_usd": 4500, "quantity": 1, "subtotal_usd": 4500},
            ],
            "valid_until": ts_future(days=3),
            "issued_by": "talon-ops@talon.example",
        },
        "assigned_analyst": "analyst-02@talon.example",
        "created_at": ts_past(days=10),
        "updated_at": ts_past(days=2),
        "_task_seed": True,
    },

    # §6.3 canonical: TSK-DRAFT-2026-0055 — drafted
    {
        "_key": "TSK-DRAFT-2026-0055",
        "task_ref": "TSK-DRAFT-2026-0055",
        "title": "Exploratory characterisation — TianHe-1 replacement orbit",
        "description": "Customer preliminary inquiry for observation coverage of NORAD 55557 following reported manoeuvre.",
        "status": "drafted",
        "requesting_party_id": "parties/party-cust-charlie",
        "target_object_id": "observations/55557",
        "target_norad_id": 55557,
        "trigger": {"type": "customer_request"},
        "sla": {
            "response_due": ts_future(days=5),
            "delivery_due": ts_future(days=30),
            "qa_window_days": 5,
        },
        "timestamps": {
            "created_at": ts_past(hours=6),
        },
        "assigned_analyst": None,
        "created_at": ts_past(hours=6),
        "updated_at": ts_past(hours=6),
        "_task_seed": True,
    },

    # Additional tasks covering remaining statuses
    {
        "_key": "TSK-2026-0002",
        "task_ref": "TSK-2026-0002",
        "title": "Routine health check — NORAD 55119",
        "description": "Scheduled quarterly observation of debris object.",
        "status": "submitted",
        "requesting_party_id": "parties/party-cust-alpha",
        "target_object_id": "observations/55119",
        "target_norad_id": 55119,
        "trigger": {"type": "renewal_cycle", "policy_id": "POL-2026-002"},
        "sla": {
            "response_due": ts_future(days=3),
            "delivery_due": ts_future(days=21),
            "qa_window_days": 5,
        },
        "timestamps": {
            "created_at": ts_past(days=1),
            "submitted_at": ts_past(hours=18),
            "quote_expires_at": ts_future(days=10),
        },
        "assigned_analyst": None,
        "created_at": ts_past(days=1),
        "updated_at": ts_past(hours=18),
        "_task_seed": True,
    },
    {
        "_key": "TSK-2026-0003",
        "task_ref": "TSK-2026-0003",
        "title": "Scoping review — ISS extended campaign",
        "description": "Requirements scoping for multi-month ISS observation campaign.",
        "status": "scoping",
        "requesting_party_id": "parties/party-cust-bravo",
        "target_object_id": "observations/25544",
        "target_norad_id": 25544,
        "trigger": {"type": "customer_request"},
        "sla": {
            "response_due": ts_future(days=5),
            "delivery_due": ts_future(days=45),
            "qa_window_days": 7,
        },
        "timestamps": {
            "created_at": ts_past(days=5),
            "submitted_at": ts_past(days=4),
            "scoping_started_at": ts_past(days=3),
            "quote_expires_at": ts_future(days=12),
        },
        "assigned_analyst": "analyst-01@talon.example",
        "created_at": ts_past(days=5),
        "updated_at": ts_past(days=3),
        "_task_seed": True,
    },
    {
        "_key": "TSK-2026-0004",
        "task_ref": "TSK-2026-0004",
        "title": "Quote issued — Starlink proximity survey",
        "description": "Quote awaiting customer acceptance for proximity survey.",
        "status": "quoted",
        "requesting_party_id": "parties/party-cust-charlie",
        "target_object_id": "observations/49260",
        "target_norad_id": 49260,
        "trigger": {"type": "customer_request"},
        "sla": {
            "response_due": ts_future(days=1),
            "delivery_due": ts_future(days=18),
            "qa_window_days": 5,
        },
        "timestamps": {
            "created_at": ts_past(days=8),
            "submitted_at": ts_past(days=7),
            "scoping_started_at": ts_past(days=6),
            "quoted_at": ts_past(days=4),
            "quote_expires_at": ts_future(days=3),
        },
        "quote": {
            "amount_usd": 15000,
            "line_items": [
                {"description": "Proximity survey campaign", "unit_price_usd": 1000, "quantity": 15, "subtotal_usd": 15000},
            ],
            "valid_until": ts_future(days=3),
            "issued_by": "talon-ops@talon.example",
        },
        "assigned_analyst": "analyst-03@talon.example",
        "created_at": ts_past(days=8),
        "updated_at": ts_past(days=4),
        "_task_seed": True,
    },
    {
        "_key": "TSK-2026-0005",
        "task_ref": "TSK-2026-0005",
        "title": "Accepted task — NORAD 55119 characterisation",
        "description": "Customer accepted quote; pending scheduling.",
        "status": "accepted",
        "requesting_party_id": "parties/party-cust-alpha",
        "target_object_id": "observations/55119",
        "target_norad_id": 55119,
        "trigger": {"type": "renewal_cycle", "policy_id": "POL-2026-003"},
        "sla": {
            "response_due": ts_past(days=2),
            "delivery_due": ts_future(days=20),
            "qa_window_days": 5,
        },
        "timestamps": {
            "created_at": ts_past(days=15),
            "submitted_at": ts_past(days=14),
            "scoping_started_at": ts_past(days=13),
            "quoted_at": ts_past(days=11),
            "accepted_at": ts_past(days=9),
            "quote_expires_at": ts_future(days=2),
        },
        "quote": {
            "amount_usd": 19500,
            "line_items": [
                {"description": "Characterisation campaign", "unit_price_usd": 1300, "quantity": 15, "subtotal_usd": 19500},
            ],
            "valid_until": ts_future(days=2),
            "issued_by": "talon-ops@talon.example",
        },
        "assigned_analyst": "analyst-01@talon.example",
        "created_at": ts_past(days=15),
        "updated_at": ts_past(days=9),
        "_task_seed": True,
    },
    {
        "_key": "TSK-2026-0006",
        "task_ref": "TSK-2026-0006",
        "title": "Scheduled campaign — ISS RF survey",
        "description": "RF signal characterisation campaign, slots reserved.",
        "status": "scheduled",
        "requesting_party_id": "parties/party-cust-bravo",
        "target_object_id": "observations/25544",
        "target_norad_id": 25544,
        "trigger": {"type": "customer_request"},
        "sla": {
            "response_due": ts_past(days=5),
            "delivery_due": ts_future(days=10),
            "qa_window_days": 5,
        },
        "timestamps": {
            "created_at": ts_past(days=20),
            "submitted_at": ts_past(days=19),
            "scoping_started_at": ts_past(days=18),
            "quoted_at": ts_past(days=16),
            "accepted_at": ts_past(days=14),
            "scheduled_at": ts_past(days=12),
            "quote_expires_at": ts_past(days=6),
        },
        "quote": {
            "amount_usd": 30000,
            "line_items": [
                {"description": "RF survey campaign", "unit_price_usd": 2000, "quantity": 15, "subtotal_usd": 30000},
            ],
            "valid_until": ts_past(days=6),
            "issued_by": "talon-ops@talon.example",
        },
        "assigned_analyst": "analyst-02@talon.example",
        "created_at": ts_past(days=20),
        "updated_at": ts_past(days=12),
        "_task_seed": True,
    },
    {
        "_key": "TSK-2026-0007",
        "task_ref": "TSK-2026-0007",
        "title": "Observations complete — Starlink debris proximity",
        "description": "All observation passes completed; awaiting analysis.",
        "status": "observations_complete",
        "requesting_party_id": "parties/party-cust-charlie",
        "target_object_id": "observations/49260",
        "target_norad_id": 49260,
        "trigger": {"type": "loss_event", "loss_event_id": "LE-2026-002"},
        "sla": {
            "response_due": ts_past(days=25),
            "delivery_due": ts_future(days=3),
            "qa_window_days": 5,
        },
        "timestamps": {
            "created_at": ts_past(days=35),
            "submitted_at": ts_past(days=34),
            "scoping_started_at": ts_past(days=33),
            "quoted_at": ts_past(days=31),
            "accepted_at": ts_past(days=29),
            "scheduled_at": ts_past(days=27),
            "executing_started_at": ts_past(days=20),
            "observations_complete_at": ts_past(days=5),
            "quote_expires_at": ts_past(days=20),
        },
        "quote": {
            "amount_usd": 25000,
            "line_items": [
                {"description": "Debris proximity survey", "unit_price_usd": 1000, "quantity": 25, "subtotal_usd": 25000},
            ],
            "valid_until": ts_past(days=20),
            "issued_by": "talon-ops@talon.example",
        },
        "assigned_analyst": "analyst-03@talon.example",
        "created_at": ts_past(days=35),
        "updated_at": ts_past(days=5),
        "_task_seed": True,
    },
    {
        "_key": "TSK-2026-0008",
        "task_ref": "TSK-2026-0008",
        "title": "Under review — NORAD 55557 manoeuvre report",
        "description": "Analysis complete, report under QA review.",
        "status": "under_review",
        "requesting_party_id": "parties/party-cust-alpha",
        "target_object_id": "observations/55557",
        "target_norad_id": 55557,
        "trigger": {"type": "customer_request"},
        "sla": {
            "response_due": ts_past(days=40),
            "delivery_due": ts_past(days=5),
            "qa_window_days": 5,
        },
        "timestamps": {
            "created_at": ts_past(days=50),
            "submitted_at": ts_past(days=49),
            "scoping_started_at": ts_past(days=48),
            "quoted_at": ts_past(days=46),
            "accepted_at": ts_past(days=44),
            "scheduled_at": ts_past(days=42),
            "executing_started_at": ts_past(days=35),
            "observations_complete_at": ts_past(days=15),
            "under_review_at": ts_past(days=10),
            "quote_expires_at": ts_past(days=35),
        },
        "quote": {
            "amount_usd": 28000,
            "line_items": [
                {"description": "Manoeuvre analysis campaign", "unit_price_usd": 1400, "quantity": 20, "subtotal_usd": 28000},
            ],
            "valid_until": ts_past(days=35),
            "issued_by": "talon-ops@talon.example",
        },
        "assigned_analyst": "analyst-01@talon.example",
        "created_at": ts_past(days=50),
        "updated_at": ts_past(days=10),
        "_task_seed": True,
    },
    {
        "_key": "TSK-2026-0009",
        "task_ref": "TSK-2026-0009",
        "title": "Delivered — ISS annual survey report",
        "description": "Report delivered to customer pending acceptance.",
        "status": "delivered",
        "requesting_party_id": "parties/party-cust-bravo",
        "target_object_id": "observations/25544",
        "target_norad_id": 25544,
        "trigger": {"type": "renewal_cycle", "policy_id": "POL-2026-001"},
        "sla": {
            "response_due": ts_past(days=70),
            "delivery_due": ts_past(days=55),
            "qa_window_days": 5,
        },
        "timestamps": {
            "created_at": ts_past(days=100),
            "submitted_at": ts_past(days=99),
            "scoping_started_at": ts_past(days=98),
            "quoted_at": ts_past(days=96),
            "accepted_at": ts_past(days=94),
            "scheduled_at": ts_past(days=90),
            "executing_started_at": ts_past(days=80),
            "observations_complete_at": ts_past(days=65),
            "under_review_at": ts_past(days=62),
            "delivered_at": ts_past(days=58),
            "quote_expires_at": ts_past(days=80),
        },
        "quote": {
            "amount_usd": 52000,
            "line_items": [
                {"description": "Annual survey — 40 passes", "unit_price_usd": 1300, "quantity": 40, "subtotal_usd": 52000},
            ],
            "valid_until": ts_past(days=80),
            "issued_by": "talon-ops@talon.example",
        },
        "assigned_analyst": "analyst-02@talon.example",
        "created_at": ts_past(days=100),
        "updated_at": ts_past(days=58),
        "_task_seed": True,
    },
    {
        "_key": "TSK-2026-0010",
        "task_ref": "TSK-2026-0010",
        "title": "Accepted by customer — NORAD 55119 report",
        "description": "Customer formally accepted the delivered report.",
        "status": "accepted_by_customer",
        "requesting_party_id": "parties/party-cust-charlie",
        "target_object_id": "observations/55119",
        "target_norad_id": 55119,
        "trigger": {"type": "renewal_cycle", "policy_id": "POL-2026-003"},
        "sla": {
            "response_due": ts_past(days=80),
            "delivery_due": ts_past(days=65),
            "qa_window_days": 5,
        },
        "timestamps": {
            "created_at": ts_past(days=110),
            "submitted_at": ts_past(days=109),
            "scoping_started_at": ts_past(days=108),
            "quoted_at": ts_past(days=106),
            "accepted_at": ts_past(days=104),
            "scheduled_at": ts_past(days=100),
            "executing_started_at": ts_past(days=90),
            "observations_complete_at": ts_past(days=75),
            "under_review_at": ts_past(days=72),
            "delivered_at": ts_past(days=68),
            "accepted_by_customer_at": ts_past(days=65),
            "quote_expires_at": ts_past(days=90),
        },
        "quote": {
            "amount_usd": 34000,
            "line_items": [
                {"description": "Characterisation — 20 passes", "unit_price_usd": 1700, "quantity": 20, "subtotal_usd": 34000},
            ],
            "valid_until": ts_past(days=90),
            "issued_by": "talon-ops@talon.example",
        },
        "assigned_analyst": "analyst-03@talon.example",
        "created_at": ts_past(days=110),
        "updated_at": ts_past(days=65),
        "_task_seed": True,
    },
    {
        "_key": "TSK-2026-0011",
        "task_ref": "TSK-2026-0011",
        "title": "Disputed — Starlink cluster report quality",
        "description": "Customer disputes accuracy of delivered observations.",
        "status": "disputed",
        "requesting_party_id": "parties/party-cust-alpha",
        "target_object_id": "observations/49260",
        "target_norad_id": 49260,
        "trigger": {"type": "customer_request"},
        "sla": {
            "response_due": ts_past(days=130),
            "delivery_due": ts_past(days=110),
            "qa_window_days": 5,
        },
        "timestamps": {
            "created_at": ts_past(days=160),
            "submitted_at": ts_past(days=159),
            "scoping_started_at": ts_past(days=158),
            "quoted_at": ts_past(days=155),
            "accepted_at": ts_past(days=152),
            "scheduled_at": ts_past(days=148),
            "executing_started_at": ts_past(days=138),
            "observations_complete_at": ts_past(days=120),
            "under_review_at": ts_past(days=116),
            "delivered_at": ts_past(days=112),
            "quote_expires_at": ts_past(days=138),
        },
        "assigned_analyst": "analyst-01@talon.example",
        "created_at": ts_past(days=160),
        "updated_at": ts_past(days=105),
        "_task_seed": True,
    },
    {
        "_key": "TSK-2026-0012",
        "task_ref": "TSK-2026-0012",
        "title": "Cancelled — superseded by TSK-2026-0028",
        "description": "Customer cancelled this task as scope was merged into TSK-2026-0028.",
        "status": "cancelled",
        "requesting_party_id": "parties/party-cust-bravo",
        "target_object_id": "observations/49260",
        "target_norad_id": 49260,
        "trigger": {"type": "customer_request"},
        "sla": {
            "response_due": ts_past(days=9),
            "delivery_due": ts_past(days=1),
            "qa_window_days": 5,
        },
        "timestamps": {
            "created_at": ts_past(days=12),
            "submitted_at": ts_past(days=11),
            "scoping_started_at": ts_past(days=10),
            "cancelled_at": ts_past(days=9),
            "quote_expires_at": ts_future(days=5),
        },
        "assigned_analyst": None,
        "created_at": ts_past(days=12),
        "updated_at": ts_past(days=9),
        "_task_seed": True,
    },

    # SLA breach demo rows
    # 1. delivery_overdue: executing with delivery_due in the past
    {
        "_key": "TSK-SLA-EXEC-OVERDUE",
        "task_ref": "TSK-SLA-EXEC-OVERDUE",
        "title": "SLA DEMO — executing, delivery overdue",
        "description": "Intentionally breached: delivery_due is in the past while still executing.",
        "status": "executing",
        "requesting_party_id": "parties/party-cust-charlie",
        "target_object_id": "observations/55119",
        "target_norad_id": 55119,
        "trigger": {"type": "customer_request"},
        "sla": {
            "response_due": ts_past(days=18),
            "delivery_due": ts_past(days=3),
            "qa_window_days": 5,
        },
        "timestamps": {
            "created_at": ts_past(days=25),
            "submitted_at": ts_past(days=24),
            "scoping_started_at": ts_past(days=23),
            "quoted_at": ts_past(days=21),
            "accepted_at": ts_past(days=19),
            "scheduled_at": ts_past(days=17),
            "executing_started_at": ts_past(days=10),
            "quote_expires_at": ts_past(days=10),
        },
        "sla_breach": {"type": "delivery_overdue", "breached_at": ts_past(days=3)},
        "assigned_analyst": "analyst-02@talon.example",
        "created_at": ts_past(days=25),
        "updated_at": ts_past(days=3),
        "_task_seed": True,
    },
    # 2. quote_expiring_soon: quoted, quote_expires_at within 24 hours
    {
        "_key": "TSK-SLA-QUOTE-EXPIRING",
        "task_ref": "TSK-SLA-QUOTE-EXPIRING",
        "title": "SLA DEMO — quoted, quote expiring soon",
        "description": "Intentionally breached: quote_expires_at within 24 hours.",
        "status": "quoted",
        "requesting_party_id": "parties/party-cust-alpha",
        "target_object_id": "observations/55557",
        "target_norad_id": 55557,
        "trigger": {"type": "customer_request"},
        "sla": {
            "response_due": ts_future(days=1),
            "delivery_due": ts_future(days=20),
            "qa_window_days": 5,
        },
        "timestamps": {
            "created_at": ts_past(days=7),
            "submitted_at": ts_past(days=6),
            "scoping_started_at": ts_past(days=5),
            "quoted_at": ts_past(days=3),
            "quote_expires_at": ts_future(hours=10),
        },
        "quote": {
            "amount_usd": 18000,
            "line_items": [
                {"description": "Survey campaign", "unit_price_usd": 1200, "quantity": 15, "subtotal_usd": 18000},
            ],
            "valid_until": ts_future(hours=10),
            "issued_by": "talon-ops@talon.example",
        },
        "sla_breach": {"type": "quote_expiring_soon", "expires_at": ts_future(hours=10)},
        "assigned_analyst": "analyst-03@talon.example",
        "created_at": ts_past(days=7),
        "updated_at": ts_past(days=3),
        "_task_seed": True,
    },
    # 3. quote_expired: quoted, quote_expires_at in the past
    {
        "_key": "TSK-SLA-QUOTE-EXPIRED",
        "task_ref": "TSK-SLA-QUOTE-EXPIRED",
        "title": "SLA DEMO — quoted, quote expired",
        "description": "Intentionally breached: quote_expires_at already past.",
        "status": "quoted",
        "requesting_party_id": "parties/party-cust-bravo",
        "target_object_id": "observations/25544",
        "target_norad_id": 25544,
        "trigger": {"type": "renewal_cycle", "policy_id": "POL-2026-002"},
        "sla": {
            "response_due": ts_past(days=2),
            "delivery_due": ts_future(days=15),
            "qa_window_days": 5,
        },
        "timestamps": {
            "created_at": ts_past(days=20),
            "submitted_at": ts_past(days=19),
            "scoping_started_at": ts_past(days=18),
            "quoted_at": ts_past(days=16),
            "quote_expires_at": ts_past(days=2),
        },
        "quote": {
            "amount_usd": 21000,
            "line_items": [
                {"description": "Survey", "unit_price_usd": 1050, "quantity": 20, "subtotal_usd": 21000},
            ],
            "valid_until": ts_past(days=2),
            "issued_by": "talon-ops@talon.example",
        },
        "sla_breach": {"type": "quote_expired", "expired_at": ts_past(days=2)},
        "assigned_analyst": "analyst-01@talon.example",
        "created_at": ts_past(days=20),
        "updated_at": ts_past(days=2),
        "_task_seed": True,
    },
    # 4. qa_overdue: under_review, updated_at more than qa_window_days ago
    {
        "_key": "TSK-SLA-QA-OVERDUE",
        "task_ref": "TSK-SLA-QA-OVERDUE",
        "title": "SLA DEMO — under_review, QA overdue",
        "description": "Intentionally breached: updated_at more than qa_window_days ago while under_review.",
        "status": "under_review",
        "requesting_party_id": "parties/party-cust-charlie",
        "target_object_id": "observations/49260",
        "target_norad_id": 49260,
        "trigger": {"type": "customer_request"},
        "sla": {
            "response_due": ts_past(days=55),
            "delivery_due": ts_past(days=10),
            "qa_window_days": 5,
        },
        "timestamps": {
            "created_at": ts_past(days=70),
            "submitted_at": ts_past(days=69),
            "scoping_started_at": ts_past(days=68),
            "quoted_at": ts_past(days=65),
            "accepted_at": ts_past(days=62),
            "scheduled_at": ts_past(days=58),
            "executing_started_at": ts_past(days=50),
            "observations_complete_at": ts_past(days=30),
            "under_review_at": ts_past(days=20),
            "quote_expires_at": ts_past(days=50),
        },
        "sla_breach": {"type": "qa_overdue", "qa_window_days": 5, "days_in_review": 20},
        "assigned_analyst": "analyst-02@talon.example",
        "created_at": ts_past(days=70),
        "updated_at": ts_past(days=20),
        "_task_seed": True,
    },
]


def _transitions_for(task: dict) -> list[dict]:
    key = task["_key"]
    status = task["status"]
    ts_map = task.get("timestamps", {})
    flow = [
        ("drafted",                ts_map.get("created_at")),
        ("submitted",              ts_map.get("submitted_at")),
        ("scoping",                ts_map.get("scoping_started_at")),
        ("quoted",                 ts_map.get("quoted_at")),
        ("accepted",               ts_map.get("accepted_at")),
        ("scheduled",              ts_map.get("scheduled_at")),
        ("executing",              ts_map.get("executing_started_at")),
        ("observations_complete",  ts_map.get("observations_complete_at")),
        ("under_review",           ts_map.get("under_review_at")),
        ("delivered",              ts_map.get("delivered_at")),
        ("accepted_by_customer",   ts_map.get("accepted_by_customer_at")),
        ("closed",                 ts_map.get("closed_at")),
        ("cancelled",              ts_map.get("cancelled_at")),
        ("disputed",               None),
    ]
    terminal_statuses = {
        "cancelled": ts_map.get("cancelled_at") or task.get("updated_at"),
        "disputed": task.get("updated_at"),
    }
    rows = []
    prev_status = None
    for s, occurred_at in flow:
        if occurred_at is None:
            continue
        idx = len(rows)
        row = {
            "_key": f"TRANS-{key}-{idx:03d}",
            "task_id": f"customer_tasks/{key}",
            "from_status": prev_status,
            "to_status": s,
            "occurred_at": occurred_at,
            "actor": "system",
            "_task_seed": True,
        }
        rows.append(row)
        prev_status = s
        if s == status:
            break
    if not rows:
        rows.append({
            "_key": f"TRANS-{key}-000",
            "task_id": f"customer_tasks/{key}",
            "from_status": None,
            "to_status": status,
            "occurred_at": task.get("created_at", ts_past(days=1)),
            "actor": "system",
            "_task_seed": True,
        })
    return rows


DELIVERABLE_STATUSES = {"delivered", "closed", "accepted_by_customer"}


def _deliverable_for(task: dict) -> dict | None:
    if task["status"] not in DELIVERABLE_STATUSES:
        return None
    key = task["_key"]
    ts_map = task.get("timestamps", {})
    delivered_at = (
        ts_map.get("delivered_at")
        or ts_map.get("accepted_by_customer_at")
        or ts_map.get("closed_at")
        or task.get("updated_at")
        or ts_past(days=1)
    )
    return {
        "_key": f"DELIV-{key}",
        "task_id": f"customer_tasks/{key}",
        "title": f"Observation Report — {task['title']}",
        "format": "pdf",
        "storage_uri": f"s3://talon-deliverables/{key}/report.pdf",
        "sha256": f"sha256:{'0' * 64}",
        "delivered_at": delivered_at,
        "accepted_by_customer": task["status"] in {"accepted_by_customer", "closed"},
        "_task_seed": True,
    }


def _collect_all_docs(tasks: list[dict]) -> dict:
    all_tasks = tasks
    all_transitions = []
    all_deliverables = []

    for t in tasks:
        all_transitions.extend(_transitions_for(t))
        d = _deliverable_for(t)
        if d:
            all_deliverables.append(d)

    return {
        "customer_tasks": all_tasks,
        "customer_task_transitions": all_transitions,
        "task_deliverables": all_deliverables,
    }


def _build_edges(tasks: list[dict], deliverables: list[dict]) -> dict:
    requested_by = []
    targets_object = []
    relates_to_policy = []
    relates_to_loss_event = []
    produced_deliverable = []

    deliverable_by_task = {d["task_id"].split("/")[1]: d["_key"] for d in deliverables}

    for t in tasks:
        key = t["_key"]
        party_id = t.get("requesting_party_id")
        object_id = t.get("target_object_id")
        trigger = t.get("trigger", {})

        if party_id:
            requested_by.append({
                "_key": f"RB-{key}",
                "_from": f"customer_tasks/{key}",
                "_to": party_id,
                "_task_seed": True,
            })
        if object_id:
            targets_object.append({
                "_key": f"TO-{key}",
                "_from": f"customer_tasks/{key}",
                "_to": object_id,
                "_task_seed": True,
            })
        policy_id = trigger.get("policy_id")
        if policy_id:
            relates_to_policy.append({
                "_key": f"RP-{key}",
                "_from": f"customer_tasks/{key}",
                "_to": f"policies/{policy_id}",
                "_task_seed": True,
            })
        loss_event_id = trigger.get("loss_event_id")
        if loss_event_id:
            relates_to_loss_event.append({
                "_key": f"RLE-{key}",
                "_from": f"customer_tasks/{key}",
                "_to": f"loss_events/{loss_event_id}",
                "_task_seed": True,
            })
        if key in deliverable_by_task:
            deliv_key = deliverable_by_task[key]
            produced_deliverable.append({
                "_key": f"PD-{key}",
                "_from": f"customer_tasks/{key}",
                "_to": f"task_deliverables/{deliv_key}",
                "_task_seed": True,
            })

    return {
        "task_requested_by": requested_by,
        "task_targets_object": targets_object,
        "task_relates_to_policy": relates_to_policy,
        "task_relates_to_loss_event": relates_to_loss_event,
        "task_produced_deliverable": produced_deliverable,
    }


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _ensure_collections(db_module):
    from database.connection import (
        COLLECTION_CUSTOMER_TASKS, COLLECTION_CUSTOMER_TASK_TRANS,
        COLLECTION_TASK_DELIVERABLES, COLLECTION_TASK_SLA_ALERTS,
        EDGE_TASK_REQUESTED_BY, EDGE_TASK_TARGETS_OBJECT,
        EDGE_TASK_RELATES_TO_POLICY, EDGE_TASK_RELATES_TO_LOSS_EVENT,
        EDGE_TASK_PRODUCED_DELIVERABLE,
    )
    db = db_module.db
    vertex_cols = [
        COLLECTION_CUSTOMER_TASKS,
        COLLECTION_CUSTOMER_TASK_TRANS,
        COLLECTION_TASK_DELIVERABLES,
        COLLECTION_TASK_SLA_ALERTS,
    ]
    edge_cols = [
        EDGE_TASK_REQUESTED_BY,
        EDGE_TASK_TARGETS_OBJECT,
        EDGE_TASK_RELATES_TO_POLICY,
        EDGE_TASK_RELATES_TO_LOSS_EVENT,
        EDGE_TASK_PRODUCED_DELIVERABLE,
    ]
    for col_name in vertex_cols:
        if not db.has_collection(col_name):
            db.create_collection(col_name)
    for col_name in edge_cols:
        if not db.has_collection(col_name):
            db.create_collection(col_name, edge=True)

    ct_col = db.collection(COLLECTION_CUSTOMER_TASKS)
    ct_col.add_persistent_index(fields=["status"], unique=False)
    ct_col.add_persistent_index(fields=["requesting_party_id"], unique=False)
    ct_col.add_persistent_index(fields=["timestamps.created_at"], unique=False)


def upsert(db_module, col_name: str, doc: dict):
    col = db_module.db.collection(col_name)
    key = doc["_key"]
    if col.has(key):
        col.update(doc)
    else:
        col.insert(doc)


def upsert_edge(db_module, col_name: str, doc: dict):
    col = db_module.db.collection(col_name)
    key = doc["_key"]
    if col.has(key):
        col.update(doc)
    else:
        col.insert(doc)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Seed TALON customer_tasks fixture data.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print documents that would be upserted and exit without touching the DB.",
    )
    args = parser.parse_args()

    docs = _collect_all_docs(CUSTOMER_TASKS)
    edges = _build_edges(CUSTOMER_TASKS, docs["task_deliverables"])

    if args.dry_run:
        output = {"documents": docs, "edges": edges}
        print(json.dumps(output, indent=2, default=str))
        sys.exit(0)

    import database as db_module
    from database.connection import (
        connect_mongodb,
        COLLECTION_PARTIES,
        COLLECTION_CUSTOMER_TASKS, COLLECTION_CUSTOMER_TASK_TRANS,
        COLLECTION_TASK_DELIVERABLES, COLLECTION_TASK_SLA_ALERTS,
        EDGE_TASK_REQUESTED_BY, EDGE_TASK_TARGETS_OBJECT,
        EDGE_TASK_RELATES_TO_POLICY, EDGE_TASK_RELATES_TO_LOSS_EVENT,
        EDGE_TASK_PRODUCED_DELIVERABLE,
    )

    try:
        connected = connect_mongodb()
    except Exception as exc:
        print(f"ERROR: Could not connect to ArangoDB — {exc}")
        sys.exit(1)

    if not connected:
        print("ERROR: Could not connect to ArangoDB. Check ARANGO_HOST, ARANGO_USER, ARANGO_PASSWORD.")
        sys.exit(1)

    print("=== TALON Customer Tasks Seed ===")

    try:
        _ensure_collections(db_module)
    except Exception as exc:
        print(f"ERROR: Failed to ensure collections/indexes — {exc}")
        sys.exit(1)

    print("Upserting placeholder parties...")
    for party in PLACEHOLDER_PARTIES:
        upsert(db_module, COLLECTION_PARTIES, party)
    print(f"  parties: {len(PLACEHOLDER_PARTIES)}")

    print("Upserting customer_tasks...")
    for task in docs["customer_tasks"]:
        upsert(db_module, COLLECTION_CUSTOMER_TASKS, task)
    print(f"  customer_tasks: {len(docs['customer_tasks'])}")

    print("Upserting customer_task_transitions...")
    for row in docs["customer_task_transitions"]:
        upsert(db_module, COLLECTION_CUSTOMER_TASK_TRANS, row)
    print(f"  customer_task_transitions: {len(docs['customer_task_transitions'])}")

    print("Upserting task_deliverables...")
    for row in docs["task_deliverables"]:
        upsert(db_module, COLLECTION_TASK_DELIVERABLES, row)
    print(f"  task_deliverables: {len(docs['task_deliverables'])}")

    print("Upserting edges...")
    for edge_doc in edges["task_requested_by"]:
        upsert_edge(db_module, EDGE_TASK_REQUESTED_BY, edge_doc)
    print(f"  task_requested_by: {len(edges['task_requested_by'])}")

    for edge_doc in edges["task_targets_object"]:
        upsert_edge(db_module, EDGE_TASK_TARGETS_OBJECT, edge_doc)
    print(f"  task_targets_object: {len(edges['task_targets_object'])}")

    for edge_doc in edges["task_relates_to_policy"]:
        upsert_edge(db_module, EDGE_TASK_RELATES_TO_POLICY, edge_doc)
    print(f"  task_relates_to_policy: {len(edges['task_relates_to_policy'])}")

    for edge_doc in edges["task_relates_to_loss_event"]:
        upsert_edge(db_module, EDGE_TASK_RELATES_TO_LOSS_EVENT, edge_doc)
    print(f"  task_relates_to_loss_event: {len(edges['task_relates_to_loss_event'])}")

    for edge_doc in edges["task_produced_deliverable"]:
        upsert_edge(db_module, EDGE_TASK_PRODUCED_DELIVERABLE, edge_doc)
    print(f"  task_produced_deliverable: {len(edges['task_produced_deliverable'])}")

    print("=== Done ===")


if __name__ == "__main__":
    main()
