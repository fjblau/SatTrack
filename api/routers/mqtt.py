from fastapi import APIRouter, HTTPException, Body
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import logging
import json

import database as db_module
from database import (
    get_mqtt_configurations_collection,
    save_mqtt_configuration,
    get_mqtt_configuration,
    delete_mqtt_configuration,
    get_enabled_mqtt_configurations,
    update_last_published
)
from database.operations import find_satellite
from api.services.tle_service import fetch_tle_by_norad_id
import mqtt_publisher
import mqtt_scheduler

router = APIRouter(prefix="/v2/mqtt", tags=["mqtt"])
cron_router = APIRouter(prefix="/api/cron", tags=["mqtt"])

class MqttBrokerConfig(BaseModel):
    host: str = Field(..., min_length=1, description="MQTT broker hostname or IP")
    port: int = Field(1883, ge=1, le=65535, description="MQTT broker port")
    username: Optional[str] = Field(None, description="MQTT username")
    password: Optional[str] = Field(None, description="MQTT password")


class MqttConfiguration(BaseModel):
    satellite_id: str = Field(..., min_length=1, description="Satellite document ID")
    norad_id: str = Field(..., min_length=1, description="NORAD catalog ID")
    mqtt_broker: MqttBrokerConfig
    topic: str = Field(..., min_length=1, description="MQTT topic for publishing")
    frequency_hours: int = Field(24, description="Publishing frequency in hours (8 or 24)")
    enabled: bool = Field(True, description="Enable/disable publishing")


class MqttTestConnectionRequest(BaseModel):
    host: str
    port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None


def redact_password(config: Dict[str, Any]) -> Dict[str, Any]:
    result = config.copy()
    if 'mqtt_broker' in result and isinstance(result['mqtt_broker'], dict):
        result['mqtt_broker'] = result['mqtt_broker'].copy()
        if result['mqtt_broker'].get('password'):
            result['mqtt_broker']['password'] = '[REDACTED]'
    return result


@router.get("/config/{satellite_id:path}")
def get_mqtt_config(satellite_id: str):
    config = get_mqtt_configuration(satellite_id)
    if not config:
        raise HTTPException(status_code=404, detail="MQTT configuration not found")
    return redact_password(config)



@router.post("/config")
def create_or_update_mqtt_config(config: MqttConfiguration):
    logging.info(f"Saving MQTT config for satellite_id: {config.satellite_id}, norad_id: {config.norad_id}")
    
    if config.frequency_hours not in [8, 24]:
        raise HTTPException(
            status_code=400,
            detail="Frequency must be either 8 or 24 hours"
        )
    
    if not config.mqtt_broker.host:
        raise HTTPException(status_code=400, detail="MQTT broker host is required")
    
    if not (1 <= config.mqtt_broker.port <= 65535):
        raise HTTPException(status_code=400, detail="Port must be between 1 and 65535")
    
    if not config.topic:
        raise HTTPException(status_code=400, detail="Topic is required")
    
    config_dict = {
        'satellite_id': config.satellite_id,
        'norad_id': config.norad_id,
        'mqtt_broker': {
            'host': config.mqtt_broker.host,
            'port': config.mqtt_broker.port,
            'username': config.mqtt_broker.username,
            'password': config.mqtt_broker.password
        },
        'topic': config.topic,
        'frequency_hours': config.frequency_hours,
        'enabled': config.enabled
    }
    
    logging.info(f"Config dict to save: {json.dumps({**config_dict, 'mqtt_broker': {**config_dict['mqtt_broker'], 'password': '***'}}, indent=2)}")
    
    saved_config = save_mqtt_configuration(config_dict)
    if not saved_config:
        logging.error(f"Failed to save MQTT configuration for satellite_id: {config.satellite_id}")
        raise HTTPException(status_code=500, detail="Failed to save MQTT configuration")
    
    logging.info(f"Successfully saved MQTT config with _key: {saved_config.get('_key')}")
    
    if config.enabled:
        mqtt_scheduler.schedule_mqtt_publish(saved_config)
        
        # Send immediate MQTT message when configuration is enabled
        try:
            # Extract international designator from satellite_id (format: satellites/2018-040E)
            intl_desig_from_id = config.satellite_id.split('/')[-1] if '/' in config.satellite_id else config.satellite_id
            satellite = find_satellite(international_designator=intl_desig_from_id)
            if satellite:
                canonical = satellite.get('canonical', {})
                intl_desig = canonical.get('international_designator')
                
                norad_id = canonical.get('norad_cat_id')
                
                if norad_id:
                    # Fetch TLE from external API (same source as frontend)
                    logging.info(f"Immediate send: Fetching TLE from external API for NORAD ID: {norad_id}")
                    tle_dict = fetch_tle_by_norad_id(str(norad_id))
                    
                    if tle_dict and tle_dict.get('line1') and tle_dict.get('line2'):
                        tle_data = tle_dict
                        
                        success, error_message = mqtt_publisher.publish_tle_to_mqtt(saved_config, tle_data, satellite)
                        
                        if success:
                            update_last_published(saved_config['_key'], datetime.now(timezone.utc))
                            logging.info(f"Initial MQTT message sent for satellite {config.satellite_id}")
                        else:
                            logging.warning(f"Failed to send initial MQTT message for satellite {config.satellite_id}: {error_message}")
        except Exception as e:
            logging.warning(f"Failed to send initial MQTT message for satellite {config.satellite_id}: {e}")
    else:
        mqtt_scheduler.remove_scheduled_job(config.satellite_id)
    
    return redact_password(saved_config)



