import json
import logging
from typing import Any, TypedDict

from config import config

logger = logging.getLogger(__name__)

_SCHEMA_CONTEXT_BASE = """
## ArangoDB Schema

### Vertex Collections

**satellites** (primary registry)
- `_id`: "satellites/<identifier>"
- `identifier`: string e.g. "2023-001A", "25544"
- `canonical.satellite_name` / `canonical.object_name`: string (either may be null)
- `canonical.country_of_registration`: string — full country name (see ENUM VALUES below)
- `canonical.status`: string — (see ENUM VALUES below)
- `canonical.orbital_band`: string — (see ENUM VALUES below)
- `canonical.launch_date`: string (ISO date)
- `canonical.norad_cat_id`: integer
- `canonical.international_designator`: string
- `canonical.apogee_km`: float
- `canonical.perigee_km`: float
- `canonical.inclination_deg`: float

**registration_documents** (UN document metadata)
- `_id`: "registration_documents/<key>"
- `title`, `country`, `date`

**observations** (health records)
- `_id`: "observations/<key>"
- `norad_id`: integer
- `source`: string
- `observation_epoch`: string (ISO datetime)
- `derived_health_score`: float 0–1
- `mass_kg`: float
- `spin_rate_rpm`: float
- `thermal_anomaly`: boolean

**observation_sources** (submitter metadata)
- `_id`: "observation_sources/<key>"
- `name`, `type`: string

### Edge Collections

| Collection | From → To | Notable fields |
|-----------|-----------|----------------|
| `constellation_membership` | satellites → satellites | `constellation_name` |
| `registration_links` | satellites → registration_documents | — |
| `orbital_proximity` | satellites → satellites | `delta_apogee_km`, `delta_perigee_km`, `delta_inclination_deg` |
| `collision_risk_edges` | satellites → satellites | `risk_score` (0–1), `min_distance_km` |
| `satellite_lineage` | satellites → satellites | `relationship` ("predecessor"/"successor") |
| `observation_satellite_edges` | observations → satellites | — |
| `observation_source_edges` | observations → observation_sources | — |
| `observation_correlation_edges` | observations → observations | `correlation_type` |
| `observation_temporal_edges` | observations → observations | temporal ordering |

### AQL Tips
- `FOR s IN satellites FILTER ... RETURN s` for document queries
- `FOR v, e IN 1..1 OUTBOUND "satellites/<id>" <edge_col>` for graph traversal
- **LIMIT must always appear before RETURN** — never after it:
  - CORRECT: `FOR s IN satellites FILTER ... SORT s.canonical.launch_date DESC LIMIT 20 RETURN s`
  - WRONG:   `FOR s IN satellites FILTER ... RETURN s LIMIT 20`
- `canonical.satellite_name` may be null — prefer `canonical.satellite_name || canonical.object_name`
- NORAD IDs are integers — do not quote them
"""

_COUNTRY_ALIASES: dict[str, str] = {
    k.lower(): v for k, v in {
        # Austria
        "at": "Austria", "aut": "Austria", "austrian": "Austria",
        # Australia
        "au": "Australia", "aus": "Australia", "australian": "Australia",
        # Belgium
        "be": "Belgium", "bel": "Belgium", "belgian": "Belgium",
        # Brazil
        "br": "Brazil", "bra": "Brazil", "brazilian": "Brazil",
        # Canada
        "ca": "Canada", "can": "Canada", "canadian": "Canada",
        # China
        "cn": "China", "chn": "China", "chinese": "China",
        "people's republic of china": "China", "prc": "China",
        # Denmark
        "dk": "Denmark", "dnk": "Denmark", "danish": "Denmark",
        # Finland
        "fi": "Finland", "fin": "Finland", "finnish": "Finland",
        # France
        "fr": "France", "fra": "France", "french": "France",
        # Germany
        "de": "Germany", "deu": "Germany", "german": "Germany",
        # India
        "in": "India", "ind": "India", "indian": "India",
        # Indonesia
        "id": "Indonesia", "idn": "Indonesia", "indonesian": "Indonesia",
        # Israel
        "il": "Israel", "isr": "Israel", "israeli": "Israel",
        # Italy
        "it": "Italy", "ita": "Italy", "italian": "Italy",
        # Japan
        "jp": "Japan", "jpn": "Japan", "japanese": "Japan",
        # Luxembourg
        "lu": "Luxembourg", "lux": "Luxembourg",
        # Netherlands
        "nl": "Netherlands", "nld": "Netherlands", "dutch": "Netherlands",
        # New Zealand
        "nz": "New Zealand", "nzl": "New Zealand",
        # Norway
        "no": "Norway", "nor": "Norway", "norwegian": "Norway",
        # Pakistan
        "pk": "Pakistan", "pak": "Pakistan", "pakistani": "Pakistan",
        # Republic of Korea
        "kr": "Republic of Korea", "kor": "Republic of Korea",
        "south korea": "Republic of Korea", "korean": "Republic of Korea",
        # Russian Federation
        "ru": "Russian Federation", "rus": "Russian Federation",
        "russia": "Russian Federation", "russian": "Russian Federation",
        # Saudi Arabia
        "sa": "Saudi Arabia", "sau": "Saudi Arabia", "saudi": "Saudi Arabia",
        # Singapore
        "sg": "Singapore", "sgp": "Singapore", "singaporean": "Singapore",
        # South Africa
        "za": "South Africa", "zaf": "South Africa", "south african": "South Africa",
        # Spain
        "es": "Spain", "esp": "Spain", "spanish": "Spain",
        # Sweden
        "se": "Sweden", "swe": "Sweden", "swedish": "Sweden",
        # Switzerland
        "ch": "Switzerland", "che": "Switzerland", "swiss": "Switzerland",
        # Thailand
        "th": "Thailand", "tha": "Thailand", "thai": "Thailand",
        # Turkey
        "tr": "Turkey", "tur": "Turkey", "turkish": "Turkey",
        # United Arab Emirates
        "ae": "United Arab Emirates", "are": "United Arab Emirates", "uae": "United Arab Emirates",
        # United Kingdom
        "gb": "United Kingdom", "gbr": "United Kingdom",
        "uk": "United Kingdom", "british": "United Kingdom", "britain": "United Kingdom",
        # United States of America
        "us": "United States of America", "usa": "United States of America",
        "usa": "United States of America", "u.s.": "United States of America",
        "united states": "United States of America", "american": "United States of America",
        # European Space Agency
        "esa": "European Space Agency",
    }.items()
}


