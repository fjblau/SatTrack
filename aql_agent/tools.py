from __future__ import annotations

import logging
from typing import Any, Literal

from aql_agent import schema_cache
from aql_agent import validator as _validator

try:
    from langchain_core.tools import tool
except ImportError:
    def tool(func):
        func.invoke = lambda args: func(**args)
        return func

logger = logging.getLogger(__name__)

_db = None


def set_db(db: Any) -> None:
    global _db
    _db = db


def _get_db() -> Any:
    if _db is not None:
        return _db
    try:
        import database.connection as db_conn
        return db_conn.db
    except Exception:
        return None


@tool
def list_collections() -> dict:
    """Return all vertex and edge collections in the Talon database.

    Use this when you are unsure whether a collection exists or
    when the user refers to data you cannot place.
    """
    db = _get_db()
    if db is None:
        return {"error": "Database not available"}
    return schema_cache.get_collections(db)


@tool
def describe_collection(name: str) -> dict:
    """Return field names, types, and three sample documents for a collection.

    Use this to confirm a field exists before referencing it in AQL,
    or to understand the shape of nested objects (e.g. canonical.*).
    """
    db = _get_db()
    if db is None:
        return {"error": "Database not available"}
    return schema_cache.describe_collection(db, name)


@tool
def distinct_values(collection: str, field: str, limit: int = 50, contains: str = "") -> dict:
    """Return distinct values for a field in a collection.

    Use this when the user refers to an entity by name and you need
    to find the exact stored spelling (e.g. operator names, constellation
    names, status enums). The `contains` filter is case-insensitive
    substring match.
    """
    db = _get_db()
    if db is None:
        return {"error": "Database not available"}
    try:
        aql = """
FOR d IN @@coll
  FILTER @contains == "" OR CONTAINS(LOWER(TO_STRING(d[@field])), LOWER(@contains))
  COLLECT v = d[@field]
  FILTER v != null
  SORT v
  LIMIT @limit_plus
  RETURN v
"""
        cursor = db.aql.execute(
            aql,
            bind_vars={
                "@coll": collection,
                "field": field,
                "contains": contains,
                "limit_plus": limit + 1,
            },
            max_runtime=5,
        )
        values = list(cursor)
        truncated = len(values) > limit
        return {"values": values[:limit], "truncated": truncated}
    except Exception as exc:
        logger.warning("distinct_values error for %s.%s: %s", collection, field, exc)
        return {"error": str(exc)}


@tool
def validate_aql(aql: str, bind_vars: dict) -> dict:
    """Statically validate AQL without executing it.

    Checks: (1) read-only, (2) all collections exist, (3) LIMIT present and before RETURN,
    (4) all bind variables referenced are provided, (5) ArangoDB parser accepts it.

    Returns errors and warnings; the agent should fix any errors before final answer.
    """
    db = _get_db()
    result = _validator.validate(aql, bind_vars, db=db)
    return {
        "ok": result.ok,
        "errors": result.errors,
        "warnings": result.warnings,
    }


@tool
def explain_aql(aql: str, bind_vars: dict) -> dict:
    """Get the ArangoDB query plan without executing.

    Use sparingly — only when you suspect a query is correct but unusually slow,
    or when the user asks about query performance.
    """
    db = _get_db()
    if db is None:
        return {"error": "Database not available"}
    try:
        plan_info = db.aql.explain(aql, bind_vars=bind_vars)
        return {"plan": plan_info.get("plan", {}), "warnings": plan_info.get("warnings", [])}
    except Exception as exc:
        return {"error": str(exc)}


@tool
def submit_answer(
    aql: str,
    bind_vars: dict,
    explanation: str,
    confidence: str = "high",
    assumptions: list = None,
    alternative: dict | None = None,
) -> str:
    """Submit your final AQL answer. Call this exactly once at the end.

    confidence: 'high' (unambiguous), 'medium' (one alternative reading), 'low' (multiple plausible readings).
    assumptions: list of human-readable interpretive choices made.
    alternative: optional dict with keys 'aql', 'bind_vars', 'explanation' for an alternative interpretation.
    When confidence == 'high', alternative MUST be None. When confidence == 'low', alternative IS REQUIRED.
    """
    return "submitted"


TOOLS = [list_collections, describe_collection, distinct_values, validate_aql, explain_aql, submit_answer]
