import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.routers.auth import router, _token_store


def make_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestAuthRouter(unittest.TestCase):

    def setUp(self):
        _token_store.clear()
        self.client = make_client()

    def tearDown(self):
        _token_store.clear()

    def test_login_success(self):
        with patch("api.routers.auth.config") as mock_config:
            mock_config.auth.USERNAME = "admin"
            mock_config.auth.PASSWORD = "secret"
            response = self.client.post(
                "/v2/auth/login", json={"username": "admin", "password": "secret"}
            )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("token", data)
        self.assertIsInstance(data["token"], str)
        self.assertTrue(len(data["token"]) > 0)
        self.assertIn(data["token"], _token_store)

    def test_login_wrong_password(self):
        with patch("api.routers.auth.config") as mock_config:
            mock_config.auth.USERNAME = "admin"
            mock_config.auth.PASSWORD = "secret"
            response = self.client.post(
                "/v2/auth/login", json={"username": "admin", "password": "wrong"}
            )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid credentials")

    def test_login_wrong_username(self):
        with patch("api.routers.auth.config") as mock_config:
            mock_config.auth.USERNAME = "admin"
            mock_config.auth.PASSWORD = "secret"
            response = self.client.post(
                "/v2/auth/login", json={"username": "hacker", "password": "secret"}
            )
        self.assertEqual(response.status_code, 401)

    def test_logout_invalidates_token(self):
        with patch("api.routers.auth.config") as mock_config:
            mock_config.auth.USERNAME = "admin"
            mock_config.auth.PASSWORD = "secret"
            login_response = self.client.post(
                "/v2/auth/login", json={"username": "admin", "password": "secret"}
            )
        token = login_response.json()["token"]
        self.assertIn(token, _token_store)

        logout_response = self.client.post("/v2/auth/logout", json={"token": token})
        self.assertEqual(logout_response.status_code, 200)
        self.assertNotIn(token, _token_store)

    def test_logout_unknown_token_is_noop(self):
        response = self.client.post("/v2/auth/logout", json={"token": "nonexistent"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["detail"], "Logged out")
