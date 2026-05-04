import json
import logging
from typing import Any, TypedDict

from config import config

logger = logging.getLogger(__name__)

_SCHEMA_CONTEXT_BASE = """
## ArangoDB Schema

### Vertex Collections

**objects** (primary space object registry — formerly 'satellites')
- `_id`: "objects/<identifier>"
- `identifier`: string e.g. "2023-001A", "25544"
- `canonical.satellite_name` / `canonical.object_name`: string (either may be null)
- `canonical.country_of_origin`: string — full country name (see ENUM VALUES below)
- `canonical.status`: string — (see ENUM VALUES below)
- `canonical.orbital_band`: string — (see ENUM VALUES below)
- `canonical.launch_date`: string (ISO date)
- `canonical.norad_cat_id`: integer
- `canonical.international_designator`: string
- `canonical.object_class`: string — DISCOSweb-aligned classification (see ENUM VALUES below)
- `canonical.object_type`: string — legacy field, deprecated; prefer object_class
- `canonical.rcs`: float — radar cross section in m² (best available proxy for physical size)
- `canonical.function`: string — stated mission/purpose
- `canonical.orbit.apogee_km`: float
- `canonical.orbit.perigee_km`: float
- `canonical.orbit.inclination_degrees`: float
- `canonical.orbit.period_minutes`: float
- `identifier_aliases.norad`: string — NORAD catalog ID as string
- `identifier_aliases.cospar`: string — COSPAR / international designator
- `identifier_aliases.discos`: string — DISCOSweb object ID
- `identifier_aliases.vimpel`: string — Vimpel catalog number
- `identifier_aliases.kestrel`: string — Kestrel internal ID

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
| `constellation_membership` | objects → objects | `constellation_name` |
| `registration_links` | objects → registration_documents | — |
| `orbital_proximity` | objects → objects | `delta_apogee_km`, `delta_perigee_km`, `delta_inclination_deg` |
| `collision_risk_edges` | objects → objects | `risk_score` (0–1), `min_distance_km` |
| `satellite_lineage` | objects → objects | `relationship` ("predecessor"/"successor") |
| `observation_satellite_edges` | observations → objects | — |
| `observation_source_edges` | observations → observation_sources | — |
| `observation_correlation_edges` | observations → observations | `correlation_type` |
| `observation_temporal_edges` | observations → observations | temporal ordering |

### AQL Tips
- `FOR s IN objects FILTER ... RETURN s` for document queries
- `FOR v, e IN 1..1 OUTBOUND "objects/<id>" <edge_col>` for graph traversal
- **LIMIT must always appear before RETURN** — never after it:
  - CORRECT: `FOR s IN objects FILTER ... SORT s.canonical.launch_date DESC LIMIT 20 RETURN s`
  - WRONG:   `FOR s IN objects FILTER ... RETURN s LIMIT 20`
- `canonical.satellite_name` may be null — prefer `canonical.satellite_name || canonical.object_name`
- NORAD IDs are integers — do not quote them
- To filter by object class: `FILTER s.canonical.object_class == "Payload"` (or "Rocket Body", "Unknown", etc.)
- To look up by NORAD alias: `FILTER s.identifier_aliases.norad == "25544"`

### Clarifying questions for ambiguous queries
- If the user says "debris" they likely want `object_class IN ["Rocket Fragmentation Debris", "Payload Fragmentation Debris", "Unknown"]`
- If the user says "rocket body" or "rocket bodies" they want `object_class == "Rocket Body"`
- If the user says "payload" or "satellite" in a functional sense they want `object_class == "Payload"`

---

## Provenance Graph Collections (DISCOS Spec 2)

### Vertex Collections

**fragmentation_events** (ESA DISCOS fragmentation events)
- `_id`: "fragmentation_events/<key>"
- `identifier`: string — e.g. "DISCOS-FRAG-1234"
- `canonical.epoch`: string (ISO date) — when the fragmentation occurred
- `canonical.altitude_km`: float — altitude of breakup
- `canonical.event_type`: string — "Explosion", "Collision", "ASAT Test", "Unknown"
- `canonical.fragment_count`: integer
- `canonical.casualty_risk`: float or null
- `metadata.policy_overlay`: null (stub field; populated in follow-on PR)

**launch_events** (ESA DISCOS launch events)
- `_id`: "launch_events/<key>"
- `identifier`: string — e.g. "1999-025" (cosparLaunchId)
- `canonical.cospar_launch_id`: string
- `canonical.launch_date`: string (ISO date)
- `sources.discos.discos_id`: string

**launch_vehicles** (ESA DISCOS launch vehicle records)
- `_id`: "launch_vehicles/<key>"
- `canonical.name`: string — e.g. "Soyuz-U"
- `canonical.family`: string

**launch_sites** (ESA DISCOS launch site records)
- `_id`: "launch_sites/<key>"
- `canonical.name`: string — e.g. "Baikonur"
- `canonical.latitude`: float
- `canonical.longitude`: float

**entities** (ESA DISCOS operators / countries / organisations)
- `_id`: "entities/<key>"
- `canonical.name`: string — operator name
- `canonical.country`: string
- `canonical.entity_type`: string

### Provenance Edge Collections

| Collection | From → To | Notable fields |
|-----------|-----------|----------------|
| `fragmented_from` | objects → objects | `confidence` (0–1), `confidence_label` ("high"/"medium"/"low") |
| `caused_by` | objects → fragmentation_events | `confidence` (0–1) |
| `launched_by` | objects → entities | — |
| `launched_via` | objects → launch_vehicles | — |
| `launched_from` | objects → launch_sites | — |

Named graph: **provenance_relationships**

### Provenance AQL Tips
- Confidence thresholds: ≥0.9 = high, 0.7–0.9 = medium, <0.7 = low (require explicit filter)
- Siblings (other fragments from same parent) require two-hop traversal:
  `FOR e IN fragmented_from FILTER e._from == @obj_id LET parent = DOCUMENT(e._to) FOR e2 IN fragmented_from FILTER e2._to == parent._id RETURN DOCUMENT(e2._from)`
- `metadata.attribution_status` on objects: "attributed" = has fragmented_from edge, "pending" = no explicit DISCOS event

### Provenance Few-Shot Examples

**Q: Find the parent object of a debris fragment**
```aql
LET fragment = DOCUMENT("objects/1999-025AHH")
FOR e IN fragmented_from
    FILTER e._from == fragment._id AND (e.confidence == null OR e.confidence >= 0.7)
    RETURN {parent: DOCUMENT(e._to), confidence: e.confidence}
```

**Q: List all fragments of the Kosmos-2251 collision event**
```aql
FOR e IN fragmentation_events
    FILTER e.canonical.epoch >= "2009-02-10" AND e.canonical.epoch <= "2009-02-11"
    FOR caused IN caused_by
        FILTER caused._to == e._id
        RETURN DOCUMENT(caused._from)
```

**Q: Find the operator of an object**
```aql
FOR obj IN objects
    FILTER obj.identifier_aliases.norad == "25544"
    FOR e IN launched_by
        FILTER e._from == obj._id
        RETURN DOCUMENT(e._to)
```

**Q: Find all objects launched from Baikonur**
```aql
FOR site IN launch_sites
    FILTER CONTAINS(LOWER(site.canonical.name), "baikonur")
    FOR e IN launched_from
        FILTER e._to == site._id
        LIMIT 100
        RETURN DOCUMENT(e._from)
```

**Q: Count fragments per fragmentation event**
```aql
FOR ev IN fragmentation_events
    LET frag_count = LENGTH(
        FOR e IN caused_by FILTER e._to == ev._id RETURN 1
    )
    FILTER frag_count > 0
    SORT frag_count DESC
    LIMIT 20
    RETURN {event: ev.identifier, fragment_count: frag_count, epoch: ev.canonical.epoch}
```
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
                "FOR s IN objects "
                "COLLECT c = s.canonical.country_of_origin RETURN c"
            ),
            "statuses": _collect(
                "FOR s IN objects "
                "COLLECT v = s.canonical.status RETURN v"
            ),
            "orbital_bands": _collect(
                "FOR s IN objects "
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

`canonical.country_of_origin` must be one of:
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
- For "physical size", "physical dimensions", or "dimensions" of satellites, use `canonical.rcs` (radar cross section in m²). Never invent fields that are not listed in the schema above.
- For "mass" or "weight" of satellites, use `mass_kg` from the observations collection.

Respond with a JSON object and no other text:
{
  "aql": "<the AQL query, with all values inlined as literals>",
  "bind_vars": {},
  "explanation": "<one sentence: what this query returns>"
}
"""
    )


