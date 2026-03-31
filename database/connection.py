from arango import ArangoClient
import os
import sys

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
COLLECTION_OBSERVATIONS = "observations"
COLLECTION_OBSERVATION_SOURCES = "observation_sources"

OBSERVATION_GRAPH_NAME = "observation_relationships"
EDGE_COLLECTION_OBS_SATELLITE = "observation_satellite_edges"
EDGE_COLLECTION_OBS_SOURCE = "observation_source_edges"
EDGE_COLLECTION_OBS_CORRELATION = "observation_correlation_edges"
EDGE_COLLECTION_OBS_TEMPORAL = "observation_temporal_edges"

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

        # Ensure observations collection exists
        if not db.has_collection(COLLECTION_OBSERVATIONS):
            db.create_collection(COLLECTION_OBSERVATIONS)
        obs_col = db.collection(COLLECTION_OBSERVATIONS)
        obs_col.add_persistent_index(fields=['norad_id'], unique=False)
        obs_col.add_persistent_index(fields=['source'], unique=False)
        obs_col.add_persistent_index(fields=['observation_epoch'], unique=False)

        # Ensure observation_sources vertex collection exists
        if not db.has_collection(COLLECTION_OBSERVATION_SOURCES):
            db.create_collection(COLLECTION_OBSERVATION_SOURCES)

        # Ensure observation edge collections exist
        obs_edge_collections = [
            EDGE_COLLECTION_OBS_SATELLITE,
            EDGE_COLLECTION_OBS_SOURCE,
            EDGE_COLLECTION_OBS_CORRELATION,
            EDGE_COLLECTION_OBS_TEMPORAL,
        ]
        for edge_col_name in obs_edge_collections:
            if not db.has_collection(edge_col_name):
                db.create_collection(edge_col_name, edge=True)

        # Ensure observation graph exists
        if not db.has_graph(OBSERVATION_GRAPH_NAME):
            db.create_graph(
                OBSERVATION_GRAPH_NAME,
                edge_definitions=[
                    {
                        "edge_collection": EDGE_COLLECTION_OBS_SATELLITE,
                        "from_vertex_collections": [COLLECTION_OBSERVATIONS],
                        "to_vertex_collections": [COLLECTION_NAME],
                    },
                    {
                        "edge_collection": EDGE_COLLECTION_OBS_SOURCE,
                        "from_vertex_collections": [COLLECTION_OBSERVATIONS],
                        "to_vertex_collections": [COLLECTION_OBSERVATION_SOURCES],
                    },
                    {
                        "edge_collection": EDGE_COLLECTION_OBS_CORRELATION,
                        "from_vertex_collections": [COLLECTION_OBSERVATIONS],
                        "to_vertex_collections": [COLLECTION_OBSERVATIONS],
                    },
                    {
                        "edge_collection": EDGE_COLLECTION_OBS_TEMPORAL,
                        "from_vertex_collections": [COLLECTION_OBSERVATIONS],
                        "to_vertex_collections": [COLLECTION_OBSERVATIONS],
                    },
                ],
            )

        pkg = sys.modules.get('database')
        if pkg is not None:
            pkg.db = db
            pkg.satellites_collection = satellites_collection

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
