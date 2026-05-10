import sys
import types
import unittest
from unittest.mock import MagicMock, patch


def _stub_langchain():
    """Install minimal stubs for langchain packages if not installed."""
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

import api.services.agent_service as svc  # noqa: E402 — must import after stubs


class TestIsReady(unittest.TestCase):

    def test_false_when_graph_is_none(self):
        original = svc._compiled_graph
        try:
            svc._compiled_graph = None
            self.assertFalse(svc.is_ready())
        finally:
            svc._compiled_graph = original

    def test_true_when_graph_is_set(self):
        original = svc._compiled_graph
        try:
            svc._compiled_graph = MagicMock()
            self.assertTrue(svc.is_ready())
        finally:
            svc._compiled_graph = original


class TestRunAgentNotReady(unittest.TestCase):

    def test_returns_unavailable_message(self):
        original = svc._compiled_graph
        try:
            svc._compiled_graph = None
            result = svc.run_agent("What is Talon?")
            self.assertIn("not available", result["answer"].lower())
            self.assertEqual(result["sources"], [])
            self.assertIsNotNone(result["session_id"])
        finally:
            svc._compiled_graph = original

    def test_generates_session_id_when_none_given(self):
        original = svc._compiled_graph
        try:
            svc._compiled_graph = None
            result = svc.run_agent("Hello?", session_id=None)
            self.assertIsNotNone(result["session_id"])
            self.assertNotEqual(result["session_id"], "")
        finally:
            svc._compiled_graph = original

    def test_returns_provided_session_id(self):
        original = svc._compiled_graph
        try:
            svc._compiled_graph = None
            result = svc.run_agent("Hello?", session_id="my-session")
            self.assertEqual(result["session_id"], "my-session")
        finally:
            svc._compiled_graph = original


class TestRunAgentWithGraph(unittest.TestCase):

    def setUp(self):
        from langchain_core.messages import AIMessage
        self._AIMessage = AIMessage

    def _make_ai_msg(self, content):
        return self._AIMessage(content=content)

    def test_answer_extracted_from_ai_message(self):
        original_graph = svc._compiled_graph
        original_history = svc._session_histories.copy()
        try:
            ai_msg = self._make_ai_msg("Talon tracks satellites.")
            mock_graph = MagicMock()
            mock_graph.invoke.return_value = {"messages": [ai_msg]}
            svc._compiled_graph = mock_graph
            svc._session_histories.clear()

            result = svc.run_agent("What does Talon do?")
            self.assertEqual(result["answer"], "Talon tracks satellites.")
            self.assertIsInstance(result["sources"], list)
        finally:
            svc._compiled_graph = original_graph
            svc._session_histories.clear()
            svc._session_histories.update(original_history)

    def test_session_stored_in_history(self):
        original_graph = svc._compiled_graph
        original_history = svc._session_histories.copy()
        try:
            ai_msg = self._make_ai_msg("It monitors orbital debris.")
            mock_graph = MagicMock()
            mock_graph.invoke.return_value = {"messages": [ai_msg]}
            svc._compiled_graph = mock_graph
            svc._session_histories.clear()

            svc.run_agent("Tell me about orbital debris.", session_id="sess-42")
            self.assertIn("sess-42", svc._session_histories)
        finally:
            svc._compiled_graph = original_graph
            svc._session_histories.clear()
            svc._session_histories.update(original_history)

    def test_invocation_error_returns_error_answer(self):
        original_graph = svc._compiled_graph
        try:
            mock_graph = MagicMock()
            mock_graph.invoke.side_effect = RuntimeError("LLM timeout")
            svc._compiled_graph = mock_graph

            result = svc.run_agent("What is the API?")
            self.assertIn("error", result["answer"].lower())
            self.assertEqual(result["sources"], [])
        finally:
            svc._compiled_graph = original_graph


class TestInitializeAgent(unittest.TestCase):

    def test_no_op_without_api_key(self):
        original = svc._compiled_graph
        try:
            svc._compiled_graph = None
            with patch("api.services.agent_service.config") as mock_cfg:
                mock_cfg.agent.OPENAI_API_KEY = ""
                svc.initialize_agent()
            self.assertIsNone(svc._compiled_graph)
        finally:
            svc._compiled_graph = original