_CLARIFY_SYSTEM_PROMPT = """You are an assistant that detects when a natural language database query is ambiguous.

The Kessler space object database (collection: 'objects') has these potentially ambiguous concepts:
- "country" could mean `canonical.country_of_origin` (where the object was built/registered by) OR a launch registration nation — always prefer `country_of_origin` unless the user explicitly asks about registration.
- "active" or "operational" objects → `canonical.status == 'in orbit'`
- "inactive" / "dead" / "decommissioned" → `canonical.status == 'decayed'`
- "name" could mean `canonical.name`, `canonical.object_name`, or `canonical.satellite_name`
- "size" or "largest" for objects → use `canonical.rcs` (radar cross section in m², the best physical size proxy available). If the user says "physical size", "physical dimensions", or "dimensions", use `canonical.rcs`. If the user says "mass" or "weight", use `observations.mass_kg`. Do NOT ask for clarification about size — always default to `canonical.rcs` unless mass is explicitly requested.
- "debris" is ambiguous — ask whether the user wants `Rocket Fragmentation Debris`, `Payload Fragmentation Debris`, `Unknown`, or all debris-like classes together.
- "satellite" in a functional sense usually means `canonical.object_class == 'Payload'`.

If the question is clear enough to generate AQL without guessing, respond:
{"needs_clarification": false}

If there is genuine ambiguity that would change the query significantly, respond:
{"needs_clarification": true, "clarifying_question": "<one short question to resolve it>"}

Respond with JSON only. No other text."""


