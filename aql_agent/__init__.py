from __future__ import annotations

from config import config


def _get_impl():
    if config.agent.VERSION == "v1":
        import aql_agent_v1 as _impl
    else:
        import aql_agent.agent as _impl
    return _impl


def run_aql_agent(question: str, clarification: str = "", user_id: str | None = None) -> dict:
    return _get_impl().run_aql_agent(question=question, clarification=clarification, user_id=user_id)


def initialize_aql_agent() -> None:
    _get_impl().initialize_aql_agent()


def is_ready() -> bool:
    return _get_impl().is_ready()


__all__ = ["run_aql_agent", "initialize_aql_agent", "is_ready"]
