# LangGraph Agent Architecture

This document describes the two LangGraph agents in Kessler, the LangChain patterns they
use, and guidance for extending them.

---

## Overview

Kessler ships two LangGraph-powered agents, both initialized at server startup via
`api/main.py`'s lifespan and served under the `/v2` prefix:

| Agent | Service file | Endpoint | Purpose |
|-------|-------------|----------|---------|
| **General Assistant** | `api/services/agent_service.py` | `POST /v2/ask` | Multi-turn Q&A over documentation and live satellite data |
| **AQL Translation Agent** | `api/services/aql_agent_service.py` | `POST /v2/aql` | Translate natural language into AQL, execute it, and return both the query and its results |

Both agents share the same `OPENAI_API_KEY` and `AGENT_MODEL` configuration values from
`config.py → AgentConfig`.

---

## Dependencies

All agent dependencies are declared in `requirements.txt`:

```
langgraph>=0.2.0
langchain-core>=0.3.0
langchain-openai>=0.2.0
langchain-community>=0.3.0
langchain-chroma>=0.1.0
langchain-text-splitters>=0.3.0
chromadb>=0.5.0
```

---

## Agent 1 — General Assistant (`agent_service.py`)

### Graph topology

```
        ┌─────────┐
  ──▶   │  agent  │  ◀──────────────────────┐
        └────┬────┘                          │
             │                               │
    tool_calls present?                      │
             │                               │
        yes  │  no                           │
             ▼   ▼                           │
          ┌──────┐  END                      │
          │tools │  ───────────────────────▶ │
          └──────┘     (loop back to agent)
```

- **Entry**: `agent` node
- **Conditional edge** (`should_continue`): if the last message has `tool_calls` → route to `tools`; otherwise → `END`
- **`tools` → `agent`**: unconditional edge (ReAct loop)

This is the canonical **ReAct (Reason + Act)** pattern: the LLM reasons, decides which
tool to call, the tool runs, and the output feeds back to the LLM for the next reasoning
step.

### State schema

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]   # full conversation history
```

Uses LangGraph's built-in `add_messages` reducer so messages from each node are appended
rather than replaced.

### Tools

Built by `_build_tools(retriever)` and bound to the LLM with `llm.bind_tools(tools)`:

| Tool | Description |
|------|-------------|
| `search_knowledge_base(query)` | RAG retrieval over indexed project documentation (ChromaDB, `text-embedding-3-small`) |
| `get_satellite_by_norad_id(norad_id)` | Direct AQL lookup by integer NORAD catalog ID |
| `search_satellites(query, limit)` | Full-text satellite registry search |
| `run_aql_query(aql)` | Execute any read-only AQL; blocked keywords: INSERT, UPDATE, REPLACE, REMOVE, UPSERT |

Tools are implemented as `@tool`-decorated functions (LangChain `langchain_core.tools`).
`ToolNode` from `langgraph.prebuilt` handles dispatching and error capture.

### RAG index (`index_service.py`)

- **Vector store**: ChromaDB, persisted to `AGENT_VECTOR_STORE_PATH` (default `.chroma`)
- **Embedding model**: `text-embedding-3-small` (OpenAI)
- **Chunking**: `RecursiveCharacterTextSplitter`, chunk size 1000, overlap 200
- **Sources indexed** (repo-root-relative):
  - `ARCHITECTURE.md`, `DEVELOPER_GUIDE.md`, `API_DOCUMENTATION.md`, `README.md`
  - `docs/GRAPH_RELATIONSHIPS.md`, `docs/MULTI_SOURCE_DATA_ARCHITECTURE.md`
  - `docs/OBSERVATIONS_IMPORT_API.md`, `docs/MONGODB_README.md`
  - `docs/LANGGRAPH_AGENT_ARCHITECTURE.md` (this file)
- **Retrieval**: top-5 chunks (`RAG_TOP_K=5`)

### Session management

In-memory `_session_histories: dict[str, list]` keyed by UUID `session_id`. Pass the
`session_id` from a previous `/v2/ask` response to continue a conversation across requests.

> **Note**: Histories are lost on server restart. For persistent sessions, replace with a
> LangGraph `MemorySaver` checkpointer backed by a database.

---

## Agent 2 — AQL Translation Agent (`aql_agent_service.py`)

### Graph topology

```
        ┌─────────┐
  ──▶   │ clarify │
        └────┬────┘
             │
   ambiguous?│  (skip if clarification already provided)
             │
        yes  ▼   no
          ┌─────┐       ┌───────────┐
          │ ask │──END  │ translate │ ◀──────────┐
          └─────┘       └─────┬─────┘            │
                              │                  │
                         ┌────▼────┐             │
                         │ execute │             │
                         └────┬────┘             │
                              │                  │
                    error & iterations < 3?      │
                              │                  │
                         yes  │  no              │
                              ▼   ▼              │
                           (retry)──────────────▶│
                                    END
