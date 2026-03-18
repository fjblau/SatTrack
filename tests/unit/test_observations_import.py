import unittest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.observations import router, ObservationInput, ThermalData


def make_client(mock_db=None):
    app = FastAPI()
    app.include_router(router)

    import api.routers.observations as obs_mod
    obs_mod_db = mock_db
    return TestClient(app, raise_server_exceptions=False), obs_mod


def _make_mock_db(allowed_norad_ids=None, existing_observations=None):
    if allowed_norad_ids is None:
        allowed_norad_ids = []
    if existing_observations is None:
        existing_observations = []

    mock_db = MagicMock()
    mock_db.has_collection.return_value = True

    mock_collection = MagicMock()
    mock_db.collection.return_value = mock_collection

    def aql_execute(query, bind_vars=None):
        mock_cursor = MagicMock()
        q = query.strip()
        if 'observations_enabled == true' in q and 'FILTER sat.canonical.norad_cat_id IN' in q:
            mock_cursor.__iter__ = lambda self: iter(allowed_norad_ids)
            list_mock = allowed_norad_ids[:]
            mock_cursor.__iter__ = lambda self: iter(list_mock)
        elif 'RETURN {norad_id: obs.norad_id' in q:
            mock_cursor.__iter__ = lambda self: iter(existing_observations)
        else:
            mock_cursor.__iter__ = lambda self: iter([])
        return mock_cursor

    mock_db.aql.execute.side_effect = aql_execute
    return mock_db, mock_collection


