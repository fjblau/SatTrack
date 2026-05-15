from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

COLLECTION_NAME = "user_query_history"


def _get_db() -> Any:
    try:
        import database.connection as db_conn
        return db_conn.db
    except Exception:
        return None


def _ensure_collection(db: Any) -> None:
    try:
        if not db.has_collection(COLLECTION_NAME):
            db.create_collection(COLLECTION_NAME)
            db.collection(COLLECTION_NAME).add_persistent_index(
                fields=["user_id", "ts"],
                unique=False,
                name="idx_user_ts",
            )
            db.collection(COLLECTION_NAME).add_persistent_index(
                fields=["user_id", "starred", "ts"],
                unique=False,
                name="idx_user_starred_ts",
            )
    except Exception as exc:
        logger.warning("Failed to ensure history collection: %s", exc)


def record_history(state: dict, user_id: str) -> str | None:
    if not user_id:
        return None

    db = _get_db()
    if db is None:
        logger.warning("History: database not available")
        return None

    try:
        _ensure_collection(db)

        outcome = "success"
        if state.get("clarifying_question") and not state.get("clarification"):
            outcome = "clarification_requested"
        elif state.get("error"):
            outcome = "execution_failed"
        elif state.get("validator_errors"):
            outcome = "validator_failed"

        started_at: datetime = state.get("started_at", datetime.utcnow())
        now = datetime.now(timezone.utc)
        ts_started = started_at.replace(tzinfo=timezone.utc) if started_at.tzinfo is None else started_at
        duration_ms = int((now - ts_started).total_seconds() * 1000)

        doc = {
            "_key": str(uuid.uuid4()),
            "user_id": user_id,
            "ts": now.isoformat(),
            "question": state.get("question", ""),
            "clarification": state.get("clarification", ""),
            "aql": state.get("aql", ""),
            "bind_vars": state.get("bind_vars", {}),
            "row_count": state.get("row_count", 0),
            "outcome": outcome,
            "duration_ms": duration_ms,
            "confidence": state.get("confidence", "high"),
            "starred": False,
            "log_id": state.get("log_id", ""),
        }

        db.collection(COLLECTION_NAME).insert(doc)
        return doc["_key"]
    except Exception as exc:
        logger.warning("History record_history failed: %s", exc)
        return None


def get_history(
    user_id: str,
    limit: int = 20,
    starred_only: bool = False,
) -> list[dict]:
    db = _get_db()
    if db is None:
        return []

    try:
        _ensure_collection(db)
        if starred_only:
            aql = """
FOR h IN user_query_history
  FILTER h.user_id == @user_id AND h.starred == true
  SORT h.ts DESC
  LIMIT @limit
  RETURN {key: h._key, ts: h.ts, question: h.question, aql: h.aql, row_count: h.row_count, outcome: h.outcome, confidence: h.confidence, starred: h.starred}
"""
        else:
            aql = """
FOR h IN user_query_history
  FILTER h.user_id == @user_id
  SORT h.ts DESC
  LIMIT @limit
  RETURN {key: h._key, ts: h.ts, question: h.question, aql: h.aql, row_count: h.row_count, outcome: h.outcome, confidence: h.confidence, starred: h.starred}
"""
        cursor = db.aql.execute(aql, bind_vars={"user_id": user_id, "limit": limit})
        return list(cursor)
    except Exception as exc:
        logger.warning("get_history failed: %s", exc)
        return []


def toggle_star(key: str, user_id: str, starred: bool) -> dict | None:
    db = _get_db()
    if db is None:
        return None

    try:
        _ensure_collection(db)
        doc = db.collection(COLLECTION_NAME).get(key)
        if doc is None:
            return None
        if doc.get("user_id") != user_id:
            return None
        db.collection(COLLECTION_NAME).update({"_key": key, "starred": starred})
        doc["starred"] = starred
        return {
            "key": key,
            "ts": doc.get("ts"),
            "question": doc.get("question"),
            "aql": doc.get("aql"),
            "row_count": doc.get("row_count"),
            "outcome": doc.get("outcome"),
            "confidence": doc.get("confidence"),
            "starred": starred,
        }
    except Exception as exc:
        logger.warning("toggle_star failed: %s", exc)
        return None
