"""Tests for aql_agent.agent routing functions."""
from __future__ import annotations

import types
import sys
import unittest


def _stub_langchain():
    if "langchain_core" not in sys.modules:
        lc_core = types.ModuleType("langchain_core")
        lc_messages = types.ModuleType("langchain_core.messages")

        class HumanMessage:
            def __init__(self, content):
                self.content = content
                self.tool_calls = []

        class AIMessage:
            def __init__(self, content, tool_calls=None):
                self.content = content
                self.tool_calls = tool_calls or []

        class SystemMessage:
            def __init__(self, content):
                self.content = content
                self.tool_calls = []

        lc_messages.HumanMessage = HumanMessage
        lc_messages.AIMessage = AIMessage
        lc_messages.SystemMessage = SystemMessage
        lc_core.messages = lc_messages
        sys.modules["langchain_core"] = lc_core
        sys.modules["langchain_core.messages"] = lc_messages

    for mod in ["langgraph", "langgraph.graph", "langgraph.prebuilt", "langchain_openai"]:
        if mod not in sys.modules:
            sys.modules[mod] = types.ModuleType(mod)


_stub_langchain()

from aql_agent.agent import _route_agent, _route_clarify, _route_validate  # noqa: E402


AIMessage = sys.modules["langchain_core.messages"].AIMessage
HumanMessage = sys.modules["langchain_core.messages"].HumanMessage


class TestRouteAgent(unittest.TestCase):

    def test_empty_messages_returns_end_error(self):
        state = {"messages": [], "iterations": 0}
        self.assertEqual(_route_agent(state), "end_error")

    def test_non_ai_message_returns_end_error(self):
        state = {"messages": [HumanMessage("hello")], "iterations": 0}
        self.assertEqual(_route_agent(state), "end_error")

    def test_ai_message_with_submit_answer_tool_call_returns_validate(self):
        tc = {"name": "submit_answer", "args": {"aql": "FOR s IN objects RETURN s", "bind_vars": {}, "explanation": "all objects"}}
        msg = AIMessage("", tool_calls=[tc])
        state = {"messages": [msg], "iterations": 0}
        self.assertEqual(_route_agent(state), "validate")

    def test_ai_message_with_other_tool_call_returns_tools(self):
        tc = {"name": "list_collections", "args": {}}
        msg = AIMessage("", tool_calls=[tc])
        state = {"messages": [msg], "iterations": 0}
        self.assertEqual(_route_agent(state), "tools")

    def test_ai_message_no_tool_calls_returns_end_error(self):
        msg = AIMessage("some plain text response")
        state = {"messages": [msg], "iterations": 0}
        self.assertEqual(_route_agent(state), "end_error")

    def test_exceeds_max_iterations_returns_end_error(self):
        from unittest.mock import patch
        tc = {"name": "list_collections", "args": {}}
        msg = AIMessage("", tool_calls=[tc])
        state = {"messages": [msg], "iterations": 999}
        with patch("aql_agent.agent.config") as mock_cfg:
            mock_cfg.agent.MAX_AGENT_ITERATIONS = 5
            self.assertEqual(_route_agent(state), "end_error")


class TestRouteClarify(unittest.TestCase):

    def test_no_clarifying_question_goes_to_agent(self):
        state = {"clarifying_question": "", "clarification": ""}
        self.assertEqual(_route_clarify(state), "agent")

    def test_clarifying_question_without_clarification_goes_to_ask(self):
        state = {"clarifying_question": "Do you mean LEO or GEO?", "clarification": ""}
        self.assertEqual(_route_clarify(state), "ask")

    def test_clarifying_question_with_clarification_goes_to_agent(self):
        state = {"clarifying_question": "Do you mean LEO or GEO?", "clarification": "LEO"}
        self.assertEqual(_route_clarify(state), "agent")


class TestRouteValidate(unittest.TestCase):

    def test_no_errors_returns_execute(self):
        state = {"validator_errors": [], "iterations": 1}
        self.assertEqual(_route_validate(state), "execute")

    def test_errors_within_limit_returns_agent(self):
        from unittest.mock import patch
        state = {"validator_errors": [{"message": "bad field"}], "iterations": 1}
        with patch("aql_agent.agent.config") as mock_cfg:
            mock_cfg.agent.MAX_AGENT_ITERATIONS = 5
            self.assertEqual(_route_validate(state), "agent")

    def test_errors_at_limit_returns_execute(self):
        from unittest.mock import patch
        state = {"validator_errors": [{"message": "bad field"}], "iterations": 5}
        with patch("aql_agent.agent.config") as mock_cfg:
            mock_cfg.agent.MAX_AGENT_ITERATIONS = 5
            self.assertEqual(_route_validate(state), "execute")


if __name__ == "__main__":
    unittest.main()
