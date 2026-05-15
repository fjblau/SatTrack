from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any

from config import config

logger = logging.getLogger(__name__)

_llm = None
_graph = None


def initialize_aql_agent() -> None:
    global _llm
    if not config.agent.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set — AQL agent v2 will be unavailable.")
        return
    try:
        from langchain_openai import ChatOpenAI
        from aql_agent.tools import TOOLS

        _llm = ChatOpenAI(
            model=config.agent.MODEL,
            api_key=config.agent.OPENAI_API_KEY,
            temperature=0,
        ).bind_tools(TOOLS)
        logger.info("AQL agent v2 initialized with model '%s'.", config.agent.MODEL)
    except Exception as exc:
        logger.error("Failed to initialize AQL agent v2: %s", exc, exc_info=True)


def is_ready() -> bool:
    return _llm is not None


def _get_graph():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


def _extract_submit_answer(message: Any) -> dict | None:
    if not hasattr(message, "tool_calls") or not message.tool_calls:
        return None
    for tc in message.tool_calls:
        name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "")
        args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {})
        if name == "submit_answer":
            return args
    return None


def _has_tool_calls(message: Any) -> bool:
    if not hasattr(message, "tool_calls"):
        return False
    return bool(message.tool_calls)


def _route_agent(state: dict) -> str:
    from langchain_core.messages import AIMessage

    messages = state.get("messages", [])
    if not messages:
        return "end_error"
    last = messages[-1]
    if not isinstance(last, AIMessage):
        return "end_error"

    if state.get("iterations", 0) >= config.agent.MAX_AGENT_ITERATIONS:
        return "end_error"

    submit = _extract_submit_answer(last)
    if submit is not None:
        return "validate"

    if _has_tool_calls(last):
        return "tools"

    return "end_error"


def _route_clarify(state: dict) -> str:
    if state.get("clarifying_question") and not state.get("clarification"):
        return "ask"
    return "agent"


def _route_validate(state: dict) -> str:
    if state.get("validator_errors"):
        if state.get("iterations", 0) >= config.agent.MAX_AGENT_ITERATIONS:
            return "execute"
        return "agent"
    return "execute"


def _route_execute(state: dict) -> str:
    if state.get("error") and state.get("execution_retries", 0) < config.agent.MAX_EXECUTION_RETRIES:
        return "agent"
    return "end"


def _load_heuristics_text() -> str:
    try:
        import yaml
        path = config.agent.HEURISTICS_PATH
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        parts: list[str] = []
        shorthands = data.get("shorthand", [])
        if shorthands:
            parts.append("### Shorthand Mappings")
            for item in shorthands:
                terms = ", ".join(f'"{t}"' for t in item.get("term", []))
                parts.append(f"- {terms} → {item.get('mapping', '')}")

        defaults = data.get("defaults", [])
        if defaults:
            parts.append("\n### Field Defaults")
            for item in defaults:
                phrases = ", ".join(f'"{p}"' for p in item.get("user_phrase", []))
                parts.append(f"- {phrases} → use `{item.get('use_field', item.get('use_expression', ''))}`")
                if item.get("notes"):
                    parts.append(f"  ({item['notes']})")

        never_dos = data.get("never_do", [])
        if never_dos:
            parts.append("\n### Never Do")
            for item in never_dos:
                parts.append(f"- {item}")

        return "\n".join(parts)
    except FileNotFoundError:
        logger.warning("Heuristics file not found at %s — agent will run without domain heuristics.", config.agent.HEURISTICS_PATH)
        return ""
    except Exception as exc:
        logger.warning("Failed to load heuristics file: %s — agent will run without domain heuristics.", exc)
        return ""


