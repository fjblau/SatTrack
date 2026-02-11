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
from database.connection import db, COLLECTION_NAME, EDGE_COLLECTION_COLLISION_RISK, EDGE_COLLECTION_SATELLITE_LINEAGE


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
        
        edge_clause = ", ".join([f"'{edge}'" for edge in edge_collections])
        
        query = f"""
        FOR v, e IN 1..@max_depth OUTBOUND @from_id
            {edge_clause}
            FILTER v._id == @to_id
            LIMIT 1
            RETURN {{
                vertices: [v],
                edges: [e],
                distance: LENGTH([v])
            }}
        """
        
        cursor = db.aql.execute(
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
        
        edge_clause = ", ".join([f"'{edge}'" for edge in edge_collections])
        
        query = f"""
        FOR v, e, p IN 1..@max_depth OUTBOUND @from_id
            {edge_clause}
            FILTER v._id == @to_id
            LIMIT @limit
            RETURN {{
                vertices: p.vertices,
                edges: p.edges,
                distance: LENGTH(p.vertices) - 1
            }}
        """
        
        cursor = db.aql.execute(
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
        
        edge_clause = ", ".join([f"'{edge}'" for edge in edge_collections])
        
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
        
        cursor = db.aql.execute(
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
        
        edge_clause = ", ".join([f"'{edge}'" for edge in edge_collections])
        
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
        
        cursor = db.aql.execute(
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
        
        edge_clause = ", ".join([f"'{edge}'" for edge in edge_collections])
        
        query = f"""
        FOR v, e IN 1..1 {direction} @vertex_id
            {edge_clause}
            RETURN {{
                vertex: v,
                edge: e,
                edge_type: PARSE_IDENTIFIER(e).collection
            }}
        """
        
        cursor = db.aql.execute(
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
            
            cursor = db.aql.execute(
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
        
        edge_clause = ", ".join([f"'{edge}'" for edge in edge_collections])
        
        query = f"""
        LET sample_nodes = (
            FOR doc IN {COLLECTION_NAME}
                LIMIT @sample_size
                RETURN doc._id
        )
        
        FOR node IN {COLLECTION_NAME}
            LET betweenness = SUM(
                FOR source IN sample_nodes
                    FILTER source != node._id
                    FOR target IN sample_nodes
                        FILTER target != node._id AND target != source
                        LET path = (
                            FOR v, e, p IN 1..5 OUTBOUND source
                                {edge_clause}
                                FILTER v._id == target
                                LIMIT 1
                                RETURN p.vertices
                        )
                        RETURN LENGTH(path) > 0 AND node._id IN path[0] ? 1 : 0
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
        
        cursor = db.aql.execute(
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
        
        edge_clause = ", ".join([f"'{edge}'" for edge in edge_collections])
        
        query = f"""
        FOR node IN {COLLECTION_NAME}
            LET reachable = (
                FOR v, e, p IN 1..@max_depth ANY node._id
                    {edge_clause}
                    RETURN {{
                        vertex: v._id,
                        distance: LENGTH(p.vertices) - 1
                    }}
            )
            LET total_distance = SUM(reachable[*].distance)
            LET reachable_count = LENGTH(reachable)
            FILTER reachable_count > 0
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
        
        cursor = db.aql.execute(
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
        
        edge_clause = ", ".join([f"'{edge}'" for edge in edge_collections])
        
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
        
        cursor = db.aql.execute(
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
        
        cursor = db.aql.execute(
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
        
        cursor = db.aql.execute(query, bind_vars=bind_vars)
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
        
        cursor = db.aql.execute(
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
        
        cursor = db.aql.execute(
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
        
        cursor = db.aql.execute(query, bind_vars=bind_vars)
        
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
        
        cursor = db.aql.execute(
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
        
        cursor = db.aql.execute(query, bind_vars=bind_vars)
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
        
        cursor = db.aql.execute(
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
        
        cursor = db.aql.execute(
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