class _State(TypedDict):
    question: str
    clarification: str
    clarifying_question: str
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

    def clarify(state: _State) -> _State:
        # Skip clarification if the user already answered a clarifying question
        if state.get("clarification"):
            return {**state, "clarifying_question": ""}

        response = _llm.invoke([
            SystemMessage(content=_CLARIFY_SYSTEM_PROMPT),
            HumanMessage(content=state["question"]),
        ])
        parsed = _parse_llm_response(response.content)
        if parsed.get("needs_clarification"):
            return {**state, "clarifying_question": parsed.get("clarifying_question", "")}
        return {**state, "clarifying_question": ""}

    def should_clarify(state: _State) -> str:
        return "ask" if state.get("clarifying_question") else "translate"

    def translate(state: _State) -> _State:
        question = state["question"]
        if state.get("clarification"):
            question = f"{question}\n\nClarification from user: {state['clarification']}"
        prompt = _annotate_question_with_countries(question, _known_countries)
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
    g.add_node("clarify", clarify)
    g.add_node("ask", lambda s: s)   # terminal: return state with clarifying_question set
    g.add_node("translate", translate)
    g.add_node("execute", execute)
    g.set_entry_point("clarify")
    g.add_conditional_edges("clarify", should_clarify, {"ask": "ask", "translate": "translate"})
    g.add_edge("ask", END)
    g.add_edge("translate", "execute")
    g.add_conditional_edges("execute", should_retry, {"translate": "translate", END: END})
    return g.compile()


def _get_graph():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


def run_aql_agent(question: str, clarification: str = "") -> dict[str, Any]:
    if _llm is None:
        return {
            "aql": "",
            "bind_vars": {},
            "result": [],
            "explanation": "",
            "error": "AQL agent unavailable. Ensure OPENAI_API_KEY is set.",
            "clarifying_question": "",
        }
    initial: _State = {
        "question": question,
        "clarification": clarification,
        "clarifying_question": "",
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
        "clarifying_question": final.get("clarifying_question", ""),
    }
