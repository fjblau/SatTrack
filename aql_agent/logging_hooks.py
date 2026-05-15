from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

from config import config

logger = logging.getLogger(__name__)


def _serialize(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def write_log_line(
    log_id: str,
    question: str,
    clarification: str,
    clarifying_question: str,
    tools_called: list[dict],
    iterations: int,
    final_aql: str,
    raw_aql: str,
    final_bind_vars: dict,
    validator_result: dict,
    db_error: str | None,
    row_count: int,
    started_at: datetime,
    outcome: str,
    model: str,
    confidence: str = "high",
    assumptions: list[str] | None = None,
    alternative: dict | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    total_ms = int((now - started_at.replace(tzinfo=timezone.utc) if started_at.tzinfo is None else now - started_at).total_seconds() * 1000)

    record = {
        "ts": now.isoformat(),
        "log_id": log_id,
        "version": "v2",
        "model": model,
        "question": question,
        "clarification": clarification,
        "clarifying_question": clarifying_question,
        "tools_called": tools_called,
        "iterations": iterations,
        "raw_aql": raw_aql,
        "final_aql": final_aql,
        "final_bind_vars": final_bind_vars,
        "validator": validator_result,
        "db_error": db_error,
        "row_count": row_count,
        "total_latency_ms": total_ms,
        "outcome": outcome,
        "confidence": confidence,
        "assumptions": assumptions or [],
        "alternative": alternative,
    }

    line = json.dumps(record, default=_serialize)

    if config.agent.LOG_TO_STDOUT:
        try:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
        except Exception as exc:
            logger.warning("Failed to write log to stdout: %s", exc)

    if config.agent.LOG_TO_FILE:
        try:
            log_dir = os.path.dirname(config.agent.LOG_PATH)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            with open(config.agent.LOG_PATH, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except Exception as exc:
            logger.warning("Failed to write log to file %s: %s", config.agent.LOG_PATH, exc)

    return log_id