@router.delete("/config/{satellite_id:path}")
def delete_mqtt_config(satellite_id: str):
    success = delete_mqtt_configuration(satellite_id)
    if not success:
        raise HTTPException(status_code=404, detail="MQTT configuration not found")
    
    mqtt_scheduler.remove_scheduled_job(satellite_id)
    
    return {"success": True, "message": "MQTT configuration deleted"}



@router.post("/test-connection")
def test_mqtt_connection(request: MqttTestConnectionRequest):
    if not request.host:
        raise HTTPException(status_code=400, detail="Host is required")
    
    if not (1 <= request.port <= 65535):
        raise HTTPException(status_code=400, detail="Port must be between 1 and 65535")
    
    config = {
        'host': request.host,
        'port': request.port,
        'username': request.username,
        'password': request.password
    }
    
    success, error_message = mqtt_publisher.test_mqtt_connection(config)
    
    if success:
        return {"success": True, "message": "Connection successful"}
    else:
        return {
            "success": False,
            "error": error_message or "Unknown error",
            "details": f"Failed to connect to {request.host}:{request.port}"
        }



@router.get("/debug/{satellite_id:path}")
def debug_mqtt_config(satellite_id: str):
    """Debug endpoint to check MQTT configuration and satellite data."""
    config = get_mqtt_configuration(satellite_id)
    
    intl_desig_from_id = satellite_id.split('/')[-1] if '/' in satellite_id else satellite_id
    satellite = find_satellite(international_designator=intl_desig_from_id)
    
    return {
        "satellite_id": satellite_id,
        "intl_desig_extracted": intl_desig_from_id,
        "config_exists": config is not None,
        "config_key": config.get('_key') if config else None,
        "satellite_exists": satellite is not None,
        "satellite_id_in_db": satellite.get('_id') if satellite else None,
        "satellite_intl_desig": satellite.get('canonical', {}).get('international_designator') if satellite else None
    }



