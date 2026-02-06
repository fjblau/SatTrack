"""
MQTT Publisher Module for Satellite TLE Data

This module handles MQTT publishing of TLE data to configured brokers.
"""

import json
import math
from datetime import datetime, timezone
from typing import Dict, Optional, Any
import paho.mqtt.client as mqtt


def calculate_orbital_parameters(tle_line2: str) -> Dict[str, Any]:
    """
    Calculate orbital parameters from TLE line 2.
    
    Args:
        tle_line2: TLE line 2 string
    
    Returns:
        Dictionary with orbital parameters
    """
    try:
        inclination = float(tle_line2[8:16])
        eccentricity = float('0.' + tle_line2[26:33])
        mean_motion_rev_day = float(tle_line2[52:63])
        
        period_minutes = 1440.0 / mean_motion_rev_day
        
        GM = 398600.4418
        n_rad_per_sec = (mean_motion_rev_day * 2 * math.pi) / 86400.0
        a = (GM / (n_rad_per_sec * n_rad_per_sec)) ** (1.0/3.0)
        
        earth_radius = 6378.137
        apogee = a * (1 + eccentricity) - earth_radius
        perigee = a * (1 - eccentricity) - earth_radius
        
        return {
            'apogee_km': round(apogee, 2),
            'perigee_km': round(perigee, 2),
            'inclination_degrees': round(inclination, 2),
            'period_minutes': round(period_minutes, 2),
            'semi_major_axis_km': round(a, 2),
            'eccentricity': round(eccentricity, 6),
            'mean_motion_rev_day': round(mean_motion_rev_day, 6)
        }
    except Exception as e:
        return {'error': str(e)}


def extract_tle_epoch(tle_line1: str) -> Optional[str]:
    """
    Extract epoch from TLE line 1 and convert to ISO8601 timestamp.
    
    Args:
        tle_line1: TLE line 1 string
    
    Returns:
        ISO8601 formatted timestamp or None on error
    """
    try:
        epoch_year = int(tle_line1[18:20])
        epoch_day = float(tle_line1[20:32])
        
        year = 2000 + epoch_year if epoch_year < 57 else 1900 + epoch_year
        
        from datetime import timedelta
        epoch_date = datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(days=epoch_day - 1)
        
        return epoch_date.isoformat()
    except Exception:
        return None


def parse_scientific_notation(field: str) -> float:
    """
    Parse TLE scientific notation format (assumed decimal point).
    Format: ±.NNNNN±N where the first ± is sign, NNNNN is mantissa, and ±N is exponent
    Example: " 10270-3" = 0.10270 x 10^-3 = 0.00010270
    """
    field = field.strip()
    if not field or field == '00000-0' or field == '00000+0':
        return 0.0
    
    try:
        if '-' in field[1:]:
            parts = field.split('-')
            mantissa = float('0.' + parts[0].strip())
            exponent = -int(parts[1])
        elif '+' in field[1:]:
            parts = field.split('+')
            mantissa = float('0.' + parts[0].strip())
            exponent = int(parts[1])
        else:
            return float(field)
        
        return mantissa * (10 ** exponent)
    except Exception:
        return 0.0


def parse_tle_line1(line1: str) -> Dict[str, Any]:
    """
    Parse TLE Line 1 according to NORAD format specification.
    
    Args:
        line1: TLE line 1 string
    
    Returns:
        Dictionary with parsed Line 1 fields
    """
    try:
        mean_motion_second_deriv_str = line1[44:52].strip()
        bstar_str = line1[53:61].strip()
        
        return {
            'line_number': int(line1[0:1]),
            'satellite_number': int(line1[2:7]),
            'classification': line1[7:8].strip(),
            'international_designator': {
                'year': line1[9:11],
                'launch_number': line1[11:14].strip(),
                'launch_piece': line1[14:17].strip(),
                'full': line1[9:17].strip()
            },
            'epoch_year': int(line1[18:20]),
            'epoch_day': float(line1[20:32]),
            'epoch_iso': extract_tle_epoch(line1),
            'mean_motion_first_derivative': float(line1[33:43]),
            'mean_motion_second_derivative': parse_scientific_notation(mean_motion_second_deriv_str),
            'bstar_drag': parse_scientific_notation(bstar_str),
            'ephemeris_type': int(line1[62:63]) if line1[62:63].strip() else 0,
            'element_number': int(line1[64:68]),
            'checksum': int(line1[68:69])
        }
    except Exception as e:
        return {'error': f'Failed to parse Line 1: {str(e)}'}


