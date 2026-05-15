from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Any, Optional

from api.services import agent_service, aql_agent_service, index_service, kestrel_agent_service
from api.middleware.auth import get_current_user

router = APIRouter(prefix="/v2", tags=["agent"])


class AskRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


class AskResponse(BaseModel):
    answer: str
    sources: list[str]
    session_id: str


@router.post("/ask", response_model=AskResponse)
def ask(body: AskRequest):
    """Ask a question about the Talon codebase, satellite data, or system architecture.

    The agent uses RAG over project documentation and has access to live satellite
    search and read-only AQL queries against the graph database.

    Pass `session_id` from a previous response to continue a multi-turn conversation.
    """
    if not agent_service.is_ready():
        raise HTTPException(
            status_code=503,
            detail="Agent is not available. Ensure OPENAI_API_KEY is set and the server restarted.",
        )

    result = agent_service.run_agent(
        question=body.question,
        session_id=body.session_id,
    )
    return AskResponse(
        answer=result["answer"],
        sources=result["sources"],
        session_id=result["session_id"],
    )


@router.get("/ask/status")
def ask_status():
    """Check whether the LangGraph agent and RAG index are ready."""
    return {
        "agent_ready": agent_service.is_ready(),
        "index_ready": index_service.is_ready(),
        "aql_agent_ready": aql_agent_service.is_ready(),
        "kestrel_advisor_ready": kestrel_agent_service.is_ready(),
    }


class AQLRequest(BaseModel):
    question: str
    clarification: Optional[str] = None


class AQLResponse(BaseModel):
    aql: str
    bind_vars: dict[str, Any]
    result: list[Any]
    explanation: str
    error: str
    clarifying_question: str
    log_id: str = ""
    trace: list[Any] = []
    confidence: str = "high"
    assumptions: list[str] = []
    alternative: Optional[dict[str, Any]] = None


@router.post("/aql", response_model=AQLResponse)
async def aql_query(body: AQLRequest, request: Request):
    """Translate a natural language question into an AQL query and execute it.

    If the question is ambiguous, the response will contain a `clarifying_question`
    and empty `aql`/`result` fields. Re-submit with `clarification` set to the user's
    answer to proceed with query generation.

    The agent automatically retries if ArangoDB returns a syntax error.
    """
    if not aql_agent_service.is_ready():
        raise HTTPException(
            status_code=503,
            detail="AQL agent is not available. Ensure OPENAI_API_KEY is set and the server restarted.",
        )

    from api.middleware.auth import get_current_user as _get_user
    user_id = await _get_user(request)

    result = aql_agent_service.run_aql_agent(
        question=body.question,
        clarification=body.clarification or "",
        user_id=user_id,
    )
    return AQLResponse(**result)


class HistoryItem(BaseModel):
    key: str
    ts: str
    question: str
    aql: str
    row_count: int
    outcome: str
    confidence: str
    starred: bool


class HistoryResponse(BaseModel):
    items: list[HistoryItem]


@router.get("/aql/history", response_model=HistoryResponse)
async def get_aql_history(
    request: Request,
    limit: int = 20,
    starred_only: bool = False,
):
    """Return query history for the authenticated user."""
    from api.middleware.auth import get_current_user as _get_user
    user_id = await _get_user(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    from aql_agent import history as _history
    items = _history.get_history(user_id=user_id, limit=min(limit, 100), starred_only=starred_only)
    return HistoryResponse(items=[HistoryItem(**item) for item in items])


@router.post("/aql/history/{key}/star", response_model=HistoryItem)
async def star_history_item(key: str, request: Request):
    """Star a history item."""
    from api.middleware.auth import get_current_user as _get_user
    user_id = await _get_user(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    from aql_agent import history as _history
    updated = _history.toggle_star(key=key, user_id=user_id, starred=True)
    if updated is None:
        raise HTTPException(status_code=404, detail="Item not found or access denied")
    return HistoryItem(**updated)


@router.delete("/aql/history/{key}/star", response_model=HistoryItem)
async def unstar_history_item(key: str, request: Request):
    """Unstar a history item."""
    from api.middleware.auth import get_current_user as _get_user
    user_id = await _get_user(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    from aql_agent import history as _history
    updated = _history.toggle_star(key=key, user_id=user_id, starred=False)
    if updated is None:
        raise HTTPException(status_code=404, detail="Item not found or access denied")
    return HistoryItem(**updated)


class KestrelMissionRequest(BaseModel):
    mission_context: dict[str, Any]
    clarification: Optional[str] = None


class KestrelMissionResponse(BaseModel):
    recommended_scenario_id: str
    reasoning: str
    trade_off_summary: str
    caveats: str
    confidence: str
    error: str
    clarifying_question: str


@router.post("/kestrel-mission", response_model=KestrelMissionResponse)
def kestrel_mission_advisor(body: KestrelMissionRequest):
    """AI mission advisor for Kestrel rendezvous scenario selection.

    Receives pre-computed orbital mechanics scenarios and recommends the best one
    based on mission type, orbital geometry, and operator constraints.

    If a clarifying question is returned, re-submit with `clarification` set to
    the operator's answer to proceed with the recommendation.
    """
    if not kestrel_agent_service.is_ready():
        raise HTTPException(
            status_code=503,
            detail="Kestrel mission advisor is not available. Ensure OPENAI_API_KEY is set.",
        )
    result = kestrel_agent_service.run_kestrel_advisor(
        mission_context=body.mission_context,
        clarification=body.clarification or "",
    )
    return KestrelMissionResponse(**result)