```

This agent combines **Human-in-the-Loop** (the `clarify → ask` branch) with an
**error-correction retry loop** (the `translate → execute → translate` cycle).

### State schema

```python
class _State(TypedDict):
    question: str            # original natural language question
    clarification: str       # user's answer to a clarifying question (empty = none given)
    clarifying_question: str # question to ask user (empty = no clarification needed)
    aql: str                 # generated AQL string
    bind_vars: dict          # AQL bind variables (always {} — values are inlined)
    explanation: str         # one-sentence description of the query
    result: list             # up to 50 rows returned by ArangoDB
    error: str               # last AQL execution error (empty = success)
    iterations: int          # number of translate→execute cycles so far
```

### Nodes

#### `clarify`

Calls the LLM with a focused system prompt (`_CLARIFY_SYSTEM_PROMPT`) that lists known
ambiguities in the Kessler schema (e.g. "country" → `country_of_origin` vs. registration
nation). Returns:

```json
{"needs_clarification": false}
// or
{"needs_clarification": true, "clarifying_question": "Do you mean country of origin or launch registration country?"}
```

Skipped entirely if `state.clarification` is non-empty (user already answered).

#### `ask` (terminal)

A pass-through node (`lambda s: s`) that exists purely to give the conditional edge a
named target. When reached, the graph ends and returns the state with `clarifying_question`
populated and `aql` empty.

#### `translate`

Builds the prompt by:
1. Running `_annotate_question_with_countries()` — a deterministic pre-processing step
   that scans the question for country aliases ("AT", "AUT", "Austrian", …) and prepends
   a resolved annotation (`[Country resolution: "austrian" → exact DB value: "Austria"]`)
2. Appending the user's `clarification` answer if present
3. Appending the previous AQL and error message if this is a retry

Calls the LLM with the AQL-focused system prompt (`_system_prompt`), which includes:
- Full database schema (collections, fields, edge collections)
- Live enum values for `country_of_origin`, `status`, and `orbital_band` fetched from
  ArangoDB at startup
- AQL syntax rules (LIMIT before RETURN, no bind variables, no write operations)

The LLM responds with a JSON object:

```json
{
  "aql": "FOR s IN satellites FILTER s.canonical.country_of_origin == 'Austria' ...",
  "bind_vars": {},
  "explanation": "Returns up to 20 active satellites registered in Austria."
}
```

#### `execute`

- Checks for forbidden keywords (INSERT, UPDATE, REPLACE, REMOVE, UPSERT)
- Runs the AQL via `db_conn.db.aql.execute()` with a 15-second timeout
- Caps results at 50 rows
- On error, populates `state.error` so the conditional edge routes back to `translate`

### Conditional edges

| From | Condition | To |
|------|-----------|----|
| `clarify` | `state.clarifying_question` non-empty | `ask` |
| `clarify` | otherwise | `translate` |
| `execute` | `state.error` and `state.iterations < 3` | `translate` (retry) |
| `execute` | otherwise | `END` |

### Country disambiguation (`_COUNTRY_ALIASES`)

A module-level `dict[str, str]` maps ~120 lowercase tokens (ISO 2-letter codes, ISO
3-letter codes, adjective forms, common names) to the exact string stored in
`canonical.country_of_origin`. Examples:

```python
"at"       → "Austria"
"aut"      → "Austria"
"austrian" → "Austria"
"us"       → "United States of America"
"usa"      → "United States of America"
"american" → "United States of America"
"ru"       → "Russian Federation"
"russian"  → "Russian Federation"
```

`_annotate_question_with_countries()` checks unigrams and bigrams against this map and,
on a match, prepends a resolution note to the prompt before it reaches the LLM. This is
a **deterministic preprocessing step** — no LLM judgment is involved in country
disambiguation.

### Enum values fetched at startup

`_fetch_enum_values()` runs three `COLLECT` queries against ArangoDB at initialization
time to retrieve every distinct value of:

- `canonical.country_of_origin`
- `canonical.status`
- `canonical.orbital_band`

These are injected verbatim into the system prompt so the LLM always uses exact stored
strings, not guesses. Falls back to `_ENUM_VALUES_FALLBACK` if the database is
unreachable.

---

## Human-in-the-Loop Pattern

The AQL agent implements a **stateless human-in-the-loop** pattern — no server-side
session storage is required.

### Flow

```
Client                          Server (/v2/aql)
  │                                    │
  │  POST {question: "show AT sats"}   │
  │ ──────────────────────────────────▶│
  │                                    │  clarify node detects ambiguity
  │  {clarifying_question: "...?"}     │
  │ ◀──────────────────────────────────│
  │                                    │
  │  User types answer in UI           │
  │                                    │
  │  POST {question: "show AT sats",   │
  │         clarification: "origin"}   │
  │ ──────────────────────────────────▶│
  │                                    │  clarify node skipped (clarification present)
  │                                    │  translate → execute
  │  {aql: "FOR s IN ...", result: []} │
  │ ◀──────────────────────────────────│
