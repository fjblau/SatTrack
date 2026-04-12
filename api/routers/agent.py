from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Optional

from api.services import agent_service, aql_agent_service, index_service

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
    """Ask a question about the Kessler codebase, satellite data, or system architecture.

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
    }


class AQLRequest(BaseModel):
    question: str


class AQLResponse(BaseModel):
    aql: str
    bind_vars: dict[str, Any]
    result: list[Any]
    explanation: str
    error: str


@router.post("/aql", response_model=AQLResponse)
def aql_query(body: AQLRequest):
    """Translate a natural language question into an AQL query and execute it.

    Returns the generated AQL, bind variables, execution results, and a plain-English
    explanation of what the query does — so users can read and learn from the query.

    The agent automatically retries (up to 3 times) if ArangoDB returns a syntax error.
    """
    if not aql_agent_service.is_ready():
        raise HTTPException(
            status_code=503,
            detail="AQL agent is not available. Ensure OPENAI_API_KEY is set and the server restarted.",
        )
    result = aql_agent_service.run_aql_agent(question=body.question)
    return AQLResponse(**result)
