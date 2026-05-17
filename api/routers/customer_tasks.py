from fastapi import APIRouter, HTTPException, Query, Body
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel
import uuid

import database as db_module
from database.connection import (
    COLLECTION_CUSTOMER_TASKS,
    COLLECTION_CUSTOMER_TASK_TRANS,
    COLLECTION_TASK_DELIVERABLES,
    COLLECTION_TASK_SLA_ALERTS,
    EDGE_TASK_REQUESTED_BY,
    EDGE_TASK_TARGETS_OBJECT,
    EDGE_TASK_RELATES_TO_POLICY,
    EDGE_TASK_RELATES_TO_LOSS_EVENT,
    EDGE_TASK_PRODUCED_DELIVERABLE,
    COLLECTION_OBSERVATIONS,
)
from database.customer_task_ops import (
    customer_status,
    get_allowed_next_states,
    transition_task,
)

router = APIRouter(prefix="/v2/customer-tasks", tags=["customer_tasks"])


def _db():
    if db_module.db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    return db_module.db


def _col(name: str):
    db = _db()
    if not db.has_collection(name):
        raise HTTPException(
            status_code=503,
            detail=f"Collection '{name}' not found — run seed_customer_tasks first",
        )
    return db.collection(name)


def _aql(query: str, bind_vars: dict | None = None):
    return list(_db().aql.execute(query, bind_vars=bind_vars or {}))


class TransitionBody(BaseModel):
    to_status: str
    actor: str
    actor_type: str
    note: str = ""


# ---------------------------------------------------------------------------
# GET /v2/customer-tasks/alerts  (must be declared before /{task_key})
# ---------------------------------------------------------------------------

@router.get("/alerts", summary="Active SLA alerts")
def list_alerts(
    status: str = Query(default="active"),
    carrier_id: Optional[str] = Query(default=None),
):
    bind_vars: dict = {"@alerts": COLLECTION_TASK_SLA_ALERTS, "status": status}

    if carrier_id:
        bind_vars["carrier_id"] = f"parties/{carrier_id}"
        carrier_clause = "FILTER task.requesting_party_id == @carrier_id"
    else:
        carrier_clause = ""

    query = f"""
        FOR a IN @@alerts
            FILTER a.status == @status
            LET task = DOCUMENT(a.task_id)
            {carrier_clause}
            SORT a.triggered_at DESC
            RETURN a
    """
    try:
        return _aql(query, bind_vars)
    except Exception:
        return []


# ---------------------------------------------------------------------------
# GET /v2/customer-tasks
# ---------------------------------------------------------------------------

@router.get("", summary="List customer tasks")
def list_tasks(
    carrier_id: Optional[str] = Query(default=None),
    status: Optional[List[str]] = Query(default=None),
    priority: Optional[str] = Query(default=None),
    limit: int = Query(default=50),
    offset: int = Query(default=0),
):
    bind_vars: dict = {
        "@tasks": COLLECTION_CUSTOMER_TASKS,
        "limit": limit,
        "offset": offset,
    }
    filters = []

    if carrier_id:
        bind_vars["carrier_id"] = f"parties/{carrier_id}"
        filters.append("t.requesting_party_id == @carrier_id")
    if status:
        bind_vars["status_list"] = status
        filters.append("t.status IN @status_list")
    if priority:
        bind_vars["priority"] = priority
        filters.append("t.priority == @priority")

    filter_clause = ("FILTER " + " AND ".join(filters)) if filters else ""

    query = f"""
        FOR t IN @@tasks
            {filter_clause}
            SORT t._key ASC
            LIMIT @offset, @limit
            RETURN {{
                _key: t._key,
                task_number: t.task_number,
                task_ref: t.task_ref,
                status: t.status,
                customer_status: null,
                target_object_id: t.target_object_id,
                priority: t.priority,
                delivery_due: t.sla.delivery_due,
                requesting_party_id: t.requesting_party_id
            }}
    """

    rows = _aql(query, bind_vars)
    for row in rows:
        try:
            row["customer_status"] = customer_status(row["status"])
        except Exception:
            row["customer_status"] = None
    return rows


# ---------------------------------------------------------------------------
# GET /v2/customer-tasks/{task_key}
# ---------------------------------------------------------------------------