def _annotate_question_with_countries(question: str, known_countries: list[str]) -> str:
    """
    Scan the question for known country aliases and prepend an unambiguous
    resolution note so the LLM uses the exact stored value.
    """
    words = question.lower().split()
    # also check two-word phrases
    bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)]
    resolved: dict[str, str] = {}

    for token in bigrams + words:
        token_clean = token.strip("'\".,;:?!()")
        if token_clean in _COUNTRY_ALIASES:
            canonical = _COUNTRY_ALIASES[token_clean]
            if canonical in known_countries or not known_countries:
                resolved[token_clean] = canonical

    if not resolved:
        return question

    notes = "; ".join(
        f'"{raw}" → exact DB value: "{canonical}"'
        for raw, canonical in resolved.items()
    )
    return f"[Country resolution: {notes}]\n{question}"


_ENUM_VALUES_FALLBACK = {
    "countries": [
        "Austria", "Australia", "Belgium", "Brazil", "Canada", "China", "Denmark",
        "European Space Agency", "Finland", "France", "Germany", "India", "Indonesia",
        "Israel", "Italy", "Japan", "Luxembourg", "Netherlands", "New Zealand", "Norway",
        "Pakistan", "Republic of Korea", "Russian Federation", "Saudi Arabia", "Singapore",
        "South Africa", "Spain", "Sweden", "Switzerland", "Thailand", "Turkey",
        "United Arab Emirates", "United Kingdom", "United States of America",
    ],
    "statuses": ["in orbit", "decayed", "unknown", "deorbited"],
    "orbital_bands": ["LEO", "MEO", "GEO", "HEO", "SSO", "Unknown"],
}


def _fetch_enum_values() -> dict:
    """Query the DB for the actual distinct field values at startup."""
    try:
        import database.connection as db_conn

        def _collect(aql: str) -> list:
            return sorted(
                v for v in db_conn.db.aql.execute(aql, max_runtime=10)
                if v is not None
            )

        return {
            "countries": _collect(
                "FOR s IN satellites "
                "COLLECT c = s.canonical.country_of_registration RETURN c"
            ),
            "statuses": _collect(
                "FOR s IN satellites "
                "COLLECT v = s.canonical.status RETURN v"
            ),
            "orbital_bands": _collect(
                "FOR s IN satellites "
                "COLLECT v = s.canonical.orbital_band RETURN v"
            ),
        }
    except Exception as exc:
        logger.warning("Could not fetch enum values from DB, using fallback: %s", exc)
        return _ENUM_VALUES_FALLBACK


