"""
Graph analytics module for advanced graph traversal and analysis.

This module provides helper functions for:
- Path finding (shortest path, all paths)
- Centrality calculations
- Community detection
- Graph traversal utilities
- Multi-edge type queries
"""
from typing import Optional, Dict, List, Any, Set
import datetime
import database.connection as db_conn
from database.connection import COLLECTION_NAME, EDGE_COLLECTION_COLLISION_RISK, EDGE_COLLECTION_SATELLITE_LINEAGE


def find_shortest_path(
    from_id: str,
    to_id: str,
    edge_types: Optional[List[str]] = None,
    max_depth: int = 10
) -> Optional[Dict[str, Any]]:
    """
    Find the shortest path between two satellites.
    
    Args:
        from_id: Source satellite document ID (e.g., "satellites/2025-206B")
        to_id: Target satellite document ID
        edge_types: Optional list of edge collection names to traverse
        max_depth: Maximum traversal depth
    
    Returns:
        Dictionary containing path information or None if no path found:
        {
            "vertices": [...],  # List of vertex documents
            "edges": [...],     # List of edge documents
            "distance": int     # Number of hops
        }
    """
    try:
        edge_collections = edge_types if edge_types else []
        
        if not edge_collections:
            from database.connection import (
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            )
            edge_collections = [
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            ]
        
        edge_clause = ", ".join(edge_collections)
        
        query = f"""
        FOR v, e, p IN 1..@max_depth ANY @from_id
            {edge_clause}
            FILTER v._id == @to_id
            LIMIT 1
            LET enriched_edges = (
                FOR edge IN p.edges
                RETURN MERGE(edge, {{relationship_type: PARSE_IDENTIFIER(edge).collection}})
            )
            LET edge_counts = (
                FOR edge IN enriched_edges
                COLLECT node_id = edge._from INTO g
                RETURN {{node_id: node_id, count: LENGTH(g)}}
            )
            LET edge_counts_to = (
                FOR edge IN enriched_edges
                COLLECT node_id = edge._to INTO g
                RETURN {{node_id: node_id, count: LENGTH(g)}}
            )
            LET hub_ids = UNION_DISTINCT(
                (FOR c IN edge_counts FILTER c.count > 1 RETURN c.node_id),
                (FOR c IN edge_counts_to FILTER c.count > 1 RETURN c.node_id)
            )
            LET enriched_vertices = (
                FOR vertex IN p.vertices
                RETURN MERGE(vertex, {{is_hub: vertex._id IN hub_ids}})
            )
            RETURN {{
                vertices: enriched_vertices,
                edges: enriched_edges,
                distance: LENGTH(p.edges)
            }}
        """
        
        cursor = db_conn.db.aql.execute(
            query,
            bind_vars={
                'from_id': from_id,
                'to_id': to_id,
                'max_depth': max_depth
            }
        )
        
        results = list(cursor)
        return results[0] if results else None
        
    except Exception as e:
        print(f"Error finding shortest path: {e}")
        return None


