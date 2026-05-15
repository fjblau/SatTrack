from __future__ import annotations

import logging
import re
from typing import Any

from config import config

logger = logging.getLogger(__name__)

_TRAVERSAL_RE = re.compile(r"\b(OUTBOUND|INBOUND|ANY)\b", re.IGNORECASE)


def _max_runtime(aql: str) -> int:
    if _TRAVERSAL_RE.search(aql):
        return config.agent.GRAPH_MAX_RUNTIME_S
    return config.agent.DEFAULT_MAX_RUNTIME_S


def execute(aql: str, bind_vars: dict[str, Any]) -> dict:
    try:
        import database.connection as db_conn

        cursor = db_conn.db.aql.execute(
            aql,
            bind_vars=bind_vars,
            max_runtime=_max_runtime(aql),
        )
        rows = list(cursor)
        return {"result": rows, "row_count": len(rows), "error": ""}
    except Exception as exc:
        logger.warning("AQL execution error: %s", exc)
        return {"result": [], "row_count": 0, "error": str(exc)}