@router.post("/publish-now/{satellite_id:path}")
def publish_now(satellite_id: str):
    logging.info(f"=== PUBLISH NOW START === satellite_id: {satellite_id}")
    
    config = get_mqtt_configuration(satellite_id)
    if not config:
        logging.error(f"MQTT configuration not found for satellite_id: {satellite_id}")
        raise HTTPException(status_code=404, detail=f"MQTT configuration not found for {satellite_id}")
    
    logging.info(f"Found config: {config.get('_key')}")
    
    if not config.get('enabled'):
        logging.error(f"MQTT feed is disabled for satellite_id: {satellite_id}")
        raise HTTPException(status_code=400, detail="MQTT feed is disabled for this satellite")
    
    # Extract international designator from satellite_id (format: satellites/2018-040E)
    intl_desig_from_id = satellite_id.split('/')[-1] if '/' in satellite_id else satellite_id
    
    satellite = find_satellite(international_designator=intl_desig_from_id)
    if not satellite:
        logging.error(f"Satellite not found for ID: {satellite_id} (searched for intl_desig: {intl_desig_from_id})")
        raise HTTPException(status_code=404, detail="Satellite not found")
    
    canonical = satellite.get('canonical', {})
    intl_desig = canonical.get('international_designator')
    
    logging.info(f"Satellite canonical data: norad={canonical.get('norad_cat_id')}, intl_desig={intl_desig}")
    
    norad_id = canonical.get('norad_cat_id')
    
    if not norad_id:
        logging.error(f"Satellite {satellite_id} has no NORAD catalog ID")
        raise HTTPException(status_code=400, detail="Satellite has no NORAD catalog ID")
    
    # Fetch TLE from external API (same source as frontend)
    logging.info(f"Fetching TLE from external API for NORAD ID: {norad_id}")
    tle_dict = fetch_tle_by_norad_id(str(norad_id))
    
    if not tle_dict or not tle_dict.get('line1') or not tle_dict.get('line2'):
        logging.error(f"TLE data not found for satellite {satellite_id} (NORAD ID: {norad_id})")
        raise HTTPException(status_code=404, detail=f"TLE data not available for NORAD ID {norad_id}")
    
    tle_data = tle_dict
    
    logging.info(f"Publishing TLE to MQTT broker: {config.get('mqtt_broker', {}).get('host')}:{config.get('mqtt_broker', {}).get('port')}")
    success, error_message = mqtt_publisher.publish_tle_to_mqtt(config, tle_data, satellite)
    
    if success:
        update_last_published(config['_key'], datetime.now(timezone.utc))
        
        payload = mqtt_publisher.convert_tle_to_json(satellite, tle_data)
        
        logging.info(f"Successfully published TLE for {satellite_id} to topic {config.get('topic')}")
        return {
            "success": True,
            "message": "TLE data published successfully",
            "topic": config.get('topic'),
            "payload": json.loads(payload)
        }
    else:
        logging.error(f"MQTT publish failed for {satellite_id}: {error_message}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to publish TLE data: {error_message}"
        )



@cron_router.get("/mqtt-publish")
def cron_mqtt_publish():
    """
    Vercel Cron Job endpoint - publishes TLE data for all enabled MQTT configurations.
    This endpoint is called by Vercel's cron scheduler every 4 hours.
    
    For serverless deployment, this replaces APScheduler's background jobs.
    """
    try:
        configs = get_enabled_mqtt_configurations()
        results = {
            "total": len(configs),
            "successful": 0,
            "failed": 0,
            "errors": []
        }
        
        for config in configs:
            satellite_id = config.get('satellite_id')
            config_id = config.get('_key')
            
            try:
                satellite = find_satellite(satellite_id)
                if not satellite:
                    results["errors"].append({
                        "satellite_id": satellite_id,
                        "error": "Satellite not found"
                    })
                    results["failed"] += 1
                    continue
                
                canonical = satellite.get('canonical', {})
                norad_id = config.get('norad_id') or canonical.get('norad_cat_id')
                
                if not norad_id:
                    results["errors"].append({
                        "satellite_id": satellite_id,
                        "error": "No NORAD catalog ID"
                    })
                    results["failed"] += 1
                    continue
                
                tle_dict = fetch_tle_by_norad_id(str(norad_id))
                
                if not tle_dict or not tle_dict.get('line1') or not tle_dict.get('line2'):
                    results["errors"].append({
                        "satellite_id": satellite_id,
                        "error": "TLE data not found"
                    })
                    results["failed"] += 1
                    continue
                
                tle_data = tle_dict
                
                success, error_message = mqtt_publisher.publish_tle_to_mqtt(config, tle_data, satellite)
                
                if success:
                    update_last_published(config_id, datetime.now(timezone.utc))
                    results["successful"] += 1
                else:
                    results["errors"].append({
                        "satellite_id": satellite_id,
                        "error": error_message
                    })
                    results["failed"] += 1
                    
            except Exception as e:
                results["errors"].append({
                    "satellite_id": satellite_id,
                    "error": str(e)
                })
                results["failed"] += 1
        
        return {
            "success": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": results
        }
        
    except Exception as e:
        logging.error(f"Cron job error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Cron job failed: {str(e)}"
        )
