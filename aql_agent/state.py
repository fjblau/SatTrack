from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

try:
    from langchain_core.messages import BaseMessage
except ImportError:
    BaseMessage = Any


class AgentState(BaseModel):
    question: str
    clarification: str = ""

    clarifying_question: str = ""

    messages: list[BaseMessage] = Field(default_factory=list)
    tool_call_count: int = 0
    iterations: int = 0

    aql: str = ""
    bind_vars: dict[str, Any] = Field(default_factory=dict)
    explanation: str = ""

    result: list[Any] = Field(default_factory=list)
    row_count: int = 0
    error: str = ""

    validator_errors: list[dict] = Field(default_factory=list)
    validator_warnings: list[dict] = Field(default_factory=list)

    log_id: str = ""
    trace: list[dict] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=datetime.utcnow)

    confidence: Literal["low", "medium", "high"] = "high"
    assumptions: list[str] = Field(default_factory=list)
    alternative: dict[str, Any] | None = None

    execution_retries: int = 0
    reflection_done: bool = False

    user_id: str | None = None

    class Config:
        arbitrary_types_allowed = True