def _build_system_prompt(enums: dict) -> str:
    countries_str = ", ".join(f'"{c}"' for c in enums["countries"])
    statuses_str = ", ".join(f'"{s}"' for s in enums["statuses"])
    bands_str = ", ".join(f'"{b}"' for b in enums["orbital_bands"])

    enum_section = f"""
### ENUM VALUES — use these exact strings, never abbreviations or ISO codes

`canonical.country_of_registration` must be one of:
{countries_str}

`canonical.status` must be one of:
{statuses_str}

`canonical.orbital_band` must be one of:
{bands_str}

When a user refers to a country by a common name, adjective, or abbreviation (e.g. "Austrian", "US", "American", "Russian"), map it to the exact string above.
"""

    return (
        "You are an AQL (ArangoDB Query Language) expert for the Kessler satellite tracking database.\n\n"
        "Translate the user's natural language question into a correct, read-only AQL query.\n\n"
        + _SCHEMA_CONTEXT_BASE
        + enum_section
        + """
Rules:
- Only FOR...RETURN queries. No INSERT / UPDATE / REPLACE / REMOVE / UPSERT.
- LIMIT must come before RETURN, never after it. This is a hard AQL requirement.
- Always include LIMIT (default 20) unless the user asks for counts or aggregates.
- Always inline values as string literals directly in the AQL — never use @bind_var placeholders. The query must be self-contained and runnable as-is.
- If you receive an error from a previous attempt, fix the query accordingly.

Respond with a JSON object and no other text:
{
  "aql": "<the AQL query, with all values inlined as literals>",
  "bind_vars": {},
  "explanation": "<one sentence: what this query returns>"
}
"""
    )


class _State(TypedDict):
    question: str
    aql: str
    bind_vars: dict
    explanation: str
    result: list
    error: str
    iterations: int


_llm = None
_graph = None
_system_prompt = None
_known_countries: list[str] = []


def initialize_aql_agent() -> None:
    global _llm, _system_prompt, _known_countries
    if not config.agent.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set — /v2/aql endpoint will be unavailable.")
        return
    try:
        from langchain_openai import ChatOpenAI

        _llm = ChatOpenAI(
            model=config.agent.MODEL,
            api_key=config.agent.OPENAI_API_KEY,
            temperature=0,
        )
        enums = _fetch_enum_values()
        _known_countries = enums["countries"]
        _system_prompt = _build_system_prompt(enums)
        logger.info(
            "AQL translation agent initialized with model '%s' (%d countries, %d statuses, %d bands).",
            config.agent.MODEL,
            len(enums["countries"]),
            len(enums["statuses"]),
            len(enums["orbital_bands"]),
        )
    except Exception as exc:
        logger.error("Failed to initialize AQL agent: %s", exc, exc_info=True)


def is_ready() -> bool:
    return _llm is not None


def _parse_llm_response(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        content = "\n".join(lines[1:])
        if content.rstrip().endswith("```"):
            content = content.rstrip()[:-3]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"aql": content, "bind_vars": {}, "explanation": ""}


def _build_graph():
    from langgraph.graph import StateGraph, END
    from langchain_core.messages import HumanMessage, SystemMessage

    def translate(state: _State) -> _State:
        prompt = _annotate_question_with_countries(state["question"], _known_countries)
        if state.get("error"):
            prompt = (
                f"{prompt}\n\n"
                f"Previous AQL:\n{state['aql']}\n\n"
                f"Execution error: {state['error']}\n\n"
                "Fix the query."
            )
        response = _llm.invoke([
            SystemMessage(content=_system_prompt),
            HumanMessage(content=prompt),
        ])
        parsed = _parse_llm_response(response.content)
        return {
            **state,
            "aql": parsed.get("aql", ""),
            "bind_vars": parsed.get("bind_vars", {}),
            "explanation": parsed.get("explanation", ""),
            "error": "",
            "iterations": state.get("iterations", 0) + 1,
        }

    def execute(state: _State) -> _State:
        aql = state.get("aql", "")
        forbidden = {"INSERT", "UPDATE", "REPLACE", "REMOVE", "UPSERT"}
        if any(kw in aql.upper() for kw in forbidden):
            return {**state, "error": "Write operations are not permitted.", "result": []}
        try:
            import database.connection as db_conn

            cursor = db_conn.db.aql.execute(
                aql,
                bind_vars=state.get("bind_vars", {}),
                max_runtime=15,
            )
            return {**state, "result": list(cursor)[:50], "error": ""}
        except Exception as exc:
            return {**state, "error": str(exc), "result": []}

    def should_retry(state: _State) -> str:
        if state.get("error") and state.get("iterations", 0) < 3:
            return "translate"
        return END

    g = StateGraph(_State)
    g.add_node("translate", translate)
    g.add_node("execute", execute)
    g.set_entry_point("translate")
    g.add_edge("translate", "execute")
    g.add_conditional_edges("execute", should_retry, {"translate": "translate", END: END})
    return g.compile()


def _get_graph():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


def run_aql_agent(question: str) -> dict[str, Any]:
    if _llm is None:
        return {
            "aql": "",
            "bind_vars": {},
            "result": [],
            "explanation": "",
            "error": "AQL agent unavailable. Ensure OPENAI_API_KEY is set.",
        }
    initial: _State = {
        "question": question,
        "aql": "",
        "bind_vars": {},
        "explanation": "",
        "result": [],
        "error": "",
        "iterations": 0,
    }
    final = _get_graph().invoke(initial)
    return {
        "aql": final.get("aql", ""),
        "bind_vars": final.get("bind_vars", {}),
        "result": final.get("result", []),
        "explanation": final.get("explanation", ""),
        "error": final.get("error", ""),
    }
