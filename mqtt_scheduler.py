"""
MQTT Scheduler Module

Handles background scheduling of periodic TLE publishing to MQTT brokers.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import logging

import mqtt_publisher
from database import (
    get_enabled_mqtt_configurations,
    get_mqtt_configuration,
    update_last_published,
    find_satellite
)

logger = logging.getLogger(__name__)

scheduler: Optional[BackgroundScheduler] = None


def initialize_scheduler() -> BackgroundScheduler:
    """
    Initialize and start the background scheduler.
    
    Returns:
        BackgroundScheduler instance
    """
    global scheduler
    
    if scheduler is not None:
        logger.warning("Scheduler already initialized")
        return scheduler
    
    scheduler = BackgroundScheduler(timezone='UTC')
    scheduler.start()
    logger.info("MQTT scheduler initialized")
    
    return scheduler


def shutdown_scheduler():
    """Gracefully shutdown the scheduler"""
    global scheduler
    
    if scheduler is not None:
        scheduler.shutdown(wait=True)
        scheduler = None
        logger.info("MQTT scheduler shutdown complete")


def get_scheduler() -> Optional[BackgroundScheduler]:
    """Get the current scheduler instance"""
    return scheduler


def publish_tle_job(config_id: str, satellite_id: str):
    """
    Scheduled job function that fetches TLE, publishes to MQTT, and updates timestamps.
    
    Args:
        config_id: MQTT configuration _key
        satellite_id: Satellite identifier
    """
    try:
        logger.info(f"Starting scheduled MQTT publish for satellite {satellite_id}")
        
        config = get_mqtt_configuration(satellite_id)
        if not config:
            logger.error(f"MQTT configuration not found for satellite {satellite_id}")
            return
        
        if not config.get('enabled'):
            logger.info(f"MQTT feed disabled for satellite {satellite_id}, skipping publish")
            return
        
        satellite = find_satellite(satellite_id)
        if not satellite:
            logger.error(f"Satellite {satellite_id} not found")
            return
        
        canonical = satellite.get('canonical', {})
        intl_desig = canonical.get('international_designator')
        
        if not intl_desig:
            logger.error(f"Satellite {satellite_id} has no international designator")
            return
        
        from api import fetch_tle_data, convert_to_norad_format
        
        tle_cache = fetch_tle_data()
        tle_data_tuple = tle_cache.get(intl_desig)
        
        if not tle_data_tuple:
            norad_format = convert_to_norad_format(intl_desig)
            if norad_format:
                tle_data_tuple = tle_cache.get(norad_format)
        
        if not tle_data_tuple:
            logger.error(f"TLE data not found for satellite {satellite_id} (designator: {intl_desig})")
            return
        
        tle_data = {
            'name': tle_data_tuple[0],
            'line1': tle_data_tuple[1],
            'line2': tle_data_tuple[2],
            'source': 'CelesTrak'
        }
        
        success, error_message = mqtt_publisher.publish_tle_to_mqtt(config, tle_data, satellite)
        
        if success:
            now = datetime.now(timezone.utc)
            update_last_published(config_id, now)
            logger.info(f"Successfully published TLE for satellite {satellite_id} to topic {config.get('topic')}")
        else:
            logger.error(f"Failed to publish TLE for satellite {satellite_id}: {error_message}")
            
    except Exception as e:
        logger.error(f"Error in scheduled MQTT publish job for satellite {satellite_id}: {e}", exc_info=True)


def schedule_mqtt_publish(config: Dict[str, Any]) -> bool:
    """
    Add or update a scheduled job for MQTT publishing.
    
    Args:
        config: MQTT configuration document with _key, satellite_id, frequency_hours, enabled
    
    Returns:
        True if scheduled successfully, False otherwise
    """
    global scheduler
    
    if scheduler is None:
        logger.error("Scheduler not initialized")
        return False
    
    try:
        satellite_id = config.get('satellite_id')
        config_id = config.get('_key')
        frequency_hours = config.get('frequency_hours', 24)
        enabled = config.get('enabled', True)
        
        if not enabled:
            logger.info(f"MQTT feed disabled for satellite {satellite_id}, not scheduling")
            remove_scheduled_job(satellite_id)
            return True
        
        job_id = f"mqtt_publish_{satellite_id}"
        
        existing_job = scheduler.get_job(job_id)
        if existing_job:
            scheduler.remove_job(job_id)
            logger.info(f"Removed existing scheduled job for satellite {satellite_id}")
        
        trigger = IntervalTrigger(hours=frequency_hours, timezone='UTC')
        
        scheduler.add_job(
            func=publish_tle_job,
            trigger=trigger,
            args=[config_id, satellite_id],
            id=job_id,
            name=f"MQTT Publish for {satellite_id}",
            replace_existing=True
        )
        
        logger.info(f"Scheduled MQTT publish for satellite {satellite_id} every {frequency_hours} hours")
        return True
        
    except Exception as e:
        logger.error(f"Failed to schedule MQTT publish: {e}", exc_info=True)
        return False


def remove_scheduled_job(satellite_id: str) -> bool:
    """
    Remove a scheduled job.
    
    Args:
        satellite_id: Satellite identifier
    
    Returns:
        True if removed or didn't exist, False on error
    """
    global scheduler
    
    if scheduler is None:
        logger.error("Scheduler not initialized")
        return False
    
    try:
        job_id = f"mqtt_publish_{satellite_id}"
        existing_job = scheduler.get_job(job_id)
        
        if existing_job:
            scheduler.remove_job(job_id)
            logger.info(f"Removed scheduled job for satellite {satellite_id}")
        else:
            logger.debug(f"No scheduled job found for satellite {satellite_id}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to remove scheduled job: {e}", exc_info=True)
        return False


def load_and_schedule_all_configs():
    """
    Load all enabled MQTT configurations and schedule their jobs.
    Called on application startup.
    """
    try:
        configs = get_enabled_mqtt_configurations()
        logger.info(f"Loading {len(configs)} enabled MQTT configurations")
        
        for config in configs:
            satellite_id = config.get('satellite_id')
            if schedule_mqtt_publish(config):
                logger.info(f"Scheduled MQTT publish for satellite {satellite_id}")
            else:
                logger.error(f"Failed to schedule MQTT publish for satellite {satellite_id}")
        
        logger.info(f"Loaded and scheduled {len(configs)} MQTT configurations")
        
    except Exception as e:
        logger.error(f"Error loading MQTT configurations: {e}", exc_info=True)
