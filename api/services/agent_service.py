import json
import logging
import uuid
from typing import Annotated, Any, Optional

from config import config

logger = logging.getLogger(__name__)


def _build_tools(retriever) -> list:
    from langchain_core.tools import tool

    @tool
    def search_knowledge_base(query: str) -> str:
        """Search the Talon codebase documentation and architecture guides.
        Use this to answer questions about the system design, API structure,
        data models, deployment, or any developer-facing documentation."""
        if retriever is None:
            return "Knowledge base is not available (index not built)."
        try:
            docs = retriever.invoke(query)
            if not docs:
                return "No relevant documentation found."
            parts = []
            for doc in docs:
                source = doc.metadata.get("source", "unknown")
                parts.append(f"[{source}]\n{doc.page_content}")
            return "\n\n---\n\n".join(parts)
        except Exception as exc:
            logger.error(f"RAG retrieval failed: {exc}")
            return f"Knowledge base lookup failed: {exc}"

    @tool
    def search_satellites(query: str, limit: int = 5) -> str:
        """Search the satellite registry by name, designator, or registration number.
        Returns basic metadata for matching satellites."""
        try:
            from database import search_satellites as _search
            results = _search(query=query, limit=limit)
            if not results:
                return "No satellites found matching that query."
            output = []
            for sat in results:
                c = sat.get("canonical", {})
                output.append({
                    "identifier": sat.get("identifier"),
                    "name": c.get("satellite_name") or c.get("object_name"),
                    "country": c.get("country_of_registration") or c.get("country"),
                    "status": c.get("status"),
                    "orbital_band": c.get("orbital_band"),
                    "launch_date": c.get("launch_date"),
                })
            return json.dumps(output, default=str)
        except Exception as exc:
            logger.error(f"Satellite search failed: {exc}")
            return f"Satellite search failed: {exc}"

    @tool
    def get_satellite_by_norad_id(norad_id: int) -> str:
        """Look up a satellite's full canonical data by its NORAD catalog ID (integer).
        Use this whenever the user provides a numeric NORAD ID (e.g. 25544, 58023).
        Returns the complete canonical fields for that satellite."""
        try:
            import database.connection as db_conn
            cursor = db_conn.db.aql.execute(
                """
                FOR s IN objects
                    FILTER s.canonical.norad_cat_id == @norad_id
                    LIMIT 1
                    RETURN s.canonical
                """,
                bind_vars={"norad_id": norad_id},
                max_runtime=10,
            )
            results = list(cursor)
            if not results:
                return f"No satellite found with NORAD ID {norad_id}."
            import json
            return json.dumps(results[0], default=str)
        except Exception as exc:
            logger.error(f"NORAD ID lookup failed: {exc}")
            return f"Lookup failed: {exc}"

    @tool
    def run_aql_query(aql: str) -> str:
        """Execute a read-only AQL query against the ArangoDB satellite graph database.
        Only SELECT-style queries (FOR … RETURN) are permitted — no INSERT/UPDATE/REMOVE.
        Use this to look up satellites, relationships, collision risks, or proximity data.

        Example:
          FOR s IN objects FILTER s.canonical.status == 'in orbit' LIMIT 5 RETURN s.identifier
        """
        forbidden = ["INSERT", "UPDATE", "REPLACE", "REMOVE", "UPSERT"]
        aql_upper = aql.upper()
        for kw in forbidden:
            if kw in aql_upper:
                return f"Write operations are not permitted. Found keyword: {kw}"
        try:
            import database.connection as db_conn
            cursor = db_conn.db.aql.execute(aql, max_runtime=10)
            rows = list(cursor)
            if not rows:
                return "Query returned no results."
            return json.dumps(rows[:50], default=str)
        except Exception as exc:
            logger.error(f"AQL query failed: {exc}")
            return f"AQL query failed: {exc}"

    return [search_knowledge_base, get_satellite_by_norad_id, search_satellites, run_aql_query]


