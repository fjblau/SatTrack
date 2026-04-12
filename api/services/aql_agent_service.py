import json
import logging
from typing import Any, TypedDict

from config import config

logger = logging.getLogger(__name__)

_SCHEMA_CONTEXT = """
## ArangoDB Schema

### Vertex Collections

**satellites** (primary registry)
- `_id`: "satellites/<identifier>"
- `identifier`: string e.g. "2023-001A", "25544"
- `canonical.satellite_name` / `canonical.object_name`: string (either may be null)
- `canonical.country_of_registration`: string e.g. "US", "CN", "RU"
- `canonical.status`: string e.g. "in orbit", "decayed", "unknown"
- `canonical.orbital_band`: string e.g. "LEO", "MEO", "GEO", "HEO"
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
- `canonical.country_of_registration` stores **full country names**, never ISO codes — e.g. `"Austria"`, `"United States of America"`, `"Russian Federation"`, `"China"`, `"France"`, `"Germany"`, `"Japan"`. Never use "AT", "US", "RU", etc.
- NORAD IDs are integers — do not quote them
"""

_SYSTEM_PROMPT = f"""You are an AQL (ArangoDB Query Language) expert for the Kessler satellite tracking database.

Translate the user's natural language question into a correct, read-only AQL query.

{_SCHEMA_CONTEXT}

Rules:
- Only FOR...RETURN queries. No INSERT / UPDATE / REPLACE / REMOVE / UPSERT.
- LIMIT must come before RETURN, never after it. This is a hard AQL requirement.
- Always include LIMIT (default 20) unless the user asks for counts or aggregates.
- Use @bind_var placeholders for user-supplied values.
- If you receive an error from a previous attempt, fix the query accordingly.

Respond with a JSON object and no other text:
{{
  "aql": "<the AQL query>",
  "bind_vars": {{}},
  "explanation": "<one sentence: what this query returns>"
}}
"""


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


def initialize_aql_agent() -> None:
    global _llm
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
        logger.info("AQL translation agent initialized with model '%s'.", config.agent.MODEL)
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
        prompt = state["question"]
        if state.get("error"):
            prompt = (
                f"{state['question']}\n\n"
                f"Previous AQL:\n{state['aql']}\n\n"
                f"Execution error: {state['error']}\n\n"
                "Fix the query."
            )
        response = _llm.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
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