```

The client stores the original question and re-sends it with the user's clarification
answer on the second request. No session ID or server-side state is needed.

### When LangGraph's `interrupt()` / `MemorySaver` would be better

The stateless approach works well for simple single-turn disambiguation. If you need:
- Multi-step wizards (multiple clarifying questions in sequence)
- Long-running workflows that pause for days
- Persistent conversation replay

…then migrate to LangGraph's native human-in-the-loop using `interrupt()` and a
`MemorySaver` (or `PostgresSaver`) checkpointer with `thread_id`-keyed state resumption.

---

## LangChain Patterns Used

| Pattern | Where used | LangChain construct |
|---------|-----------|---------------------|
| ReAct agent loop | `agent_service.py` | `StateGraph` + `ToolNode` + `bind_tools` |
| Tool definition | `agent_service.py` | `@tool` decorator (`langchain_core.tools`) |
| Prebuilt tool dispatch | `agent_service.py` | `langgraph.prebuilt.ToolNode` |
| Message accumulation | `agent_service.py` | `add_messages` reducer (`langgraph.graph.message`) |
| RAG retrieval | `index_service.py` + `agent_service.py` | `Chroma`, `RecursiveCharacterTextSplitter`, `OpenAIEmbeddings` |
| Structured LLM output (JSON mode) | `aql_agent_service.py` | System prompt + `_parse_llm_response()` |
| Custom `StateGraph` pipeline | `aql_agent_service.py` | `StateGraph` with typed `TypedDict` state |
| Conditional edges | Both agents | `add_conditional_edges` |
| Deterministic pre-processing | `aql_agent_service.py` | `_annotate_question_with_countries()` |
| Human-in-the-loop (stateless) | `aql_agent_service.py` | `clarify` node + client re-submission |

---

## API Response Shapes

### `POST /v2/ask`

```json
{
  "answer": "string",
  "sources": ["string"],
  "session_id": "uuid"
}
```

### `POST /v2/aql`

```json
{
  "aql": "FOR s IN satellites ...",
  "bind_vars": {},
  "result": [ ... ],
  "explanation": "Returns up to 20 active Austrian satellites.",
  "error": "",
  "clarifying_question": ""
}
```

When `clarifying_question` is non-empty, `aql` and `result` are empty strings/arrays.
Re-submit with `clarification` to proceed.

### `GET /v2/ask/status`

```json
{
  "agent_ready": true,
  "index_ready": true,
  "aql_agent_ready": true
}
```

---

## Configuration Reference

All values are read from environment variables (`.env` supported via `python-dotenv`):

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | **Required** for both agents |
| `AGENT_MODEL` | `gpt-4o-mini` | OpenAI model name for both agents |
| `AGENT_EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model for RAG index |
| `AGENT_VECTOR_STORE_PATH` | `.chroma` | ChromaDB persistence directory |
| `AGENT_RAG_CHUNK_SIZE` | `1000` | Token chunk size for text splitter |
| `AGENT_RAG_CHUNK_OVERLAP` | `200` | Overlap between chunks |
| `AGENT_RAG_TOP_K` | `5` | Number of RAG chunks retrieved per query |

---

## Extending the Agents

### Adding a tool to the General Assistant

1. Add a `@tool`-decorated function inside `_build_tools()` in `agent_service.py`
2. Append it to the returned list
3. Update the system prompt to describe when to use it
4. Restart the server

### Extending the AQL agent schema context

Edit `_SCHEMA_CONTEXT_BASE` in `aql_agent_service.py`. If you add a new collection,
document its fields and any edge relationships there.

### Adding a known country alias

Add an entry to `_COUNTRY_ALIASES` in `aql_agent_service.py`:

```python
"my_alias": "Exact Stored Country Name",
```

### Switching to a more powerful model

Set `AGENT_MODEL=gpt-4o` in `.env`. Both agents share this setting.

### Enabling persistent sessions (General Assistant)

Replace the in-memory `_session_histories` with a LangGraph `MemorySaver`:

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
graph = graph.compile(checkpointer=checkpointer)

# invoke with thread_id
graph.invoke({"messages": [HumanMessage(content=question)]},
             config={"configurable": {"thread_id": session_id}})
```

---

## Initialization Sequence

```
api/main.py lifespan (startup)
    │
    ├── connect_mongodb()          # ArangoDB connection
    │
    ├── index_service.build_index()
    │       └── load docs → chunk → embed → persist ChromaDB
    │
    ├── agent_service.initialize_agent()
    │       └── ChatOpenAI(model) + retriever → _build_tools() → _build_graph()
    │
    └── aql_agent_service.initialize_aql_agent()
            ├── ChatOpenAI(model)
            ├── _fetch_enum_values()   # 3 AQL COLLECT queries against live DB
            ├── _build_system_prompt() # injects live enum values
            └── _build_graph() (lazy — compiled on first request)
```