def _build_graph(llm, tools):
    from langgraph.graph import StateGraph, END
    from langgraph.graph.message import add_messages
    from langgraph.prebuilt import ToolNode
    from langchain_core.messages import SystemMessage
    from typing import TypedDict

    class AgentState(TypedDict):
        messages: Annotated[list, add_messages]

    SYSTEM_PROMPT = (
        "You are a knowledgeable assistant for the Talon satellite tracking application. "
        "You help users understand the application, satellite data, orbital mechanics, and the API.\n\n"
        "You have access to four tools — use them in this order of preference:\n"
        "1. search_knowledge_base — ALWAYS try this first for any conceptual, architectural, "
        "or how-to question. It searches indexed documentation, API guides, and architecture docs.\n"
        "2. get_satellite_by_norad_id — use this IMMEDIATELY when the user provides a numeric "
        "NORAD ID (e.g. 'NORAD ID 58023', 'satellite 25544'). Returns the full canonical data.\n"
        "3. search_satellites — use this when the user asks about a satellite by name or designator.\n"
        "4. run_aql_query — use this ONLY when the user explicitly asks for a live database query "
        "or when other tools have no answer. If the query fails, explain what you know instead.\n\n"
        "For general questions about graph relationships, orbital bands, data structure, or "
        "application features, always use search_knowledge_base — do not run AQL queries for "
        "conceptual questions.\n\n"
        "If a tool returns an error, fall back to what you know from other tools or documentation. "
        "Never report a tool failure as your final answer — always provide the best answer you can."
    )

    llm_with_tools = llm.bind_tools(tools)
    tool_node = ToolNode(tools)

    def agent_node(state: AgentState) -> AgentState:
        messages = state["messages"]
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: AgentState) -> str:
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


_compiled_graph = None
_session_histories: dict[str, list] = {}


def initialize_agent() -> None:
    global _compiled_graph

    if not config.agent.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set — agent will be unavailable.")
        return

    try:
        from langchain_openai import ChatOpenAI
        from api.services.index_service import get_retriever

        llm = ChatOpenAI(
            model=config.agent.MODEL,
            api_key=config.agent.OPENAI_API_KEY,
            temperature=0,
        )
        retriever = get_retriever()
        tools = _build_tools(retriever)
        _compiled_graph = _build_graph(llm, tools)
        logger.info(f"LangGraph agent initialized with model '{config.agent.MODEL}'.")
    except Exception as exc:
        logger.error(f"Failed to initialize LangGraph agent: {exc}", exc_info=True)


def run_agent(question: str, session_id: Optional[str] = None) -> dict[str, Any]:
    if _compiled_graph is None:
        return {
            "answer": "The agent is not available. Check that OPENAI_API_KEY is set and the server started correctly.",
            "sources": [],
            "session_id": session_id or str(uuid.uuid4()),
        }

    from langchain_core.messages import HumanMessage, AIMessage

    sid = session_id or str(uuid.uuid4())
    history = _session_histories.get(sid, [])
    history.append(HumanMessage(content=question))

    try:
        result = _compiled_graph.invoke({"messages": history})
        updated_messages = result["messages"]
        _session_histories[sid] = updated_messages

        answer_msg = next(
            (m for m in reversed(updated_messages) if isinstance(m, AIMessage)),
            None,
        )
        answer = answer_msg.content if answer_msg else "No answer generated."

        sources = []
        for msg in updated_messages:
            if hasattr(msg, "content") and isinstance(msg.content, str):
                if msg.content.startswith("[") and "]\n" in msg.content:
                    for line in msg.content.split("---"):
                        src_line = line.strip().split("\n")[0]
                        if src_line.startswith("[") and src_line.endswith("]"):
                            src = src_line[1:-1]
                            if src not in sources:
                                sources.append(src)

        return {"answer": answer, "sources": sources, "session_id": sid}

    except Exception as exc:
        logger.error(f"Agent invocation failed: {exc}", exc_info=True)
        return {
            "answer": f"An error occurred while processing your question: {exc}",
            "sources": [],
            "session_id": sid,
        }


def is_ready() -> bool:
    return _compiled_graph is not None