@router.get("/{task_key}", summary="Task detail")
def get_task(task_key: str):
    col = _col(COLLECTION_CUSTOMER_TASKS)
    doc = col.get(task_key)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_key}' not found")

    task_status = doc.get("status", "drafted")
    doc["customer_status"] = customer_status(task_status)
    doc["allowed_next_states"] = get_allowed_next_states(task_status)

    norad_id = doc.get("target_norad_id")
    if norad_id is not None:
        scope = doc.get("scope") or {}
        win_start = scope.get("time_window_start")
        win_end = scope.get("time_window_end")

        count_aql = """
            RETURN LENGTH(
                FOR obs IN @@observations
                    FILTER obs.norad_id == @norad_id
                    FILTER @win_start == null OR obs.observation_epoch >= @win_start
                    FILTER @win_end   == null OR obs.observation_epoch <= @win_end
                    RETURN 1
            )
        """
        obs_count_result = _aql(
            count_aql,
            {
                "@observations": COLLECTION_OBSERVATIONS,
                "norad_id": norad_id,
                "win_start": win_start,
                "win_end": win_end,
            },
        )
        doc["observation_count"] = obs_count_result[0] if obs_count_result else 0

        doc["passes"] = _aql(
            """
            FOR obs IN @@observations
                FILTER obs.norad_id == @norad_id
                FILTER @win_start == null OR obs.observation_epoch >= @win_start
                FILTER @win_end   == null OR obs.observation_epoch <= @win_end
                FILTER obs.pass_id != null
                COLLECT pass_id = obs.pass_id, kestrel_id = obs.kestrel_id
                    AGGREGATE
                        frame_count    = LENGTH(1),
                        sunlit_frames  = SUM(obs.illumination == "sunlit" ? 1 : 0),
                        first_epoch    = MIN(obs.observation_epoch),
                        last_epoch     = MAX(obs.observation_epoch)
                SORT pass_id ASC
                LIMIT 50
                RETURN {
                    pass_id: pass_id,
                    kestrel_id: kestrel_id,
                    first_epoch: first_epoch,
                    last_epoch: last_epoch,
                    frame_count: frame_count,
                    sunlit_frames: sunlit_frames
                }
            """,
            {
                "@observations": COLLECTION_OBSERVATIONS,
                "norad_id": norad_id,
                "win_start": win_start,
                "win_end": win_end,
            },
        )
    else:
        doc["observation_count"] = 0
        doc["passes"] = []

    task_id = f"{COLLECTION_CUSTOMER_TASKS}/{task_key}"

    doc["deliverables"] = _aql(
        """
        FOR e IN @@edge
            FILTER e._from == @task_id
            FOR d IN @@deliverables
                FILTER d._id == e._to
                RETURN d
        """,
        {
            "@edge": EDGE_TASK_PRODUCED_DELIVERABLE,
            "@deliverables": COLLECTION_TASK_DELIVERABLES,
            "task_id": task_id,
        },
    )

    doc["recent_transitions"] = _aql(
        """
        FOR tr IN @@transitions
            FILTER tr.task_id == @task_id
            SORT tr.occurred_at DESC
            LIMIT 10
            RETURN tr
        """,
        {"@transitions": COLLECTION_CUSTOMER_TASK_TRANS, "task_id": task_id},
    )

    doc["active_alerts"] = _aql(
        """
        FOR a IN @@alerts
            FILTER a.task_id == @task_id AND a.status == "active"
            RETURN a
        """,
        {"@alerts": COLLECTION_TASK_SLA_ALERTS, "task_id": task_id},
    )

    return doc


# ---------------------------------------------------------------------------
# POST /v2/customer-tasks
# ---------------------------------------------------------------------------

