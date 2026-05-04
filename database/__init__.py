"""
Database module for Kessler satellite tracking application.

This module provides a unified interface for all database operations,
organized into focused submodules:
- connection: Database connection and initialization
- operations: CRUD operations and queries
- transformations: Data canonicalization and transformation
- graph_operations: Graph database operations
- mqtt_config: MQTT configuration management
- utils: Utility functions (field utils, normalization)
"""

# Connection functions
from database.connection import (
    ARANGO_HOST,
    ARANGO_USER,
    ARANGO_PASSWORD,
    DB_NAME,
    COLLECTION_NAME,
    GRAPH_NAME,
    EDGE_COLLECTION_CONSTELLATION,
    EDGE_COLLECTION_REGISTRATION,
    EDGE_COLLECTION_PROXIMITY,
    EDGE_COLLECTION_COLLISION_RISK,
    EDGE_COLLECTION_SATELLITE_LINEAGE,
    COLLECTION_REG_DOCS,
    COLLECTION_OBSERVATIONS,
    COLLECTION_EPHEMERIS,
    PROVENANCE_GRAPH_NAME,
    COLLECTION_FRAGMENTATION_EVENTS,
    COLLECTION_LAUNCH_EVENTS,
    COLLECTION_LAUNCH_VEHICLES,
    COLLECTION_LAUNCH_SITES,
    COLLECTION_ENTITIES,
    EDGE_COLLECTION_FRAGMENTED_FROM,
    EDGE_COLLECTION_CAUSED_BY,
    EDGE_COLLECTION_LAUNCHED_BY,
    EDGE_COLLECTION_LAUNCHED_VIA,
    EDGE_COLLECTION_LAUNCHED_FROM,
    client,
    db,
    satellites_collection,
    objects_collection,
    connect_arangodb,
    connect_mongodb,  # Backward compatibility alias
    disconnect_arangodb,
    disconnect_mongodb,  # Backward compatibility alias
    get_objects_collection,
    get_satellites_collection,
)

# Operations functions
from database.operations import (
    create_satellite_document,
    find_satellite,
    search_satellites,
    count_satellites,
    get_all_countries,
    get_all_statuses,
    get_all_orbital_bands,
    get_all_congestion_risks,
    get_all_object_types,
    get_all_object_classes,
    clear_collection,
    update_satellite_tle,
)

# Transformation functions
from database.transformations import (
    record_transformation,
    update_canonical,
)

# Graph operations
from database.graph_operations import (
    create_edge_collection,
    create_document_collection,
    create_graph,
    get_edge_collection,
    insert_edge,
    bulk_insert_edges,
    clear_edge_collection,
    get_graph,
    add_edge_indexes,
)

# Graph analytics
from database.graph_analytics import (
    find_shortest_path,
    find_all_paths,
    calculate_degree_centrality,
    traverse_graph,
    get_neighbors,
    count_edges_by_type,
    find_connected_components,
)

# MQTT configuration
from database.mqtt_config import (
    MQTT_CONFIG_COLLECTION,
    get_mqtt_configurations_collection,
    save_mqtt_configuration,
    get_mqtt_configuration,
    delete_mqtt_configuration,
    get_enabled_mqtt_configurations,
    update_last_published,
)

# Ephemeris operations
from database.ephemeris_ops import (
    save_ephemeris_envelope,
    list_ephemeris_envelopes,
    count_ephemeris_envelopes,
    get_ephemeris_envelope,
    delete_ephemeris_envelope,
)

# Utility functions
from database.utils.field_utils import (
    get_nested_field,
    set_nested_field,
)

from database.utils.normalization import (
    CountryNormalizer,
)

# Backward compatibility: expose normalize_country function
def normalize_country(country):
    """
    Normalize country codes and names (backward compatibility wrapper).
    
    Args:
        country: Country code or name to normalize
        
    Returns:
        Normalized country code
    """
    normalizer = CountryNormalizer()
    return normalizer.normalize(country)


__all__ = [
    # Constants
    'ARANGO_HOST',
    'ARANGO_USER',
    'ARANGO_PASSWORD',
    'DB_NAME',
    'COLLECTION_NAME',
    'GRAPH_NAME',
    'EDGE_COLLECTION_CONSTELLATION',
    'EDGE_COLLECTION_REGISTRATION',
    'EDGE_COLLECTION_PROXIMITY',
    'EDGE_COLLECTION_COLLISION_RISK',
    'EDGE_COLLECTION_SATELLITE_LINEAGE',
    'COLLECTION_REG_DOCS',
    'COLLECTION_OBSERVATIONS',
    'COLLECTION_EPHEMERIS',
    'MQTT_CONFIG_COLLECTION',
    'PROVENANCE_GRAPH_NAME',
    'COLLECTION_FRAGMENTATION_EVENTS',
    'COLLECTION_LAUNCH_EVENTS',
    'COLLECTION_LAUNCH_VEHICLES',
    'COLLECTION_LAUNCH_SITES',
    'COLLECTION_ENTITIES',
    'EDGE_COLLECTION_FRAGMENTED_FROM',
    'EDGE_COLLECTION_CAUSED_BY',
    'EDGE_COLLECTION_LAUNCHED_BY',
    'EDGE_COLLECTION_LAUNCHED_VIA',
    'EDGE_COLLECTION_LAUNCHED_FROM',
    
    # Module-level variables
    'client',
    'db',
    'satellites_collection',
    'objects_collection',
    
    # Connection
    'connect_arangodb',
    'connect_mongodb',
    'disconnect_arangodb',
    'disconnect_mongodb',
    'get_objects_collection',
    'get_satellites_collection',
    
    # Operations
    'create_satellite_document',
    'find_satellite',
    'search_satellites',
    'count_satellites',
    'get_all_countries',
    'get_all_statuses',
    'get_all_orbital_bands',
    'get_all_congestion_risks',
    'get_all_object_types',
    'get_all_object_classes',
    'clear_collection',
    'update_satellite_tle',
    
    # Transformations
    'record_transformation',
    'update_canonical',
    'normalize_country',
    
    # Graph operations
    'create_edge_collection',
    'create_document_collection',
    'create_graph',
    'get_edge_collection',
    'insert_edge',
    'bulk_insert_edges',
    'clear_edge_collection',
    'get_graph',
    'add_edge_indexes',
    
    # Graph analytics
    'find_shortest_path',
    'find_all_paths',
    'calculate_degree_centrality',
    'traverse_graph',
    'get_neighbors',
    'count_edges_by_type',
    'find_connected_components',
    
    # MQTT configuration
    'get_mqtt_configurations_collection',
    'save_mqtt_configuration',
    'get_mqtt_configuration',
    'delete_mqtt_configuration',
    'get_enabled_mqtt_configurations',
    'update_last_published',
    
    # Ephemeris operations
    'save_ephemeris_envelope',
    'list_ephemeris_envelopes',
    'count_ephemeris_envelopes',
    'get_ephemeris_envelope',
    'delete_ephemeris_envelope',

    # Utilities
    'get_nested_field',
    'set_nested_field',
    'CountryNormalizer',
]
