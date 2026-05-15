from __future__ import annotations

import re

_TOP_LEVEL_KEYWORDS = [
    "FOR", "FILTER", "LET", "COLLECT", "SORT", "LIMIT", "RETURN",
    "WITH", "INSERT", "UPDATE", "REPLACE", "REMOVE", "UPSERT", "OPTIONS",
]

_KW_RE = re.compile(
    r"(?<!['\"`\w])(" + "|".join(_TOP_LEVEL_KEYWORDS) + r")(?!['\"`\w])",
    re.IGNORECASE,
)

_MAX_LINE_LEN = 100


def _is_in_string(pos: int, text: str) -> bool:
    in_single = False
    in_double = False
    in_backtick = False
    i = 0
    while i < pos:
        c = text[i]
        if c == "'" and not in_double and not in_backtick:
            in_single = not in_single
        elif c == '"' and not in_single and not in_backtick:
            in_double = not in_double
        elif c == '`' and not in_single and not in_double:
            in_backtick = not in_backtick
        i += 1
    return in_single or in_double or in_backtick


def _split_at_top_level_keywords(aql: str) -> list[str]:
    normalized = " ".join(aql.split())

    positions: list[tuple[int, str]] = []
    for m in _KW_RE.finditer(normalized):
        if not _is_in_string(m.start(), normalized):
            positions.append((m.start(), m.group(0).upper()))

    if not positions:
        return [normalized]

    clauses: list[str] = []
    for i, (pos, kw) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(normalized)
        chunk = normalized[pos:end].strip()
        clauses.append(chunk)
    return clauses


def _wrap_long_line(line: str, indent: int = 4) -> str:
    if len(line) <= _MAX_LINE_LEN:
        return line
    pad = " " * indent
    for connector in [" AND ", " OR "]:
        if connector in line:
            parts = line.split(connector)
            result = parts[0]
            for part in parts[1:]:
                result += "\n" + pad + connector.strip() + " " + part
            return result
    return line


def format_aql(aql: str) -> str:
    if not aql or not aql.strip():
        return aql

    try:
        return _format_aql_impl(aql)
    except Exception:
        return aql


def _format_aql_impl(aql: str) -> str:
    clauses = _split_at_top_level_keywords(aql)
    if not clauses:
        return aql

    lines: list[str] = []
    prev_was_return = False

    for clause in clauses:
        kw = clause.split()[0].upper() if clause else ""

        if kw == "FOR" and prev_was_return and lines:
            lines.append("")

        wrapped = _wrap_long_line(clause)
        lines.append(wrapped)

        prev_was_return = kw == "RETURN"

    result = "\n".join(lines)

    result = re.sub(r",\s+", ", ", result)
    result = re.sub(r"\(\s+", "(", result)
    result = re.sub(r"\[\s+", "[", result)
    result = re.sub(r"\s+\)", ")", result)
    result = re.sub(r"\s+\]", "]", result)

    return result
