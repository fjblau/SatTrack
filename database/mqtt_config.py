from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any
import logging
from database.connection import db, connect_mongodb

MQTT_CONFIG_COLLECTION = "mqtt_configurations"


def get_mqtt_configurations_collection():
    """
    Get or create the MQTT configurations collection with indexes.
    
    Returns:
        Collection object or None on error
    """
    # Ensure database is connected
    if db is None:
        connect_mongodb()
    
    # Check again after connection attempt
    if db is None:
        print("Failed to connect to database")
        return None
    
    try:
        if not db.has_collection(MQTT_CONFIG_COLLECTION):
            mqtt_collection = db.create_collection(MQTT_CONFIG_COLLECTION)
            print(f"Created collection: {MQTT_CONFIG_COLLECTION}")
        else:
            mqtt_collection = db.collection(MQTT_CONFIG_COLLECTION)
        
        # Add indexes for efficient queries (ignore if they already exist)
        try:
            mqtt_collection.add_persistent_index(fields=['satellite_id'], unique=True)
        except Exception:
            pass
        
        try:
            mqtt_collection.add_persistent_index(fields=['norad_id'], unique=False)
        except Exception:
            pass
        
        try:
            mqtt_collection.add_persistent_index(fields=['enabled'], unique=False)
        except Exception:
            pass
        
        try:
            mqtt_collection.add_persistent_index(fields=['next_publish'], unique=False)
        except Exception:
            pass
        
        return mqtt_collection
    except Exception as e:
        print(f"Failed to get/create MQTT configurations collection: {e}")
        return None


def save_mqtt_configuration(config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Create or update MQTT configuration for a satellite.
    
    Args:
        config: Configuration dictionary containing:
            - satellite_id (required)
            - norad_id (required)
            - mqtt_broker (dict with host, port, username, password)
            - topic (required)
            - frequency_hours (required, 8 or 24)
            - enabled (boolean)
    
    Returns:
        Saved configuration with generated fields or None on error
    """
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Saving MQTT config for satellite_id: {config.get('satellite_id')}")
        mqtt_collection = get_mqtt_configurations_collection()
        if not mqtt_collection:
            logger.error("MQTT collection not available")
            return None
        
        satellite_id = config.get('satellite_id')
        if not satellite_id:
            logger.error("satellite_id is required but not provided")
            raise ValueError("satellite_id is required")
        
        # Check if configuration exists
        aql = """
        FOR doc IN @@collection
            FILTER doc.satellite_id == @satellite_id
            LIMIT 1
            RETURN doc
        """
        cursor = db.aql.execute(
            aql,
            bind_vars={'@collection': MQTT_CONFIG_COLLECTION, 'satellite_id': satellite_id}
        )
        existing = list(cursor)
        existing_doc = existing[0] if existing else None
        
        # Calculate next_publish based on frequency
        frequency_hours = config.get('frequency_hours', 24)
        next_publish = datetime.now(timezone.utc) + timedelta(hours=frequency_hours)
        
        if existing_doc:
            # Update existing
            existing_doc.update({
                'norad_id': config.get('norad_id'),
                'mqtt_broker': config.get('mqtt_broker'),
                'topic': config.get('topic'),
                'frequency_hours': frequency_hours,
                'enabled': config.get('enabled', True),
                'next_publish': next_publish.isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            })
            
            mqtt_collection.update(existing_doc)
            return existing_doc
        else:
            # Create new
            new_doc = {
                'satellite_id': satellite_id,
                'norad_id': config.get('norad_id'),
                'mqtt_broker': config.get('mqtt_broker'),
                'topic': config.get('topic'),
                'frequency_hours': frequency_hours,
                'enabled': config.get('enabled', True),
                'last_published': None,
                'next_publish': next_publish.isoformat(),
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            result = mqtt_collection.insert(new_doc)
            new_doc['_key'] = result['_key']
            new_doc['_id'] = result['_id']
            return new_doc
            
    except Exception as e:
        print(f"Failed to save MQTT configuration: {e}")
        return None


def get_mqtt_configuration(satellite_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve MQTT configuration for a satellite.
    
    Args:
        satellite_id: Satellite identifier
    
    Returns:
        Configuration document or None if not found
    """
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Getting MQTT config for satellite_id: {satellite_id}")
        mqtt_collection = get_mqtt_configurations_collection()
        if not mqtt_collection:
            logger.error("MQTT collection not available")
            return None
        
        aql = """
        FOR doc IN @@collection
            FILTER doc.satellite_id == @satellite_id
            LIMIT 1
            RETURN doc
        """
        cursor = db.aql.execute(
            aql,
            bind_vars={'@collection': MQTT_CONFIG_COLLECTION, 'satellite_id': satellite_id}
        )
        results = list(cursor)
        
        if results:
            logger.info(f"Found MQTT config: {results[0].get('_key')}")
        else:
            logger.warning(f"No MQTT config found for satellite_id: {satellite_id}")
            
        return results[0] if results else None
        
    except Exception as e:
        logger.error(f"Failed to get MQTT configuration: {e}", exc_info=True)
        return None


def delete_mqtt_configuration(satellite_id: str) -> bool:
    """
    Delete MQTT configuration for a satellite.
    
    Args:
        satellite_id: Satellite identifier
    
    Returns:
        True if deleted, False otherwise
    """
    try:
        mqtt_collection = get_mqtt_configurations_collection()
        if not mqtt_collection:
            return False
        
        config = get_mqtt_configuration(satellite_id)
        if not config:
            return False
        
        mqtt_collection.delete(config['_key'])
        return True
        
    except Exception as e:
        print(f"Failed to delete MQTT configuration: {e}")
        return False


def get_enabled_mqtt_configurations() -> List[Dict[str, Any]]:
    """
    Get all enabled MQTT configurations.
    
    Returns:
        List of enabled configuration documents
    """
    try:
        mqtt_collection = get_mqtt_configurations_collection()
        if not mqtt_collection:
            return []
        
        aql = """
        FOR doc IN @@collection
            FILTER doc.enabled == true
            RETURN doc
        """
        cursor = db.aql.execute(
            aql,
            bind_vars={'@collection': MQTT_CONFIG_COLLECTION}
        )
        return list(cursor)
        
    except Exception as e:
        print(f"Failed to get enabled MQTT configurations: {e}")
        return []


def update_last_published(config_id: str, timestamp: datetime) -> bool:
    """
    Update the last_published timestamp and calculate next_publish for a configuration.
    
    Args:
        config_id: Configuration _key or _id
        timestamp: Publication timestamp
    
    Returns:
        True if successful, False otherwise
    """
    try:
        mqtt_collection = get_mqtt_configurations_collection()
        if not mqtt_collection:
            return False
        
        # Get the config to determine frequency
        if '/' in config_id:
            # Full _id provided
            key = config_id.split('/')[-1]
        else:
            key = config_id
        
        config = mqtt_collection.get(key)
        if not config:
            return False
        
        # Calculate next publish time
        frequency_hours = config.get('frequency_hours', 24)
        next_publish = timestamp + timedelta(hours=frequency_hours)
        
        # Update the document
        mqtt_collection.update({
            '_key': key,
            'last_published': timestamp.isoformat(),
            'next_publish': next_publish.isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        })
        
        return True
        
    except Exception as e:
        print(f"Failed to update last_published: {e}")
        return False