@router.post("", summary="Create a new task", status_code=201)
def create_task(body: dict = Body(...)):
    _col(COLLECTION_CUSTOMER_TASKS)

    year = datetime.now(timezone.utc).year
    prefix = f"TSK-{year}-"
    count_result = _aql(
        """
        RETURN LENGTH(
            FOR t IN @@tasks
                FILTER STARTS_WITH(t._key, @prefix)
                RETURN 1
        )
        """,
        {"@tasks": COLLECTION_CUSTOMER_TASKS, "prefix": prefix},
    )
    seq = (count_result[0] if count_result else 0) + 1
    task_key = f"{prefix}{seq:04d}"

    now_iso = datetime.now(timezone.utc).isoformat()
    doc = dict(body)
    doc["_key"] = task_key
    doc["task_number"] = f"TALON-{task_key}"
    doc["task_ref"] = task_key
    doc.setdefault("status", "drafted")
    doc.setdefault("timestamps", {})
    doc["timestamps"]["created_at"] = now_iso

    col = _db().collection(COLLECTION_CUSTOMER_TASKS)
    col.insert(doc)

    trans_col = _col(COLLECTION_CUSTOMER_TASK_TRANS)
    trans_col.insert({
        "_key": str(uuid.uuid4()),
        "task_id": f"{COLLECTION_CUSTOMER_TASKS}/{task_key}",
        "from_status": None,
        "to_status": "drafted",
        "occurred_at": now_iso,
        "actor": "api",
        "actor_type": "system",
        "note": "",
    })

    requesting_party_id = doc.get("requesting_party_id")
    if requesting_party_id:
        try:
            rb_col = _col(EDGE_TASK_REQUESTED_BY)
            rb_col.insert({
                "_key": f"RB-{task_key}",
                "_from": f"{COLLECTION_CUSTOMER_TASKS}/{task_key}",
                "_to": requesting_party_id,
            })
        except Exception:
            pass

    target_object_id = doc.get("target_object_id")
    if target_object_id:
        try:
            to_col = _col(EDGE_TASK_TARGETS_OBJECT)
            to_col.insert({
                "_key": f"TO-{task_key}",
                "_from": f"{COLLECTION_CUSTOMER_TASKS}/{task_key}",
                "_to": target_object_id,
            })
        except Exception:
            pass

    trigger = doc.get("trigger", {})
    policy_id = trigger.get("policy_id")
    if policy_id:
        try:
            rp_col = _col(EDGE_TASK_RELATES_TO_POLICY)
            rp_col.insert({
                "_key": f"RP-{task_key}",
                "_from": f"{COLLECTION_CUSTOMER_TASKS}/{task_key}",
                "_to": f"policies/{policy_id}",
            })
        except Exception:
            pass

    loss_event_id = trigger.get("loss_event_id")
    if loss_event_id:
        try:
            rle_col = _col(EDGE_TASK_RELATES_TO_LOSS_EVENT)
            rle_col.insert({
                "_key": f"RLE-{task_key}",
                "_from": f"{COLLECTION_CUSTOMER_TASKS}/{task_key}",
                "_to": f"loss_events/{loss_event_id}",
            })
        except Exception:
            pass

    return col.get(task_key)


# ---------------------------------------------------------------------------
# POST /v2/customer-tasks/{task_key}/transition
# ---------------------------------------------------------------------------

@router.post("/{task_key}/transition", summary="State transition")
def transition(task_key: str, body: TransitionBody):
    db = _db()
    try:
        updated = transition_task(
            db=db,
            task_id=task_key,
            to_status=body.to_status,
            actor=body.actor,
            actor_type=body.actor_type,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return updated


# ---------------------------------------------------------------------------
# GET /v2/customer-tasks/{task_key}/observations
# ---------------------------------------------------------------------------

@router.get("/{task_key}/observations", summary="Overlay observation query")
def get_observations(task_key: str, limit: int = Query(default=100)):
    col = _col(COLLECTION_CUSTOMER_TASKS)
    task = col.get(task_key)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_key}' not found")

    norad_id = task.get("target_norad_id")
    if norad_id is None:
        return []

    return _aql(
        """
        FOR obs IN @@observations
            FILTER obs.norad_id == @norad_id
            SORT obs.observation_epoch DESC
            LIMIT @limit
            RETURN obs
        """,
        {"@observations": COLLECTION_OBSERVATIONS, "norad_id": norad_id, "limit": limit},
    )


# ---------------------------------------------------------------------------
# GET /v2/customer-tasks/{task_key}/passes
# ---------------------------------------------------------------------------

@router.get("/{task_key}/passes", summary="Per-pass breakdown")
def get_passes(task_key: str):
    col = _col(COLLECTION_CUSTOMER_TASKS)
    task = col.get(task_key)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_key}' not found")

    norad_id = task.get("target_norad_id")
    if norad_id is None:
        return []

    return _aql(
        """
        FOR obs IN @@observations
            FILTER obs.norad_id == @norad_id
            FILTER obs.pass_id != null
            COLLECT pass_id = obs.pass_id, kestrel_id = obs.kestrel_id
                AGGREGATE
                    frame_count   = LENGTH(1),
                    sunlit_frames = SUM(obs.illumination == "sunlit" ? 1 : 0),
                    first_epoch   = MIN(obs.observation_epoch),
                    last_epoch    = MAX(obs.observation_epoch)
            SORT pass_id ASC
            RETURN {
                pass_id: pass_id,
                kestrel_id: kestrel_id,
                first_epoch: first_epoch,
                last_epoch: last_epoch,
                frame_count: frame_count,
                sunlit_frames: sunlit_frames
            }
        """,
        {"@observations": COLLECTION_OBSERVATIONS, "norad_id": norad_id},
    )
