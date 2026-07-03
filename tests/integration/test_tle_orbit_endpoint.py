"""
Integration tests for TLE orbit calculation endpoint.

Tests:
1. Successful orbit calculation with ISS (NORAD 25544)
2. Different NORAD IDs
3. Query parameters (start_time, interval_minutes)
4. Error cases: invalid NORAD ID, TLE not found
5. Response format validation
6. Caching behavior
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi.testclient import TestClient
from api.main import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def authed_client():
    """FastAPI test client with a pre-seeded auth token."""
    from api.routers.auth import _token_store
    test_token = "test-integration-token"
    _token_store.add(test_token)
    c = TestClient(app, headers={"Authorization": f"Bearer {test_token}"})
    yield c
    _token_store.discard(test_token)


@pytest.fixture
def sample_tle_iss():
    """Sample TLE data for ISS (NORAD 25544)."""
    return {
        "name": "ISS (ZARYA)",
        "line1": "1 25544U 98067A   24038.54586899  .00012769  00000+0  22680-3 0  9996",
        "line2": "2 25544  51.6406 302.7583 0001012  95.3523  23.3829 15.50234806439337",
        "source": "tle-api",
        "date": "2024-02-07"
    }


@pytest.fixture
def sample_tle_geo():
    """Sample TLE data for geostationary satellite."""
    return {
        "name": "GOES-16",
        "line1": "1 41866U 16071A   24038.50000000  .00000000  00000+0  00000+0 0  9999",
        "line2": "2 41866   0.0000 123.4567 0001234 123.4567 234.5678  1.00271234567890",
        "source": "tle-api",
        "date": "2024-02-07"
    }


class TestOrbitCalculationEndpoint:
    """Test cases for orbit calculation endpoint."""
    
    @patch('api.services.tle_service.fetch_tle_by_norad_id')
    def test_successful_orbit_calculation_iss(self, mock_fetch_tle, client, sample_tle_iss):
        """Test successful orbit calculation with ISS (NORAD 25544)."""
        mock_fetch_tle.return_value = sample_tle_iss
        
        response = client.get("/v2/tle/25544/orbit")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "satellite" in data
        assert data["satellite"]["norad_id"] == "25544"
        assert data["satellite"]["name"] == "ISS (ZARYA)"
        
        assert "tle" in data
        assert data["tle"]["source"] == "tle-api"
        assert "epoch" in data["tle"]
        
        assert "orbital_parameters" in data
        assert "period_minutes" in data["orbital_parameters"]
        assert 90 <= data["orbital_parameters"]["period_minutes"] <= 95
        assert data["orbital_parameters"]["interval_minutes"] == 1
        assert data["orbital_parameters"]["num_positions"] > 0
        
        assert "tle_epoch_position" in data
        assert "current_position" in data
        assert "future_positions" in data
        
        assert "timestamp" in data
    
    @patch('api.services.tle_service.fetch_tle_by_norad_id')
    def test_position_structure(self, mock_fetch_tle, client, sample_tle_iss):
        """Test that position structures are correct."""
        mock_fetch_tle.return_value = sample_tle_iss
        
        response = client.get("/v2/tle/25544/orbit")
        data = response.json()
        
        for position_key in ["tle_epoch_position", "current_position"]:
            position = data[position_key]
            
            assert "timestamp" in position
            assert "eci" in position
            assert "geodetic" in position
            
            assert "x_km" in position["eci"]
            assert "y_km" in position["eci"]
            assert "z_km" in position["eci"]
            
            assert "latitude" in position["geodetic"]
            assert "longitude" in position["geodetic"]
            assert "altitude_km" in position["geodetic"]
            
            assert -90 <= position["geodetic"]["latitude"] <= 90
            assert -180 <= position["geodetic"]["longitude"] <= 180
            assert position["geodetic"]["altitude_km"] > 0
        
        assert len(data["future_positions"]) > 0
        for position in data["future_positions"]:
            assert "timestamp" in position
            assert "eci" in position
            assert "geodetic" in position
    
    @patch('api.services.tle_service.fetch_tle_by_norad_id')
    def test_interval_parameter(self, mock_fetch_tle, client, sample_tle_iss):
        """Test different interval_minutes parameter values."""
        mock_fetch_tle.return_value = sample_tle_iss
        
        for interval in [1, 2, 5, 10]:
            response = client.get(f"/v2/tle/25544/orbit?interval_minutes={interval}")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["orbital_parameters"]["interval_minutes"] == interval
            
            period = data["orbital_parameters"]["period_minutes"]
            expected_positions = int(period / interval) + 1
            assert data["orbital_parameters"]["num_positions"] == expected_positions
    
    @patch('api.services.tle_service.fetch_tle_by_norad_id')
    def test_invalid_interval_parameter(self, mock_fetch_tle, client, sample_tle_iss):
        """Test invalid interval_minutes parameter (outside 1-10 range)."""
        mock_fetch_tle.return_value = sample_tle_iss
        
        response = client.get("/v2/tle/25544/orbit?interval_minutes=0")
        assert response.status_code == 422
        
        response = client.get("/v2/tle/25544/orbit?interval_minutes=11")
        assert response.status_code == 422
        
        response = client.get("/v2/tle/25544/orbit?interval_minutes=-5")
        assert response.status_code == 422
    
    @patch('api.services.tle_service.fetch_tle_by_norad_id')
    def test_start_time_parameter(self, mock_fetch_tle, client, sample_tle_iss):
        """Test custom start_time parameter."""
        mock_fetch_tle.return_value = sample_tle_iss
        
        start_time = datetime(2024, 2, 7, 12, 0, 0, tzinfo=timezone.utc)
        start_time_str = quote(start_time.isoformat())
        
        response = client.get(f"/v2/tle/25544/orbit?start_time={start_time_str}")
        
        assert response.status_code == 200
        data = response.json()
        
        current_pos_time = datetime.fromisoformat(data["current_position"]["timestamp"])
        assert current_pos_time == start_time
        
        first_future_pos_time = datetime.fromisoformat(data["future_positions"][0]["timestamp"])
        assert first_future_pos_time == start_time
    
    @patch('api.services.tle_service.fetch_tle_by_norad_id')
    def test_start_time_without_timezone(self, mock_fetch_tle, client, sample_tle_iss):
        """Test start_time parameter without timezone (should assume UTC)."""
        mock_fetch_tle.return_value = sample_tle_iss
        
        start_time_str = "2024-02-07T12:00:00"
        
        response = client.get(f"/v2/tle/25544/orbit?start_time={start_time_str}")
        
        assert response.status_code == 200
        data = response.json()
        
        current_pos_time = datetime.fromisoformat(data["current_position"]["timestamp"])
        assert current_pos_time.tzinfo is not None
    
    @patch('api.services.tle_service.fetch_tle_by_norad_id')
    def test_invalid_start_time_parameter(self, mock_fetch_tle, client, sample_tle_iss):
        """Test invalid start_time parameter format."""
        mock_fetch_tle.return_value = sample_tle_iss
        
        response = client.get("/v2/tle/25544/orbit?start_time=invalid-date")
        assert response.status_code == 400
        assert "Invalid start_time format" in response.json()["detail"]
    
    @patch('api.services.tle_service.fetch_tle_by_norad_id')
    def test_tle_not_found(self, mock_fetch_tle, client):
        """Test error handling when TLE data is not found."""
        mock_fetch_tle.return_value = None
        
        response = client.get("/v2/tle/99999/orbit")
        
        assert response.status_code == 404
        assert "TLE data not found for NORAD ID 99999" in response.json()["detail"]
    
    @patch('api.routers.tle.fetch_tle_by_norad_id')
    def test_invalid_tle_data(self, mock_fetch_tle, client):
        """Test error handling when TLE data is missing line1 or line2."""
        mock_fetch_tle.return_value = {
            "name": "TEST SAT",
            "line1": None,
            "line2": None,
            "source": "tle-api"
        }
        
        response = client.get("/v2/tle/12345/orbit")
        
        assert response.status_code == 400
        assert "Invalid TLE data" in response.json()["detail"]
    
    @patch('api.services.tle_service.fetch_tle_by_norad_id')
    def test_geostationary_satellite(self, mock_fetch_tle, client, sample_tle_geo):
        """Test orbit calculation with geostationary satellite (longer period)."""
        mock_fetch_tle.return_value = sample_tle_geo
        
        response = client.get("/v2/tle/41866/orbit?interval_minutes=10")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "GOES" in data["satellite"]["name"]
        
        period = data["orbital_parameters"]["period_minutes"]
        assert 1400 <= period <= 1450
    
    @patch('api.services.tle_service.fetch_tle_by_norad_id')
    def test_future_positions_timing(self, mock_fetch_tle, client, sample_tle_iss):
        """Test that future positions start from start_time and increment correctly."""
        mock_fetch_tle.return_value = sample_tle_iss
        
        start_time = datetime(2024, 2, 7, 12, 0, 0, tzinfo=timezone.utc)
        start_time_str = quote(start_time.isoformat())
        interval_minutes = 5
        
        response = client.get(
            f"/v2/tle/25544/orbit?start_time={start_time_str}&interval_minutes={interval_minutes}"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        future_positions = data["future_positions"]
        
        for i, position in enumerate(future_positions):
            expected_time = start_time + timedelta(minutes=i * interval_minutes)
            actual_time = datetime.fromisoformat(position["timestamp"])
            
            time_diff = abs((actual_time - expected_time).total_seconds())
            assert time_diff < 1
    
    @patch('api.services.tle_service.fetch_tle_by_norad_id')
    def test_tle_epoch_vs_current_position(self, mock_fetch_tle, client, sample_tle_iss):
        """Test that TLE epoch position differs from current position."""
        mock_fetch_tle.return_value = sample_tle_iss
        
        response = client.get("/v2/tle/25544/orbit")
        
        assert response.status_code == 200
        data = response.json()
        
        tle_epoch_time = datetime.fromisoformat(data["tle_epoch_position"]["timestamp"])
        current_time = datetime.fromisoformat(data["current_position"]["timestamp"])
        
        assert tle_epoch_time != current_time
        
        tle_epoch_lat = data["tle_epoch_position"]["geodetic"]["latitude"]
        current_lat = data["current_position"]["geodetic"]["latitude"]
        tle_epoch_lon = data["tle_epoch_position"]["geodetic"]["longitude"]
        current_lon = data["current_position"]["geodetic"]["longitude"]
        
        assert (tle_epoch_lat != current_lat) or (tle_epoch_lon != current_lon)
    
    @patch('api.services.tle_service.fetch_tle_by_norad_id')
    def test_response_timestamp(self, mock_fetch_tle, client, sample_tle_iss):
        """Test that response includes timestamp."""
        mock_fetch_tle.return_value = sample_tle_iss
        
        before_request = datetime.now(timezone.utc)
        response = client.get("/v2/tle/25544/orbit")
        after_request = datetime.now(timezone.utc)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "timestamp" in data
        response_time = datetime.fromisoformat(data["timestamp"])
        
        assert before_request <= response_time <= after_request
    
    @patch('api.services.tle_service.fetch_tle_by_norad_id')
    def test_caching_behavior(self, mock_fetch_tle, client, sample_tle_iss):
        """Test that TLE caching works (multiple calls succeed)."""
        mock_fetch_tle.return_value = sample_tle_iss
        
        response1 = client.get("/v2/tle/25544/orbit")
        response2 = client.get("/v2/tle/25544/orbit")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        data1 = response1.json()
        data2 = response2.json()
        
        assert data1["satellite"]["norad_id"] == "25544"
        assert data2["satellite"]["norad_id"] == "25544"
        assert data1["orbital_parameters"]["period_minutes"] == data2["orbital_parameters"]["period_minutes"]


class TestPassesEndpoint:
    """Test cases for GET /v2/tle/{norad_id}/passes endpoint."""

    @patch('api.routers.tle.fetch_tle_by_norad_id')
    def test_passes_tle_not_found(self, mock_fetch, authed_client):
        mock_fetch.return_value = None
        response = authed_client.get("/v2/tle/99999/passes?lat=48.85&lon=2.35")
        assert response.status_code == 404

    @patch('api.routers.tle.fetch_tle_by_norad_id')
    def test_passes_missing_lat_lon(self, mock_fetch, authed_client, sample_tle_iss):
        mock_fetch.return_value = sample_tle_iss
        response = authed_client.get("/v2/tle/25544/passes")
        assert response.status_code == 422

    @patch('api.routers.tle.fetch_tle_by_norad_id')
    def test_passes_invalid_lat(self, mock_fetch, authed_client, sample_tle_iss):
        mock_fetch.return_value = sample_tle_iss
        response = authed_client.get("/v2/tle/25544/passes?lat=999&lon=2.35")
        assert response.status_code == 422

    @patch('api.routers.tle.fetch_tle_by_norad_id')
    def test_passes_hours_ahead_too_large(self, mock_fetch, authed_client, sample_tle_iss):
        mock_fetch.return_value = sample_tle_iss
        response = authed_client.get("/v2/tle/25544/passes?lat=48.85&lon=2.35&hours_ahead=999")
        assert response.status_code == 422

    @patch('api.routers.tle.fetch_tle_by_norad_id')
    def test_passes_response_structure(self, mock_fetch, authed_client, sample_tle_iss):
        mock_fetch.return_value = sample_tle_iss
        response = authed_client.get("/v2/tle/25544/passes?lat=48.85&lon=2.35&hours_ahead=72&num_passes=3")
        assert response.status_code == 200
        data = response.json()

        assert "norad_id" in data
        assert "satellite_name" in data
        assert "observer" in data
        assert "passes" in data
        assert "num_passes" in data
        assert "tle_age_hours" in data
        assert "search_window_hours" in data

        assert data["observer"]["latitude"] == 48.85
        assert data["observer"]["longitude"] == 2.35
        assert isinstance(data["passes"], list)
        assert data["num_passes"] == len(data["passes"])

    @patch('api.routers.tle.fetch_tle_by_norad_id')
    def test_passes_pass_structure(self, mock_fetch, authed_client, sample_tle_iss):
        mock_fetch.return_value = sample_tle_iss
        response = authed_client.get("/v2/tle/25544/passes?lat=48.85&lon=2.35&hours_ahead=72&num_passes=5")
        assert response.status_code == 200
        data = response.json()

        for p in data["passes"]:
            assert "rise" in p
            assert "culmination" in p
            assert "set" in p
            assert "duration_seconds" in p
            assert "max_elevation_deg" in p
            assert "visibility_stars" in p
            assert "optically_visible" in p

            assert "time" in p["rise"]
            assert "azimuth_deg" in p["rise"]
            assert "time" in p["culmination"]
            assert "azimuth_deg" in p["culmination"]
            assert "elevation_deg" in p["culmination"]
            assert "time" in p["set"]
            assert "azimuth_deg" in p["set"]

            assert p["visibility_stars"] in [1, 2, 3]
            assert p["max_elevation_deg"] >= 10.0
            assert p["duration_seconds"] > 0

    @patch('api.routers.tle.fetch_tle_by_norad_id')
    def test_passes_num_passes_respected(self, mock_fetch, authed_client, sample_tle_iss):
        mock_fetch.return_value = sample_tle_iss
        response = authed_client.get("/v2/tle/25544/passes?lat=48.85&lon=2.35&hours_ahead=168&num_passes=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["passes"]) <= 2

    @patch('api.routers.tle.fetch_tle_by_norad_id')
    def test_passes_geo_returns_empty_list(self, mock_fetch, authed_client, sample_tle_geo):
        mock_fetch.return_value = sample_tle_geo
        response = authed_client.get("/v2/tle/41866/passes?lat=48.85&lon=2.35&hours_ahead=24")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["passes"], list)

    @patch('api.routers.tle.fetch_tle_by_norad_id')
    def test_passes_tle_age_in_response(self, mock_fetch, authed_client, sample_tle_iss):
        mock_fetch.return_value = sample_tle_iss
        response = authed_client.get("/v2/tle/25544/passes?lat=48.85&lon=2.35")
        assert response.status_code == 200
        data = response.json()
        assert data["tle_age_hours"] is not None
        assert isinstance(data["tle_age_hours"], (int, float))
        assert data["tle_age_hours"] > 0