def _build_graph():
    from langgraph.graph import StateGraph, END
    from langgraph.prebuilt import ToolNode
    from langchain_core.messages import AIMessage, SystemMessage, HumanMessage

    from aql_agent.tools import TOOLS
    from aql_agent import validator as _validator
    from aql_agent import executor as _executor
    from aql_agent import formatter as _formatter
    from aql_agent import smartness as _smartness
    from aql_agent.prompts import CLARIFY_SYSTEM_PROMPT, _build_agent_system_prompt
    from aql_agent import logging_hooks

    heuristics_text = _load_heuristics_text()
    agent_prompt = _build_agent_system_prompt(heuristics_text)

    tool_node = ToolNode(TOOLS)

    def clarify_node(state: dict) -> dict:
        if state.get("clarification"):
            return {**state, "clarifying_question": ""}

        response = _llm.invoke([
            SystemMessage(content=CLARIFY_SYSTEM_PROMPT),
            HumanMessage(content=state["question"]),
        ])
        content = response.content
        content = content.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(lines[1:])
            if content.rstrip().endswith("```"):
                content = content.rstrip()[:-3]
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = {"needs_clarification": False}

        if parsed.get("needs_clarification"):
            return {**state, "clarifying_question": parsed.get("clarifying_question", "")}
        return {**state, "clarifying_question": ""}

    def agent_node(state: dict) -> dict:
        messages = state.get("messages", [])
        if not messages:
            question = state["question"]
            if state.get("clarification"):
                question = f"{question}\n\nUser clarification: {state['clarification']}"
            messages = [
                SystemMessage(content=agent_prompt),
                HumanMessage(content=question),
            ]

        iterations = state.get("iterations", 0) + 1
        response = _llm.invoke(messages)
        messages = messages + [response]

        tool_calls = []
        if hasattr(response, "tool_calls") and response.tool_calls:
            for tc in response.tool_calls:
                name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "")
                tool_calls.append({"name": name})

        trace = state.get("trace", [])
        if tool_calls:
            trace = trace + [{"step": iterations, "tool_calls": tool_calls}]

        return {
            **state,
            "messages": messages,
            "iterations": iterations,
            "trace": trace,
            "tool_call_count": state.get("tool_call_count", 0) + len(tool_calls),
        }

    def tools_node(state: dict) -> dict:
        messages = state.get("messages", [])
        result = tool_node.invoke({"messages": messages})
        new_msgs = result.get("messages", messages)

        trace = state.get("trace", [])
        return {
            **state,
            "messages": new_msgs,
            "trace": trace,
        }

    def validate_node(state: dict) -> dict:
        from langchain_core.messages import AIMessage as _AIMsg
        messages = state.get("messages", [])
        if not messages:
            return state

        last_ai = next((m for m in reversed(messages) if isinstance(m, _AIMsg)), None)
        if last_ai is None:
            return state

        submit_args = _extract_submit_answer(last_ai)
        if submit_args is None:
            return state

        raw_aql = submit_args.get("aql", "")
        bind_vars = submit_args.get("bind_vars", {}) or {}
        explanation = submit_args.get("explanation", "")
        confidence = submit_args.get("confidence", "high")
        assumptions = submit_args.get("assumptions") or []
        alternative_raw = submit_args.get("alternative")

        formatted_aql = _formatter.format_aql(raw_aql)

        try:
            import database.connection as db_conn
            db = db_conn.db
        except Exception:
            db = None

        val_result = _validator.validate(
            formatted_aql, bind_vars, db=db, original_question=state.get("question", "")
        )

        alternative = None
        if alternative_raw and isinstance(alternative_raw, dict):
            alt_aql = _formatter.format_aql(alternative_raw.get("aql", ""))
            val_alt = _validator.validate(alt_aql, alternative_raw.get("bind_vars", {}), db=db)
            alternative = {
                "aql": alt_aql,
                "bind_vars": alternative_raw.get("bind_vars", {}),
                "explanation": alternative_raw.get("explanation", ""),
                "valid": val_alt.ok,
            }

        updated = {
            **state,
            "aql": formatted_aql,
            "bind_vars": bind_vars,
            "explanation": explanation,
            "confidence": confidence,
            "assumptions": assumptions,
            "alternative": alternative,
            "validator_errors": val_result.errors,
            "validator_warnings": val_result.warnings,
        }

        if val_result.errors:
            error_summary = "; ".join(e["message"] for e in val_result.errors)
            fix_msg = HumanMessage(
                content=f"Validator found errors in your AQL — please fix them and submit again.\n\nErrors: {error_summary}\n\nYour AQL was:\n{formatted_aql}"
            )
            updated["messages"] = messages + [fix_msg]

        return updated

    def execute_node(state: dict) -> dict:
        aql = state.get("aql", "")
        bind_vars = state.get("bind_vars", {}) or {}

        exec_result = _executor.execute(aql, bind_vars)

        updated = {
            **state,
            "result": exec_result["result"],
            "row_count": exec_result["row_count"],
            "error": exec_result["error"],
        }

        if exec_result["error"]:
            retries = state.get("execution_retries", 0) + 1
            fix_msg = HumanMessage(
                content=f"ArangoDB returned an error executing your query. Please fix and resubmit.\n\nError: {exec_result['error']}\n\nYour AQL was:\n{aql}"
            )
            updated["execution_retries"] = retries
            updated["messages"] = state.get("messages", []) + [fix_msg]
            return updated

        if config.agent.RESULT_REFLECTION_ENABLED and not state.get("reflection_done", False):
            result_rows = exec_result["result"]
            trigger = _smartness.check_reflection_trigger(
                rows=result_rows,
                row_count=exec_result["row_count"],
                aql=aql,
            )
            if trigger:
                sample = result_rows[:3]
                limit_match = __import__("re").search(r"\bLIMIT\s+(\d+)", aql, __import__("re").IGNORECASE)
                effective_limit = int(limit_match.group(1)) if limit_match else 20
                reflection_msg = HumanMessage(
                    content=(
                        f"RESULT_REVIEW: trigger={trigger}, row_count={exec_result['row_count']}, "
                        f"effective_limit={effective_limit}, sample={json.dumps(sample, default=str)[:500]}.\n"
                        "Decide: (a) the result is genuinely correct — submit_confirmation with a 1-sentence explanation; "
                        "(b) the query needs revision — call tools as needed and submit_answer again."
                    )
                )
                updated["messages"] = state.get("messages", []) + [reflection_msg]
                updated["reflection_done"] = True
                updated["error"] = ""
                return updated

        if config.agent.EMPTY_RESULT_REPAIR_ENABLED and exec_result["row_count"] == 0 and not exec_result["error"]:
            repaired = _smartness.try_empty_result_repair(
                state=state,
                result_count=0,
            )
            if repaired is not None:
                updated.update(repaired)
                updated["reflection_done"] = True
                return updated

        _write_run_log(state=updated)
        return updated

    def _write_run_log(state: dict) -> None:
        try:
            messages = state.get("messages", [])
            tools_called = []
            for t in state.get("trace", []):
                for tc in t.get("tool_calls", []):
                    tools_called.append({"name": tc.get("name", ""), "ok": True})

            outcome = "success"
            if state.get("clarifying_question") and not state.get("clarification"):
                outcome = "clarification_requested"
            elif state.get("error"):
                outcome = "execution_failed"
            elif state.get("validator_errors"):
                outcome = "validator_failed"

            logging_hooks.write_log_line(
                log_id=state.get("log_id", ""),
                question=state.get("question", ""),
                clarification=state.get("clarification", ""),
                clarifying_question=state.get("clarifying_question", ""),
                tools_called=tools_called,
                iterations=state.get("iterations", 0),
                final_aql=state.get("aql", ""),
                raw_aql=state.get("aql", ""),
                final_bind_vars=state.get("bind_vars", {}),
                validator_result={
                    "errors": state.get("validator_errors", []),
                    "warnings": state.get("validator_warnings", []),
                },
                db_error=state.get("error") or None,
                row_count=state.get("row_count", 0),
                started_at=state.get("started_at", datetime.utcnow()),
                outcome=outcome,
                model=config.agent.MODEL,
                confidence=state.get("confidence", "high"),
                assumptions=state.get("assumptions", []),
                alternative=state.get("alternative"),
            )
        except Exception as exc:
            logger.warning("Failed to write run log: %s", exc)

    g = StateGraph(dict)
    g.add_node("clarify", clarify_node)
    g.add_node("ask", lambda s: s)
    g.add_node("agent", agent_node)
    g.add_node("tools", tools_node)
    g.add_node("validate", validate_node)
    g.add_node("execute", execute_node)

    g.set_entry_point("clarify")
    g.add_conditional_edges("clarify", _route_clarify, {"ask": "ask", "agent": "agent"})
    g.add_edge("ask", END)
    g.add_conditional_edges("agent", _route_agent, {"tools": "tools", "validate": "validate", "end_error": END})
    g.add_edge("tools", "agent")
    g.add_conditional_edges("validate", _route_validate, {"agent": "agent", "execute": "execute"})
    g.add_conditional_edges("execute", _route_execute, {"agent": "agent", "end": END})

    return g.compile()


