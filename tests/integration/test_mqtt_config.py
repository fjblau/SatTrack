"""
Unit tests for MQTT configuration and publishing functionality.

Tests:
1. MQTT configuration persistence (create, read, update)
2. MQTT message publishing with immediate send on configuration
3. Validation of required fields
4. TLE data retrieval and formatting for MQTT
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timezone, timedelta
import json
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi.testclient import TestClient
from api.main import app
from api.routers.mqtt import MqttConfiguration, MqttBrokerConfig


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def sample_mqtt_config():
    """Sample MQTT configuration."""
    return {
        "satellite_id": "satellites/2017-036V",
        "norad_id": "42792",
        "mqtt_broker": {
            "host": "broker.hivemq.com",
            "port": 1883,
            "username": "testuser",
            "password": "testpass"
        },
        "topic": "satellites/tle/2017-036V",
        "frequency_hours": 24,
        "enabled": True
    }


@pytest.fixture
def sample_satellite_data():
    """Sample satellite document from database."""
    return {
        "_id": "satellites/2017-036V",
        "_key": "2017-036V",
        "canonical": {
            "international_designator": "2017-036V",
            "norad_cat_id": 42792,
            "name": "LEMUR-2-AUSTINTACIOUS",
            "orbit": {
                "apogee_km": 503.0,
                "perigee_km": 489.0,
                "inclination_deg": 97.4
            }
        }
    }


@pytest.fixture
def sample_tle_data():
    """Sample TLE data."""
    return {
        "name": "LEMUR-2-AUSTINTACIOUS",
        "line1": "1 42792U 17036V   24001.00000000  .00001234  00000-0  12345-3 0  9999",
        "line2": "2 42792  97.4000 123.4567 0012345 123.4567 234.5678 15.12345678123456",
        "source": "CelesTrak"
    }


class TestMqttConfigurationPersistence:
    """Test MQTT configuration persistence in database."""
    
    @patch('database.mqtt_config.save_mqtt_configuration')
    @patch('mqtt_scheduler.schedule_mqtt_publish')
    @patch('database.operations.find_satellite')
    @patch('api.services.tle_service.fetch_tle_data')
    def test_create_mqtt_config(self, mock_fetch_tle, mock_find_sat, 
                                mock_schedule, mock_save, client, 
                                sample_mqtt_config, sample_satellite_data, sample_tle_data):
        """Test creating a new MQTT configuration persists correctly."""
        saved_config = {
            **sample_mqtt_config,
            "_key": "mqtt_config_1",
            "_id": "mqtt_configurations/mqtt_config_1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "last_published": None,
            "next_publish": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        }
        
        mock_save.return_value = saved_config
        mock_find_sat.return_value = sample_satellite_data
        mock_fetch_tle.return_value = {"2017-036V": (
            sample_tle_data["name"],
            sample_tle_data["line1"],
            sample_tle_data["line2"]
        )}
        
        response = client.post("/v2/mqtt/config", json=sample_mqtt_config)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["satellite_id"] == sample_mqtt_config["satellite_id"]
        assert data["norad_id"] == sample_mqtt_config["norad_id"]
        assert data["mqtt_broker"]["host"] == sample_mqtt_config["mqtt_broker"]["host"]
        assert data["topic"] == sample_mqtt_config["topic"]
        assert data["frequency_hours"] == 24
        assert data["enabled"] is True
        
        mock_save.assert_called_once()
        mock_schedule.assert_called_once()
    
    @patch('database.mqtt_config.get_mqtt_configuration')
    def test_retrieve_mqtt_config(self, mock_get, client, sample_mqtt_config):
        """Test retrieving existing MQTT configuration."""
        saved_config = {
            **sample_mqtt_config,
            "_key": "mqtt_config_1",
            "_id": "mqtt_configurations/mqtt_config_1",
        }
        mock_get.return_value = saved_config
        
        response = client.get("/v2/mqtt/config/satellites/2017-036V")
        
        assert response.status_code == 200
        data = response.json()
        assert data["satellite_id"] == "satellites/2017-036V"
        assert data["mqtt_broker"]["password"] == "[REDACTED]"
    
    @patch('database.mqtt_config.save_mqtt_configuration')
    @patch('mqtt_scheduler.schedule_mqtt_publish')
    @patch('database.operations.find_satellite')
    @patch('api.services.tle_service.fetch_tle_data')
    def test_update_mqtt_config(self, mock_fetch_tle, mock_find_sat,
                                mock_schedule, mock_save, client, sample_mqtt_config):
        """Test updating existing MQTT configuration persists changes."""
        updated_config = sample_mqtt_config.copy()
        updated_config["frequency_hours"] = 8
        updated_config["enabled"] = False
        
        mock_save.return_value = {
            **updated_config,
            "_key": "mqtt_config_1",
            "_id": "mqtt_configurations/mqtt_config_1",
        }
        mock_find_sat.return_value = None
        
        response = client.post("/v2/mqtt/config", json=updated_config)
        
        assert response.status_code == 200
        data = response.json()
        assert data["frequency_hours"] == 8
        assert data["enabled"] is False


class TestMqttConfigurationValidation:
    """Test validation of required MQTT configuration fields."""
    
    def test_missing_broker_host(self, client, sample_mqtt_config):
        """Test that missing broker host is rejected."""
        invalid_config = sample_mqtt_config.copy()
        invalid_config["mqtt_broker"]["host"] = ""
        
        response = client.post("/v2/mqtt/config", json=invalid_config)
        assert response.status_code == 422
    
    def test_missing_topic(self, client, sample_mqtt_config):
        """Test that missing topic is rejected."""
        invalid_config = sample_mqtt_config.copy()
        invalid_config["topic"] = ""
        
        response = client.post("/v2/mqtt/config", json=invalid_config)
        assert response.status_code == 422
    
    def test_missing_satellite_id(self, client, sample_mqtt_config):
        """Test that missing satellite_id is rejected."""
        invalid_config = sample_mqtt_config.copy()
        invalid_config["satellite_id"] = ""
        
        response = client.post("/v2/mqtt/config", json=invalid_config)
        assert response.status_code == 422
    
    def test_invalid_frequency(self, client, sample_mqtt_config):
        """Test that invalid frequency values are rejected."""
        invalid_config = sample_mqtt_config.copy()
        invalid_config["frequency_hours"] = 12
        
        response = client.post("/v2/mqtt/config", json=invalid_config)
        assert response.status_code == 400
        assert "8 or 24" in response.json()["detail"]


class TestMqttPublishing:
    """Test MQTT message publishing functionality."""
    
    @patch('time.sleep')
    @patch('mqtt_publisher.mqtt.Client')
    def test_mqtt_connection_and_publish(self, mock_mqtt_client, mock_sleep, sample_mqtt_config, 
                                         sample_tle_data, sample_satellite_data):
        """Test that MQTT messages are published to broker."""
        from mqtt_publisher import publish_tle_to_mqtt
        
        mock_client_instance = MagicMock()
        mock_mqtt_client.return_value = mock_client_instance
        
        mock_result = MagicMock()
        mock_result.rc = 0
        mock_client_instance.publish.return_value = mock_result
        
        connection_triggered = {'done': False}
        
        def trigger_on_connect(*args, **kwargs):
            if not connection_triggered['done']:
                connection_triggered['done'] = True
                if hasattr(mock_client_instance, 'on_connect'):
                    mock_client_instance.on_connect(mock_client_instance, None, None, 0)
        
        mock_client_instance.connect.side_effect = trigger_on_connect
        mock_client_instance.loop_start.side_effect = trigger_on_connect
        
        success, error = publish_tle_to_mqtt(
            sample_mqtt_config,
            sample_tle_data,
            sample_satellite_data
        )
        
        assert success is True
        assert error is None
        
        mock_client_instance.username_pw_set.assert_called_once_with(
            "testuser", "testpass"
        )
        
        mock_client_instance.connect.assert_called_once_with(
            "broker.hivemq.com", 1883, keepalive=60
        )
        
        mock_client_instance.publish.assert_called_once()
        call_args = mock_client_instance.publish.call_args
        assert call_args[0][0] == "satellites/tle/2017-036V"
        
        payload = json.loads(call_args[0][1])
        assert payload["satellite"]["name"] == sample_tle_data["name"]
        assert payload["satellite"]["international_designator"] == "2017-036V"
        assert "tle" in payload
        assert payload["tle"]["line1"] == sample_tle_data["line1"]
        assert payload["tle"]["line2"] == sample_tle_data["line2"]
    
    @patch('time.sleep')
    @patch('mqtt_publisher.mqtt.Client')
    def test_mqtt_publish_connection_failure(self, mock_mqtt_client, mock_sleep,
                                             sample_mqtt_config, sample_tle_data,
                                             sample_satellite_data):
        """Test handling of MQTT connection failures."""
        from mqtt_publisher import publish_tle_to_mqtt
        
        mock_client_instance = MagicMock()
        mock_mqtt_client.return_value = mock_client_instance
        
        connection_triggered = {'done': False}
        
        def on_connect_fail(*args, **kwargs):
            if not connection_triggered['done']:
                connection_triggered['done'] = True
                if hasattr(mock_client_instance, 'on_connect'):
                    mock_client_instance.on_connect(mock_client_instance, None, None, 5)
        
        mock_client_instance.connect.side_effect = on_connect_fail
        mock_client_instance.loop_start.side_effect = on_connect_fail
        
        success, error = publish_tle_to_mqtt(
            sample_mqtt_config,
            sample_tle_data,
            sample_satellite_data
        )
        
        assert success is False
        assert error is not None


class TestImmediateMqttSend:
    """Test immediate MQTT send on configuration."""
    
    @patch('database.mqtt_config.update_last_published')
    @patch('mqtt_publisher.publish_tle_to_mqtt')
    @patch('database.mqtt_config.save_mqtt_configuration')
    @patch('mqtt_scheduler.schedule_mqtt_publish')
    @patch('database.operations.find_satellite')
    @patch('api.services.tle_service.fetch_tle_data')
    def test_immediate_send_on_new_config(self, mock_fetch_tle, mock_find_sat,
                                          mock_schedule, mock_save, mock_publish,
                                          mock_update_last, client, sample_mqtt_config,
                                          sample_satellite_data, sample_tle_data):
        """Test that enabling MQTT config sends immediate message."""
        saved_config = {
            **sample_mqtt_config,
            "_key": "mqtt_config_1",
            "_id": "mqtt_configurations/mqtt_config_1",
        }
        
        mock_save.return_value = saved_config
        mock_find_sat.return_value = sample_satellite_data
        mock_fetch_tle.return_value = {"2017-036V": (
            sample_tle_data["name"],
            sample_tle_data["line1"],
            sample_tle_data["line2"]
        )}
        mock_publish.return_value = (True, None)
        
        response = client.post("/v2/mqtt/config", json=sample_mqtt_config)
        
        assert response.status_code == 200
        
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args[0]
        assert call_args[0] == saved_config
        assert call_args[1]["name"] == sample_tle_data["name"]
        assert call_args[1]["line1"] == sample_tle_data["line1"]
        assert call_args[2] == sample_satellite_data
        
        mock_update_last.assert_called_once()
        assert mock_update_last.call_args[0][0] == "mqtt_config_1"
    
    @patch('mqtt_publisher.publish_tle_to_mqtt')
    @patch('database.mqtt_config.save_mqtt_configuration')
    @patch('mqtt_scheduler.schedule_mqtt_publish')
    @patch('mqtt_scheduler.remove_scheduled_job')
    @patch('database.operations.find_satellite')
    def test_no_immediate_send_when_disabled(self, mock_find_sat, mock_remove,
                                             mock_schedule, mock_save, mock_publish,
                                             client, sample_mqtt_config):
        """Test that disabling MQTT config does not send immediate message."""
        disabled_config = sample_mqtt_config.copy()
        disabled_config["enabled"] = False
        
        mock_save.return_value = {
            **disabled_config,
            "_key": "mqtt_config_1",
        }
        mock_find_sat.return_value = None
        
        response = client.post("/v2/mqtt/config", json=disabled_config)
        
        assert response.status_code == 200
        mock_publish.assert_not_called()
        mock_remove.assert_called_once()


class TestMqttTestConnection:
    """Test MQTT connection testing endpoint."""
    
    @patch('time.sleep')
    @patch('mqtt_publisher.mqtt.Client')
    def test_successful_connection_test(self, mock_mqtt_client, mock_sleep, client):
        """Test successful MQTT broker connection test."""
        mock_client_instance = MagicMock()
        mock_mqtt_client.return_value = mock_client_instance
        
        connection_triggered = {'done': False}
        
        def on_connect_trigger(*args, **kwargs):
            if not connection_triggered['done']:
                connection_triggered['done'] = True
                if hasattr(mock_client_instance, 'on_connect'):
                    mock_client_instance.on_connect(mock_client_instance, None, None, 0)
        
        mock_client_instance.connect.side_effect = on_connect_trigger
        mock_client_instance.loop_start.side_effect = on_connect_trigger
        
        response = client.post("/v2/mqtt/test-connection", json={
            "host": "broker.hivemq.com",
            "port": 1883,
            "username": "test",
            "password": "test"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    @patch('time.sleep')
    @patch('mqtt_publisher.mqtt.Client')
    def test_failed_connection_test(self, mock_mqtt_client, mock_sleep, client):
        """Test failed MQTT broker connection test."""
        mock_client_instance = MagicMock()
        mock_mqtt_client.return_value = mock_client_instance
        
        connection_triggered = {'done': False}
        
        def on_connect_fail(*args, **kwargs):
            if not connection_triggered['done']:
                connection_triggered['done'] = True
                if hasattr(mock_client_instance, 'on_connect'):
                    mock_client_instance.on_connect(mock_client_instance, None, None, 5)
        
        mock_client_instance.connect.side_effect = on_connect_fail
        mock_client_instance.loop_start.side_effect = on_connect_fail
        
        response = client.post("/v2/mqtt/test-connection", json={
            "host": "invalid.broker",
            "port": 1883
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "error" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