class TestObservationInputValidation(unittest.TestCase):

    def test_valid_minimal_observation(self):
        obs = ObservationInput(
            norad_id=12345,
            observation_epoch="2026-03-01T12:00:00Z",
            source="ground_station_A",
        )
        self.assertEqual(obs.norad_id, 12345)
        self.assertEqual(obs.source, "ground_station_A")

    def test_invalid_norad_id_zero(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            ObservationInput(
                norad_id=0,
                observation_epoch="2026-03-01T12:00:00Z",
                source="src",
            )

    def test_invalid_norad_id_negative(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            ObservationInput(
                norad_id=-1,
                observation_epoch="2026-03-01T12:00:00Z",
                source="src",
            )

    def test_invalid_observation_epoch_format(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            ObservationInput(
                norad_id=12345,
                observation_epoch="not-a-date",
                source="src",
            )

    def test_valid_observation_epoch_with_z(self):
        obs = ObservationInput(
            norad_id=12345,
            observation_epoch="2026-03-01T12:00:00Z",
            source="src",
        )
        self.assertEqual(obs.observation_epoch, "2026-03-01T12:00:00Z")

    def test_valid_observation_epoch_with_offset(self):
        obs = ObservationInput(
            norad_id=12345,
            observation_epoch="2026-03-01T12:00:00+05:30",
            source="src",
        )
        self.assertIsNotNone(obs.observation_epoch)

    def test_empty_source_rejected(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            ObservationInput(
                norad_id=12345,
                observation_epoch="2026-03-01T12:00:00Z",
                source="   ",
            )

    def test_source_trimmed(self):
        obs = ObservationInput(
            norad_id=12345,
            observation_epoch="2026-03-01T12:00:00Z",
            source="  my_source  ",
        )
        self.assertEqual(obs.source, "my_source")

    def test_negative_mass_rejected(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            ObservationInput(
                norad_id=12345,
                observation_epoch="2026-03-01T12:00:00Z",
                source="src",
                estimated_mass_kg=-5.0,
            )

    def test_negative_spin_rejected(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            ObservationInput(
                norad_id=12345,
                observation_epoch="2026-03-01T12:00:00Z",
                source="src",
                spin_rate_rpm=-1.0,
            )

    def test_health_score_out_of_range(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            ObservationInput(
                norad_id=12345,
                observation_epoch="2026-03-01T12:00:00Z",
                source="src",
                derived_health_score=101.0,
            )

    def test_health_score_valid_boundary(self):
        obs = ObservationInput(
            norad_id=12345,
            observation_epoch="2026-03-01T12:00:00Z",
            source="src",
            derived_health_score=0.0,
        )
        self.assertEqual(obs.derived_health_score, 0.0)

        obs2 = ObservationInput(
            norad_id=12345,
            observation_epoch="2026-03-01T12:00:00Z",
            source="src",
            derived_health_score=100.0,
        )
        self.assertEqual(obs2.derived_health_score, 100.0)


class TestImportObservationsEndpoint(unittest.TestCase):

    def _make_app_with_mock_db(self, allowed_norad_ids=None, existing_observations=None):
        app = FastAPI()
        app.include_router(router)
        mock_db, mock_collection = _make_mock_db(allowed_norad_ids, existing_observations)
        return TestClient(app, raise_server_exceptions=False), mock_db, mock_collection

    def test_import_success(self):
        with patch('api.routers.observations.db_module') as mock_module:
            mock_db, mock_col = _make_mock_db(allowed_norad_ids=[12345])
            mock_module.db = mock_db

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.post("/v2/observations/import", json={
                "observations": [
                    {
                        "norad_id": 12345,
                        "observation_epoch": "2026-03-01T12:00:00Z",
                        "source": "ground_station_A",
                    }
                ]
            })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["inserted"], 1)
        self.assertEqual(data["skipped_duplicates"], 0)
        self.assertEqual(data["skipped_not_allowed"], 0)
        self.assertEqual(data["total_submitted"], 1)
        self.assertEqual(data["errors"], [])

    def test_import_not_allowed(self):
        with patch('api.routers.observations.db_module') as mock_module:
            mock_db, mock_col = _make_mock_db(allowed_norad_ids=[])
            mock_module.db = mock_db

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.post("/v2/observations/import", json={
                "observations": [
                    {
                        "norad_id": 99999,
                        "observation_epoch": "2026-03-01T12:00:00Z",
                        "source": "ground_station_A",
                    }
                ]
            })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["inserted"], 0)
        self.assertEqual(data["skipped_not_allowed"], 1)
        self.assertEqual(len(data["errors"]), 1)
        self.assertIn("not in allowed tracking list", data["errors"][0]["error"])

    def test_import_duplicate_skipped(self):
        existing = [
            {"norad_id": 12345, "observation_epoch": "2026-03-01T12:00:00Z", "source": "ground_station_A"}
        ]
        with patch('api.routers.observations.db_module') as mock_module:
            mock_db, mock_col = _make_mock_db(allowed_norad_ids=[12345], existing_observations=existing)
            mock_module.db = mock_db

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.post("/v2/observations/import", json={
                "observations": [
                    {
                        "norad_id": 12345,
                        "observation_epoch": "2026-03-01T12:00:00Z",
                        "source": "ground_station_A",
                    }
                ]
            })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["inserted"], 0)
        self.assertEqual(data["skipped_duplicates"], 1)
        self.assertEqual(data["skipped_not_allowed"], 0)
        self.assertEqual(data["errors"], [])

    def test_import_mixed_batch(self):
        existing = [
            {"norad_id": 12345, "observation_epoch": "2026-03-01T12:00:00Z", "source": "src"}
        ]
        with patch('api.routers.observations.db_module') as mock_module:
            mock_db, mock_col = _make_mock_db(allowed_norad_ids=[12345, 22222], existing_observations=existing)
            mock_module.db = mock_db

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.post("/v2/observations/import", json={
                "observations": [
                    {
                        "norad_id": 12345,
                        "observation_epoch": "2026-03-01T12:00:00Z",
                        "source": "src",
                    },
                    {
                        "norad_id": 22222,
                        "observation_epoch": "2026-03-02T12:00:00Z",
                        "source": "src",
                    },
                    {
                        "norad_id": 33333,
                        "observation_epoch": "2026-03-03T12:00:00Z",
                        "source": "src",
                    },
                ]
            })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["inserted"], 1)
        self.assertEqual(data["skipped_duplicates"], 1)
        self.assertEqual(data["skipped_not_allowed"], 1)
        self.assertEqual(data["total_submitted"], 3)

    def test_import_empty_list_rejected(self):
        with patch('api.routers.observations.db_module') as mock_module:
            mock_db, _ = _make_mock_db()
            mock_module.db = mock_db

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.post("/v2/observations/import", json={"observations": []})

        self.assertEqual(response.status_code, 422)

    def test_import_missing_required_field(self):
        with patch('api.routers.observations.db_module') as mock_module:
            mock_db, _ = _make_mock_db()
            mock_module.db = mock_db

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.post("/v2/observations/import", json={
                "observations": [
                    {
                        "norad_id": 12345,
                        "source": "src",
                    }
                ]
            })

        self.assertEqual(response.status_code, 422)

    def test_import_database_unavailable(self):
        with patch('api.routers.observations.db_module') as mock_module:
            mock_module.db = None

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app, raise_server_exceptions=False)

            response = client.post("/v2/observations/import", json={
                "observations": [
                    {
                        "norad_id": 12345,
                        "observation_epoch": "2026-03-01T12:00:00Z",
                        "source": "src",
                    }
                ]
            })

        self.assertEqual(response.status_code, 503)

    def test_import_intra_batch_dedup(self):
        with patch('api.routers.observations.db_module') as mock_module:
            mock_db, mock_col = _make_mock_db(allowed_norad_ids=[12345])
            mock_module.db = mock_db

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.post("/v2/observations/import", json={
                "observations": [
                    {
                        "norad_id": 12345,
                        "observation_epoch": "2026-03-01T12:00:00Z",
                        "source": "src",
                    },
                    {
                        "norad_id": 12345,
                        "observation_epoch": "2026-03-01T12:00:00Z",
                        "source": "src",
                    },
                ]
            })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["inserted"], 1)
        self.assertEqual(data["skipped_duplicates"], 1)
        self.assertEqual(data["total_submitted"], 2)

    def test_import_with_optional_fields(self):
        with patch('api.routers.observations.db_module') as mock_module:
            mock_db, mock_col = _make_mock_db(allowed_norad_ids=[12345])
            mock_module.db = mock_db

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.post("/v2/observations/import", json={
                "observations": [
                    {
                        "norad_id": 12345,
                        "observation_epoch": "2026-03-01T12:00:00Z",
                        "source": "src",
                        "object_name": "ISS",
                        "object_type": "payload",
                        "origin_country": "US",
                        "derived_health_score": 85.5,
                        "estimated_mass_kg": 420000.0,
                        "spin_rate_rpm": 0.0,
                        "thermal": {"anomaly_flag": False},
                    }
                ]
            })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["inserted"], 1)


