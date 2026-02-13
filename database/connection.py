from arango import ArangoClient
import os

ARANGO_HOST = os.getenv("ARANGO_HOST", "http://localhost:8529")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "kessler_dev_password")
DB_NAME = "kessler"
COLLECTION_NAME = "satellites"

GRAPH_NAME = "satellite_relationships"
EDGE_COLLECTION_CONSTELLATION = "constellation_membership"
EDGE_COLLECTION_REGISTRATION = "registration_links"
EDGE_COLLECTION_PROXIMITY = "orbital_proximity"
EDGE_COLLECTION_COLLISION_RISK = "collision_risk_edges"
EDGE_COLLECTION_SATELLITE_LINEAGE = "satellite_lineage"
COLLECTION_REG_DOCS = "registration_documents"

client = None
db = None
satellites_collection = None


def connect_arangodb():
    """Initialize ArangoDB connection"""
    global client, db, satellites_collection
    try:
        client = ArangoClient(hosts=ARANGO_HOST)
        
        sys_db = client.db('_system', username=ARANGO_USER, password=ARANGO_PASSWORD)
        
        if not sys_db.has_database(DB_NAME):
            sys_db.create_database(DB_NAME)
        
        db = client.db(DB_NAME, username=ARANGO_USER, password=ARANGO_PASSWORD)
        
        if not db.has_collection(COLLECTION_NAME):
            satellites_collection = db.create_collection(COLLECTION_NAME)
        else:
            satellites_collection = db.collection(COLLECTION_NAME)
        
        satellites_collection.add_persistent_index(fields=['canonical.international_designator'], unique=False)
        satellites_collection.add_persistent_index(fields=['canonical.registration_number'], unique=False)
        satellites_collection.add_persistent_index(fields=['identifier'], unique=True)
        
        print(f"Connected to ArangoDB: {DB_NAME}.{COLLECTION_NAME}")
        return True
    except Exception as e:
        print(f"Failed to connect to ArangoDB: {e}")
        return False


def connect_mongodb():
    """Initialize ArangoDB connection (kept name for backward compatibility)"""
    return connect_arangodb()


def disconnect_arangodb():
    """Close ArangoDB connection"""
    global client
    if client:
        client.close()


def disconnect_mongodb():
    """Close ArangoDB connection (kept name for backward compatibility)"""
    disconnect_arangodb()


def get_satellites_collection():
    """Get satellites collection (lazy initialization)"""
    global satellites_collection
    if satellites_collection is None:
        connect_arangodb()
    return satellites_collection
