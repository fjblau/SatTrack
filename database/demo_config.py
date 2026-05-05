from typing import Optional, Dict, Any
import database.connection as db_connection

APP_SETTINGS_COLLECTION = "app_settings"
DEMO_CONFIG_KEY = "demo_config"


def _get_collection():
    if db_connection.db is None:
        db_connection.connect_mongodb()
    if db_connection.db is None:
        return None
    try:
        if not db_connection.db.has_collection(APP_SETTINGS_COLLECTION):
            db_connection.db.create_collection(APP_SETTINGS_COLLECTION)
        return db_connection.db.collection(APP_SETTINGS_COLLECTION)
    except Exception as e:
        print(f"Failed to get/create {APP_SETTINGS_COLLECTION} collection: {e}")
        return None


def get_demo_config() -> Optional[Dict[str, Any]]:
    col = _get_collection()
    if col is None:
        return None
    try:
        doc = col.get(DEMO_CONFIG_KEY)
        if doc is None:
            return None
        return doc.get("config")
    except Exception as e:
        print(f"Failed to get demo config: {e}")
        return None


def save_demo_config(config: Dict[str, Any]) -> bool:
    col = _get_collection()
    if col is None:
        return False
    try:
        doc = {"_key": DEMO_CONFIG_KEY, "config": config}
        if col.has(DEMO_CONFIG_KEY):
            col.update(doc)
        else:
            col.insert(doc)
        return True
    except Exception as e:
        print(f"Failed to save demo config: {e}")
        return False
