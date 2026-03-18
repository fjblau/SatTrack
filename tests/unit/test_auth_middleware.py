import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.auth import router as auth_router, _token_store
from api.middleware.auth import AuthMiddleware


def make_client():
    app = FastAPI()

    @app.get("/v2/satellites")
    def satellites():
        return {"data": []}

    app.add_middleware(AuthMiddleware)
    app.include_router(auth_router)
    return TestClient(app, raise_server_exceptions=False)


class TestAuthMiddleware(unittest.TestCase):

    def setUp(self):
        _token_store.clear()
        self.client = make_client()

    def tearDown(self):
        _token_store.clear()

    def test_unauthenticated_request_returns_401(self):
        response = self.client.get("/v2/satellites")
        self.assertEqual(response.status_code, 401)
        self.assertIn("detail", response.json())

    def test_authenticated_request_passes_through(self):
        token = "test-valid-token"
        _token_store.add(token)
        response = self.client.get(
            "/v2/satellites", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 200)

    def test_invalid_token_returns_401(self):
        response = self.client.get(
            "/v2/satellites", headers={"Authorization": "Bearer bogus-token"}
        )
        self.assertEqual(response.status_code, 401)

    def test_missing_bearer_prefix_returns_401(self):
        token = "test-valid-token"
        _token_store.add(token)
        response = self.client.get(
            "/v2/satellites", headers={"Authorization": token}
        )
        self.assertEqual(response.status_code, 401)

    def test_login_endpoint_bypassed(self):
        from unittest.mock import patch
        with patch("api.routers.auth.config") as mock_config:
            mock_config.auth.USERNAME = "admin"
            mock_config.auth.PASSWORD = "secret"
            response = self.client.post(
                "/v2/auth/login", json={"username": "admin", "password": "secret"}
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.json())
