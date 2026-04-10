import unittest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.agent import router


def make_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestAskStatus(unittest.TestCase):

    def setUp(self):
        self.client = make_client()

    def test_status_when_not_ready(self):
        with (
            patch("api.routers.agent.agent_service.is_ready", return_value=False),
            patch("api.routers.agent.index_service.is_ready", return_value=False),
        ):
            resp = self.client.get("/v2/ask/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["agent_ready"])
        self.assertFalse(data["index_ready"])

    def test_status_when_ready(self):
        with (
            patch("api.routers.agent.agent_service.is_ready", return_value=True),
            patch("api.routers.agent.index_service.is_ready", return_value=True),
        ):
            resp = self.client.get("/v2/ask/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["agent_ready"])
        self.assertTrue(data["index_ready"])


class TestAskEndpoint(unittest.TestCase):

    def setUp(self):
        self.client = make_client()

    def test_ask_returns_503_when_agent_not_ready(self):
        with patch("api.routers.agent.agent_service.is_ready", return_value=False):
            resp = self.client.post("/v2/ask", json={"question": "What is this app?"})
        self.assertEqual(resp.status_code, 503)
        self.assertIn("not available", resp.json()["detail"])

    def test_ask_returns_answer(self):
        mock_result = {
            "answer": "Kessler is a satellite tracking application.",
            "sources": ["ARCHITECTURE.md"],
            "session_id": "test-session-123",
        }
        with (
            patch("api.routers.agent.agent_service.is_ready", return_value=True),
            patch("api.routers.agent.agent_service.run_agent", return_value=mock_result),
        ):
            resp = self.client.post("/v2/ask", json={"question": "What is Kessler?"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["answer"], "Kessler is a satellite tracking application.")
        self.assertEqual(data["sources"], ["ARCHITECTURE.md"])
        self.assertEqual(data["session_id"], "test-session-123")

    def test_ask_forwards_session_id(self):
        mock_result = {
            "answer": "Follow-up answer.",
            "sources": [],
            "session_id": "existing-session",
        }
        with (
            patch("api.routers.agent.agent_service.is_ready", return_value=True),
            patch("api.routers.agent.agent_service.run_agent", return_value=mock_result) as mock_run,
        ):
            resp = self.client.post(
                "/v2/ask",
                json={"question": "Tell me more", "session_id": "existing-session"},
            )
        self.assertEqual(resp.status_code, 200)
        mock_run.assert_called_once_with(
            question="Tell me more", session_id="existing-session"
        )

    def test_ask_missing_question_returns_422(self):
        with patch("api.routers.agent.agent_service.is_ready", return_value=True):
            resp = self.client.post("/v2/ask", json={})
        self.assertEqual(resp.status_code, 422)