def run_aql_agent(
    question: str,
    clarification: str = "",
    user_id: str | None = None,
) -> dict:
    if not is_ready():
        return {
            "aql": "",
            "bind_vars": {},
            "result": [],
            "explanation": "",
            "error": "AQL agent unavailable. Ensure OPENAI_API_KEY is set.",
            "clarifying_question": "",
            "log_id": "",
            "trace": [],
            "confidence": "high",
            "assumptions": [],
            "alternative": None,
        }

    log_id = str(uuid.uuid4())
    started_at = datetime.utcnow()

    initial: dict = {
        "question": question,
        "clarification": clarification,
        "clarifying_question": "",
        "messages": [],
        "tool_call_count": 0,
        "iterations": 0,
        "aql": "",
        "bind_vars": {},
        "explanation": "",
        "result": [],
        "row_count": 0,
        "error": "",
        "validator_errors": [],
        "validator_warnings": [],
        "log_id": log_id,
        "trace": [],
        "started_at": started_at,
        "confidence": "high",
        "assumptions": [],
        "alternative": None,
        "execution_retries": 0,
        "reflection_done": False,
        "user_id": user_id,
    }

    try:
        final = _get_graph().invoke(initial)
    except Exception as exc:
        logger.error("AQL agent graph error: %s", exc, exc_info=True)
        final = {**initial, "error": str(exc)}

    response = {
        "aql": final.get("aql", ""),
        "bind_vars": final.get("bind_vars", {}),
        "result": final.get("result", []),
        "explanation": final.get("explanation", ""),
        "error": final.get("error", ""),
        "clarifying_question": final.get("clarifying_question", ""),
        "log_id": log_id,
        "trace": [
            {"name": tc.get("name", ""), "ok": True}
            for t in final.get("trace", [])
            for tc in t.get("tool_calls", [])
        ],
        "confidence": final.get("confidence", "high"),
        "assumptions": final.get("assumptions", []),
        "alternative": final.get("alternative"),
    }

    if user_id and config.agent.HISTORY_ENABLED:
        _record_history_async(final, user_id)

    return response


def _record_history_async(final_state: dict, user_id: str) -> None:
    import threading
    from aql_agent import history

    def _write() -> None:
        try:
            history.record_history(final_state, user_id)
        except Exception as exc:
            logger.warning("History write failed: %s", exc)

    t = threading.Thread(target=_write, daemon=True)
    t.start()