class TestAllowedObjectsEndpoint(unittest.TestCase):

    def test_get_allowed_objects(self):
        with patch('api.routers.observations.db_module') as mock_module:
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.__iter__ = lambda self: iter([
                {"norad_id": 25544, "name": "ISS"},
                {"norad_id": 43013, "name": "STARLINK-1"},
            ])
            mock_db.aql.execute.return_value = mock_cursor
            mock_module.db = mock_db

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.get("/v2/observations/allowed-objects")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["data"]), 2)

    def test_enable_observations_for_object(self):
        with patch('api.routers.observations.db_module') as mock_module:
            mock_db = MagicMock()

            call_count = 0

            def aql_side_effect(query, bind_vars=None):
                mock_cursor = MagicMock()
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    mock_cursor.__iter__ = lambda self: iter(["some_key"])
                else:
                    mock_cursor.__iter__ = lambda self: iter([])
                return mock_cursor

            mock_db.aql.execute.side_effect = aql_side_effect
            mock_module.db = mock_db

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.put("/v2/observations/allowed-objects/25544")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["norad_id"], 25544)
        self.assertTrue(data["observations_enabled"])

    def test_enable_observations_not_found(self):
        with patch('api.routers.observations.db_module') as mock_module:
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.__iter__ = lambda self: iter([])
            mock_db.aql.execute.return_value = mock_cursor
            mock_module.db = mock_db

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app, raise_server_exceptions=False)

            response = client.put("/v2/observations/allowed-objects/99999")

        self.assertEqual(response.status_code, 404)

    def test_disable_observations_for_object(self):
        with patch('api.routers.observations.db_module') as mock_module:
            mock_db = MagicMock()

            call_count = 0

            def aql_side_effect(query, bind_vars=None):
                mock_cursor = MagicMock()
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    mock_cursor.__iter__ = lambda self: iter(["some_key"])
                else:
                    mock_cursor.__iter__ = lambda self: iter([])
                return mock_cursor

            mock_db.aql.execute.side_effect = aql_side_effect
            mock_module.db = mock_db

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.delete("/v2/observations/allowed-objects/25544")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["norad_id"], 25544)
        self.assertFalse(data["observations_enabled"])


if __name__ == "__main__":
    unittest.main()
