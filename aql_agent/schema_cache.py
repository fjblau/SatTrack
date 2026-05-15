from __future__ import annotations

import logging
import time
from typing import Any

from config import config

logger = logging.getLogger(__name__)

_collections_cache: dict | None = None
_collections_cache_ts: float = 0.0

_describe_cache: dict[str, tuple[dict, float]] = {}


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (0 if ca == cb else 1)))
        prev = curr
    return prev[-1]


def get_collections(db: Any) -> dict:
    global _collections_cache, _collections_cache_ts
    now = time.time()
    if _collections_cache is not None and (now - _collections_cache_ts) < config.agent.SCHEMA_CACHE_TTL_S:
        return _collections_cache

    try:
        all_colls = db.collections()
        vertex = []
        edge = []
        for c in all_colls:
            name = c["name"] if isinstance(c, dict) else c.name
            ctype = c.get("type", 2) if isinstance(c, dict) else getattr(c, "type", 2)
            if name.startswith("_"):
                continue
            if ctype == 3:
                edge.append(name)
            else:
                vertex.append(name)
        result = {"vertex": sorted(vertex), "edge": sorted(edge)}
        _collections_cache = result
        _collections_cache_ts = now
        return result
    except Exception as exc:
        logger.warning("Failed to list collections: %s", exc)
        return {"vertex": [], "edge": []}


def get_all_collection_names(db: Any) -> list[str]:
    colls = get_collections(db)
    return colls["vertex"] + colls["edge"]


def did_you_mean(name: str, candidates: list[str], threshold: int = 2) -> list[str]:
    return [c for c in candidates if _levenshtein(name.lower(), c.lower()) <= threshold]


def flatten_fields(doc: dict, prefix: str = "", depth: int = 0, max_depth: int = 3) -> list[str]:
    fields: list[str] = []
    if depth >= max_depth:
        return fields
    for k, v in doc.items():
        full_key = f"{prefix}.{k}" if prefix else k
        fields.append(full_key)
        if isinstance(v, dict):
            fields.extend(flatten_fields(v, full_key, depth + 1, max_depth))
    return fields


def describe_collection(db: Any, name: str) -> dict:
    now = time.time()
    if name in _describe_cache:
        cached, ts = _describe_cache[name]
        if (now - ts) < config.agent.SCHEMA_CACHE_TTL_S:
            return cached

    all_names = get_all_collection_names(db)
    if name not in all_names:
        suggestions = did_you_mean(name, all_names)
        result: dict = {"error": "collection not found", "did_you_mean": suggestions}
        return result

    try:
        coll = db.collection(name)
        is_edge = name in get_collections(db)["edge"]

        cursor = db.aql.execute(
            "FOR d IN @@coll LIMIT 20 RETURN d",
            bind_vars={"@coll": name},
            max_runtime=10,
        )
        sample_docs = list(cursor)

        field_set: set[str] = set()
        for doc in sample_docs:
            field_set.update(flatten_fields(doc))

        indexes_data: list[dict] = []
        if config.agent.DESCRIBE_INCLUDE_INDEXES:
            try:
                for idx in coll.indexes():
                    indexes_data.append({
                        "type": idx.get("type"),
                        "fields": idx.get("fields", []),
                        "unique": idx.get("unique", False),
                    })
            except Exception:
                pass

        sample = sample_docs[:3]

        result = {
            "collection": name,
            "is_edge": is_edge,
            "fields": sorted(field_set),
            "indexes": indexes_data,
            "sample": sample,
        }
        _describe_cache[name] = (result, now)
        return result
    except Exception as exc:
        logger.warning("Failed to describe collection %s: %s", name, exc)
        return {"error": str(exc)}


def invalidate_cache() -> None:
    global _collections_cache, _collections_cache_ts
    _collections_cache = None
    _collections_cache_ts = 0.0
    _describe_cache.clear()
