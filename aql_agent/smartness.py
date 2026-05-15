from __future__ import annotations

import logging
import re
from typing import Any

from aql_agent.schema_cache import did_you_mean

logger = logging.getLogger(__name__)

_AGGREGATE_RE = re.compile(
    r"\b(COLLECT\s+WITH\s+COUNT\s+INTO|COUNT\s*\(|LENGTH\s*\(|SUM\s*\(|AVG\s*\(|MIN\s*\(|MAX\s*\()",
    re.IGNORECASE,
)
_LIMIT_RE = re.compile(r"\bLIMIT\s+(\d+)", re.IGNORECASE)


def check_reflection_trigger(
    rows: list,
    row_count: int,
    aql: str,
) -> str | None:
    is_aggregate = bool(_AGGREGATE_RE.search(aql))

    if row_count == 0 and not is_aggregate:
        return "EMPTY_RESULT"

    limit_match = _LIMIT_RE.search(aql)
    if limit_match:
        effective_limit = int(limit_match.group(1))
        if effective_limit > 0 and row_count >= 0.8 * effective_limit:
            return "LIMIT_BRUSHED"

    if rows and len(rows) > 0:
        sample = rows[:20]
        null_heavy_count = 0
        for row in sample:
            if isinstance(row, dict) and row:
                top_vals = list(row.values())
                if top_vals and all(v is None for v in top_vals):
                    null_heavy_count += 1
        if len(sample) > 0 and null_heavy_count / len(sample) > 0.5:
            return "NULL_HEAVY"

    if is_aggregate and row_count == 1 and rows:
        row = rows[0]
        if isinstance(row, dict):
            if all(v in (0, None) for v in row.values()):
                return "AGGREGATE_ZERO"
        elif row in (0, None):
            return "AGGREGATE_ZERO"

    return None


def try_empty_result_repair(
    state: dict,
    result_count: int,
) -> dict | None:
    if result_count != 0:
        return None

    aql = state.get("aql", "")
    bind_vars = state.get("bind_vars", {}) or {}
    question = state.get("question", "")

    if not bind_vars:
        return None

    try:
        import database.connection as db_conn
        db = db_conn.db
    except Exception:
        return None

    question_tokens = set(
        w.lower().strip("'\".,;:?!()") for w in question.split() if len(w) >= 3
    )

    for bk, bv in bind_vars.items():
        if not isinstance(bv, str):
            continue
        if bv.lower() not in question_tokens and bv not in question:
            continue

        field_match = re.search(
            r"\bFILTER\b[^#\n]*?d\.([\w.]+)\s*==\s*@" + re.escape(bk.lstrip("@")),
            aql,
            re.IGNORECASE,
        )
        if not field_match:
            collection_match = re.search(r"\bFOR\s+\w+\s+IN\s+(\w+)", aql, re.IGNORECASE)
            if not collection_match:
                continue
            collection = collection_match.group(1)
            field = None
        else:
            collection_match = re.search(r"\bFOR\s+\w+\s+IN\s+(\w+)", aql, re.IGNORECASE)
            collection = collection_match.group(1) if collection_match else None
            field = field_match.group(1)

        if not collection or not field:
            continue

        try:
            cursor = db.aql.execute(
                "FOR d IN @@coll COLLECT v = d[@field] FILTER v != null SORT v LIMIT 51 RETURN v",
                bind_vars={"@coll": collection, "field": field},
                max_runtime=5,
            )
            candidates = [str(v) for v in cursor if v is not None]
        except Exception:
            continue

        close_match = _find_close_match(bv, candidates)
        if close_match is None:
            top5 = candidates[:5]
            existing_assumptions = state.get("assumptions", []) or []
            return {
                "assumptions": existing_assumptions + [
                    f"No rows match. Verified '{bv}' is not present in {collection}.{field}. Closest stored values: {top5}."
                ],
                "confidence": "medium",
            }

        if close_match != bv:
            new_bind_vars = {**bind_vars, bk: close_match}
            try:
                import database.connection as db_conn
                from aql_agent import executor as _executor
                repair_result = _executor.execute(aql, new_bind_vars)
                if repair_result["row_count"] > 0:
                    existing_assumptions = state.get("assumptions", []) or []
                    return {
                        "aql": aql,
                        "bind_vars": new_bind_vars,
                        "result": repair_result["result"],
                        "row_count": repair_result["row_count"],
                        "error": "",
                        "assumptions": existing_assumptions + [
                            f"No rows matched '{bv}' in {collection}.{field}. Substituted closest match '{close_match}'."
                        ],
                        "confidence": "medium",
                    }
            except Exception:
                pass

    return None


def _find_close_match(value: str, candidates: list[str]) -> str | None:
    from aql_agent.schema_cache import _levenshtein

    best: str | None = None
    best_dist = 4

    for c in candidates:
        if value.lower() == c.lower():
            return c
        dist = _levenshtein(value.lower(), c.lower())
        if dist <= 3 and dist < best_dist:
            best_dist = dist
            best = c
        if value.lower() in c.lower() or c.lower() in value.lower():
            if best_dist > 1:
                best_dist = 1
                best = c

    return best