def parse_tle_line2(line2: str) -> Dict[str, Any]:
    """
    Parse TLE Line 2 according to NORAD format specification.
    
    Args:
        line2: TLE line 2 string
    
    Returns:
        Dictionary with parsed Line 2 fields
    """
    try:
        return {
            'line_number': int(line2[0:1]),
            'satellite_number': int(line2[2:7]),
            'inclination_degrees': float(line2[8:16]),
            'right_ascension_degrees': float(line2[17:25]),
            'eccentricity': float('0.' + line2[26:33]),
            'argument_of_perigee_degrees': float(line2[34:42]),
            'mean_anomaly_degrees': float(line2[43:51]),
            'mean_motion_rev_per_day': float(line2[52:63]),
            'revolution_number': int(line2[63:68]),
            'checksum': int(line2[68:69])
        }
    except Exception as e:
        return {'error': f'Failed to parse Line 2: {str(e)}'}


def convert_tle_to_json(satellite_data: Dict[str, Any], tle_data: Dict[str, Any]) -> str:
    """
    Convert TLE data and satellite metadata to JSON format for MQTT publishing.
    
    Args:
        satellite_data: Satellite document from database with canonical fields
        tle_data: TLE data dictionary with name, line1, line2
    
    Returns:
        JSON string with formatted TLE and satellite data
    """
    tle_line1 = tle_data.get('line1', '')
    tle_line2 = tle_data.get('line2', '')
    
    canonical = satellite_data.get('canonical', {})
    
    line1_parsed = parse_tle_line1(tle_line1) if tle_line1 else {}
    line2_parsed = parse_tle_line2(tle_line2) if tle_line2 else {}
    
    international_designator = canonical.get('international_designator', '')
    if not international_designator and line1_parsed.get('international_designator'):
        international_designator = line1_parsed['international_designator']['full']
    
    classification = line1_parsed.get('classification', 'U')
    epoch = line1_parsed.get('epoch_iso')
    
    orbital_params = calculate_orbital_parameters(tle_line2) if tle_line2 else {}
    
    payload = {
        "satellite": {
            "norad_id": canonical.get('norad_cat_id', ''),
            "name": canonical.get('name', tle_data.get('name', '')),
            "international_designator": international_designator,
            "country_of_origin": canonical.get('state_of_registry', '')
        },
        "tle": {
            "raw": {
                "line0": tle_data.get('name', ''),
                "line1": tle_line1,
                "line2": tle_line2
            },
            "parsed": {
                "line1": line1_parsed,
                "line2": line2_parsed
            },
            "epoch": epoch,
            "classification": classification
        },
        "orbital_parameters": orbital_params,
        "metadata": {
            "published_at": datetime.now(timezone.utc).isoformat(),
            "data_source": tle_data.get('source', 'tle-api'),
            "publisher": "Kessler MQTT Feed"
        }
    }
    
    return json.dumps(payload, indent=2)