def find_all_paths(
    from_id: str,
    to_id: str,
    edge_types: Optional[List[str]] = None,
    max_depth: int = 5,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Find all paths between two satellites up to max_depth.
    
    Args:
        from_id: Source satellite document ID
        to_id: Target satellite document ID
        edge_types: Optional list of edge collection names to traverse
        max_depth: Maximum traversal depth
        limit: Maximum number of paths to return
    
    Returns:
        List of path dictionaries
    """
    try:
        edge_collections = edge_types if edge_types else []
        
        if not edge_collections:
            from database.connection import (
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            )
            edge_collections = [
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            ]
        
        edge_clause = ", ".join(edge_collections)
        
        query = f"""
        FOR v, e, p IN 1..@max_depth ANY @from_id
            {edge_clause}
            FILTER v._id == @to_id
            LIMIT @limit
            LET enriched_edges = (
                FOR edge IN p.edges
                RETURN MERGE(edge, {{relationship_type: PARSE_IDENTIFIER(edge).collection}})
            )
            LET edge_counts = (
                FOR edge IN enriched_edges
                COLLECT node_id = edge._from INTO g
                RETURN {{node_id: node_id, count: LENGTH(g)}}
            )
            LET edge_counts_to = (
                FOR edge IN enriched_edges
                COLLECT node_id = edge._to INTO g
                RETURN {{node_id: node_id, count: LENGTH(g)}}
            )
            LET hub_ids = UNION_DISTINCT(
                (FOR c IN edge_counts FILTER c.count > 1 RETURN c.node_id),
                (FOR c IN edge_counts_to FILTER c.count > 1 RETURN c.node_id)
            )
            LET enriched_vertices = (
                FOR vertex IN p.vertices
                RETURN MERGE(vertex, {{is_hub: vertex._id IN hub_ids}})
            )
            RETURN {{
                vertices: enriched_vertices,
                edges: enriched_edges,
                distance: LENGTH(p.edges)
            }}
        """
        
        cursor = db_conn.db.aql.execute(
            query,
            bind_vars={
                'from_id': from_id,
                'to_id': to_id,
                'max_depth': max_depth,
                'limit': limit
            }
        )
        
        return list(cursor)
        
    except Exception as e:
        print(f"Error finding all paths: {e}")
        return []


def calculate_degree_centrality(
    edge_types: Optional[List[str]] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Calculate degree centrality for satellites.
    
    Args:
        edge_types: Optional list of edge collections to consider
        limit: Maximum number of results to return
    
    Returns:
        List of satellites with their degree centrality scores
    """
    try:
        edge_collections = edge_types if edge_types else []
        
        if not edge_collections:
            from database.connection import (
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            )
            edge_collections = [
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            ]
        
        edge_clause = ", ".join(edge_collections)
        
        query = f"""
        FOR doc IN {COLLECTION_NAME}
            LET outbound_count = LENGTH(
                FOR v IN 1..1 OUTBOUND doc._id {edge_clause}
                RETURN v
            )
            LET inbound_count = LENGTH(
                FOR v IN 1..1 INBOUND doc._id {edge_clause}
                RETURN v
            )
            LET degree = outbound_count + inbound_count
            FILTER degree > 0
            SORT degree DESC
            LIMIT @limit
            RETURN {{
                _id: doc._id,
                identifier: doc.identifier,
                name: doc.canonical.name,
                degree: degree,
                inbound: inbound_count,
                outbound: outbound_count
            }}
        """
        
        cursor = db_conn.db.aql.execute(
            query,
            bind_vars={'limit': limit}
        )
        
        return list(cursor)
        
    except Exception as e:
        print(f"Error calculating degree centrality: {e}")
        return []


def traverse_graph(
    start_id: str,
    edge_types: Optional[List[str]] = None,
    direction: str = 'OUTBOUND',
    min_depth: int = 1,
    max_depth: int = 3,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Generic graph traversal function.
    
    Args:
        start_id: Starting vertex document ID
        edge_types: Optional list of edge collections to traverse
        direction: Traversal direction ('OUTBOUND', 'INBOUND', 'ANY')
        min_depth: Minimum traversal depth
        max_depth: Maximum traversal depth
        limit: Optional limit on results
    
    Returns:
        List of reached vertices with path information
    """
    try:
        edge_collections = edge_types if edge_types else []
        
        if not edge_collections:
            from database.connection import (
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            )
            edge_collections = [
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            ]
        
        edge_clause = ", ".join(edge_collections)
        
        limit_clause = f"LIMIT {limit}" if limit else ""
        
        query = f"""
        FOR v, e, p IN @min_depth..@max_depth {direction} @start_id
            {edge_clause}
            {limit_clause}
            RETURN {{
                vertex: v,
                edge: e,
                path: p,
                depth: LENGTH(p.vertices) - 1
            }}
        """
        
        cursor = db_conn.db.aql.execute(
            query,
            bind_vars={
                'start_id': start_id,
                'min_depth': min_depth,
                'max_depth': max_depth
            }
        )
        
        return list(cursor)
        
    except Exception as e:
        print(f"Error traversing graph: {e}")
        return []


def get_neighbors(
    vertex_id: str,
    edge_types: Optional[List[str]] = None,
    direction: str = 'ANY'
) -> List[Dict[str, Any]]:
    """
    Get direct neighbors of a vertex.
    
    Args:
        vertex_id: Vertex document ID
        edge_types: Optional list of edge collections
        direction: Traversal direction ('OUTBOUND', 'INBOUND', 'ANY')
    
    Returns:
        List of neighbor vertices with edge information
    """
    try:
        edge_collections = edge_types if edge_types else []
        
        if not edge_collections:
            from database.connection import (
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            )
            edge_collections = [
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            ]
        
        edge_clause = ", ".join(edge_collections)
        
        query = f"""
        FOR v, e IN 1..1 {direction} @vertex_id
            {edge_clause}
            RETURN {{
                vertex: v,
                edge: e,
                edge_type: PARSE_IDENTIFIER(e).collection
            }}
        """
        
        cursor = db_conn.db.aql.execute(
            query,
            bind_vars={'vertex_id': vertex_id}
        )
        
        return list(cursor)
        
    except Exception as e:
        print(f"Error getting neighbors: {e}")
        return []


def count_edges_by_type(vertex_id: str) -> Dict[str, int]:
    """
    Count edges by type for a given vertex.
    
    Args:
        vertex_id: Vertex document ID
    
    Returns:
        Dictionary mapping edge collection names to counts
    """
    try:
        from database.connection import (
            EDGE_COLLECTION_CONSTELLATION,
            EDGE_COLLECTION_REGISTRATION,
            EDGE_COLLECTION_PROXIMITY
        )
        
        edge_collections = [
            EDGE_COLLECTION_CONSTELLATION,
            EDGE_COLLECTION_REGISTRATION,
            EDGE_COLLECTION_PROXIMITY
        ]
        
        counts = {}
        for edge_collection in edge_collections:
            query = f"""
            LET outbound = LENGTH(
                FOR v IN 1..1 OUTBOUND @vertex_id {edge_collection}
                RETURN v
            )
            LET inbound = LENGTH(
                FOR v IN 1..1 INBOUND @vertex_id {edge_collection}
                RETURN v
            )
            RETURN {{
                outbound: outbound,
                inbound: inbound,
                total: outbound + inbound
            }}
            """
            
            cursor = db_conn.db.aql.execute(
                query,
                bind_vars={'vertex_id': vertex_id}
            )
            
            result = list(cursor)[0]
            counts[edge_collection] = result
        
        return counts
        
    except Exception as e:
        print(f"Error counting edges by type: {e}")
        return {}


def calculate_betweenness_centrality(
    edge_types: Optional[List[str]] = None,
    limit: int = 100,
    sample_size: int = 100
) -> List[Dict[str, Any]]:
    """
    Calculate betweenness centrality for satellites.
    
    Betweenness centrality measures how often a node appears on shortest paths
    between other nodes. Higher scores indicate nodes that serve as bridges
    in the network.
    
    Optimized to use K_SHORTEST_PATHS for better performance.
    
    Args:
        edge_types: Optional list of edge collections to consider
        limit: Maximum number of results to return
        sample_size: Number of nodes to sample for path calculations
    
    Returns:
        List of satellites with their betweenness centrality scores
    """
    try:
        edge_collections = edge_types if edge_types else []
        
        if not edge_collections:
            from database.connection import (
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            )
            edge_collections = [
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            ]
        
        edge_clause = ", ".join(edge_collections)
        
        query = f"""
        LET sample_nodes = (
            FOR doc IN {COLLECTION_NAME}
                SORT RAND()
                LIMIT @sample_size
                RETURN doc._id
        )
        
        LET path_computations = (
            FOR source IN sample_nodes
                FOR target IN sample_nodes
                    FILTER source != target
                    LET shortest_path = FIRST(
                        FOR v, e IN OUTBOUND 
                            K_SHORTEST_PATHS source TO target
                            {edge_clause}
                            OPTIONS {{weightAttribute: null, defaultWeight: 1}}
                            LIMIT 1
                            RETURN {{vertices: v[*]._id}}
                    )
                    FILTER shortest_path != null
                    RETURN shortest_path
        )
        
        FOR node IN {COLLECTION_NAME}
            LET betweenness = LENGTH(
                FOR path IN path_computations
                    FILTER node._id IN path.vertices AND 
                           path.vertices[0] != node._id AND 
                           path.vertices[-1] != node._id
                    RETURN 1
            )
            FILTER betweenness > 0
            SORT betweenness DESC
            LIMIT @limit
            RETURN {{
                _id: node._id,
                identifier: node.identifier,
                name: node.canonical.name,
                betweenness_centrality: betweenness,
                normalized_score: betweenness / (@sample_size * (@sample_size - 1))
            }}
        """
        
        cursor = db_conn.db.aql.execute(
            query,
            bind_vars={
                'limit': limit,
                'sample_size': sample_size
            }
        )
        
        return list(cursor)
        
    except Exception as e:
        print(f"Error calculating betweenness centrality: {e}")
        return []


def calculate_closeness_centrality(
    edge_types: Optional[List[str]] = None,
    limit: int = 100,
    max_depth: int = 5
) -> List[Dict[str, Any]]:
    """
    Calculate closeness centrality for satellites.
    
    Closeness centrality measures how close a node is to all other nodes
    in the network. Higher scores indicate nodes that can reach others quickly.
    
    Optimized to reduce redundant calculations with COLLECT AGGREGATE.
    
    Args:
        edge_types: Optional list of edge collections to consider
        limit: Maximum number of results to return
        max_depth: Maximum depth for reachability calculations
    
    Returns:
        List of satellites with their closeness centrality scores
    """
    try:
        edge_collections = edge_types if edge_types else []
        
        if not edge_collections:
            from database.connection import (
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            )
            edge_collections = [
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            ]
        
        edge_clause = ", ".join(edge_collections)
        
        query = f"""
        FOR node IN {COLLECTION_NAME}
            LET distances = (
                FOR v, e, p IN 1..@max_depth ANY node._id
                    {edge_clause}
                    COLLECT vertex = v._id 
                    AGGREGATE min_distance = MIN(LENGTH(p.vertices) - 1)
                    RETURN min_distance
            )
            LET reachable_count = LENGTH(distances)
            FILTER reachable_count > 0
            LET total_distance = SUM(distances)
            LET closeness = reachable_count / total_distance
            SORT closeness DESC
            LIMIT @limit
            RETURN {{
                _id: node._id,
                identifier: node.identifier,
                name: node.canonical.name,
                closeness_centrality: closeness,
                reachable_nodes: reachable_count,
                avg_distance: total_distance / reachable_count
            }}
        """
        
        cursor = db_conn.db.aql.execute(
            query,
            bind_vars={
                'limit': limit,
                'max_depth': max_depth
            }
        )
        
        return list(cursor)
        
    except Exception as e:
        print(f"Error calculating closeness centrality: {e}")
        return []


def find_connected_components(
    edge_types: Optional[List[str]] = None,
    min_component_size: int = 2
) -> List[Dict[str, Any]]:
    """
    Find connected components in the graph.
    
    Args:
        edge_types: Optional list of edge collections
        min_component_size: Minimum size for a component to be included
    
    Returns:
        List of components with their members
    """
    try:
        edge_collections = edge_types if edge_types else []
        
        if not edge_collections:
            from database.connection import (
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            )
            edge_collections = [
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            ]
        
        edge_clause = ", ".join(edge_collections)
        
        query = f"""
        FOR doc IN {COLLECTION_NAME}
            LET component = (
                FOR v IN 0..100 ANY doc._id {edge_clause}
                RETURN DISTINCT v._id
            )
            FILTER LENGTH(component) >= @min_size
            COLLECT components = component
            RETURN {{
                size: LENGTH(components),
                members: components
            }}
        """
        
        cursor = db_conn.db.aql.execute(
            query,
            bind_vars={'min_size': min_component_size}
        )
        
        return list(cursor)
        
    except Exception as e:
        print(f"Error finding connected components: {e}")
        return []


def get_collision_risk_neighbors(
    satellite_id: str,
    risk_threshold: float = 0.5,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Get satellites with collision risk to a specific satellite.
    
    Args:
        satellite_id: Satellite document ID
        risk_threshold: Minimum risk score threshold
        limit: Maximum number of results
    
    Returns:
        List of satellites with collision risk information
    """
    try:
        if "/" not in satellite_id:
            satellite_id = f"{COLLECTION_NAME}/{satellite_id}"
        
        query = f"""
        FOR v, e IN 1..1 ANY @satellite_id {EDGE_COLLECTION_COLLISION_RISK}
            FILTER e.risk_score >= @risk_threshold
            SORT e.risk_score DESC
            LIMIT @limit
            RETURN {{
                satellite: v,
                edge: e,
                risk_score: e.risk_score,
                risk_level: e.risk_level,
                orbital_band: e.orbital_band,
                differences: {{
                    apogee_km: e.apogee_diff_km,
                    perigee_km: e.perigee_diff_km,
                    inclination_degrees: e.inclination_diff_degrees
                }}
            }}
        """
        
        cursor = db_conn.db.aql.execute(
            query,
            bind_vars={
                'satellite_id': satellite_id,
                'risk_threshold': risk_threshold,
                'limit': limit
            }
        )
        
        return list(cursor)
        
    except Exception as e:
        print(f"Error getting collision risk neighbors: {e}")
        return []


def analyze_collision_clusters(
    orbital_band: Optional[str] = None,
    risk_threshold: float = 0.7,
    min_cluster_size: int = 3
) -> List[Dict[str, Any]]:
    """
    Identify clusters of satellites with high collision risk.
    
    Args:
        orbital_band: Optional filter by orbital band
        risk_threshold: Minimum risk score to consider
        min_cluster_size: Minimum number of satellites in a cluster
    
    Returns:
        List of collision risk clusters
    """
    try:
        bind_vars = {
            'risk_threshold': risk_threshold,
            'min_cluster_size': min_cluster_size
        }
        
        band_filter = ""
        if orbital_band:
            band_filter = "FILTER edge.orbital_band == @orbital_band"
            bind_vars['orbital_band'] = orbital_band
        
        query = f"""
        LET high_risk_edges = (
            FOR edge IN {EDGE_COLLECTION_COLLISION_RISK}
                {band_filter}
                FILTER edge.risk_score >= @risk_threshold
                RETURN edge
        )
        
        FOR doc IN {COLLECTION_NAME}
            LET cluster_satellites = (
                FOR v, e IN 1..2 ANY doc._id {EDGE_COLLECTION_COLLISION_RISK}
                    FILTER e.risk_score >= @risk_threshold
                    {band_filter.replace('edge.', 'e.')}
                    RETURN DISTINCT v
            )
            FILTER LENGTH(cluster_satellites) >= @min_cluster_size
            
            LET cluster_edges = (
                FOR edge IN high_risk_edges
                    FILTER edge._from IN cluster_satellites[*]._id OR edge._to IN cluster_satellites[*]._id
                    RETURN edge
            )
            
            RETURN {{
                center_satellite: {{
                    _id: doc._id,
                    identifier: doc.identifier,
                    name: doc.canonical.name,
                    orbital_band: doc.canonical.orbital_band
                }},
                cluster_size: LENGTH(cluster_satellites),
                satellites: cluster_satellites,
                internal_edges: LENGTH(cluster_edges),
                avg_risk_score: AVERAGE(cluster_edges[*].risk_score),
                max_risk_score: MAX(cluster_edges[*].risk_score)
            }}
        """
        
        cursor = db_conn.db.aql.execute(query, bind_vars=bind_vars)
        return list(cursor)
        
    except Exception as e:
        print(f"Error analyzing collision clusters: {e}")
        return []


def find_cross_constellation_proximity(
    limit: int = 100,
    proximity_threshold: float = 0.7
) -> Dict[str, Any]:
    """
    Find satellites from different constellations that are in orbital proximity.
    
    This demonstrates multi-dimensional graph traversal combining:
    - Constellation membership edges
    - Orbital proximity edges
    
    Args:
        limit: Maximum number of satellite pairs to return
        proximity_threshold: Minimum proximity score
    
    Returns:
        Dictionary containing nodes and edges showing cross-constellation proximity
    """
    try:
        from database.connection import (
            EDGE_COLLECTION_CONSTELLATION,
            EDGE_COLLECTION_PROXIMITY
        )
        
        query = f"""
        LET proximity_pairs = (
            FOR edge IN {EDGE_COLLECTION_PROXIMITY}
                FILTER edge.proximity_score >= @proximity_threshold
                LIMIT @limit * 2
                
                LET sat_from = DOCUMENT(edge._from)
                LET sat_to = DOCUMENT(edge._to)
                
                FILTER sat_from.canonical.constellation != null
                FILTER sat_to.canonical.constellation != null
                FILTER sat_from.canonical.constellation != sat_to.canonical.constellation
                
                RETURN {{
                    sat_from: sat_from,
                    sat_to: sat_to,
                    edge: edge
                }}
        )
        
        LET limited_pairs = SLICE(proximity_pairs, 0, @limit)
        
        LET satellite_ids = UNIQUE(FLATTEN(
            FOR pair IN limited_pairs
                RETURN [pair.sat_from._id, pair.sat_to._id]
        ))
        
        LET nodes = (
            FOR sat_id IN satellite_ids
                LET sat = DOCUMENT(sat_id)
                RETURN {{
                    id: sat._id,
                    key: sat._key,
                    identifier: sat.identifier,
                    name: sat.canonical.name,
                    constellation: sat.canonical.constellation,
                    country: sat.canonical.country_of_origin,
                    orbital_band: sat.canonical.orbital_band,
                    apogee_km: sat.canonical.orbit.apogee_km,
                    perigee_km: sat.canonical.orbit.perigee_km
                }}
        )
        
        LET edges = (
            FOR pair IN limited_pairs
                RETURN {{
                    id: pair.edge._key,
                    source: pair.edge._from,
                    target: pair.edge._to,
                    proximity_score: pair.edge.proximity_score,
                    constellation_from: pair.sat_from.canonical.constellation,
                    constellation_to: pair.sat_to.canonical.constellation,
                    orbital_band: pair.edge.orbital_band,
                    edge_type: "cross_constellation_proximity"
                }}
        )
        
        LET constellation_stats = (
            FOR edge IN edges
                COLLECT pair = CONCAT(edge.constellation_from, " <-> ", edge.constellation_to) 
                WITH COUNT INTO pair_count
                SORT pair_count DESC
                LIMIT 20
                RETURN {{
                    constellation_pair: pair,
                    proximity_count: pair_count
                }}
        )
        
        RETURN {{
            nodes: nodes,
            edges: edges,
            stats: {{
                total_satellites: LENGTH(nodes),
                total_proximity_pairs: LENGTH(edges),
                constellation_pairs: LENGTH(constellation_stats),
                top_constellation_pairs: constellation_stats
            }}
        }}
        """
        
        cursor = db_conn.db.aql.execute(
            query,
            bind_vars={
                'limit': limit,
                'proximity_threshold': proximity_threshold
            }
        )
        
        results = list(cursor)
        return results[0] if results else {}
        
    except Exception as e:
        print(f"Error finding cross-constellation proximity: {e}")
        return {}


def find_country_cooperation_network(
    limit: int = 50,
    min_shared_satellites: int = 2
) -> Dict[str, Any]:
    """
    Find countries that cooperate through multiple relationship types.
    
    This demonstrates multi-dimensional analysis combining:
    - Shared registration documents
    - Satellites in orbital proximity
    - Constellation membership
    
    Args:
        limit: Maximum number of country pairs to return
        min_shared_satellites: Minimum number of shared satellites/connections
    
    Returns:
        Dictionary containing country cooperation network data
    """
    try:
        from database.connection import (
            EDGE_COLLECTION_CONSTELLATION,
            EDGE_COLLECTION_REGISTRATION,
            EDGE_COLLECTION_PROXIMITY,
            COLLECTION_REG_DOCS
        )
        
        query = f"""
        LET country_pairs = (
            FOR doc IN {COLLECTION_REG_DOCS}
                FILTER LENGTH(doc.countries) >= 2
                
                FOR country1 IN doc.countries
                    FOR country2 IN doc.countries
                        FILTER country1 < country2
                        
                        LET satellites_country1 = (
                            FOR v IN 1..1 INBOUND doc._id {EDGE_COLLECTION_REGISTRATION}
                                FILTER v.canonical.country_of_origin == country1
                                RETURN v._id
                        )
                        
                        LET satellites_country2 = (
                            FOR v IN 1..1 INBOUND doc._id {EDGE_COLLECTION_REGISTRATION}
                                FILTER v.canonical.country_of_origin == country2
                                RETURN v._id
                        )
                        
                        FILTER LENGTH(satellites_country1) > 0 AND LENGTH(satellites_country2) > 0
                        
                        LET proximity_connections = LENGTH(
                            FOR edge IN {EDGE_COLLECTION_PROXIMITY}
                                FILTER edge._from IN satellites_country1 AND edge._to IN satellites_country2
                                    OR edge._from IN satellites_country2 AND edge._to IN satellites_country1
                                RETURN 1
                        )
                        
                        RETURN {{
                            country1: country1,
                            country2: country2,
                            shared_document: doc._key,
                            satellites_country1: LENGTH(satellites_country1),
                            satellites_country2: LENGTH(satellites_country2),
                            proximity_connections: proximity_connections,
                            cooperation_score: LENGTH(satellites_country1) + LENGTH(satellites_country2) + proximity_connections
                        }}
        )
        
        LET aggregated_pairs = (
            FOR pair IN country_pairs
                COLLECT 
                    c1 = pair.country1, 
                    c2 = pair.country2 
                AGGREGATE 
                    total_shared_docs = LENGTH(pair),
                    total_satellites_c1 = SUM(pair.satellites_country1),
                    total_satellites_c2 = SUM(pair.satellites_country2),
                    total_proximity = SUM(pair.proximity_connections),
                    total_cooperation_score = SUM(pair.cooperation_score)
                
                FILTER total_shared_docs >= @min_shared_satellites 
                    OR total_proximity > 0
                
                SORT total_cooperation_score DESC
                LIMIT @limit
                
                RETURN {{
                    country1: c1,
                    country2: c2,
                    shared_documents: total_shared_docs,
                    satellites_country1: total_satellites_c1,
                    satellites_country2: total_satellites_c2,
                    proximity_connections: total_proximity,
                    cooperation_score: total_cooperation_score,
                    cooperation_types: {{
                        shared_registration: total_shared_docs > 0,
                        orbital_proximity: total_proximity > 0
                    }}
                }}
        )
        
        LET country_nodes = UNIQUE(FLATTEN(
            FOR pair IN aggregated_pairs
                RETURN [pair.country1, pair.country2]
        ))
        
        LET nodes = (
            FOR country IN country_nodes
                LET satellite_count = LENGTH(
                    FOR sat IN {COLLECTION_NAME}
                        FILTER sat.canonical.country_of_origin == country
                        RETURN 1
                )
                RETURN {{
                    id: country,
                    name: country,
                    type: "country",
                    satellite_count: satellite_count
                }}
        )
        
        LET edges = (
            FOR pair IN aggregated_pairs
                RETURN {{
                    id: CONCAT(pair.country1, "_to_", pair.country2),
                    source: pair.country1,
                    target: pair.country2,
                    shared_documents: pair.shared_documents,
                    proximity_connections: pair.proximity_connections,
                    cooperation_score: pair.cooperation_score,
                    cooperation_types: pair.cooperation_types,
                    edge_type: "country_cooperation"
                }}
        )
        
        RETURN {{
            nodes: nodes,
            edges: edges,
            stats: {{
                total_countries: LENGTH(nodes),
                total_cooperation_pairs: LENGTH(edges),
                avg_cooperation_score: AVERAGE(edges[*].cooperation_score),
                max_cooperation_score: MAX(edges[*].cooperation_score)
            }}
        }}
        """
        
        cursor = db_conn.db.aql.execute(
            query,
            bind_vars={
                'limit': limit,
                'min_shared_satellites': min_shared_satellites
            }
        )
        
        results = list(cursor)
        return results[0] if results else {}
        
    except Exception as e:
        print(f"Error finding country cooperation network: {e}")
        return {}


def find_function_based_clusters(
    orbital_band: Optional[str] = None,
    limit: int = 20,
    min_cluster_size: int = 3
) -> Dict[str, Any]:
    """
    Find satellite clusters based on shared function, orbital band, and proximity.
    
    This demonstrates multi-dimensional clustering combining:
    - Similar satellite functions
    - Same orbital band
    - Orbital proximity relationships
    
    Args:
        orbital_band: Optional filter by specific orbital band
        limit: Maximum number of clusters to return
        min_cluster_size: Minimum satellites in a cluster
    
    Returns:
        Dictionary containing function-based clusters
    """
    try:
        from database.connection import EDGE_COLLECTION_PROXIMITY
        
        band_filter = ""
        bind_vars = {
            'limit': limit,
            'min_cluster_size': min_cluster_size
        }
        
        if orbital_band:
            band_filter = "FILTER sat.canonical.orbital_band == @orbital_band"
            bind_vars['orbital_band'] = orbital_band
        
        query = f"""
        LET function_groups = (
            FOR sat IN {COLLECTION_NAME}
                FILTER sat.canonical.function != null
                {band_filter}
                COLLECT 
                    func = sat.canonical.function,
                    band = sat.canonical.orbital_band
                INTO group
                
                LET satellites = group[*].sat
                FILTER LENGTH(satellites) >= @min_cluster_size
                
                LET proximity_edges = (
                    FOR edge IN {EDGE_COLLECTION_PROXIMITY}
                        FILTER edge._from IN satellites[*]._id 
                            AND edge._to IN satellites[*]._id
                        RETURN edge
                )
                
                LET internal_proximity = LENGTH(proximity_edges)
                LET density = internal_proximity > 0 
                    ? internal_proximity / (LENGTH(satellites) * (LENGTH(satellites) - 1) / 2) 
                    : 0
                
                FILTER internal_proximity > 0
                
                SORT density DESC, LENGTH(satellites) DESC
                LIMIT @limit
                
                RETURN {{
                    function: func,
                    orbital_band: band,
                    satellites: satellites,
                    cluster_size: LENGTH(satellites),
                    internal_proximity_edges: internal_proximity,
                    density: density,
                    countries: UNIQUE(satellites[*].canonical.country_of_origin),
                    constellations: UNIQUE(
                        FOR s IN satellites
                            FILTER s.canonical.constellation != null
                            RETURN s.canonical.constellation
                    )
                }}
        )
        
        LET all_satellite_ids = UNIQUE(FLATTEN(
            FOR cluster IN function_groups
                RETURN cluster.satellites[*]._id
        ))
        
        LET nodes = (
            FOR sat_id IN all_satellite_ids
                LET sat = DOCUMENT(sat_id)
                RETURN {{
                    id: sat._id,
                    key: sat._key,
                    identifier: sat.identifier,
                    name: sat.canonical.name,
                    function: sat.canonical.function,
                    orbital_band: sat.canonical.orbital_band,
                    country: sat.canonical.country_of_origin,
                    constellation: sat.canonical.constellation
                }}
        )
        
        LET edges = FLATTEN(
            FOR cluster IN function_groups
                FOR edge IN {EDGE_COLLECTION_PROXIMITY}
                    FILTER edge._from IN cluster.satellites[*]._id 
                        AND edge._to IN cluster.satellites[*]._id
                    RETURN {{
                        id: edge._key,
                        source: edge._from,
                        target: edge._to,
                        proximity_score: edge.proximity_score,
                        function_cluster: cluster.function,
                        orbital_band: cluster.orbital_band,
                        edge_type: "function_cluster_proximity"
                    }}
        )
        
        LET clusters = (
            FOR cluster IN function_groups
                RETURN {{
                    function: cluster.function,
                    orbital_band: cluster.orbital_band,
                    size: cluster.cluster_size,
                    density: cluster.density,
                    countries: cluster.countries,
                    country_count: LENGTH(cluster.countries),
                    constellations: cluster.constellations,
                    constellation_count: LENGTH(cluster.constellations)
                }}
        )
        
        RETURN {{
            nodes: nodes,
            edges: edges,
            clusters: clusters,
            stats: {{
                total_clusters: LENGTH(clusters),
                total_satellites: LENGTH(nodes),
                total_proximity_edges: LENGTH(edges),
                avg_cluster_size: AVERAGE(clusters[*].size),
                avg_density: AVERAGE(clusters[*].density)
            }}
        }}
        """
        
        cursor = db_conn.db.aql.execute(query, bind_vars=bind_vars)
        
        results = list(cursor)
        return results[0] if results else {}
        
    except Exception as e:
        print(f"Error finding function-based clusters: {e}")
        return {}


def traverse_lineage_tree(
    satellite_id: str,
    direction: str = "ANY",
    max_depth: int = 5
) -> List[Dict[str, Any]]:
    """
    Traverse satellite lineage tree (ancestors and/or descendants).
    
    Args:
        satellite_id: Starting satellite document ID
        direction: "OUTBOUND" (descendants), "INBOUND" (ancestors), or "ANY" (both)
        max_depth: Maximum traversal depth
    
    Returns:
        List of related satellites with lineage edge information
    """
    try:
        if "/" not in satellite_id:
            satellite_id = f"{COLLECTION_NAME}/{satellite_id}"
        
        query = f"""
        FOR v, e, p IN 1..@max_depth {direction} @satellite_id
            {EDGE_COLLECTION_SATELLITE_LINEAGE}
            RETURN {{
                satellite: {{
                    _id: v._id,
                    identifier: v.identifier,
                    name: v.canonical.name,
                    manufacturer: v.canonical.manufacturer,
                    launch_date: v.canonical.date_of_launch,
                    orbital_band: v.canonical.orbital_band
                }},
                edge: {{
                    relationship_type: e.relationship_type,
                    family_name: e.family_name,
                    generation_from: e.generation_from,
                    generation_to: e.generation_to,
                    generation_gap: e.generation_gap
                }},
                depth: LENGTH(p.vertices) - 1,
                path: {{
                    vertices: p.vertices,
                    edges: p.edges
                }}
            }}
        """
        
        cursor = db_conn.db.aql.execute(
            query,
            bind_vars={
                "satellite_id": satellite_id,
                "max_depth": max_depth
            }
        )
        
        return list(cursor)
        
    except Exception as e:
        print(f"Error traversing lineage tree: {e}")
        return []


def get_lineage_neighbors(
    satellite_id: str,
    relationship_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get direct lineage neighbors (immediate predecessors and successors).
    
    Args:
        satellite_id: Satellite document ID
        relationship_type: Optional filter for relationship type
    
    Returns:
        List of directly connected satellites in lineage graph
    """
    try:
        if "/" not in satellite_id:
            satellite_id = f"{COLLECTION_NAME}/{satellite_id}"
        
        filter_clause = ""
        bind_vars = {"satellite_id": satellite_id}
        
        if relationship_type:
            filter_clause = "FILTER e.relationship_type == @relationship_type"
            bind_vars["relationship_type"] = relationship_type
        
        query = f"""
        FOR v, e IN 1..1 ANY @satellite_id
            {EDGE_COLLECTION_SATELLITE_LINEAGE}
            {filter_clause}
            RETURN {{
                satellite: {{
                    _id: v._id,
                    identifier: v.identifier,
                    name: v.canonical.name,
                    manufacturer: v.canonical.manufacturer
                }},
                edge: {{
                    relationship_type: e.relationship_type,
                    family_name: e.family_name,
                    generation_from: e.generation_from,
                    generation_to: e.generation_to
                }},
                direction: e._from == @satellite_id ? "successor" : "predecessor"
            }}
        """
        
        cursor = db_conn.db.aql.execute(query, bind_vars=bind_vars)
        return list(cursor)
        
    except Exception as e:
        print(f"Error getting lineage neighbors: {e}")
        return []


def find_satellite_generation(satellite_id: str) -> Optional[Dict[str, Any]]:
    """
    Find satellite's generation within its family.
    
    Args:
        satellite_id: Satellite document ID
    
    Returns:
        Dictionary with generation information or None
    """
    try:
        if "/" not in satellite_id:
            satellite_id = f"{COLLECTION_NAME}/{satellite_id}"
        
        query = f"""
        LET sat = DOCUMENT(@satellite_id)
        
        LET predecessors = (
            FOR v, e IN 1..10 INBOUND @satellite_id
                {EDGE_COLLECTION_SATELLITE_LINEAGE}
                RETURN e
        )
        
        LET successors = (
            FOR v, e IN 1..10 OUTBOUND @satellite_id
                {EDGE_COLLECTION_SATELLITE_LINEAGE}
                RETURN e
        )
        
        LET family_name = FIRST(
            FOR e IN APPEND(predecessors, successors)
                FILTER e.family_name != null
                RETURN e.family_name
        )
        
        RETURN {{
            satellite: {{
                _id: sat._id,
                identifier: sat.identifier,
                name: sat.canonical.name
            }},
            family_name: family_name,
            predecessor_count: LENGTH(predecessors),
            successor_count: LENGTH(successors),
            is_root: LENGTH(predecessors) == 0,
            is_leaf: LENGTH(successors) == 0
        }}
        """
        
        cursor = db_conn.db.aql.execute(
            query,
            bind_vars={"satellite_id": satellite_id}
        )
        
        results = list(cursor)
        return results[0] if results else None
        
    except Exception as e:
        print(f"Error finding satellite generation: {e}")
        return None


def get_lineage_family_members(family_name: str, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get all satellites in a specific family lineage.
    
    Args:
        family_name: Family name (e.g., "GPS", "IRIDIUM")
        limit: Maximum number of satellites to return
    
    Returns:
        List of satellites in the family
    """
    try:
        query = f"""
        LET family_edges = (
            FOR edge IN {EDGE_COLLECTION_SATELLITE_LINEAGE}
                FILTER edge.family_name == @family_name
                RETURN edge
        )
        
        LET satellite_ids = UNIQUE(FLATTEN(
            FOR edge IN family_edges
                RETURN [edge._from, edge._to]
        ))
        
        FOR sat_id IN satellite_ids
            LIMIT @limit
            LET sat = DOCUMENT(sat_id)
            
            LET generation = FIRST(
                FOR edge IN family_edges
                    FILTER edge._from == sat_id OR edge._to == sat_id
                    RETURN edge._from == sat_id ? edge.generation_from : edge.generation_to
            )
            
            RETURN {{
                _id: sat._id,
                identifier: sat.identifier,
                name: sat.canonical.name,
                manufacturer: sat.canonical.manufacturer,
                launch_date: sat.canonical.date_of_launch,
                orbital_band: sat.canonical.orbital_band,
                family_name: @family_name,
                generation: generation
            }}
        """
        
        cursor = db_conn.db.aql.execute(
            query,
            bind_vars={
                "family_name": family_name.upper(),
                "limit": limit
            }
        )
        
        return list(cursor)
        
    except Exception as e:
        print(f"Error getting lineage family members: {e}")
        return []


def detect_communities_label_propagation(
    edge_types: Optional[List[str]] = None,
    min_community_size: int = 2,
    max_iterations: int = 10,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Detect communities using label propagation algorithm.
    
    Label propagation is an efficient community detection algorithm where
    nodes iteratively adopt the most common label among their neighbors.
    
    Args:
        edge_types: Optional list of edge collections to consider
        min_community_size: Minimum size for a community to be included
        max_iterations: Maximum number of propagation iterations
        limit: Maximum number of communities to return
    
    Returns:
        List of communities with their members and statistics
    """
    try:
        edge_collections = edge_types if edge_types else []
        
        if not edge_collections:
            from database.connection import (
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            )
            edge_collections = [
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            ]
        
        edge_clause = ", ".join(edge_collections)
        
        query = f"""
        LET satellites = (
            FOR doc IN {COLLECTION_NAME}
                LIMIT 500
                RETURN doc
        )
        
        LET initial_labels = (
            FOR sat IN satellites
                RETURN {{
                    id: sat._id,
                    label: sat._id,
                    name: sat.canonical.name,
                    identifier: sat.identifier,
                    orbital_band: sat.canonical.orbital_band,
                    country: sat.canonical.country_of_origin
                }}
        )
        
        LET communities_raw = (
            FOR node IN initial_labels
                LET neighbors = (
                    FOR v, e IN 1..1 ANY node.id
                        {edge_clause}
                        RETURN v._id
                )
                
                FILTER LENGTH(neighbors) > 0
                
                LET community_label = FIRST(
                    FOR neighbor_id IN neighbors
                        LET neighbor = FIRST(
                            FOR n IN initial_labels
                                FILTER n.id == neighbor_id
                                RETURN n.label
                        )
                        FILTER neighbor != null
                        COLLECT label = neighbor WITH COUNT INTO label_count
                        SORT label_count DESC
                        LIMIT 1
                        RETURN label
                )
                
                RETURN {{
                    satellite_id: node.id,
                    satellite_name: node.name,
                    identifier: node.identifier,
                    orbital_band: node.orbital_band,
                    country: node.country,
                    community_label: community_label != null ? community_label : node.label
                }}
        )
        
        LET communities = (
            FOR member IN communities_raw
                COLLECT community_id = member.community_label 
                INTO group
                LET members = group[*].member
                FILTER LENGTH(members) >= @min_community_size
                
                LET member_ids = members[*].satellite_id
                LET internal_edges = LENGTH(
                    FOR edge IN (
                        FOR e_type IN [{edge_clause}]
                            FOR edge IN COLLECTION(e_type)
                                FILTER edge._from IN member_ids AND edge._to IN member_ids
                                RETURN edge
                    )
                    RETURN edge
                )
                
                LET orbital_bands = (
                    FOR member IN members
                        FILTER member.orbital_band != null
                        COLLECT band = member.orbital_band WITH COUNT INTO count
                        SORT count DESC
                        RETURN {{band: band, count: count}}
                )
                
                LET countries = (
                    FOR member IN members
                        FILTER member.country != null
                        COLLECT country = member.country WITH COUNT INTO count
                        SORT count DESC
                        RETURN {{country: country, count: count}}
                )
                
                SORT LENGTH(members) DESC
                LIMIT @limit
                
                RETURN {{
                    community_id: community_id,
                    size: LENGTH(members),
                    members: members,
                    internal_edges: internal_edges,
                    density: internal_edges / (LENGTH(members) * (LENGTH(members) - 1) / 2),
                    dominant_orbital_band: FIRST(orbital_bands),
                    orbital_band_distribution: orbital_bands,
                    country_distribution: countries,
                    algorithm: "label_propagation"
                }}
        )
        
        RETURN communities
        """
        
        cursor = db_conn.db.aql.execute(
            query,
            bind_vars={
                'min_community_size': min_community_size,
                'limit': limit
            }
        )
        
        results = list(cursor)
        return results[0] if results else []
        
    except Exception as e:
        print(f"Error detecting communities with label propagation: {e}")
        return []


def detect_communities(
    algorithm: str = "connected_components",
    edge_types: Optional[List[str]] = None,
    min_community_size: int = 2,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Detect communities in the satellite network using specified algorithm.
    
    Supports multiple community detection algorithms:
    - connected_components: Find isolated clusters of connected satellites
    - label_propagation: Iterative algorithm where nodes adopt neighbor labels
    
    Args:
        algorithm: Algorithm to use ("connected_components" or "label_propagation")
        edge_types: Optional list of edge collections to consider
        min_community_size: Minimum size for a community to be included
        **kwargs: Additional algorithm-specific parameters
    
    Returns:
        List of communities with members and statistics
    """
    try:
        if algorithm == "label_propagation":
            max_iterations = kwargs.get("max_iterations", 10)
            limit = kwargs.get("limit", 100)
            return detect_communities_label_propagation(
                edge_types=edge_types,
                min_community_size=min_community_size,
                max_iterations=max_iterations,
                limit=limit
            )
        elif algorithm == "connected_components":
            components = find_connected_components(
                edge_types=edge_types,
                min_component_size=min_community_size
            )
            
            enriched_components = []
            for idx, component in enumerate(components):
                member_ids = component.get("members", [])
                
                member_details = []
                for member_id in member_ids[:100]:
                    try:
                        sat = db_conn.db.collection(COLLECTION_NAME).get(member_id.split("/")[1])
                        if sat:
                            member_details.append({
                                "satellite_id": member_id,
                                "satellite_name": sat.get("canonical", {}).get("name"),
                                "identifier": sat.get("identifier"),
                                "orbital_band": sat.get("canonical", {}).get("orbital_band"),
                                "country": sat.get("canonical", {}).get("country_of_origin")
                            })
                    except:
                        pass
                
                orbital_bands = {}
                countries = {}
                for member in member_details:
                    band = member.get("orbital_band")
                    country = member.get("country")
                    if band:
                        orbital_bands[band] = orbital_bands.get(band, 0) + 1
                    if country:
                        countries[country] = countries.get(country, 0) + 1
                
                orbital_band_dist = [
                    {"band": k, "count": v}
                    for k, v in sorted(orbital_bands.items(), key=lambda x: x[1], reverse=True)
                ]
                
                country_dist = [
                    {"country": k, "count": v}
                    for k, v in sorted(countries.items(), key=lambda x: x[1], reverse=True)
                ]
                
                enriched_components.append({
                    "community_id": f"component_{idx}",
                    "size": component.get("size", 0),
                    "members": member_details,
                    "dominant_orbital_band": orbital_band_dist[0] if orbital_band_dist else None,
                    "orbital_band_distribution": orbital_band_dist,
                    "country_distribution": country_dist,
                    "algorithm": "connected_components"
                })
            
            return enriched_components
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")
            
    except Exception as e:
        print(f"Error detecting communities: {e}")
        return []


def get_graph_snapshot_by_date(
    target_date: str,
    edge_types: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Get graph snapshot statistics at a specific date.
    
    Args:
        target_date: Date in YYYY-MM-DD format or YYYY-MM or YYYY
        edge_types: Optional list of edge collections to consider
    
    Returns:
        Dictionary with node count, edge count, and density metrics
    """
    try:
        edge_collections = edge_types if edge_types else []
        
        if not edge_collections:
            from database.connection import (
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY,
                EDGE_COLLECTION_COLLISION_RISK,
                EDGE_COLLECTION_SATELLITE_LINEAGE
            )
            edge_collections = [
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY,
                EDGE_COLLECTION_COLLISION_RISK,
                EDGE_COLLECTION_SATELLITE_LINEAGE
            ]
        
        date_len = len(target_date)
        date_filter = ""
        
        if date_len == 4:
            date_filter = "STARTS_WITH(doc.canonical.date_of_launch, @target_date)"
        elif date_len == 7:
            date_filter = "STARTS_WITH(doc.canonical.date_of_launch, @target_date)"
        else:
            date_filter = "doc.canonical.date_of_launch <= @target_date"
        
        query = f"""
        LET satellites_at_date = (
            FOR doc IN {COLLECTION_NAME}
                FILTER doc.canonical.date_of_launch != null
                FILTER {date_filter}
                RETURN doc
        )
        
        LET node_count = LENGTH(satellites_at_date)
        LET satellite_ids = satellites_at_date[*]._id
        
        LET total_edges = SUM(
            FOR edge_collection IN @edge_collections
                LET edge_count = LENGTH(
                    FOR edge IN @@edge_collection_var
                        FILTER edge._from IN satellite_ids
                        FILTER edge._to IN satellite_ids
                        RETURN 1
                )
                RETURN edge_count
        )
        
        LET density = node_count > 1 ? total_edges / (node_count * (node_count - 1)) : 0
        
        RETURN {{
            date: @target_date,
            node_count: node_count,
            edge_count: total_edges,
            density: density,
            avg_degree: node_count > 0 ? (total_edges * 2) / node_count : 0
        }}
        """
        
        edge_counts = {}
        for edge_collection in edge_collections:
            count_query = f"""
            LET satellites_at_date = (
                FOR doc IN {COLLECTION_NAME}
                    FILTER doc.canonical.date_of_launch != null
                    FILTER {date_filter}
                    RETURN doc._id
            )
            
            RETURN LENGTH(
                FOR edge IN {edge_collection}
                    FILTER edge._from IN satellites_at_date
                    FILTER edge._to IN satellites_at_date
                    RETURN 1
            )
            """
            
            cursor = db_conn.db.aql.execute(
                count_query,
                bind_vars={'target_date': target_date}
            )
            edge_counts[edge_collection] = list(cursor)[0]
        
        satellite_query = f"""
        FOR doc IN {COLLECTION_NAME}
            FILTER doc.canonical.date_of_launch != null
            FILTER {date_filter}
            RETURN doc
        """
        
        cursor = db_conn.db.aql.execute(
            satellite_query,
            bind_vars={'target_date': target_date}
        )
        
        satellites = list(cursor)
        node_count = len(satellites)
        total_edges = sum(edge_counts.values())
        
        density = total_edges / (node_count * (node_count - 1)) if node_count > 1 else 0
        avg_degree = (total_edges * 2) / node_count if node_count > 0 else 0
        
        return {
            "date": target_date,
            "node_count": node_count,
            "edge_count": total_edges,
            "edge_counts_by_type": edge_counts,
            "density": density,
            "avg_degree": avg_degree
        }
        
    except Exception as e:
        print(f"Error getting graph snapshot: {e}")
        return {
            "date": target_date,
            "node_count": 0,
            "edge_count": 0,
            "edge_counts_by_type": {},
            "density": 0,
            "avg_degree": 0
        }


def calculate_graph_evolution_timeline(
    start_date: str,
    end_date: str,
    granularity: str = 'year',
    edge_types: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Calculate graph evolution metrics over a time period.
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        granularity: Time granularity ('year', 'month', 'quarter')
        edge_types: Optional list of edge collections to consider
    
    Returns:
        List of timeline snapshots with growth metrics
    """
    try:
        edge_collections = edge_types if edge_types else []
        
        if not edge_collections:
            from database.connection import (
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY,
                EDGE_COLLECTION_COLLISION_RISK,
                EDGE_COLLECTION_SATELLITE_LINEAGE
            )
            edge_collections = [
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY,
                EDGE_COLLECTION_COLLISION_RISK,
                EDGE_COLLECTION_SATELLITE_LINEAGE
            ]
        
        edge_clause = ", ".join(edge_collections)
        
        if granularity == 'year':
            start_year = int(start_date[:4])
            end_year = int(end_date[:4])
            date_periods = [str(year) for year in range(start_year, end_year + 1)]
        elif granularity == 'month':
            start = datetime.datetime.strptime(start_date[:7], '%Y-%m')
            end = datetime.datetime.strptime(end_date[:7], '%Y-%m')
            
            date_periods = []
            current = start
            while current <= end:
                date_periods.append(current.strftime('%Y-%m'))
                month = current.month + 1
                year = current.year
                if month > 12:
                    month = 1
                    year += 1
                current = datetime.datetime(year, month, 1)
        elif granularity == 'quarter':
            start_year = int(start_date[:4])
            end_year = int(end_date[:4])
            
            date_periods = []
            for year in range(start_year, end_year + 1):
                for quarter in range(1, 5):
                    date_periods.append(f"{year}-Q{quarter}")
        else:
            raise ValueError(f"Unknown granularity: {granularity}")
        
        timeline = []
        previous_snapshot = None
        
        for period in date_periods:
            if granularity == 'quarter':
                year, quarter = period.split('-Q')
                quarter_end_month = int(quarter) * 3
                period_date = f"{year}-{quarter_end_month:02d}"
            else:
                period_date = period
            
            snapshot = get_graph_snapshot_by_date(period_date, edge_types)
            
            if previous_snapshot:
                snapshot['node_growth'] = snapshot['node_count'] - previous_snapshot['node_count']
                snapshot['edge_growth'] = snapshot['edge_count'] - previous_snapshot['edge_count']
                snapshot['density_change'] = snapshot['density'] - previous_snapshot['density']
            else:
                snapshot['node_growth'] = snapshot['node_count']
                snapshot['edge_growth'] = snapshot['edge_count']
                snapshot['density_change'] = snapshot['density']
            
            snapshot['period'] = period
            timeline.append(snapshot)
            previous_snapshot = snapshot
        
        return timeline
        
    except Exception as e:
        print(f"Error calculating graph evolution timeline: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_temporal_network_metrics(
    date_ranges: List[tuple],
    edge_types: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Calculate network metrics across multiple time periods for comparison.
    
    Args:
        date_ranges: List of (start_date, end_date) tuples
        edge_types: Optional list of edge collections to consider
    
    Returns:
        Dictionary with comparative metrics across time periods
    """
    try:
        periods_data = []
        
        for start_date, end_date in date_ranges:
            snapshot = get_graph_snapshot_by_date(end_date, edge_types)
            snapshot['period_start'] = start_date
            snapshot['period_end'] = end_date
            periods_data.append(snapshot)
        
        return {
            "periods": periods_data,
            "summary": {
                "total_periods": len(periods_data),
                "avg_density": sum(p['density'] for p in periods_data) / len(periods_data) if periods_data else 0,
                "max_nodes": max(p['node_count'] for p in periods_data) if periods_data else 0,
                "max_edges": max(p['edge_count'] for p in periods_data) if periods_data else 0
            }
        }
        
    except Exception as e:
        print(f"Error calculating temporal network metrics: {e}")
        return {"periods": [], "summary": {}}


def calculate_jaccard_similarity(
    satellite_id: str,
    candidate_id: str,
    edge_types: Optional[List[str]] = None
) -> float:
    """
    Calculate Jaccard similarity between two satellites based on their neighbors.
    
    Jaccard similarity = |A ∩ B| / |A ∪ B|
    
    Args:
        satellite_id: First satellite document ID
        candidate_id: Second satellite document ID
        edge_types: Optional list of edge collections to consider
    
    Returns:
        Similarity score between 0 and 1
    """
    try:
        edge_collections = edge_types if edge_types else []
        
        if not edge_collections:
            from database.connection import (
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            )
            edge_collections = [
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            ]
        
        edge_clause = ", ".join(edge_collections)
        
        query = f"""
        LET neighbors_a = (
            FOR v IN 1..1 ANY @satellite_id {edge_clause}
            RETURN v._id
        )
        
        LET neighbors_b = (
            FOR v IN 1..1 ANY @candidate_id {edge_clause}
            RETURN v._id
        )
        
        LET intersection = LENGTH(
            FOR id IN neighbors_a
            FILTER id IN neighbors_b
            RETURN id
        )
        
        LET union = LENGTH(UNIQUE(APPEND(neighbors_a, neighbors_b)))
        
        RETURN union > 0 ? intersection / union : 0
        """
        
        cursor = db_conn.db.aql.execute(
            query,
            bind_vars={
                'satellite_id': satellite_id,
                'candidate_id': candidate_id
            }
        )
        
        results = list(cursor)
        return results[0] if results else 0.0
        
    except Exception as e:
        print(f"Error calculating Jaccard similarity: {e}")
        return 0.0


def get_similar_satellites(
    satellite_id: str,
    edge_types: Optional[List[str]] = None,
    limit: int = 10,
    min_similarity: float = 0.1
) -> List[Dict[str, Any]]:
    """
    Find satellites similar to the given satellite based on graph structure.
    
    Uses Jaccard similarity of neighbor sets to determine similarity.
    
    Args:
        satellite_id: Reference satellite document ID
        edge_types: Optional list of edge collections to consider
        limit: Maximum number of similar satellites to return
        min_similarity: Minimum similarity threshold (0-1)
    
    Returns:
        List of similar satellites with similarity scores
    """
    try:
        edge_collections = edge_types if edge_types else []
        
        if not edge_collections:
            from database.connection import (
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            )
            edge_collections = [
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            ]
        
        edge_clause = ", ".join(edge_collections)
        
        query = f"""
        LET source_neighbors = (
            FOR v IN 1..1 ANY @satellite_id {edge_clause}
            RETURN v._id
        )
        
        FOR candidate IN {COLLECTION_NAME}
            FILTER candidate._id != @satellite_id
            
            LET candidate_neighbors = (
                FOR v IN 1..1 ANY candidate._id {edge_clause}
                RETURN v._id
            )
            
            LET intersection = LENGTH(
                FOR id IN source_neighbors
                FILTER id IN candidate_neighbors
                RETURN id
            )
            
            LET union = LENGTH(UNIQUE(APPEND(source_neighbors, candidate_neighbors)))
            
            LET similarity = union > 0 ? intersection / union : 0
            
            FILTER similarity >= @min_similarity
            SORT similarity DESC
            LIMIT @limit
            
            RETURN {{
                _id: candidate._id,
                identifier: candidate.identifier,
                name: candidate.canonical.name,
                country: candidate.canonical.country_of_origin,
                orbital_band: candidate.canonical.orbital_band,
                similarity_score: similarity,
                common_neighbors: intersection,
                total_neighbors: LENGTH(candidate_neighbors)
            }}
        """
        
        cursor = db_conn.db.aql.execute(
            query,
            bind_vars={
                'satellite_id': satellite_id,
                'limit': limit,
                'min_similarity': min_similarity
            }
        )
        
        return list(cursor)
        
    except Exception as e:
        print(f"Error finding similar satellites: {e}")
        return []


def get_neighbor_based_recommendations(
    satellite_id: str,
    edge_types: Optional[List[str]] = None,
    limit: int = 10,
    strategy: str = "similar_neighbors"
) -> List[Dict[str, Any]]:
    """
    Get recommendations based on neighbor analysis.
    
    Strategies:
    - "similar_neighbors": Recommend neighbors of similar satellites
    - "second_degree": Recommend satellites at distance 2 (friends of friends)
    - "common_neighbors": Recommend satellites with most common neighbors
    
    Args:
        satellite_id: Reference satellite document ID
        edge_types: Optional list of edge collections
        limit: Maximum number of recommendations
        strategy: Recommendation strategy to use
    
    Returns:
        List of recommended satellites with relevance scores
    """
    try:
        edge_collections = edge_types if edge_types else []
        
        if not edge_collections:
            from database.connection import (
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            )
            edge_collections = [
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            ]
        
        edge_clause = ", ".join(edge_collections)
        
        if strategy == "similar_neighbors":
            query = f"""
            LET similar_sats = (
                LET source_neighbors = (
                    FOR v IN 1..1 ANY @satellite_id {edge_clause}
                    RETURN v._id
                )
                
                FOR candidate IN {COLLECTION_NAME}
                    FILTER candidate._id != @satellite_id
                    
                    LET candidate_neighbors = (
                        FOR v IN 1..1 ANY candidate._id {edge_clause}
                        RETURN v._id
                    )
                    
                    LET intersection = LENGTH(
                        FOR id IN source_neighbors
                        FILTER id IN candidate_neighbors
                        RETURN id
                    )
                    
                    LET union = LENGTH(UNIQUE(APPEND(source_neighbors, candidate_neighbors)))
                    LET similarity = union > 0 ? intersection / union : 0
                    
                    FILTER similarity > 0.1
                    SORT similarity DESC
                    LIMIT 5
                    RETURN candidate._id
            )
            
            LET direct_neighbors = (
                FOR v IN 1..1 ANY @satellite_id {edge_clause}
                RETURN v._id
            )
            
            FOR similar_id IN similar_sats
                FOR recommendation IN 1..1 ANY similar_id {edge_clause}
                    FILTER recommendation._id != @satellite_id
                    FILTER recommendation._id NOT IN direct_neighbors
                    COLLECT rec = recommendation INTO groups
                    LET score = LENGTH(groups)
                    SORT score DESC
                    LIMIT @limit
                    RETURN {{
                        _id: rec._id,
                        identifier: rec.identifier,
                        name: rec.canonical.name,
                        country: rec.canonical.country_of_origin,
                        orbital_band: rec.canonical.orbital_band,
                        relevance_score: score,
                        recommendation_type: "similar_neighbors"
                    }}
            """
        
        elif strategy == "second_degree":
            query = f"""
            LET direct_neighbors = (
                FOR v IN 1..1 ANY @satellite_id {edge_clause}
                RETURN v._id
            )
            
            FOR v IN 2..2 ANY @satellite_id {edge_clause}
                FILTER v._id != @satellite_id
                FILTER v._id NOT IN direct_neighbors
                COLLECT recommendation = v INTO groups
                LET score = LENGTH(groups)
                SORT score DESC
                LIMIT @limit
                RETURN {{
                    _id: recommendation._id,
                    identifier: recommendation.identifier,
                    name: recommendation.canonical.name,
                    country: recommendation.canonical.country_of_origin,
                    orbital_band: recommendation.canonical.orbital_band,
                    relevance_score: score,
                    recommendation_type: "second_degree"
                }}
            """
        
        elif strategy == "common_neighbors":
            query = f"""
            LET source_neighbors = (
                FOR v IN 1..1 ANY @satellite_id {edge_clause}
                RETURN v._id
            )
            
            FOR candidate IN {COLLECTION_NAME}
                FILTER candidate._id != @satellite_id
                FILTER candidate._id NOT IN source_neighbors
                
                LET candidate_neighbors = (
                    FOR v IN 1..1 ANY candidate._id {edge_clause}
                    RETURN v._id
                )
                
                LET common_count = LENGTH(
                    FOR id IN source_neighbors
                    FILTER id IN candidate_neighbors
                    RETURN id
                )
                
                FILTER common_count > 0
                SORT common_count DESC
                LIMIT @limit
                
                RETURN {{
                    _id: candidate._id,
                    identifier: candidate.identifier,
                    name: candidate.canonical.name,
                    country: candidate.canonical.country_of_origin,
                    orbital_band: candidate.canonical.orbital_band,
                    relevance_score: common_count,
                    recommendation_type: "common_neighbors"
                }}
            """
        
        else:
            return []
        
        cursor = db_conn.db.aql.execute(
            query,
            bind_vars={
                'satellite_id': satellite_id,
                'limit': limit
            }
        )
        
        return list(cursor)
        
    except Exception as e:
        print(f"Error getting neighbor-based recommendations: {e}")
        return []


def get_collaborative_filtering_recommendations(
    satellite_id: str,
    edge_types: Optional[List[str]] = None,
    limit: int = 10,
    min_common_connections: int = 2
) -> List[Dict[str, Any]]:
    """
    Get recommendations using collaborative filtering approach.
    
    Finds satellites that share many connections with the source satellite
    but are not directly connected. Similar to "users who liked X also liked Y".
    
    Args:
        satellite_id: Reference satellite document ID
        edge_types: Optional list of edge collections
        limit: Maximum number of recommendations
        min_common_connections: Minimum number of shared connections required
    
    Returns:
        List of recommended satellites with relevance scores
    """
    try:
        edge_collections = edge_types if edge_types else []
        
        if not edge_collections:
            from database.connection import (
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            )
            edge_collections = [
                EDGE_COLLECTION_CONSTELLATION,
                EDGE_COLLECTION_REGISTRATION,
                EDGE_COLLECTION_PROXIMITY
            ]
        
        edge_clause = ", ".join(edge_collections)
        
        query = f"""
        LET source_neighbors = (
            FOR v IN 1..1 ANY @satellite_id {edge_clause}
            RETURN v._id
        )
        
        LET direct_connections = APPEND(source_neighbors, [@satellite_id])
        
        FOR neighbor IN source_neighbors
            FOR second_degree IN 1..1 ANY neighbor {edge_clause}
                FILTER second_degree._id NOT IN direct_connections
                COLLECT recommendation = second_degree INTO groups
                LET common_connections = LENGTH(groups)
                FILTER common_connections >= @min_common_connections
                SORT common_connections DESC
                LIMIT @limit
                RETURN {{
                    _id: recommendation._id,
                    identifier: recommendation.identifier,
                    name: recommendation.canonical.name,
                    country: recommendation.canonical.country_of_origin,
                    orbital_band: recommendation.canonical.orbital_band,
                    status: recommendation.canonical.status,
                    relevance_score: common_connections,
                    common_connections: common_connections,
                    recommendation_type: "collaborative_filtering"
                }}
        """
        
        cursor = db_conn.db.aql.execute(
            query,
            bind_vars={
                'satellite_id': satellite_id,
                'limit': limit,
                'min_common_connections': min_common_connections
            }
        )
        
        return list(cursor)
        
    except Exception as e:
        print(f"Error getting collaborative filtering recommendations: {e}")
        return []
