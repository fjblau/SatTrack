from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from aql_agent.schema_cache import did_you_mean, get_all_collection_names


@dataclass
class ValidationError:
    code: str
    message: str


@dataclass
class ValidationWarning:
    code: str
    message: str


@dataclass
class ValidationResult:
    ok: bool
    errors: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)


_WRITE_RE = re.compile(r"\b(INSERT|UPDATE|REPLACE|REMOVE|UPSERT)\b", re.IGNORECASE)

_TOP_LEVEL_FOR_RE = re.compile(r"\bFOR\b", re.IGNORECASE)
_COLLECT_RE = re.compile(r"\bCOLLECT\b", re.IGNORECASE)
_AGGREGATE_FN_RE = re.compile(r"\b(COUNT|SUM|AVG|MIN|MAX|LENGTH)\s*\(", re.IGNORECASE)
_LIMIT_RE = re.compile(r"\bLIMIT\b", re.IGNORECASE)
_RETURN_RE = re.compile(r"\bRETURN\b", re.IGNORECASE)

_BIND_VAR_RE = re.compile(r"@@([A-Za-z_][A-Za-z0-9_]*)|@([A-Za-z_][A-Za-z0-9_]*)")

_FOR_COLLECTION_RE = re.compile(
    r"\bFOR\s+\w+\s+IN\s+(`?)([A-Za-z_][A-Za-z0-9_]*)(`?)",
    re.IGNORECASE,
)
_TRAVERSAL_COLLECTION_RE = re.compile(
    r"\b(?:OUTBOUND|INBOUND|ANY)\b[^#\n]*?[,\s](`?)([A-Za-z_][A-Za-z0-9_]*)(`?)",
    re.IGNORECASE,
)
_DOCUMENT_FUNC_RE = re.compile(
    r'\bDOCUMENT\s*\(\s*["\']([A-Za-z_][A-Za-z0-9_]*)/[^"\']+["\']',
    re.IGNORECASE,
)
_ID_LITERAL_RE = re.compile(r'["\']([A-Za-z_][A-Za-z0-9_]*)/[^"\']+["\']')


def _extract_collections_from_aql(aql: str) -> list[str]:
    names: list[str] = []
    for m in _FOR_COLLECTION_RE.finditer(aql):
        names.append(m.group(2))
    for m in _TRAVERSAL_COLLECTION_RE.finditer(aql):
        names.append(m.group(2))
    for m in _DOCUMENT_FUNC_RE.finditer(aql):
        names.append(m.group(1))
    return names


def _find_bind_vars_in_aql(aql: str) -> dict[str, str]:
    refs: dict[str, str] = {}
    for m in _BIND_VAR_RE.finditer(aql):
        if m.group(1):
            refs[m.group(1)] = "collection"
        else:
            refs[m.group(2)] = "value"
    return refs


def validate(
    aql: str,
    bind_vars: dict[str, Any],
    db: Any = None,
    original_question: str = "",
) -> ValidationResult:
    errors: list[dict] = []
    warnings: list[dict] = []

    if _WRITE_RE.search(aql):
        errors.append({"code": "WRITE_OPERATION", "message": "Write operations are not permitted."})

    if db is not None:
        try:
            db.aql.validate(aql)
        except Exception as exc:
            errors.append({"code": "SYNTAX_ERROR", "message": str(exc)})

    if db is not None:
        known = set(get_all_collection_names(db))
        for cname in _extract_collections_from_aql(aql):
            if not cname.startswith("@") and cname not in known:
                suggestions = did_you_mean(cname, list(known))
                errors.append({
                    "code": "UNKNOWN_COLLECTION",
                    "message": f"Collection '{cname}' does not exist. Did you mean {suggestions}?",
                })

    if db is not None:
        known = set(get_all_collection_names(db))
        for m in _ID_LITERAL_RE.finditer(aql):
            prefix = m.group(1)
            if prefix not in known:
                errors.append({
                    "code": "UNKNOWN_ID_PREFIX",
                    "message": f"Unknown collection prefix '{prefix}' in _id literal.",
                })

    has_for = bool(_TOP_LEVEL_FOR_RE.search(aql))
    has_return = bool(_RETURN_RE.search(aql))
    has_collect = bool(_COLLECT_RE.search(aql))
    has_aggregate = bool(_AGGREGATE_FN_RE.search(aql))
    has_limit = bool(_LIMIT_RE.search(aql))

    if has_for and has_return and not has_collect and not has_aggregate and not has_limit:
        warnings.append({
            "code": "MISSING_LIMIT",
            "message": "Query has FOR...RETURN without LIMIT. Add LIMIT to bound result size.",
        })

    if has_limit and has_return:
        limit_pos = aql.upper().rfind("LIMIT")
        return_pos = aql.upper().rfind("RETURN")
        if limit_pos > return_pos:
            errors.append({
                "code": "LIMIT_AFTER_RETURN",
                "message": "LIMIT must appear before RETURN.",
            })

    aql_refs = _find_bind_vars_in_aql(aql)
    for ref_name, ref_type in aql_refs.items():
        key = f"@{ref_name}" if ref_type == "collection" else ref_name
        if key not in bind_vars and ref_name not in bind_vars:
            errors.append({
                "code": "MISSING_BIND_VAR",
                "message": f"Bind variable '@{ref_name}' is referenced in AQL but not provided in bind_vars.",
            })
    for bk in bind_vars:
        clean = bk.lstrip("@")
        if clean not in aql_refs:
            warnings.append({
                "code": "UNUSED_BIND_VAR",
                "message": f"Bind variable '{bk}' is provided but not referenced in AQL.",
            })

    if original_question:
        tokens = [w.lower().strip("'\".,;:?!()") for w in original_question.split() if len(w) >= 3]
        for token in tokens:
            pattern = re.compile(r'["\']' + re.escape(token) + r'["\']', re.IGNORECASE)
            if pattern.search(aql):
                warnings.append({
                    "code": "INLINED_STRING_LITERAL",
                    "message": f"Consider parameterizing literal '{token}' as a bind variable.",
                })
                break

    if "ephemeris_envelopes" in aql:
        has_unset = bool(re.search(r"\bUNSET\b", aql, re.IGNORECASE))
        if not has_unset:
            warnings.append({
                "code": "UNBOUNDED_EPHEMERIS_PAYLOAD",
                "message": "Query touches ephemeris_envelopes without UNSET on ephemeris_points.",
            })

    return ValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)