def publish_tle_to_mqtt(
    config: Dict[str, Any],
    tle_data: Dict[str, Any],
    satellite_data: Dict[str, Any]
) -> tuple[bool, Optional[str]]:
    """
    Publish TLE data to MQTT broker using configuration.
    
    Args:
        config: MQTT configuration with broker details and topic
        tle_data: TLE data dictionary
        satellite_data: Satellite document from database
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        mqtt_broker = config.get('mqtt_broker', {})
        host = mqtt_broker.get('host')
        port = mqtt_broker.get('port', 1883)
        username = mqtt_broker.get('username')
        password = mqtt_broker.get('password')
        topic = config.get('topic', 'satellites/tle')
        
        # Replace {norad_id} placeholder with actual NORAD catalog ID
        canonical = satellite_data.get('canonical', {})
        norad_id = canonical.get('norad_cat_id', '')
        if norad_id and '{norad_id}' in topic:
            topic = topic.replace('{norad_id}', str(norad_id))
            logger.info(f"Replaced {{norad_id}} placeholder with {norad_id}")
        
        logger.info(f"MQTT Publish: host={host}, port={port}, topic={topic}, has_username={bool(username)}")
        
        if not host:
            logger.error("MQTT broker host not configured")
            return False, "MQTT broker host not configured"
        
        json_payload = convert_tle_to_json(satellite_data, tle_data)
        logger.info(f"Generated JSON payload, length={len(json_payload)} bytes")
        
        client_id = f"kessler_{config.get('satellite_id', 'unknown').replace('/', '_')}"
        logger.info(f"Creating MQTT client with id: {client_id}")
        
        client = mqtt.Client(
            client_id=client_id,
            protocol=mqtt.MQTTv311
        )
        
        if username and password:
            logger.info(f"Setting MQTT credentials for user: {username}")
            client.username_pw_set(username, password)
        
        connection_result = {'success': False, 'error': None}
        
        def on_connect(client, userdata, flags, rc):
            logger.info(f"MQTT on_connect callback: rc={rc}")
            if rc == 0:
                connection_result['success'] = True
            else:
                connection_result['error'] = f"Connection failed with code {rc}"
        
        def on_publish(client, userdata, mid):
            logger.info(f"MQTT on_publish callback: mid={mid}")
        
        client.on_connect = on_connect
        client.on_publish = on_publish
        
        logger.info(f"Connecting to MQTT broker {host}:{port}")
        client.connect(host, port, keepalive=60)
        client.loop_start()
        logger.info("MQTT loop started")
        
        import time
        timeout = 10
        start_time = time.time()
        while not connection_result['success'] and not connection_result['error']:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                logger.error(f"MQTT connection timeout after {elapsed:.2f} seconds")
                client.loop_stop()
                client.disconnect()
                return False, "Connection timeout"
            time.sleep(0.1)
        
        logger.info(f"Connection result: success={connection_result['success']}, error={connection_result['error']}")
        
        if not connection_result['success']:
            client.loop_stop()
            client.disconnect()
            logger.error(f"MQTT connection failed: {connection_result['error']}")
            return False, connection_result['error']
        
        logger.info(f"Publishing to topic: {topic}")
        result = client.publish(topic, json_payload, qos=1)
        logger.info(f"Publish initiated: rc={result.rc}, mid={result.mid}")
        
        result.wait_for_publish(timeout=5)
        logger.info("Publish wait completed")
        
        client.loop_stop()
        client.disconnect()
        logger.info("MQTT client disconnected")
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            logger.info("MQTT publish successful")
            return True, None
        else:
            logger.error(f"MQTT publish failed with code {result.rc}")
            return False, f"Publish failed with code {result.rc}"
        
    except Exception as e:
        logger.error(f"MQTT publish exception: {str(e)}", exc_info=True)
        return False, f"MQTT publish error: {str(e)}"


def test_mqtt_connection(config: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Test MQTT broker connectivity.
    
    Args:
        config: Dictionary with host, port, username, password
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    try:
        host = config.get('host')
        port = config.get('port', 1883)
        username = config.get('username')
        password = config.get('password')
        
        if not host:
            return False, "Host is required"
        
        client = mqtt.Client(
            client_id="kessler_connection_test",
            protocol=mqtt.MQTTv311
        )
        
        if username and password:
            client.username_pw_set(username, password)
        
        connection_result = {'success': False, 'error': None}
        
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                connection_result['success'] = True
            else:
                error_messages = {
                    1: "Connection refused - incorrect protocol version",
                    2: "Connection refused - invalid client identifier",
                    3: "Connection refused - server unavailable",
                    4: "Connection refused - bad username or password",
                    5: "Connection refused - not authorized"
                }
                connection_result['error'] = error_messages.get(rc, f"Connection failed with code {rc}")
        
        client.on_connect = on_connect
        
        client.connect(host, port, keepalive=60)
        client.loop_start()
        
        import time
        timeout = 10
        start_time = time.time()
        while not connection_result['success'] and not connection_result['error']:
            if time.time() - start_time > timeout:
                client.loop_stop()
                client.disconnect()
                return False, "Connection timeout - broker may be unreachable"
            time.sleep(0.1)
        
        client.loop_stop()
        client.disconnect()
        
        if connection_result['success']:
            return True, None
        else:
            return False, connection_result['error']
        
    except Exception as e:
        return False, f"Connection test error: {str(e)}"
