import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI, Request

from api.routers.observations import router as observations_router
from api.routers.auth import router as auth_router, _demo_token_store, _token_store

def make_app():
    app = FastAPI()
    app.include_router(observations_router)
    app.include_router(auth_router)
    return app

class TestObservationsAnalytics(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.client = TestClient(self.app)
        _demo_token_store.clear()
        _token_store.clear()

    @patch("database.db")
    def test_get_health_over_time(self, mock_db):
        mock_cursor = MagicMock()
        mock_cursor.__iter__.return_value = [
            {"date": "2023-01-01", "average_health_score": 85.0},
            {"date": "2023-01-02", "average_health_score": 86.0}
        ]
        mock_db.aql.execute.return_value = mock_cursor
        
        response = self.client.get("/v2/observations/analytics/health-over-time")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)
        self.assertEqual(response.json()[0]["date"], "2023-01-01")

    @patch("database.db")
    def test_get_anomaly_distribution(self, mock_db):
        mock_cursor = MagicMock()
        mock_cursor.__iter__.return_value = [
            {"label": "Anomaly", "value": 10},
            {"label": "Normal", "value": 90}
        ]
        mock_db.aql.execute.return_value = mock_cursor
        
        response = self.client.get("/v2/observations/analytics/anomaly-distribution")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)

    @patch("database.db")
    def test_get_source_distribution(self, mock_db):
        mock_cursor = MagicMock()
        mock_cursor.__iter__.return_value = [
            {"label": "Source A", "value": 50},
            {"label": "Source B", "value": 50}
        ]
        mock_db.aql.execute.return_value = mock_cursor
        
        response = self.client.get("/v2/observations/analytics/source-distribution")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)

    @patch("database.db")
    def test_execute_aql_admin_success(self, mock_db):
        # Login as admin
        with patch("api.routers.auth.config") as mock_config:
            mock_config.auth.valid_users.return_value = {"admin": "admin"}
            login_resp = self.client.post("/v2/auth/login", json={"username": "admin", "password": "admin"})
        
        token = login_resp.json()["token"]
        
        mock_cursor = MagicMock()
        mock_cursor.__iter__.return_value = [{"result": 1}]
        mock_db.aql.execute.return_value = mock_cursor
        
        response = self.client.post(
            "/v2/observations/aql", 
            json={"query": "RETURN 1"},
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], [{"result": 1}])

    @patch("database.db")
    def test_execute_aql_demo_forbidden(self, mock_db):
        # Login as demo
        login_resp = self.client.post("/v2/auth/login", json={"username": "demo", "password": "demo"})
        token = login_resp.json()["token"]
        
        response = self.client.post(
            "/v2/observations/aql", 
            json={"query": "RETURN 1"},
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "AQL execution is restricted to administrators")
